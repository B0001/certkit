"""Banded eigenvalue counting: interval LDL^T that stays inside the band.

Why this exists
---------------
`checker.count_eigenvalues_below` runs a full interval LDL^T. It is correct but
it accumulates width: pivot j depends on all j previous columns, so on a 1D
Laplacian the growth swallows a pivot by n = 40 and the checker abstains.

For a banded operator that work is mostly wasted. The LDL^T of a symmetric
matrix of bandwidth b has L of the same bandwidth -- no fill outside the band --
so pivot j depends on at most b previous columns rather than j. At b = 1 the
recurrence collapses to the classical Sturm sequence
``d_j = (a_jj - beta) - a_{j,j-1}^2 / d_{j-1}``. The cost drops from O(n^3) to
O(n b^2) and, far more importantly here, so does the width growth.

The conclusion is identical to the dense route's -- a count of eigenvalues
strictly below beta, by Sylvester's law of inertia -- so this is a drop-in
alternative producer of the same claim, which is exactly what the certificate
composition in `checker.py` was built to allow.

This module is TRUSTED: standard library only, no producer imports.
"""

from __future__ import annotations

from .interval import Iv, IntervalError
from .operators import Operator

MAX_BANDWIDTH = 64


def band_structure(op: Operator, max_bandwidth: int = MAX_BANDWIDTH):
    """Return (rows, bandwidth), or raise if the operator is not banded enough.

    Rows are read through `op.row`, so this works on any backend -- including
    matrix-free ones, which simply turn out not to be banded.
    """
    rows = []
    bandwidth = 0
    for i in range(op.n):
        entries = op.row(i)
        for j, v in entries.items():
            if v.lo == 0.0 and v.hi == 0.0:
                continue
            d = abs(i - j)
            if d > max_bandwidth:
                raise IntervalError(
                    f"operator bandwidth exceeds {max_bandwidth} (entry at {i},{j})"
                )
            if d > bandwidth:
                bandwidth = d
        rows.append(entries)
    return rows, bandwidth


def count_eigenvalues_below_banded(
    op: Operator, beta: float, max_bandwidth: int = MAX_BANDWIDTH
) -> int:
    """Eigenvalues of `op` strictly below `beta`, via banded interval LDL^T.

    Raises IntervalError if the operator is not banded, or if a pivot interval
    straddles zero -- in which case the inertia is undetermined and the caller
    must abstain rather than pick a sign.
    """
    n = op.n
    rows, b = band_structure(op, max_bandwidth)
    shift = Iv.exact(beta)
    zero = Iv.exact(0.0)

    def entry(i: int, j: int) -> Iv:
        v = rows[i].get(j, zero)
        return v - shift if i == j else v

    d: list[Iv] = []
    lmat: dict[tuple[int, int], Iv] = {}

    for j in range(n):
        s = entry(j, j)
        for k in range(max(0, j - b), j):
            ljk = lmat.get((j, k))
            if ljk is not None:
                s = s - ljk * ljk * d[k]
        if s.contains_zero:
            raise IntervalError(
                f"pivot {j} straddles zero; inertia not determined (gap too tight)"
            )
        d.append(s)

        for i in range(j + 1, min(n, j + b + 1)):
            t = entry(i, j)
            for k in range(max(0, i - b), j):
                lik = lmat.get((i, k))
                ljk = lmat.get((j, k))
                if lik is not None and ljk is not None:
                    t = t - lik * ljk * d[k]
            lmat[(i, j)] = t / s

        # Columns more than b behind can never be referenced again.
        stale = j - b
        if stale >= 0:
            for i in range(stale + 1, min(n, stale + b + 1)):
                lmat.pop((i, stale), None)

    return sum(1 for x in d if x.is_negative)
