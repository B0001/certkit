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

from .interval import Iv
from .operators import decode_operator, encode_dense, operator_ref
from .schema import SCHEMA_VERSION, f2h, seal

def _as_encoding(operator: Any) -> dict:
    """Accept either an operator encoding or a plain list-of-lists matrix."""
    if isinstance(operator, dict):
        return operator
    return encode_dense([[float(v) for v in row] for row in operator])


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


def _ground_state(enc: dict):
    """Best available eigenvector estimate, plus a guess at lambda_2."""
    apply, n = _float_apply(enc)
    op = decode_operator(enc)
    rows = op.dense_rows()
    if rows is not None:
        w, v = np.linalg.eigh(np.array(rows))
        lam2 = float(w[1]) if n > 1 else float(w[0] + 1.0)
        return v[:, 0], float(w[0]), lam2, apply
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


def _pad(value: float, rel: float = 1e-9, n: int = 1, spread: float = 0.0) -> float:
    """How far the producer widens its claim before shipping it.

    The checker's interval arithmetic accumulates roughly n ulps across a dot
    product of length n, so a claim padded by a fixed relative slack starts
    getting refused at large n -- correctly, since it really is tighter than
    what the checker can re-derive. Padding with an n-dependent term keeps
    coverage without touching soundness: over-padding only ever makes the
    claim weaker.
    """
    scale = max(1.0, abs(value)) + abs(spread)
    return rel * scale + 16.0 * U * n * scale + 1e-300


# -- certificate producers ------------------------------------------------
def certify_lambda_min(operator: Any, *, slack: float = 1e-9) -> tuple[dict, dict]:
    """Temple + inertia: the tight route. Needs a gap and an O(n^3) route."""
    enc = _as_encoding(operator)
    x, lam1, lam2, apply = _ground_state(enc)

    # Gap parameter: anywhere strictly between lambda_1 and lambda_2. The
    # checker discharges it by inertia count, so a bad guess costs coverage,
    # never soundness.
    beta = 0.5 * (lam1 + lam2)

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

    pad = _pad(mu, slack, len(x), mu - lower)
    return _emit(enc, "lambda_min_enclosure", "temple_inertia", x,
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

    pad = _pad(mu, slack, len(x), mu - lower)
    return _emit(enc, "lambda_min_enclosure", "gershgorin_rayleigh", x,
                 lower - pad, mu + pad)


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

    pad = _pad(mu, slack)
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

    pad = _pad(mu, slack, len(x), mu - lower)
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
    pad = _pad(mu, slack, op.n, mu - lower)
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

    pad = _pad(mu, slack, len(x), mu - lower)
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

    pad = _pad(mu, slack, len(x), mu - lower)
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
