"""The checker: re-derives every claim from the witness, trusting nothing.

The trust boundary
------------------
This module may import `interval`, `schema`, `operators` and the standard
library. It must NEVER import `producer`, and must never use a number the
producer computed as an input to its own reasoning -- only as a *claim to be
implied*. `tests/test_trust_boundary.py` enforces this mechanically.

Verdicts are two-valued by design. There is no "probably fine":

    VERIFIED  -- the claim follows, from the witness, under no assumptions
    ABSTAIN   -- anything else, with a reason string

An ABSTAIN is not an error. It is the correct output whenever a proof was not
produced, and callers are expected to treat it as "no answer".

Composition
-----------
A witness may discharge a hypothesis by *referencing another certificate* by
content hash. `check_bundle` resolves those references, and a dependency that
abstains makes its dependents abstain -- there is no partial credit.

Two consequences worth naming. First, a rule stops caring how its hypothesis
was established: `temple_ref` needs an eigenvalue count, not a particular way
of counting, so a future Sturm-sequence counter drops in without touching the
Temple code. Second, because references are content hashes and a certificate's
hash covers its references, building a cycle would require finding a hash
fixed point. Cycles are not merely detected here; they are infeasible to
construct. The detection below is defence in depth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from .backward_error import count_eigenvalues_below_backward
from .banded import count_eigenvalues_below_banded
from .interval import CIv, CZERO, Iv, IntervalError, cdot, csqnorm, dot, sqnorm
from .operators import Operator, decode_operator, operator_ref
from .schema import SCHEMA_VERSION, SchemaError, h2f, require, verify_seal

MAX_DEPTH = 8


@dataclass(frozen=True)
class Verdict:
    status: str  # "VERIFIED" | "ABSTAIN"
    reason: str = ""
    claim_kind: str = ""
    rule: str = ""
    enclosure: tuple[float, float] | None = None
    rederived: tuple[float, float] | None = None
    depends_on: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return self.status == "VERIFIED"

    @property
    def width(self) -> float | None:
        return None if self.rederived is None else self.rederived[1] - self.rederived[0]

    def __str__(self) -> str:  # pragma: no cover - display only
        if not self.ok:
            return f"ABSTAIN   {self.reason}"
        dep = f"  <- {len(self.depends_on)} dep(s)" if self.depends_on else ""
        if self.enclosure is None:
            return f"VERIFIED  {self.claim_kind} via {self.rule}{dep}"
        lo, hi = self.enclosure
        return f"VERIFIED  {self.claim_kind} via {self.rule}  [{lo!r}, {hi!r}]{dep}"


def _abstain(reason: str, **kw) -> Verdict:
    return Verdict(status="ABSTAIN", reason=reason, **kw)


# -- rigorous inertia count ----------------------------------------------
def count_eigenvalues_below(rows: Sequence[Sequence[Any]], beta: float) -> int:
    """Number of eigenvalues of the symmetric operator strictly below `beta`.

    Rows may be floats or intervals; intervals are what a matrix-free backend
    can honestly supply. Interval LDL^T of (A - beta*I) plus Sylvester's law of
    inertia. Every pivot is enclosed; if no pivot interval straddles zero then
    the sign pattern -- and hence the inertia -- is determined, and A - beta*I
    is provably nonsingular, so beta is not itself an eigenvalue.

    Raises IntervalError if a pivot cannot be sign-determined (the honest
    outcome for a near-degenerate gap).
    """
    n = len(rows)
    b = Iv.exact(beta)
    m = [[v if isinstance(v, Iv) else Iv.exact(v) for v in rows[i]] for i in range(n)]
    for i in range(n):
        m[i][i] = m[i][i] - b

    d: list[Iv] = []
    lmat: list[list[Iv]] = [[Iv.exact(0.0)] * n for _ in range(n)]
    for j in range(n):
        s = m[j][j]
        for k in range(j):
            s = s - lmat[j][k] * lmat[j][k] * d[k]
        if s.contains_zero:
            raise IntervalError(
                f"pivot {j} straddles zero; inertia not determined (gap too tight)"
            )
        d.append(s)
        for i in range(j + 1, n):
            t = m[i][j]
            for k in range(j):
                t = t - lmat[i][k] * lmat[j][k] * d[k]
            lmat[i][j] = t / s
    return sum(1 for x in d if x.is_negative)


# -- quantities re-derived from the witness alone -------------------------
def _rayleigh_and_residual(op: Operator, x: Sequence[float]) -> tuple[Iv, Iv]:
    """Return (mu, rho2): enclosures of x'Ax/x'x and ||Ax - mu x||^2/||x||^2.

    The residual is formed against the *interval* mu, so the enclosure is valid
    for every real value the Rayleigh quotient could take. Only `op.apply` is
    used, so this is matrix-free wherever the backend is.
    """
    xv = [Iv.exact(v) for v in x]
    nx2 = sqnorm(xv)
    if not nx2.is_positive:
        raise IntervalError("witness vector is (or may be) zero")
    ax = op.apply(xv)
    mu = dot(xv, ax) / nx2
    resid = [ax[i] - mu * xv[i] for i in range(len(xv))]
    return mu, sqnorm(resid) / nx2


def _gershgorin_lower(op: Operator) -> Iv:
    """A rigorous lower bound on the whole spectrum, from row access alone.

    Every eigenvalue of a symmetric operator lies in some disc centred at a
    diagonal entry with radius the off-diagonal absolute row sum. Loose, but it
    needs no gap, no factorisation, and no matrix.
    """
    best: Iv | None = None
    for i in range(op.n):
        entries = op.row(i)
        diag = entries.get(i, Iv.exact(0.0))
        radius = Iv.exact(0.0)
        for j, v in entries.items():
            if j != i:
                mag = v.mag_ub
                radius = radius + Iv(mag, mag)
        low = diag - radius
        if best is None or low.lo < best.lo:
            best = low
    if best is None:
        raise IntervalError("empty operator")
    return best


def _gershgorin_upper(op: Operator) -> Iv:
    """A rigorous upper bound on the whole spectrum, from row access alone.

    The mirror image of `_gershgorin_lower`: every eigenvalue lies in some disc
    centred at a diagonal entry with radius the off-diagonal absolute row sum,
    so the largest disc ceiling bounds the whole spectrum from above.
    """
    best: Iv | None = None
    for i in range(op.n):
        entries = op.row(i)
        diag = entries.get(i, Iv.exact(0.0))
        radius = Iv.exact(0.0)
        for j, v in entries.items():
            if j != i:
                mag = v.mag_ub
                radius = radius + Iv(mag, mag)
        high = diag + radius
        if best is None or high.hi > best.hi:
            best = high
    if best is None:
        raise IntervalError("empty operator")
    return best


def _gershgorin_lower_complex(op: Operator) -> Iv:
    """A rigorous lower bound on the real spectrum of a complex Hermitian
    operator, from row access alone.

    The Gershgorin circle theorem holds for any square matrix, real or
    complex: every eigenvalue lies in some disc `D(a_ii, R_i)` in the complex
    plane, with `R_i` the off-diagonal absolute row sum (a modulus sum here,
    via `CIv.mag_ub`, rather than an absolute-value sum). Hermitian-ness --
    checked exactly by `DenseHermitianComplex.check_symmetric` -- makes both
    `a_ii` and every eigenvalue real, so each disc's intersection with the
    real line, `[a_ii - R_i, a_ii + R_i]`, is what matters, and the identical
    "smallest left endpoint across all discs is a sound global floor"
    argument used by `_gershgorin_lower` applies verbatim: whichever disc
    contains the true lambda_min, its left endpoint is at least the minimum
    left endpoint over every disc, so that minimum is itself a sound floor.
    """
    best: Iv | None = None
    for i in range(op.n):
        entries = op.row(i)
        diag = entries.get(i, CZERO)
        radius = Iv.exact(0.0)
        for j, v in entries.items():
            if j != i:
                mag = v.mag_ub
                radius = radius + Iv(mag, mag)
        low = diag.re - radius
        if best is None or low.lo < best.lo:
            best = low
    if best is None:
        raise IntervalError("empty operator")
    return best


def _implies(claim_lo, claim_hi, lo, hi, kind, rule, deps=()) -> Verdict:
    """The claim is accepted iff the re-derived enclosure implies it."""
    if not (claim_lo <= lo and hi <= claim_hi):
        return Verdict(
            status="ABSTAIN",
            reason="claimed interval is tighter than the re-derived enclosure",
            claim_kind=kind,
            rule=rule,
            enclosure=(claim_lo, claim_hi),
            rederived=(lo, hi),
            depends_on=tuple(deps),
        )
    return Verdict(
        status="VERIFIED",
        claim_kind=kind,
        rule=rule,
        enclosure=(claim_lo, claim_hi),
        rederived=(lo, hi),
        depends_on=tuple(deps),
    )


# -- dependency resolution ------------------------------------------------
class Unresolved(SchemaError):
    """A referenced certificate is missing, cyclic, or itself unverified."""


@dataclass
class Context:
    """Everything a rule needs to resolve references, and nothing else."""

    operators: dict[str, Any]
    index: dict[str, Any]
    memo: dict[str, Verdict]
    stack: tuple[str, ...]

    def dep(self, ref: Any, kind: str, operator_ref_: str) -> dict:
        """Resolve `ref`, require it VERIFIED, of `kind`, on the same operator.

        Returns the dependency's claim. Raises Unresolved otherwise.
        """
        if not isinstance(ref, str):
            raise Unresolved("reference is not a string")
        if ref in self.stack:
            raise Unresolved(f"cyclic reference to {ref}")
        if len(self.stack) >= MAX_DEPTH:
            raise Unresolved(f"dependency chain deeper than {MAX_DEPTH}")
        sub = self.index.get(ref)
        if sub is None:
            raise Unresolved(f"referenced certificate {ref} is not in the bundle")

        # Structural checks first: a dependency that proves the wrong thing is
        # rejected on that ground, and never gets an expensive re-derivation.
        claim = sub.get("claim") if isinstance(sub, dict) else None
        if not isinstance(claim, dict):
            raise Unresolved(f"dependency {ref} has no claim")
        if claim.get("kind") != kind:
            raise Unresolved(f"dependency {ref} proves {claim.get('kind')!r}, need {kind!r}")
        if claim.get("operator_ref") != operator_ref_:
            raise Unresolved(f"dependency {ref} is about a different operator")

        verdict = _verify(sub, Context(self.operators, self.index, self.memo,
                                       self.stack + (ref,)))
        if not verdict.ok:
            raise Unresolved(f"dependency {ref} did not verify: {verdict.reason}")
        return claim


# -- rules ----------------------------------------------------------------
def _rule_residual(op, claim, witness, ctx) -> Verdict:
    """Unconditional: some eigenvalue lies within rho of mu.

    Deliberately NOT a claim about lambda_min. Without gap information the
    nearest eigenvalue to mu need not be the smallest, and conflating the two
    is exactly the failure mode this kit exists to stop.
    """
    x = _witness_vector(witness, op)
    lo, hi = _enclosure(claim)
    mu, rho2 = _rayleigh_and_residual(op, x)
    rho = rho2.sqrt()
    return _implies(lo, hi, (mu - rho).lo, (mu + rho).hi, "spectrum_contains", "residual")


def _temple(op, x, beta, claim_lo, claim_hi, rule, deps=()) -> Verdict:
    """lambda_min in [mu - rho^2/(beta - mu), mu], given beta <= lambda_2.

    Upper bound: Rayleigh-Ritz, lambda_min <= mu for any nonzero x.
    Lower bound: Temple's inequality. The caller is responsible for having
    established the gap; this function assumes nothing on its own.

    Note what "the gap" means here: lambda_2 of the *whole* operator, not of
    whatever subspace a producer used to find x and beta. A solver that only
    ever explored one symmetry sector may pick beta from that sector's own
    local spectrum -- this function does not know or care. mu and rho are
    recomputed from x against the full operator (`_rayleigh_and_residual`),
    and both callers below discharge beta by counting the full operator's
    eigenvalues, not the sector's. A sector-local beta that fails to separate
    the *full* spectrum makes that count come out wrong and the caller
    abstains before this function is even reached -- it cannot produce a
    false enclosure by having looked at the wrong subspace. See
    `tests/test_sector_scope.py` (certkit-487) for a constructed case.
    """
    mu, rho2 = _rayleigh_and_residual(op, x)
    denom = Iv.exact(beta) - mu
    if not denom.is_positive:
        return _abstain("Rayleigh quotient is not provably below beta", rule=rule)
    return _implies(claim_lo, claim_hi, (mu - rho2 / denom).lo, mu.hi,
                    "lambda_min_enclosure", rule, deps)


def _rule_temple_inertia(op, claim, witness, ctx) -> Verdict:
    """Temple with the gap discharged inline by an inertia count.

    beta is not taken on faith. If exactly one eigenvalue lies below beta then
    beta <= lambda_2 -- and that count comes from interval LDL^T, which needs
    explicit rows. A backend that refuses to materialise gets an honest
    abstention, not a weakened rule.
    """
    x = _witness_vector(witness, op)
    lo, hi = _enclosure(claim)
    beta = h2f(witness.get("beta"))

    rows = op.interval_rows()
    if rows is None:
        return _abstain(
            f"backend {op.kind!r} (n={op.n}) will not materialise; inertia "
            "counting unavailable -- use gershgorin_rayleigh, or reference a "
            "count certificate with temple_ref",
            rule="temple_inertia",
        )
    below = count_eigenvalues_below(rows, beta)
    if below != 1:
        return _abstain(
            f"gap parameter not discharged: {below} eigenvalues lie below beta, need exactly 1",
            rule="temple_inertia",
        )
    return _temple(op, x, beta, lo, hi, "temple_inertia")


def _rule_temple_ref(op, claim, witness, ctx) -> Verdict:
    """Temple with the gap discharged by a referenced count certificate.

    The rule requires an eigenvalue *count*, not a particular way of counting.
    Whatever produced the referenced certificate is irrelevant here, so long as
    that certificate verifies on its own terms.
    """
    x = _witness_vector(witness, op)
    lo, hi = _enclosure(claim)
    beta = h2f(witness.get("beta"))
    ref = witness.get("gap_ref")

    dep = ctx.dep(ref, "eigenvalue_count_below", claim["operator_ref"])
    if h2f(dep.get("beta")) != beta:
        raise Unresolved("count certificate is for a different beta")
    if dep.get("count") != 1:
        raise Unresolved(
            f"count certificate says {dep.get('count')} eigenvalues below beta, need exactly 1"
        )
    return _temple(op, x, beta, lo, hi, "temple_ref", deps=(ref,))


def _rule_gershgorin_rayleigh(op, claim, witness, ctx) -> Verdict:
    """lambda_min in [Gershgorin lower bound, mu]. No gap, no factorisation.

    The matrix-free route. Both endpoints need only operator application and
    row access, so it reaches where the Temple routes cannot. The price is a
    much wider interval, which the verdict reports.
    """
    x = _witness_vector(witness, op)
    lo, hi = _enclosure(claim)
    mu, _ = _rayleigh_and_residual(op, x)
    low = _gershgorin_lower(op)
    if low.lo > mu.hi:
        return _abstain(
            "Gershgorin bound exceeds the Rayleigh quotient (inconsistent witness)",
            rule="gershgorin_rayleigh",
        )
    return _implies(lo, hi, low.lo, mu.hi, "lambda_min_enclosure", "gershgorin_rayleigh")


def _rule_gen_gershgorin_rayleigh(op, claim, witness, ctx) -> Verdict:
    """The generalized eigenproblem A x = lambda S x: lambda_min(A, S) in
    [Gershgorin-pencil lower bound, generalized Rayleigh quotient].

    `op` is A, decoded by the framework from `claim["operator_ref"]` as usual.
    S is resolved here, by hand, from `claim["metric_ref"]` -- there is no
    second slot in the generic dispatch, so this rule owns that lookup and
    abstains on its own terms if S was not supplied, exactly like the
    framework does for a missing A.

    Derivation, from scratch, no source consulted for a constant:

    S is symmetric; take it as a hypothesis that it is also positive definite,
    which the checker only accepts once it is proven -- see below. Under that
    hypothesis <u, v>_S := u^T S v is a genuine inner product, and a short
    computation shows T := S^{-1} A is self-adjoint with respect to it:
    <Tu, v>_S = u^T A^T S^{-T} S v = u^T A v = u^T S (S^{-1} A) v = <u, Tv>_S,
    using A^T = A and S^{-T} = S^{-1}. The eigenvalues of T are exactly the
    generalized eigenvalues (Tv = lambda v  <=>  A v = lambda S v), so the
    ordinary Rayleigh quotient theorem for self-adjoint operators -- applied
    in the <.,.>_S inner product space rather than the Euclidean one -- gives,
    for every nonzero x:

        lambda_min(A, S)  <=  <Tx, x>_S / <x, x>_S  =  (x'Ax) / (x'Sx)  <=  lambda_max(A, S)

    which is the generalized Rayleigh-Ritz upper bound: mu(x) = x'Ax / x'Sx is
    always a sound upper bound on lambda_min(A, S), for ANY nonzero x -- this
    is the witness vector, and mu is recomputed here from it, never taken from
    the witness.

    For the lower bound, the ordinary (ungeneralized) Rayleigh quotient bound
    holds unconditionally for any symmetric matrix: for every nonzero x,
    x'Ax lies in ||x||^2 * [lambda_min(A), lambda_max(A)], and the same for S.
    Both intervals are enclosed matrix-free by Gershgorin discs (already
    proven sound by `_gershgorin_lower`/`_gershgorin_upper`). Writing
    a = (x'Ax)/||x||^2 and s = (x'Sx)/||x||^2 -- both real numbers, sitting
    inside the two Gershgorin-enclosed intervals -- the identity
    (x'Ax)/(x'Sx) = a/s holds exactly (the ||x||^2 cancels), so this ratio,
    for EVERY nonzero x, lies inside the interval quotient of the two
    Gershgorin enclosures. In particular this holds at the x that minimizes
    the generalized Rayleigh quotient, whose value is lambda_min(A, S) itself
    -- so lambda_min(A, S) lies in that quotient interval too. Its lower
    endpoint is therefore a sound, witness-free floor, exactly mirroring how
    `_gershgorin_lower` alone is the floor in the ungeneralized rule (S = I
    recovers it exactly: dividing by the degenerate interval [1, 1] is a
    no-op).

    S positive-definiteness is not assumed -- it is established the same
    matrix-free way: if the Gershgorin lower bound on S's own spectrum is
    strictly positive, every eigenvalue of S is positive, which is exactly
    positive definiteness. If Gershgorin cannot show that (S is not
    diagonally dominant enough), the rule abstains rather than guess.
    """
    x = _witness_vector(witness, op)
    lo, hi = _enclosure(claim)

    metric_ref = claim.get("metric_ref")
    require(isinstance(metric_ref, str), "missing metric_ref (S operator reference)")
    s_enc = ctx.operators.get(metric_ref)
    if s_enc is None:
        return _abstain(
            "metric operator (S) does not match the one the certificate was issued against"
            if ctx.operators else "no metric operator supplied",
            rule="gen_gershgorin_rayleigh",
        )
    s_op = decode_operator(s_enc)
    if s_op.n != op.n:
        return _abstain(
            "metric operator dimension does not match the primary operator",
            rule="gen_gershgorin_rayleigh",
        )

    s_low = _gershgorin_lower(s_op)
    if not s_low.is_positive:
        return _abstain(
            "cannot prove S positive definite from Gershgorin discs",
            rule="gen_gershgorin_rayleigh",
        )
    s_high = _gershgorin_upper(s_op)
    a_low = _gershgorin_lower(op)
    a_high = _gershgorin_upper(op)

    a_spec = Iv(a_low.lo, a_high.hi)
    s_spec = Iv(s_low.lo, s_high.hi)
    floor = a_spec / s_spec  # sound: s_spec is strictly positive, never straddles zero

    xv = [Iv.exact(v) for v in x]
    sx = s_op.apply(xv)
    sxx = dot(xv, sx)
    if not sxx.is_positive:
        return _abstain(
            "witness vector is (or may be) S-degenerate",
            rule="gen_gershgorin_rayleigh",
        )
    ax = op.apply(xv)
    mu = dot(xv, ax) / sxx

    if floor.lo > mu.hi:
        return _abstain(
            "Gershgorin pencil bound exceeds the generalized Rayleigh quotient "
            "(inconsistent witness)",
            rule="gen_gershgorin_rayleigh",
        )
    return _implies(lo, hi, floor.lo, mu.hi, "lambda_min_enclosure", "gen_gershgorin_rayleigh")


def _rule_hermitian_gershgorin_rayleigh(op, claim, witness, ctx) -> Verdict:
    """lambda_min in [Gershgorin floor, Re<x|A|x>/<x|x>], for complex
    Hermitian A. The complex analogue of `gershgorin_rayleigh`: no gap, no
    factorisation -- just operator application and row access, generalised
    from the real inner product to the Hermitian one.

    Derivation, from scratch:

    mu(x) := <x|A x> / <x|x>, with <u|v> := sum_i conj(u_i) v_i, is the
    Hermitian Rayleigh quotient. It is a sound upper bound on lambda_min(A)
    for every nonzero complex x -- the Rayleigh-Ritz variational theorem for
    self-adjoint operators, applied in the Hermitian inner-product space
    rather than the real Euclidean one (the same theorem `gershgorin_rayleigh`
    already relies on for real symmetric A, since real-symmetric is the
    special case of Hermitian with a zero imaginary part throughout).

    mu(x) is also always a real number when A is Hermitian:
    conj(<x|Ax>) = <Ax|x> = x^H A^H x = x^H A x = <x|Ax>
    (using A^H = A, Hermitian by hypothesis and checked exactly by
    `DenseHermitianComplex.check_symmetric`), so <x|Ax> equals its own
    conjugate and is real. `cdot(x, ax)` -- built from already-sound `CIv`
    arithmetic -- therefore encloses a genuinely real complex number, and its
    `.re` component is a sound `Iv` enclosure of that real value; the `.im`
    component is guaranteed (by the same argument, plus soundness of the
    enclosure) to enclose zero, but is not needed for anything here.

    Lower bound: `_gershgorin_lower_complex`, unconditional and witness-free,
    exactly mirroring how `_gershgorin_lower` alone is the floor in
    `gershgorin_rayleigh`.
    """
    x = _cwitness_vector(witness, op)
    lo, hi = _enclosure(claim)
    nx2 = csqnorm(x)
    if not nx2.is_positive:
        return _abstain(
            "witness vector is (or may be) zero", rule="hermitian_gershgorin_rayleigh"
        )
    ax = op.apply(x)
    mu = cdot(x, ax).re / nx2
    low = _gershgorin_lower_complex(op)
    if low.lo > mu.hi:
        return _abstain(
            "Gershgorin bound exceeds the Rayleigh quotient (inconsistent witness)",
            rule="hermitian_gershgorin_rayleigh",
        )
    return _implies(lo, hi, low.lo, mu.hi, "lambda_min_enclosure", "hermitian_gershgorin_rayleigh")


def _rule_gershgorin(op, claim, witness, ctx) -> Verdict:
    """Every eigenvalue is at least `bound`. Witness-free: the operator is it."""
    bound = h2f(claim.get("bound"))
    low = _gershgorin_lower(op)
    if bound > low.lo:
        return _abstain(
            "claimed lower bound is above the re-derived Gershgorin bound",
            claim_kind="spectrum_lower_bound", rule="gershgorin",
            rederived=(low.lo, low.lo),
        )
    return Verdict(status="VERIFIED", claim_kind="spectrum_lower_bound",
                   rule="gershgorin", enclosure=(bound, bound),
                   rederived=(low.lo, low.lo))


def _rule_rayleigh(op, claim, witness, ctx) -> Verdict:
    """lambda_min <= bound, from a trial vector. Unconditional."""
    x = _witness_vector(witness, op)
    bound = h2f(claim.get("bound"))
    mu, _ = _rayleigh_and_residual(op, x)
    if bound < mu.hi:
        return _abstain(
            "claimed upper bound is below the re-derived Rayleigh quotient",
            claim_kind="lambda_min_upper_bound", rule="rayleigh",
            rederived=(mu.hi, mu.hi),
        )
    return Verdict(status="VERIFIED", claim_kind="lambda_min_upper_bound",
                   rule="rayleigh", enclosure=(bound, bound),
                   rederived=(mu.hi, mu.hi))


def _rule_inertia(op, claim, witness, ctx) -> Verdict:
    """Exactly `count` eigenvalues lie below `beta`. Witness-free."""
    beta = h2f(claim.get("beta"))
    count = claim.get("count")
    require(isinstance(count, int) and count >= 0, "count must be a non-negative integer")

    rows = op.interval_rows()
    if rows is None:
        return _abstain(
            f"backend {op.kind!r} (n={op.n}) will not materialise; inertia unavailable",
            claim_kind="eigenvalue_count_below", rule="inertia",
        )
    got = count_eigenvalues_below(rows, beta)
    if got != count:
        return _abstain(
            f"claimed {count} eigenvalues below beta, re-derived {got}",
            claim_kind="eigenvalue_count_below", rule="inertia",
        )
    return Verdict(status="VERIFIED", claim_kind="eigenvalue_count_below", rule="inertia")


def _rule_sturm(op, claim, witness, ctx) -> Verdict:
    """Exactly `count` eigenvalues below `beta`, via banded interval LDL^T.

    Proves the identical claim to `inertia` at O(n b^2) instead of O(n^3), and
    on operators far larger than the dense route will touch. It is a second
    producer of the same certificate, not a second kind of certificate --
    which is the whole reason `temple_ref` takes a reference rather than doing
    the counting itself.
    """
    beta = h2f(claim.get("beta"))
    count = claim.get("count")
    require(isinstance(count, int) and count >= 0, "count must be a non-negative integer")

    got = count_eigenvalues_below_banded(op, beta)
    if got != count:
        return _abstain(
            f"claimed {count} eigenvalues below beta, re-derived {got}",
            claim_kind="eigenvalue_count_below", rule="sturm",
        )
    return Verdict(status="VERIFIED", claim_kind="eigenvalue_count_below", rule="sturm")


def _rule_sturm_be(op, claim, witness, ctx) -> Verdict:
    """The same claim again, by backward error analysis instead of enclosure.

    The float sweep is an exact factorisation of a nearby matrix, and the
    distance to that matrix is measured from the entries at runtime rather than
    taken from a published constant. Two bracketing sweeps pin the count for the
    operator itself, or the rule abstains because an eigenvalue is too close to
    beta to separate.

    Third producer of `eigenvalue_count_below`, and `temple_ref` still does not
    know the difference.
    """
    beta = h2f(claim.get("beta"))
    count = claim.get("count")
    require(isinstance(count, int) and count >= 0, "count must be a non-negative integer")

    got = count_eigenvalues_below_backward(op, beta)
    if got != count:
        return _abstain(
            f"claimed {count} eigenvalues below beta, re-derived {got}",
            claim_kind="eigenvalue_count_below", rule="sturm_be",
        )
    return Verdict(status="VERIFIED", claim_kind="eigenvalue_count_below", rule="sturm_be")


def _rule_combine(op, claim, witness, ctx) -> Verdict:
    """A derivation node: no numerics of its own, only two references.

    Sandwiches a spectrum lower bound and a lambda_min upper bound into an
    enclosure. This is where composition earns its keep -- the two halves can
    be produced by different rules, on different days, by different tools.
    """
    lo, hi = _enclosure(claim)
    ref_lo = witness.get("lower_ref")
    ref_hi = witness.get("upper_ref")
    op_ref = claim["operator_ref"]

    low = h2f(ctx.dep(ref_lo, "spectrum_lower_bound", op_ref).get("bound"))
    high = h2f(ctx.dep(ref_hi, "lambda_min_upper_bound", op_ref).get("bound"))
    if low > high:
        return _abstain("combined bounds are inconsistent (lower exceeds upper)",
                        rule="combine")
    return _implies(lo, hi, low, high, "lambda_min_enclosure", "combine",
                    deps=(ref_lo, ref_hi))


RULES = {
    "residual": ("spectrum_contains", _rule_residual, True),
    "temple_inertia": ("lambda_min_enclosure", _rule_temple_inertia, True),
    "temple_ref": ("lambda_min_enclosure", _rule_temple_ref, True),
    "gershgorin_rayleigh": ("lambda_min_enclosure", _rule_gershgorin_rayleigh, True),
    "gen_gershgorin_rayleigh": ("lambda_min_enclosure", _rule_gen_gershgorin_rayleigh, True),
    "hermitian_gershgorin_rayleigh": (
        "lambda_min_enclosure", _rule_hermitian_gershgorin_rayleigh, True,
    ),
    "gershgorin": ("spectrum_lower_bound", _rule_gershgorin, False),
    "rayleigh": ("lambda_min_upper_bound", _rule_rayleigh, True),
    "inertia": ("eigenvalue_count_below", _rule_inertia, False),
    "sturm": ("eigenvalue_count_below", _rule_sturm, False),
    "sturm_be": ("eigenvalue_count_below", _rule_sturm_be, False),
    "combine": ("lambda_min_enclosure", _rule_combine, False),
}

# Rules built on `CIv` (complex-interval) arithmetic, valid only against a
# complex operator backend. Every other rule assumes `op.row`/`op.apply`
# return `Iv`, not `CIv` -- calling one against the wrong backend would not
# produce a false VERIFIED (the value types are incompatible and arithmetic
# between them raises), but it would crash `check()` uncaught instead of
# abstaining, which `_verify_uncached`'s dispatch guard below exists to
# prevent.
COMPLEX_RULES = frozenset({"hermitian_gershgorin_rayleigh"})
COMPLEX_OPERATOR_KINDS = frozenset({"dense_hermitian_complex"})


# -- claim field helpers --------------------------------------------------
def _enclosure(claim: dict) -> tuple[float, float]:
    enc = claim.get("enclosure")
    require(isinstance(enc, dict), "missing enclosure")
    lo, hi = h2f(enc.get("lo")), h2f(enc.get("hi"))
    require(lo <= hi, "inverted claimed enclosure")
    return lo, hi


def _witness_vector(witness: dict, op: Operator) -> list[float]:
    xh = witness.get("vector")
    require(isinstance(xh, list) and len(xh) == op.n, "witness vector shape mismatch")
    return [h2f(v) for v in xh]


def _cwitness_vector(witness: dict, op: Operator) -> list[CIv]:
    xh = witness.get("vector")
    require(isinstance(xh, list) and len(xh) == op.n, "witness vector shape mismatch")
    out = []
    for entry in xh:
        require(isinstance(entry, dict), "complex witness entry must be an object")
        out.append(CIv(Iv.exact(h2f(entry.get("re"))), Iv.exact(h2f(entry.get("im")))))
    return out


# -- core -----------------------------------------------------------------
def _verify(cert: Any, ctx: Context) -> Verdict:
    key = cert.get("content_hash") if isinstance(cert, dict) else None
    if key is not None and key in ctx.memo:
        return ctx.memo[key]
    verdict = _verify_uncached(cert, ctx)
    if key is not None:
        ctx.memo[key] = verdict
    return verdict


def _verify_uncached(cert: Any, ctx: Context) -> Verdict:
    try:
        verify_seal(cert)
        require(cert.get("schema") == SCHEMA_VERSION, "unknown schema version")

        claim, witness = cert.get("claim"), cert.get("witness")
        require(isinstance(claim, dict), "missing claim")
        require(isinstance(witness, dict), "missing witness")

        rule = witness.get("rule")
        require(rule in RULES, f"unknown witness rule {rule!r}")
        kind, handler, _needs_vector = RULES[rule]
        require(claim.get("kind") == kind, "claim kind does not match witness rule")

        op_ref = claim.get("operator_ref")
        enc = ctx.operators.get(op_ref)
        if enc is None:
            return _abstain(
                "operator does not match the one the certificate was issued against"
                if ctx.operators else "no operator supplied",
                claim_kind=kind, rule=rule,
            )
        op = decode_operator(enc)
        is_complex_op = op.kind in COMPLEX_OPERATOR_KINDS
        is_complex_rule = rule in COMPLEX_RULES
        if is_complex_op != is_complex_rule:
            return _abstain(
                f"rule {rule!r} is not compatible with operator kind {op.kind!r}",
                claim_kind=kind, rule=rule,
            )
        return handler(op, claim, witness, ctx)

    except Unresolved as exc:
        return _abstain(f"dependency: {exc}")
    except SchemaError as exc:
        return _abstain(f"schema: {exc}")
    except IntervalError as exc:
        return _abstain(f"numeric: {exc}")


def check(cert: Any, operator_obj: Any) -> Verdict:
    """Check a single certificate against an independently supplied operator.

    Rules that reference other certificates will abstain here -- use
    `check_bundle` when the certificate has dependencies.
    """
    if isinstance(cert, list):
        return _abstain("a list of certificates was passed; use check_bundle")
    ops = {}
    if isinstance(operator_obj, dict):
        try:
            ops[operator_ref(operator_obj)] = operator_obj
        except SchemaError:
            pass
    return _verify(cert, Context(ops, {}, {}, ()))


def check_bundle(certs: Sequence[Any], operator_encodings: Sequence[Any]) -> dict[str, Verdict]:
    """Check every certificate in a bundle, resolving references between them.

    Returns a mapping from each certificate's content hash to its verdict.
    Dependencies are verified on their own terms; a dependency that abstains
    makes every dependent abstain.
    """
    ops: dict[str, Any] = {}
    for enc in operator_encodings:
        try:
            ops[operator_ref(enc)] = enc
        except SchemaError:
            continue
    index = {
        c["content_hash"]: c
        for c in certs
        if isinstance(c, dict) and isinstance(c.get("content_hash"), str)
    }
    memo: dict[str, Verdict] = {}
    out: dict[str, Verdict] = {}
    for i, cert in enumerate(certs):
        key = cert.get("content_hash") if isinstance(cert, dict) else None
        stack = (key,) if isinstance(key, str) else ()
        out[key if isinstance(key, str) else f"<unhashed:{i}>"] = _verify(
            cert, Context(ops, index, memo, stack)
        )
    return out


def bundle_verdict(results: dict[str, Verdict], kind: str = "lambda_min_enclosure") -> Verdict:
    """The verified top-level claim of the requested kind, or an abstention.

    A bundle proves what its root proves; the intermediate certificates are
    scaffolding. If more than one root of the same kind verifies, the tightest
    is returned.
    """
    ok = [v for v in results.values() if v.ok and v.claim_kind == kind and v.width is not None]
    if not ok:
        failed = [v for v in results.values() if not v.ok]
        reason = failed[0].reason if failed else f"no verified {kind} in bundle"
        return _abstain(reason)
    return min(ok, key=lambda v: v.width)
