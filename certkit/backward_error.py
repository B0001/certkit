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

    delta >= ||A - Atilde||_inf    (row sum >= ETA*|p| + two_u*(|b_prev|+|b_next|)
                                     per row, Certkit.Soundness.sweep_row_bound)
          >= ||A - Atilde||_2      (via ||E||_2 <= ||E||_inf for symmetric E,
                                     Certkit.Soundness.l2_opNorm_le_rowSum_of_isHermitian)

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

from .banded import MAX_BANDWIDTH
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

    Symmetry is checked here rather than assumed. `decode_operator` already
    refuses an asymmetric operator, but the derivation above needs symmetry
    twice over -- Sylvester's law on the LDL^T pivot signs, and Weyl via
    ||E||_2 <= ||E||_inf for symmetric E -- and `sweep` reads only one of each
    off-diagonal pair. Trusting a caller for that is the kind of silent
    dependency this kit refuses (certkit-279).
    """
    n = op.n
    diag = [0.0] * n
    off = [0.0] * max(n - 1, 1)
    low = [0.0] * max(n - 1, 1)  # the mirrored entries, compared at the end
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
            elif j == i - 1:
                low[i - 1] = v.lo
            else:
                raise NotTridiagonal(f"operator is not tridiagonal (entry at {i},{j})")
    for i, (a, b) in enumerate(zip(off, low)):
        if a != b:
            raise IntervalError(
                f"operator is not symmetric: [{i},{i + 1}] = {a}, [{i + 1},{i}] = {b}"
            )
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
    if GAMMA / 2.0 > 2.0 * U:  # sqrt bound must stay dominated by the budget used
        raise IntervalError("GAMMA budget exceeds the coefficient used for |b|*(sqrt(1+gamma) - 1)")
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
        # Certkit.Soundness.sweep_row_bound proves this dominates the true row
        # sum; that this Iv accumulation encloses the real value it computes
        # is interval.py's own soundness contract, not a separate obligation.
        row = eta * Iv(abs(p), abs(p))
        for b in (off[j - 1] if j > 0 else 0.0, off[j] if j < n - 1 else 0.0):
            row = row + two_u * Iv(abs(b), abs(b))
        if row.hi > worst.hi:
            worst = row

    return Sweep(count=count, delta=worst.hi)


def _bracket_count(beta: float, sweep_at) -> int:
    """Two bracketing sweeps at beta -/+ delta pin the exact count, or the
    honest answer is that an eigenvalue is too close to beta to separate.

    This driver is shared by every backward-error counting route (tridiagonal
    or banded): the bracketing argument only needs `sweep_at(shift)` to return
    a `Sweep` for the pivot recurrence evaluated at that shift, and does not
    care how the recurrence itself is organised.
    """
    probe = sweep_at(beta)
    guess = probe.delta

    for _ in range(MAX_REFINEMENTS):
        if guess == 0.0:  # an exactly diagonal operator, or beta on the entries
            guess = TINY
        lo_shift = (Iv.exact(beta) - Iv.exact(guess)).lo
        hi_shift = (Iv.exact(beta) + Iv.exact(guess)).hi

        low = sweep_at(lo_shift)
        high = sweep_at(hi_shift)

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


def count_eigenvalues_below_backward(op: Operator, beta: float) -> int:
    """Eigenvalues of `op` strictly below `beta`, by backward error analysis.

    Raises IntervalError if the operator is not tridiagonal, if the recurrence
    breaks down, or if an eigenvalue lies within the computed perturbation of
    `beta` so that the count cannot be pinned.
    """
    diag, off = tridiagonal_arrays(op)
    return _bracket_count(beta, lambda shift: sweep(diag, off, shift))


# -- bandwidth > 1: the same idea, without a hand-derived rounding budget ---
#
# The tridiagonal derivation above hand-counts how many roundings compose onto
# each of the two quantities that matter (the shifted diagonal, and the
# squared off-diagonal) and pads each count into ETA/GAMMA. That works because
# a tridiagonal pivot depends on exactly one previous column. A banded pivot of
# bandwidth b depends on up to b previous columns, and each of those
# contributes a term built from an L entry that was itself the result of a
# division by an *earlier* pivot -- so the "how many roundings compose here"
# question no longer has one clean answer independent of b, and re-deriving a
# symbolic ETA_b/GAMMA_b by hand for general b is exactly the kind of ad hoc
# constant-fitting this kit exists to avoid.
#
# The way out is to stop counting roundings at all, in favour of a computation
# that is rigorous regardless of how many roundings occurred. Run the banded
# LDL^T elimination in plain floats to get L (unit lower triangular, band b)
# and D (diagonal) -- whatever floats come out, however they got there. These
# specific floats *define* a symmetric matrix
#
#     Mtilde := L D L^T          (real arithmetic, no rounding in this equation)
#
# with bandwidth <= b, because L has bandwidth <= b by construction (a formal
# identity: Mtilde_ii = D_i + sum_k L_ik^2 D_k, Mtilde_ij = L_ij D_j +
# sum_{k<j} L_ik L_jk D_k for i > j, both finite sums over the band). D's
# negative-pivot count is Mtilde's inertia by Sylvester's law -- again a formal
# fact about *this specific* L and D, not a claim about how they were computed.
# Atilde := Mtilde + beta*I is then the matrix whose count-below-beta is
# exactly the negative-pivot count, and the only work left is bounding
# ||A - Atilde||, entry by entry, which is bounding
#
#     E_ii = Mtilde_ii - (A_ii - beta),   E_ij = Mtilde_ij - A_ij  (i > j)
#
# Every quantity on the right of both equations -- the specific L and D floats,
# the exact matrix entries, beta -- is already a known, exact real number by
# the time the elimination finishes. So E can be *rigorously enclosed* by
# plugging those exact numbers into `Iv` arithmetic and reading off the
# resulting interval's magnitude: no rounding-count argument is needed,
# because `Iv` is already proven to enclose the true real result of any
# expression built from `+`, `-`, `*` regardless of how many operations there
# are (interval.py's soundness contract, checked against 240k exact-rational
# cases -- certkit-jcb's 2026-09-01 review). This is strictly more general than
# hand-counting roundings, and it is what makes bandwidth-independent-in-form
# code possible here: the loop bound `b` changes; the argument for why the
# result is sound does not.
#
# A consequence worth stating: unlike ETA/GAMMA, this bound does not assume the
# "each op commits at most one rounding" model at all -- not because that
# model is wrong (it is CPython's IEEE-754 behaviour, `certkit-8hn` checked it
# cross-architecture), but because this argument never needs it. Only two
# things must hold for correctness: every pivot must be a genuine nonzero
# float (so its sign, and hence Sylvester's law, is well defined) and no
# intermediate may be NaN/infinite/subnormal (so the elimination has not left
# IEEE's normal range in a way this kit does not model elsewhere). Both are
# checked with the same `_finite_normal` guard the tridiagonal sweep uses, out
# of conservatism and consistency, not because this argument requires it.


def banded_arrays(
    op: Operator, max_bandwidth: int = MAX_BANDWIDTH
) -> tuple[list[dict[int, float]], int]:
    """Return (per-row exact entries, actual bandwidth), or refuse.

    Generalises `tridiagonal_arrays` to bandwidth > 1: entries must be exactly
    representable (no single matrix exists for an enclosed entry, as for a
    Pauli sum), symmetric (checked here, not delegated -- certkit-279), and
    within `max_bandwidth` of the diagonal.
    """
    n = op.n
    rows: list[dict[int, float]] = [dict() for _ in range(n)]
    bandwidth = 0
    for i in range(n):
        for j, v in op.row(i).items():
            if v.lo != v.hi:
                raise NotTridiagonal(
                    "operator entries are inexact; the float recurrence needs "
                    "an exactly represented matrix"
                )
            if v.lo == 0.0:
                continue
            d = abs(i - j)
            if d > max_bandwidth:
                raise IntervalError(
                    f"operator bandwidth exceeds {max_bandwidth} (entry at {i},{j})"
                )
            if d > bandwidth:
                bandwidth = d
            rows[i][j] = v.lo

    for i in range(n):
        for j, val in rows[i].items():
            if j == i:
                continue
            mirror = rows[j].get(i)
            if mirror != val:
                raise IntervalError(
                    f"operator is not symmetric: [{i},{j}] = {val}, [{j},{i}] = {mirror}"
                )
    return rows, bandwidth


def sweep_banded(rows: list[dict[int, float]], bandwidth: int, shift: float) -> Sweep:
    """One float banded LDL^T sweep plus a rigorous bound on the implied
    perturbation, computed by auditing the reconstruction with `Iv` rather
    than by a hand-derived rounding budget. See the module comment above.

    Raises IntervalError on a zero pivot, on overflow, or on any subnormal
    intermediate -- the same discipline `sweep` uses, for the same reason.
    """
    n = len(rows)
    if not math.isfinite(shift):
        raise IntervalError("non-finite shift")
    b = bandwidth

    def entry(i: int, j: int) -> float:
        return rows[i].get(j, 0.0)

    d: list[float] = [0.0] * n
    lmat: dict[tuple[int, int], float] = {}
    row_err = [Iv.exact(0.0) for _ in range(n)]

    count = 0
    for j in range(n):
        p = entry(j, j) - shift
        if not _finite_normal(p):
            raise IntervalError(f"diagonal term {j} is not a normal float")

        s = p
        recon = Iv.exact(0.0)  # will hold D_j + sum_k L_jk^2 D_k, audited
        for k in range(max(0, j - b), j):
            ljk = lmat[(j, k)]
            term = ljk * ljk * d[k]
            if not (term == 0.0 or _finite_normal(term)):
                raise IntervalError(f"pivot {j} correction from column {k} left the normal range")
            s = s - term
            if not (s == 0.0 or _finite_normal(s)):
                raise IntervalError(f"pivot {j} left the normal range while subtracting column {k}")
            recon = recon + Iv.exact(ljk) * Iv.exact(ljk) * Iv.exact(d[k])

        if not _finite_normal(s) or s == 0.0:
            raise IntervalError(f"pivot {j} is zero or subnormal; inertia not determined")
        d[j] = s
        if s < 0.0:
            count += 1

        recon = recon + Iv.exact(d[j])
        e_jj = recon - (Iv.exact(entry(j, j)) - Iv.exact(shift))
        row_err[j] = row_err[j] + Iv.exact(e_jj.mag_ub)

        for i in range(j + 1, min(n, j + b + 1)):
            t = entry(i, j)
            recon_ij = Iv.exact(0.0)
            for k in range(max(0, i - b), j):
                lik = lmat.get((i, k))
                if lik is None:
                    continue
                ljk = lmat[(j, k)]
                prod = lik * ljk * d[k]
                if not (prod == 0.0 or _finite_normal(prod)):
                    raise IntervalError(
                        f"entry ({i},{j}) correction from column {k} left the normal range"
                    )
                t = t - prod
                if not (t == 0.0 or _finite_normal(t)):
                    raise IntervalError(f"entry ({i},{j}) left the normal range")
                recon_ij = recon_ij + Iv.exact(lik) * Iv.exact(ljk) * Iv.exact(d[k])

            if t == 0.0:
                lij = 0.0
            else:
                lij = t / d[j]
                if not _finite_normal(lij):
                    raise IntervalError(f"L[{i},{j}] left the normal range")
            lmat[(i, j)] = lij

            recon_ij = recon_ij + Iv.exact(lij) * Iv.exact(d[j])
            e_ij = recon_ij - Iv.exact(entry(i, j))
            contribution = Iv.exact(e_ij.mag_ub)
            row_err[i] = row_err[i] + contribution
            row_err[j] = row_err[j] + contribution

        stale = j - b
        if stale >= 0:
            for i in range(stale + 1, min(n, stale + b + 1)):
                lmat.pop((i, stale), None)

    worst = 0.0
    for r in row_err:
        if r.hi > worst:
            worst = r.hi
    return Sweep(count=count, delta=worst)


def count_eigenvalues_below_backward_banded(
    op: Operator, beta: float, max_bandwidth: int = MAX_BANDWIDTH
) -> int:
    """Eigenvalues of `op` strictly below `beta`, by backward error analysis
    over the whole band rather than just the tridiagonal case.

    Raises IntervalError if the operator is not within `max_bandwidth` of the
    diagonal, if the recurrence breaks down, or if an eigenvalue lies within
    the computed perturbation of `beta` so the count cannot be pinned.
    """
    rows, b = banded_arrays(op, max_bandwidth)
    return _bracket_count(beta, lambda shift: sweep_banded(rows, b, shift))
