"""Eigenvalue counting by backward error analysis, with delta computed at runtime.

Why not intervals
-----------------
`banded.count_eigenvalues_below_banded` tracks a forward enclosure of every
pivot. The Sturm recurrence divides by the previous pivot, so the enclosure
width is amplified at every step, and past a few thousand dimensions a pivot
interval straddles zero and the checker must abstain.

The way out is not a tighter forward bound; it is to stop tracking the pivots
at all. Run the recurrence in plain floating point. The computed sequence is
then the *exact* pivot sequence of a slightly different tridiagonal matrix, and
Sylvester's law applies to that matrix without any error term. Weyl's
inequality converts the difference back into a statement about the operator we
care about.

No universal constant
---------------------
The classical form of this argument (Kahan 1966; Demmel, Dhillon and Ren for
the IEEE correctness proof) ends in a symbolic bound with a small constant. A
transcribed constant is exactly the kind of trust the rest of this kit refuses:
get it slightly wrong and the failure mode is a confident wrong answer rather
than an abstention. So the perturbation is bounded *for the matrix and shift in
front of us*, from the entries themselves, in outward-rounded interval
arithmetic. Weaker than the sharp constant, and answerable without believing
anyone.

The derivation, per step
------------------------
With ``u = 2^-53`` and every operation committing at most one rounding::

    p_j   = fl(a_j - beta)          = (a_j - beta)(1 + e2)
    s_j   = fl(b_{j-1} * b_{j-1})   = b_{j-1}^2 (1 + e0)
    t_j   = fl(s_j / d_{j-1})       = (s_j / d_{j-1})(1 + e1)
    d_j   = fl(p_j - t_j)           = (p_j - t_j)(1 + e3)

Collecting the factors, the computed ``d`` satisfies exactly

    d_j = (atilde_j - beta) - btilde_{j-1}^2 / d_{j-1}

with ``atilde_j - beta = (a_j - beta)(1 + eta)``, ``|eta| <= 2u + O(u^2)``, and
``btilde^2 = b^2 (1 + gamma)``, ``|gamma| <= 3u + O(u^2)``. So the float sweep
is an exact factorisation of ``Atilde - beta I``, and by Sylvester's law the
number of negative ``d_j`` is the number of eigenvalues of ``Atilde`` strictly
below beta. The row sums of ``A - Atilde`` are computed directly, giving

    delta >= ||A - Atilde||_2      (via ||E||_2 <= ||E||_inf for symmetric E)

Weyl then gives, for every k, ``|lambda_k(A) - lambda_k(Atilde)| <= delta``.

Turning that into an exact count
--------------------------------
One sweep bounds the count; two bracket it. Sweeping at ``beta - delta`` gives
a lower bound on ``n_A(beta)`` and sweeping at ``beta + delta`` an upper bound,
so when the two sweeps agree the count for the *original* operator is pinned
exactly -- and the claim is the same `eigenvalue_count_below` that the interval
routes prove, consumable by `temple_ref` with no change to the Temple rule.

When they disagree, an eigenvalue lies within delta of beta and the honest
answer is that the count is undetermined. Abstain.

This module is TRUSTED: standard library only, no producer imports.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .interval import Iv, IntervalError
from .operators import Operator

U = 2.0**-53
TINY = 2.2250738585072014e-308  # smallest normal double

# Rounding-factor budgets from the derivation above, with room for the O(u^2)
# terms. ETA covers two roundings on (a_j - beta); GAMMA covers three on b^2.
ETA = 2.1 * U
GAMMA = 3.1 * U
MAX_REFINEMENTS = 8


class NotTridiagonal(IntervalError):
    """The backward-error derivation above is specific to tridiagonal form."""


@dataclass(frozen=True)
class Sweep:
    count: int
    delta: float  # rigorous upper bound on ||A - Atilde||_2


def tridiagonal_arrays(op: Operator) -> tuple[list[float], list[float]]:
    """Extract exact (diagonal, off-diagonal) arrays, or refuse.

    Entries must be exactly representable: an operator whose rows are only
    *enclosed* (a Pauli sum, say) is not something the float recurrence can be
    run on, because there is no single matrix it would be running on.
    """
    n = op.n
    diag = [0.0] * n
    off = [0.0] * max(n - 1, 1)
    for i in range(n):
        for j, v in op.row(i).items():
            if v.lo != v.hi:
                raise NotTridiagonal(
                    "operator entries are inexact; the float recurrence needs "
                    "an exactly represented matrix"
                )
            if v.lo == 0.0:
                continue
            if j == i:
                diag[i] = v.lo
            elif j == i + 1:
                off[i] = v.lo
            elif j != i - 1:
                raise NotTridiagonal(f"operator is not tridiagonal (entry at {i},{j})")
    return diag, off


def _finite_normal(x: float) -> bool:
    return math.isfinite(x) and (x == 0.0 or abs(x) >= TINY)


def sweep(diag: list[float], off: list[float], shift: float) -> Sweep:
    """One float Sturm sweep plus a rigorous bound on the implied perturbation.

    Raises IntervalError on a zero pivot, on overflow, or on any subnormal
    intermediate -- all cases where the one-rounding-per-operation model that
    the derivation rests on no longer holds.
    """
    n = len(diag)
    if not math.isfinite(shift):
        raise IntervalError("non-finite shift")

    # ||A - Atilde||_inf, accumulated outward-rounded as we go.
    eta = Iv.exact(ETA)
    two_u = Iv.exact(2.0 * U)  # covers |b|*(sqrt(1+gamma) - 1) for |gamma| <= GAMMA
    assert GAMMA / 2.0 <= 2.0 * U  # sqrt bound is dominated by the budget used
    worst = Iv.exact(0.0)

    count = 0
    d = 0.0
    for j in range(n):
        p = diag[j] - shift
        if not _finite_normal(p):
            raise IntervalError(f"diagonal term {j} is not a normal float")
        if j == 0:
            d = p
        else:
            b = off[j - 1]
            s = b * b
            if not _finite_normal(s):
                raise IntervalError(f"squared off-diagonal {j - 1} left the normal range")
            t = s / d if s != 0.0 else 0.0
            if not _finite_normal(t) or (s != 0.0 and t == 0.0):
                raise IntervalError(f"quotient at step {j} left the normal range")
            d = p - t
        if not _finite_normal(d) or d == 0.0:
            raise IntervalError(f"pivot {j} is zero or subnormal; inertia not determined")
        if d < 0.0:
            count += 1

        # Row j of |A - Atilde|: the diagonal perturbation plus both neighbours.
        row = eta * Iv(abs(p), abs(p))
        for b in (off[j - 1] if j > 0 else 0.0, off[j] if j < n - 1 else 0.0):
            row = row + two_u * Iv(abs(b), abs(b))
        if row.hi > worst.hi:
            worst = row

    return Sweep(count=count, delta=worst.hi)


def count_eigenvalues_below_backward(op: Operator, beta: float) -> int:
    """Eigenvalues of `op` strictly below `beta`, by backward error analysis.

    Raises IntervalError if the operator is not tridiagonal, if the recurrence
    breaks down, or if an eigenvalue lies within the computed perturbation of
    `beta` so that the count cannot be pinned.
    """
    diag, off = tridiagonal_arrays(op)

    probe = sweep(diag, off, beta)
    guess = probe.delta

    for _ in range(MAX_REFINEMENTS):
        if guess == 0.0:  # an exactly diagonal operator, or beta on the entries
            guess = TINY
        lo_shift = (Iv.exact(beta) - Iv.exact(guess)).lo
        hi_shift = (Iv.exact(beta) + Iv.exact(guess)).hi

        low = sweep(diag, off, lo_shift)
        high = sweep(diag, off, hi_shift)

        # The bracketing argument needs the shifts to be at least as far out as
        # each sweep's own perturbation bound. Checked, never assumed.
        margin_lo = (Iv.exact(beta) - Iv.exact(lo_shift)).lo
        margin_hi = (Iv.exact(hi_shift) - Iv.exact(beta)).lo
        if margin_lo < low.delta or margin_hi < high.delta:
            guess = max(low.delta, high.delta) * 2.0
            continue

        if low.count != high.count:
            raise IntervalError(
                f"an eigenvalue lies within {guess:.3e} of beta; count is "
                f"{low.count} or {high.count} and cannot be determined"
            )
        return low.count

    raise IntervalError("perturbation bound did not settle")
