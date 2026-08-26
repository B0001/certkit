"""The producer: an ordinary, *untrusted* numerical solver that emits witnesses.

Nothing in this file is part of the trusted base. It uses LAPACK via numpy,
plain floating point, and heuristics. If it is buggy, sloppy, or malicious, the
worst it can do is emit a certificate the checker refuses -- an ABSTAIN, not a
wrong answer.

That asymmetry is the point: solver quality becomes a *coverage* question (how
often do we get an answer?) instead of a *soundness* question (is the answer we
got real?).

It may import the trusted modules; the ban runs the other way.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np

from .interval import CZERO, Iv
from .operators import decode_operator, encode_dense, encode_dense_hermitian, operator_ref
from .schema import SCHEMA_VERSION, f2h, seal

def _as_encoding(operator: Any) -> dict:
    """Accept either an operator encoding or a plain list-of-lists matrix."""
    if isinstance(operator, dict):
        return operator
    return encode_dense([[float(v) for v in row] for row in operator])


def _as_encoding_hermitian(operator: Any) -> dict:
    """Accept either a `dense_hermitian_complex` encoding or a plain
    list-of-lists / ndarray of complex numbers."""
    if isinstance(operator, dict):
        return operator
    return encode_dense_hermitian([[complex(v) for v in row] for row in operator])


# -- float-side operator application (untrusted, fast) --------------------
def _float_apply(enc: dict):
    """Return a fast numpy matvec for the encoding, matrix-free where possible."""
    kind = enc["kind"]

    if kind == "pauli_sum_real":
        q = enc["qubits"]
        n = 1 << q
        idx = np.arange(n, dtype=np.int64)
        terms = []
        for t in enc["terms"]:
            c = float.fromhex(t["coeff"])
            s = t["string"]
            mask = zy = ny = 0
            for k, p in enumerate(s):
                if p in "XY":
                    mask |= 1 << k
                if p in "ZY":
                    zy |= 1 << k
                if p == "Y":
                    ny += 1
            c *= -1.0 if (ny // 2) % 2 else 1.0
            src = idx ^ mask
            sign = 1.0 - 2.0 * (np.bitwise_count(src & zy) & 1)
            terms.append((c, src, sign))

        def apply(x: np.ndarray) -> np.ndarray:
            out = np.zeros(n)
            for c, src, sign in terms:
                out += c * sign * x[src]
            return out

        return apply, n

    op = decode_operator(enc)
    n = op.n
    if kind == "dense_symmetric_real":
        a = np.array([[float.fromhex(v) for v in r] for r in enc["rows"]])
        return (lambda x: a @ x), n

    indptr = np.array(enc["indptr"])
    indices = np.array(enc["indices"])
    data = np.array([float.fromhex(v) for v in enc["data"]])

    counts = np.diff(indptr)

    def apply(x: np.ndarray) -> np.ndarray:
        if len(data) == 0:
            return np.zeros(n)
        sums = np.add.reduceat(data * x[indices], indptr[:-1])
        return np.where(counts > 0, sums, 0.0)

    return apply, n


def _lanczos_ground_state(apply, n: int, k: int = 120, seed: int = 0, start=None):
    """Matrix-free Lanczos with full reorthogonalisation.

    Returns (x, theta_1, theta_2). The second Ritz value is only an estimate of
    lambda_2, which is all the gap parameter ever needs to be -- the checker
    establishes the real separation itself, and a bad estimate costs coverage
    rather than soundness.
    """
    rng = np.random.default_rng(seed)
    k = min(k, n)
    q = start if start is not None else rng.standard_normal(n)
    q = q / np.linalg.norm(q)
    basis, alphas, betas = [q], [], []
    for j in range(k):
        w = apply(basis[-1])
        a = float(basis[-1] @ w)
        alphas.append(a)
        for v in basis:  # full reorthogonalisation: cost is fine, drift is not
            w -= (v @ w) * v
        b = float(np.linalg.norm(w))
        if b < 1e-13 or j == k - 1:
            break
        betas.append(b)
        basis.append(w / b)
    t = np.diag(alphas) + np.diag(betas, 1) + np.diag(betas, -1)
    vals, vecs = np.linalg.eigh(t)
    x = np.array(basis).T @ vecs[:, 0]
    theta2 = float(vals[1]) if len(vals) > 1 else float(vals[0] + 1.0)
    return x / np.linalg.norm(x), float(vals[0]), theta2


def _tridiagonal_ground_state(diag, off, n: int):
    """The two lowest eigenpairs of a real symmetric tridiagonal matrix, via
    LAPACK's MRRR algorithm (scipy.linalg.eigh_tridiagonal), when scipy is
    importable.

    This is the shift-and-invert style fix the coverage-cliff finding asked
    for, specialised to the case the producer can actually reach for cheaply:
    when the operator's own encoding is tridiagonal (as schrodinger_1d's is),
    LAPACK computes the extreme eigenpairs directly in O(n) without ever
    forming a dense matrix, to machine precision -- not the O(1)-scale
    residual a few hundred steps of matrix-free Lanczos leaves on an operator
    whose ground state is delocalised over most of n. Returns None (never
    raises) if scipy is unavailable or n == 0, so the caller falls back to
    the matrix-free Lanczos route -- a producer-side solver choice, so a
    fallback only ever costs coverage, never soundness.
    """
    if n == 0:
        return None
    try:
        from scipy.linalg import eigh_tridiagonal
    except ImportError:
        return None
    d = np.asarray(diag, dtype=float)
    e = np.asarray(off[: n - 1], dtype=float) if n > 1 else np.zeros(0)
    hi = min(1, n - 1)
    w, v = eigh_tridiagonal(d, e, select="i", select_range=(0, hi))
    lam1 = float(w[0])
    lam2 = float(w[1]) if len(w) > 1 else float(w[0] + 1.0)
    return v[:, 0], lam1, lam2


def _ground_state(enc: dict):
    """Best available eigenvector estimate, plus a guess at lambda_2."""
    apply, n = _float_apply(enc)
    op = decode_operator(enc)
    rows = op.dense_rows()
    if rows is not None:
        w, v = np.linalg.eigh(np.array(rows))
        lam2 = float(w[1]) if n > 1 else float(w[0] + 1.0)
        return v[:, 0], float(w[0]), lam2, apply

    tri = _tridiagonal_arrays(enc)
    if tri is not None:
        result = _tridiagonal_ground_state(tri[0], tri[1], n)
        if result is not None:
            x, lam1, lam2 = result
            return x, lam1, lam2, apply

    # A random start has almost no overlap with a localised ground state, so
    # bias it toward the smallest diagonal entry and then restart from the Ritz
    # vector. Untrusted heuristics, both of them: a poor estimate here costs
    # coverage, because the checker establishes the gap for itself.
    diagonal = np.array([_midpoint(op.row(i).get(i)) for i in range(n)])
    start = np.exp(-((np.arange(n) - int(diagonal.argmin())) ** 2) / 64.0)
    start += 1e-3 * np.random.default_rng(0).standard_normal(n)

    x, theta1, theta2 = _lanczos_ground_state(apply, n, start=start)
    for _ in range(2):
        x, theta1, theta2 = _lanczos_ground_state(apply, n, start=x)
    return x, theta1, theta2, apply


def _midpoint(v) -> float:
    return 0.0 if v is None else 0.5 * (v.lo + v.hi)


def _tridiagonal_arrays(enc: dict):
    """Extract (diag, offdiag) if the encoding is tridiagonal, else None."""
    if enc.get("kind") != "sparse_csr_symmetric_real":
        return None
    n = enc["n"]
    indptr, indices = enc["indptr"], enc["indices"]
    data = [float.fromhex(v) for v in enc["data"]]
    diag = [0.0] * n
    off = [0.0] * max(n - 1, 1)
    for i in range(n):
        for k in range(indptr[i], indptr[i + 1]):
            j = indices[k]
            if j == i:
                diag[i] += data[k]
            elif j == i + 1:
                off[i] += data[k]
            elif j != i - 1:
                return None
    return diag, off


def _sturm_margin(diag, off, beta: float):
    """Float Sturm sweep: (count below beta, smallest |pivot| seen).

    Producer-side only. It is a *search heuristic* for a well-conditioned gap
    parameter -- the checker redoes the whole thing in interval arithmetic and
    is free to disagree.
    """
    n = len(diag)
    d = diag[0] - beta
    count = 1 if d < 0 else 0
    margin = abs(d)
    for j in range(1, n):
        if d == 0.0:
            return count, 0.0
        d = (diag[j] - beta) - off[j - 1] * off[j - 1] / d
        if d < 0:
            count += 1
        margin = min(margin, abs(d))
    return count, margin


def _choose_beta(enc: dict, lam1: float, lam2: float) -> float:
    """Locate a gap parameter by bisecting on the float Sturm count.

    A Ritz estimate of lambda_2 is often bad -- Lanczos converges the second
    eigenvalue far more slowly than the first -- and a beta above lambda_2 makes
    the checker report a count of forty rather than one. Bisecting on the count
    itself finds the real separation, and the margin search then picks the point
    inside it whose pivots sit furthest from zero.

    All of this is producer-side guesswork. A bad choice costs coverage; the
    checker establishes the count for itself either way.
    """
    tri = _tridiagonal_arrays(enc)
    default = 0.5 * (lam1 + lam2)
    if tri is None:
        return default
    diag, off = tri

    def count(x: float) -> int:
        return _sturm_margin(diag, off, x)[0]

    lo = lam1 - max(1.0, abs(lam1))
    for _ in range(40):
        if count(lo) == 0:
            break
        lo -= max(1.0, abs(lo))
    else:
        return default

    hi = lam1 + max(1e-6, (lam2 - lam1) if lam2 > lam1 else 1.0)
    for _ in range(60):
        if count(hi) >= 2:
            break
        hi += hi - lo
    else:
        return default

    def first_above(k: int, a: float, b: float) -> float:
        for _ in range(50):
            m = 0.5 * (a + b)
            if m <= a or m >= b:
                break
            if count(m) >= k:
                b = m
            else:
                a = m
        return b

    x1 = first_above(1, lo, hi)
    x2 = first_above(2, x1, hi)
    if not (x2 > x1):
        return default

    best, best_margin = 0.5 * (x1 + x2), -1.0
    for frac in (0.5, 0.35, 0.65, 0.2, 0.8, 0.45, 0.55):
        beta = x1 + frac * (x2 - x1)
        c, margin = _sturm_margin(diag, off, beta)
        if c == 1 and margin > best_margin:
            best, best_margin = beta, margin
    return best


U = 2.0**-53


def pad_claim(value: float, rel: float = 1e-9, n: int = 1, spread: float = 0.0) -> float:
    """How far a producer must widen a claim before shipping it to `check()`.

    The checker re-derives every bound itself, in outward-rounded interval
    arithmetic, from the witness and the operator -- never from anything the
    producer computed. That re-derivation accumulates roughly n ulps across a
    dot product of length n, so its enclosure is *strictly wider* than any
    exact-float bound a producer computes. An unpadded transcription of a
    correct bound is therefore always refused as "tighter than the re-derived
    enclosure" -- this is a calibration requirement, not a soundness bug.

    `value` is the point estimate being padded around (typically the Rayleigh
    quotient mu), `rel` is a relative slack, `n` is the problem size driving
    the ulp accumulation above, and `spread` is any extra distance already
    known between the estimate and the bound being widened (e.g. mu - lower)
    that should also scale the pad. Returns a pad added on the wide side and
    subtracted on the tight side; over-padding only ever costs coverage, never
    soundness, so producers should round this up rather than down.

    Every `certify_*` function in this module uses this convention. External
    producers are expected to pad their own claims the same way -- see the
    README's "Writing a producer" section.
    """
    scale = max(1.0, abs(value)) + abs(spread)
    return rel * scale + 16.0 * U * n * scale + 1e-300


# -- certificate producers ------------------------------------------------
def _temple_inertia_bracket(apply, x, beta: float, slack: float):
    """mu, lower bound, and pad for a Temple+inertia certificate around `x`.

    Every quantity here is computed from `x`, `apply`, and `beta` alone -- none
    of it is inherited from wherever `x` originally came from. This is what
    makes it safe to share between `certify_lambda_min` (which finds its own
    witness) and `certify_lambda_min_from_witness` (which takes one from the
    caller): there is no code path by which a bound computed against a
    *different* vector could leak into the result.
    """
    ax = apply(x)
    nx2 = float(x @ x)
    mu = float(x @ ax) / nx2
    r = ax - mu * x
    rho2 = float(r @ r) / nx2

    gap = beta - mu
    if gap > 0 and np.isfinite(rho2 / gap):
        lower = mu - rho2 / gap
    else:
        # Degenerate or inverted gap: the producer has nothing real to say. It
        # emits anyway, deliberately -- the checker is the component that
        # decides, and the inertia discharge will refuse this.
        lower = mu - 1.0 - abs(mu)

    pad = pad_claim(mu, slack, len(x), mu - lower)
    return mu, lower, pad


def certify_lambda_min(operator: Any, *, slack: float = 1e-9) -> tuple[dict, dict]:
    """Temple + inertia: the tight route. Needs a gap and an O(n^3) route."""
    enc = _as_encoding(operator)
    x, lam1, lam2, apply = _ground_state(enc)

    # Gap parameter: anywhere strictly between lambda_1 and lambda_2. The
    # checker discharges it by inertia count, so a bad guess costs coverage,
    # never soundness.
    beta = 0.5 * (lam1 + lam2)

    mu, lower, pad = _temple_inertia_bracket(apply, x, beta, slack)
    return _emit(enc, "lambda_min_enclosure", "temple_inertia", x,
                 lower - pad, mu + pad, beta=beta)


def certify_lambda_min_from_witness(operator: Any, x: Sequence[float], *,
                                     slack: float = 1e-9) -> tuple[dict, dict]:
    """Temple + inertia around a witness vector the *caller* supplies.

    `certify_lambda_min` always finds its own trial vector via `_ground_state`.
    That is unusable for a producer whose vector comes from somewhere else
    entirely -- e.g. an external real-time Krylov solver whose ground-state
    estimate is complex, where only the real (or imaginary) part is a valid
    real witness (certkit-bz5). mu, the residual, and the resulting lower
    bound are all recomputed here from `x` and `operator` alone, via the same
    `_temple_inertia_bracket` helper `certify_lambda_min` uses -- never
    accepted from the caller. That makes it structurally impossible to ship a
    certificate whose numbers were computed against a different vector (e.g.
    a complex trial state) than the one actually placed in the witness field:
    the bug this function exists to make unrepresentable.

    Callers are responsible for `x` being a real vector of the operator's
    dimension; everything else -- including whether `x` is any good as a
    witness -- costs coverage, not soundness, exactly as with
    `certify_lambda_min`.
    """
    enc = _as_encoding(operator)
    apply, n = _float_apply(enc)
    xv = np.asarray(x, dtype=float)
    if xv.shape != (n,):
        raise ValueError(f"witness has shape {xv.shape}, operator has dimension {n}")
    if not float(xv @ xv) > 0:
        raise ValueError("witness vector must be nonzero")

    # An independent estimate of lambda_2 for the gap parameter: a full
    # solve of the operator itself, unrelated to the caller's x. A bad
    # estimate only costs coverage -- the checker discharges beta by an
    # inertia count against the true operator, not by trusting this.
    _, lam1, lam2, _ = _ground_state(enc)
    beta = 0.5 * (lam1 + lam2)

    mu, lower, pad = _temple_inertia_bracket(apply, xv, beta, slack)
    return _emit(enc, "lambda_min_enclosure", "temple_inertia", xv,
                 lower - pad, mu + pad, beta=beta)


def certify_lambda_min_matrixfree(operator: Any, *, slack: float = 1e-9) -> tuple[dict, dict]:
    """Gershgorin + Rayleigh: the loose route that always applies.

    No gap, no factorisation, no matrix. Works on operators the tight route
    refuses to touch.
    """
    enc = _as_encoding(operator)
    x, _, _, apply = _ground_state(enc)

    ax = apply(x)
    nx2 = float(x @ x)
    mu = float(x @ ax) / nx2

    op = decode_operator(enc)
    lower = float("inf")
    for i in range(op.n):
        entries = op.row(i)
        diag = entries.get(i, Iv.exact(0.0)).lo
        radius = sum(v.mag_ub for j, v in entries.items() if j != i)
        lower = min(lower, diag - radius)

    pad = pad_claim(mu, slack, len(x), mu - lower)
    return _emit(enc, "lambda_min_enclosure", "gershgorin_rayleigh", x,
                 lower - pad, mu + pad)


def certify_lambda_min_hermitian(operator: Any, *, slack: float = 1e-9) -> tuple[dict, dict]:
    """Gershgorin + Hermitian Rayleigh: the matrix-free route for complex
    Hermitian operators, checked by `hermitian_gershgorin_rayleigh`.

    This is the only route complex Hermitian operators have today -- there is
    no complex analogue of the interval-LDL^T inertia count yet (it would
    need outward-rounded `CIv` pivoting, which is unimplemented and out of
    scope for certkit-3ta; see the README's Complex Hermitian operators
    section). A bad trial vector, exactly as in `certify_lambda_min_
    matrixfree`, only ever costs coverage: the checker recomputes mu and the
    Gershgorin floor from the operator and witness alone.
    """
    enc = _as_encoding_hermitian(operator)
    n = enc["n"]
    a = np.array(
        [
            [complex(float.fromhex(e["re"]), float.fromhex(e["im"])) for e in row]
            for row in enc["rows"]
        ]
    )
    _, vecs = np.linalg.eigh(a)  # LAPACK's Hermitian eigensolver, complex-aware
    x = vecs[:, 0]

    ax = a @ x
    nx2 = float(np.vdot(x, x).real)
    mu = float(np.vdot(x, ax).real) / nx2

    op = decode_operator(enc)
    lower = float("inf")
    for i in range(op.n):
        entries = op.row(i)
        diag = entries.get(i, CZERO).re.lo
        radius = sum(v.mag_ub for j, v in entries.items() if j != i)
        lower = min(lower, diag - radius)

    pad = pad_claim(mu, slack, n, mu - lower)
    witness = {
        "rule": "hermitian_gershgorin_rayleigh",
        "vector": [
            {"re": f2h(float(z.real)), "im": f2h(float(z.imag))} for z in x
        ],
    }
    claim = {
        "kind": "lambda_min_enclosure",
        "enclosure": {"lo": f2h(lower - pad), "hi": f2h(mu + pad)},
    }
    return _cert(enc, claim, witness), enc


def certify_lambda_min_generalized(A: Any, S: Any, *, slack: float = 1e-9) -> tuple[dict, dict, dict]:
    """The generalized eigenproblem A x = lambda S x: the matrix-free floor
    and ceiling, checked by `gen_gershgorin_rayleigh`.

    A trial vector is found by reducing to a standard problem via a Cholesky
    factorisation of S (numpy, untrusted -- purely to get a good witness; the
    checker never sees this reduction and redoes everything from A, S, and the
    vector alone). Needs both A and S dense-materialisable; the checker's rule
    itself has no such limit, since it only ever calls `apply` and `row`.

    Returns (certificate, A_encoding, S_encoding).
    """
    a_enc = _as_encoding(A)
    s_enc = _as_encoding(S)
    a_op = decode_operator(a_enc)
    s_op = decode_operator(s_enc)
    if a_op.n != s_op.n:
        raise ValueError("A and S must have the same dimension")

    a_rows, s_rows = a_op.dense_rows(), s_op.dense_rows()
    if a_rows is None or s_rows is None:
        raise ValueError("certify_lambda_min_generalized needs dense-materialisable A and S")

    a = np.array(a_rows)
    s = np.array(s_rows)
    try:
        linv = np.linalg.inv(np.linalg.cholesky(s))
        b = linv @ a @ linv.T
        b = 0.5 * (b + b.T)
        _, vecs = np.linalg.eigh(b)
        x = linv.T @ vecs[:, 0]
        x = x / np.linalg.norm(x)
    except np.linalg.LinAlgError:
        # S did not even look positive definite to a float Cholesky. Emit
        # anyway with an arbitrary trial vector -- a bad witness costs
        # coverage, and the checker's own PD check will abstain regardless.
        x = np.eye(a_op.n)[0]

    sxx = float(x @ (s @ x))
    if sxx > 0:
        mu = float(x @ (a @ x)) / sxx
    else:
        # Same story: not this function's job to decide S is unusable.
        mu = float(x @ (a @ x))

    a_lower = a_upper = None
    s_lower = s_upper = None
    for op, lo_name in ((a_op, "a"), (s_op, "s")):
        lower, upper = float("inf"), float("-inf")
        for i in range(op.n):
            entries = op.row(i)
            diag = entries.get(i, Iv.exact(0.0))
            radius = sum(v.mag_ub for j, v in entries.items() if j != i)
            lower = min(lower, diag.lo - radius)
            upper = max(upper, diag.hi + radius)
        if lo_name == "a":
            a_lower, a_upper = lower, upper
        else:
            s_lower, s_upper = lower, upper

    if s_lower > 0:
        corners = (a_lower / s_lower, a_lower / s_upper, a_upper / s_lower, a_upper / s_upper)
        floor = min(corners)
    else:
        # Cannot show S is positive definite from Gershgorin discs, so the
        # checker's rule will abstain before ever looking at this bound --
        # emit something rather than gatekeep; the checker is the component
        # that decides.
        floor = mu - 1.0 - abs(mu)

    pad = pad_claim(mu, slack, a_op.n, mu - floor)
    lo_bound, hi_bound = floor - pad, mu + pad

    cert = seal({
        "schema": SCHEMA_VERSION,
        "claim": {
            "operator_ref": operator_ref(a_enc),
            "metric_ref": operator_ref(s_enc),
            "kind": "lambda_min_enclosure",
            "enclosure": {"lo": f2h(lo_bound), "hi": f2h(hi_bound)},
        },
        "witness": {
            "rule": "gen_gershgorin_rayleigh",
            "vector": [f2h(float(v)) for v in x],
        },
        "producer": {"name": "certkit.producer", "backend": "numpy"},
    })
    return cert, a_enc, s_enc


def certify_spectrum_point(operator: Any, index: int = 0, *, slack: float = 1e-9):
    """Unconditional 'some eigenvalue lies here'. Needs no gap; says less."""
    enc = _as_encoding(operator)
    op = decode_operator(enc)
    rows = op.dense_rows()
    if rows is None:
        raise ValueError("spectrum_point producer needs an explicit matrix")
    _, v = np.linalg.eigh(np.array(rows))
    x = v[:, index]

    a = np.array(rows)
    ax = a @ x
    nx2 = float(x @ x)
    mu = float(x @ ax) / nx2
    rho = float(np.sqrt(max((ax - mu * x) @ (ax - mu * x), 0.0) / nx2))

    pad = pad_claim(mu, slack)
    return _emit(enc, "spectrum_contains", "residual", x, mu - rho - pad, mu + rho + pad)


def _cert(enc: dict, claim_body: dict, witness: dict) -> dict:
    cert = {
        "schema": SCHEMA_VERSION,
        "claim": {"operator_ref": operator_ref(enc), **claim_body},
        "witness": witness,
        "producer": {"name": "certkit.producer", "backend": "numpy"},
    }
    return seal(cert)


def _emit(enc, kind, rule, x, lo, hi, beta=None) -> tuple[dict, dict]:
    witness = {"rule": rule, "vector": [f2h(float(v)) for v in x]}
    if beta is not None:
        witness["beta"] = f2h(float(beta))
    claim = {"kind": kind, "enclosure": {"lo": f2h(float(lo)), "hi": f2h(float(hi))}}
    return _cert(enc, claim, witness), enc


# -- composed certificates ------------------------------------------------
def certify_count_below(operator: Any, beta: float, count: int) -> tuple[dict, dict]:
    """A standalone claim: exactly `count` eigenvalues lie below `beta`.

    Witness-free. The operator and beta are the whole input; the checker
    re-derives the count itself and compares.
    """
    enc = _as_encoding(operator)
    claim = {"kind": "eigenvalue_count_below", "beta": f2h(float(beta)), "count": int(count)}
    return _cert(enc, claim, {"rule": "inertia"}), enc


def certify_lambda_min_composed(operator: Any, *, slack: float = 1e-9):
    """The Temple bound, split into a count certificate and a Temple node.

    Same guarantee as `certify_lambda_min`, but the gap hypothesis is now a
    separate, independently checkable artifact. Swapping in a different way of
    counting eigenvalues means replacing one certificate, not editing a rule.

    Returns (certificates, operator_encodings) for `check_bundle`.
    """
    enc = _as_encoding(operator)
    x, lam1, lam2, apply = _ground_state(enc)
    beta = 0.5 * (lam1 + lam2)

    count_cert, _ = certify_count_below(enc, beta, 1)

    ax = apply(x)
    nx2 = float(x @ x)
    mu = float(x @ ax) / nx2
    r = ax - mu * x
    rho2 = float(r @ r) / nx2
    gap = beta - mu
    lower = mu - rho2 / gap if gap > 0 and np.isfinite(rho2 / gap) else mu - 1.0 - abs(mu)

    pad = pad_claim(mu, slack, len(x), mu - lower)
    temple = _cert(
        enc,
        {
            "kind": "lambda_min_enclosure",
            "enclosure": {"lo": f2h(lower - pad), "hi": f2h(mu + pad)},
        },
        {
            "rule": "temple_ref",
            "vector": [f2h(float(v)) for v in x],
            "beta": f2h(float(beta)),
            "gap_ref": count_cert["content_hash"],
        },
    )
    return [count_cert, temple], [enc]


def certify_bounds_composed(operator: Any, *, slack: float = 1e-9):
    """A Gershgorin floor and a Rayleigh ceiling, sandwiched by a derivation.

    Three certificates: two independent one-sided bounds and a `combine` node
    that has no numerics of its own. The halves are separately reusable -- the
    Gershgorin floor does not depend on the trial vector at all.
    """
    enc = _as_encoding(operator)
    x, _, _, apply = _ground_state(enc)
    op = decode_operator(enc)

    lower = float("inf")
    for i in range(op.n):
        entries = op.row(i)
        diag = entries.get(i, Iv.exact(0.0)).lo
        radius = sum(v.mag_ub for j, v in entries.items() if j != i)
        lower = min(lower, diag - radius)

    ax = apply(x)
    mu = float(x @ ax) / float(x @ x)
    pad = pad_claim(mu, slack, op.n, mu - lower)
    lo_bound, hi_bound = lower - pad, mu + pad

    floor = _cert(enc, {"kind": "spectrum_lower_bound", "bound": f2h(lo_bound)},
                  {"rule": "gershgorin"})
    ceiling = _cert(enc, {"kind": "lambda_min_upper_bound", "bound": f2h(hi_bound)},
                    {"rule": "rayleigh", "vector": [f2h(float(v)) for v in x]})
    combined = _cert(
        enc,
        {"kind": "lambda_min_enclosure",
         "enclosure": {"lo": f2h(lo_bound), "hi": f2h(hi_bound)}},
        {"rule": "combine",
         "lower_ref": floor["content_hash"],
         "upper_ref": ceiling["content_hash"]},
    )
    return [floor, ceiling, combined], [enc]


# -- convenience operator builders (test fixtures, not trusted) -----------
def tfim_hamiltonian(qubits: int, field: float = 1.0, coupling: float = 1.0) -> dict:
    """Transverse-field Ising model as a Pauli sum: -J sum ZZ - h sum X."""
    from .operators import encode_pauli

    terms = []
    for k in range(qubits - 1):
        s = ["I"] * qubits
        s[k] = s[k + 1] = "Z"
        terms.append((-coupling, "".join(s)))
    for k in range(qubits):
        s = ["I"] * qubits
        s[k] = "X"
        terms.append((-field, "".join(s)))
    return encode_pauli(qubits, terms)


def certify_count_below_sturm(operator: Any, beta: float, count: int) -> tuple[dict, dict]:
    """The same claim as `certify_count_below`, established by the banded route."""
    enc = _as_encoding(operator)
    claim = {"kind": "eigenvalue_count_below", "beta": f2h(float(beta)), "count": int(count)}
    return _cert(enc, claim, {"rule": "sturm"}), enc


def certify_lambda_min_banded(operator: Any, *, slack: float = 1e-9):
    """Temple, with the gap counted by the banded route instead of the dense one.

    The Temple certificate produced here is identical to the one from
    `certify_lambda_min_composed` apart from which count certificate it points
    at. That is the payoff of composition stated as an artifact rather than an
    aspiration.
    """
    enc = _as_encoding(operator)
    x, lam1, lam2, apply = _ground_state(enc)
    beta = _choose_beta(enc, lam1, lam2)
    count_cert, _ = certify_count_below_sturm(enc, beta, 1)

    ax = apply(x)
    nx2 = float(x @ x)
    mu = float(x @ ax) / nx2
    r = ax - mu * x
    rho2 = float(r @ r) / nx2
    gap = beta - mu
    lower = mu - rho2 / gap if gap > 0 and np.isfinite(rho2 / gap) else mu - 1.0 - abs(mu)

    pad = pad_claim(mu, slack, len(x), mu - lower)
    temple = _cert(
        enc,
        {"kind": "lambda_min_enclosure",
         "enclosure": {"lo": f2h(lower - pad), "hi": f2h(mu + pad)}},
        {"rule": "temple_ref",
         "vector": [f2h(float(v)) for v in x],
         "beta": f2h(float(beta)),
         "gap_ref": count_cert["content_hash"]},
    )
    return [count_cert, temple], [enc]


def schrodinger_1d(n: int, well: float = 0.002, hop: float = -1.0) -> dict:
    """Discrete 1D Schrodinger operator: a hopping term plus a harmonic well.

    Tridiagonal, large, and with a genuinely isolated ground state -- the shape
    of problem the banded route exists for.
    """
    from .operators import encode_csr

    centre = (n - 1) / 2
    indptr, indices, data = [0], [], []
    for i in range(n):
        potential = well * (i - centre) ** 2
        for j in (i - 1, i, i + 1):
            if 0 <= j < n:
                indices.append(j)
                data.append(2.0 + potential if j == i else hop)
        indptr.append(len(indices))
    return encode_csr(n, indptr, indices, data)


def certify_count_below_backward(operator: Any, beta: float, count: int):
    """The same claim once more, established by backward error analysis."""
    enc = _as_encoding(operator)
    claim = {"kind": "eigenvalue_count_below", "beta": f2h(float(beta)), "count": int(count)}
    return _cert(enc, claim, {"rule": "sturm_be"}), enc


def certify_lambda_min_backward(operator: Any, *, slack: float = 1e-9):
    """Temple, with the gap counted by the backward-error route.

    Identical to `certify_lambda_min_banded` except for the rule named in the
    count certificate -- which is the point.
    """
    enc = _as_encoding(operator)
    x, lam1, lam2, apply = _ground_state(enc)
    beta = _choose_beta(enc, lam1, lam2)
    count_cert, _ = certify_count_below_backward(enc, beta, 1)

    ax = apply(x)
    nx2 = float(x @ x)
    mu = float(x @ ax) / nx2
    r = ax - mu * x
    rho2 = float(r @ r) / nx2
    gap = beta - mu
    lower = mu - rho2 / gap if gap > 0 and np.isfinite(rho2 / gap) else mu - 1.0 - abs(mu)

    pad = pad_claim(mu, slack, len(x), mu - lower)
    temple = _cert(
        enc,
        {"kind": "lambda_min_enclosure",
         "enclosure": {"lo": f2h(lower - pad), "hi": f2h(mu + pad)}},
        {"rule": "temple_ref",
         "vector": [f2h(float(v)) for v in x],
         "beta": f2h(float(beta)),
         "gap_ref": count_cert["content_hash"]},
    )
    return [count_cert, temple], [enc]


def laplacian_1d(n: int) -> dict:
    """The 1D Laplacian: a tridiagonal whose ground-state gap shrinks like 1/n^2."""
    from .operators import encode_csr

    indptr, indices, data = [0], [], []
    for i in range(n):
        for j in (i - 1, i, i + 1):
            if 0 <= j < n:
                indices.append(j)
                data.append(2.0 if j == i else -1.0)
        indptr.append(len(indices))
    return encode_csr(n, indptr, indices, data)
