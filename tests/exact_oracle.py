"""A general-shape exact rational oracle for eigenvalue-count claims.

`tests/test_banded.py` and `tests/test_backward.py` each carry an
`exact_lambda_min` that bisects the classical two-term Sturm recurrence over
`fractions.Fraction`. That recurrence is exact -- an IEEE double is exactly a
rational, so there is no rounding anywhere in it -- but it only exists because
those matrices are tridiagonal. It has already caught a real disagreement
(see `test_banded.py::test_the_certified_interval_can_be_narrower_than_lapack
_error`: at n = 400 the certified enclosure is narrower than LAPACK's own
backward error, so `eigvalsh` lands outside it). Nothing comparable covered a
genuinely banded (bandwidth > 1) or dense operator: those tests only checked
the certified enclosure against `numpy.linalg.eigvalsh`, which is exactly the
library whose own error the tridiagonal case demonstrates can exceed the
certified width.

This module is the general case: a Fraction-exact LDL^T factorisation of
`A - beta*I`, plus Sylvester's law of inertia -- the same algorithm as
`checker.count_eigenvalues_below`, but over `Fraction` instead of `Iv`, so
there is no width to abstain over. It does not exploit or assume any band
structure, so it is valid ground truth for a banded operator exactly as it
would be for a dense one; bandedness is a producer-side optimisation, not a
fact about the spectrum. The price is O(n^3) per evaluation instead of the
tridiagonal recurrence's O(n), which is why the tests that use this oracle
stay at n in the tens, not the thousands.

This module is test-only support, not part of the trust boundary: it is
imported by test files, never by `certkit/*`, and `test_trust_boundary.py`
does not look at anything under `tests/`.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any, Sequence

from certkit.operators import Operator
from certkit.schema import h2f


def dense_rows_to_fractions(rows: Sequence[Sequence[float]]) -> list[list[Fraction]]:
    """Convert a plain dense list-of-lists of floats to exact Fraction rows."""
    return [[Fraction(v) for v in row] for row in rows]


def operator_to_fraction_rows(op: Operator) -> list[list[Fraction]]:
    """Materialise an `Operator` as exact Fraction rows, via `op.row` alone.

    Works for any backend whose `row` never *adds* two intervals together --
    dense and CSR, as used here, since each of their row entries is either a
    single stored value or absent. Raises ValueError if any entry is a
    non-degenerate interval (lo != hi) -- that only happens for a backend
    honestly reporting it cannot supply an exact value, and silently taking
    `.lo` there would make this "oracle" disagree with the operator it claims
    to be truth for.

    Does NOT work for `pauli_sum_real`: `PauliSumReal.row` combines same-
    column contributions from different Pauli terms with interval addition,
    and `Iv.__add__` widens outward by a ULP on *every* call regardless of
    whether the underlying float sum happens to be exact (`interval.py`'s
    `_widen`) -- deliberate conservatism for the trusted checker, not
    sloppiness, but it means a row with more than one contribution to the
    same entry is never Iv-degenerate even when the true sum is an exact
    dyadic rational like -1.0 + -1.0. Use `pauli_sum_to_fraction_rows`
    instead, which sums the term coefficients directly in `Fraction` and
    never goes through `Iv` at all.
    """
    n = op.n
    out = [[Fraction(0)] * n for _ in range(n)]
    for i in range(n):
        for j, v in op.row(i).items():
            if v.lo != v.hi:
                raise ValueError(
                    f"entry ({i}, {j}) is a non-degenerate interval "
                    f"[{v.lo}, {v.hi}]; not usable as exact-oracle input"
                )
            out[i][j] = Fraction(v.lo)
    return out


def pauli_sum_to_fraction_rows(enc: dict[str, Any]) -> list[list[Fraction]]:
    """Exact Fraction rows for a `pauli_sum_real` operator encoding.

    Recomputes the same bit-mask/phase logic `PauliSumReal.__init__`/`.row`
    (certkit/operators.py) use to turn a Pauli string into a signed diagonal
    shift or off-diagonal flip, but sums directly in `Fraction` from the
    start instead of going through `Iv`. `Fraction(coeff)` is exact -- a
    Python float is a dyadic rational, and `Fraction.__new__` from a float is
    an exact conversion, not a decimal approximation -- so the result is the
    true operator to the last bit, independent of `Iv`'s conservative
    widening (see `operator_to_fraction_rows` for why that widening makes it
    unusable here). Cross-checked against an explicit Kronecker-product
    construction of the same terms (independent of both this function and
    `PauliSumReal`) while developing this oracle.

    `enc` is the plain-dict encoding (`certkit.operators.encode_pauli`'s
    output, e.g. `producer.tfim_hamiltonian`'s return value), not a decoded
    `Operator` -- there is no `Iv` anywhere in this path.
    """
    qubits = enc["qubits"]
    n = 1 << qubits
    compiled = []
    for t in enc["terms"]:
        coeff = h2f(t["coeff"])
        s = t["string"]
        mask = zy = ny = 0
        for k, p in enumerate(s):
            bit = 1 << k
            if p in ("X", "Y"):
                mask |= bit
            if p in ("Z", "Y"):
                zy |= bit
            if p == "Y":
                ny += 1
        sign = -1 if (ny // 2) % 2 else 1
        compiled.append((Fraction(coeff) * sign, mask, zy))

    rows = [[Fraction(0)] * n for _ in range(n)]
    for i in range(n):
        for c, mask, zy in compiled:
            j = i ^ mask
            term = -c if bin(j & zy).count("1") & 1 else c
            rows[i][j] += term
    return rows


def exact_count_below(rows: Sequence[Sequence[Fraction]], beta: Fraction) -> int:
    """Eigenvalues of the symmetric matrix `rows` strictly below `beta`.

    Exact Fraction LDL^T of (A - beta*I) plus Sylvester's law of inertia:
    identical in structure to `checker.count_eigenvalues_below`, but over
    `Fraction` rather than `Iv`, so every pivot's sign is exact rather than
    enclosed -- there is nothing to abstain over.

    Raises ZeroDivisionError if a pivot is exactly zero, i.e. `beta` is
    exactly an eigenvalue of some leading principal submatrix. For a beta
    reached by bisecting over the reals with random input matrices this is a
    measure-zero event; if it happens, pick a different bracket or beta
    rather than special-casing it here.
    """
    n = len(rows)
    m = [[rows[i][j] - (beta if i == j else 0) for j in range(n)] for i in range(n)]
    d: list[Fraction] = []
    lmat = [[Fraction(0)] * n for _ in range(n)]
    for j in range(n):
        s = m[j][j]
        for k in range(j):
            s -= lmat[j][k] * lmat[j][k] * d[k]
        if s == 0:
            raise ZeroDivisionError(f"pivot {j} is exactly zero; beta is exactly an eigenvalue")
        d.append(s)
        for i in range(j + 1, n):
            t = m[i][j]
            for k in range(j):
                t -= lmat[i][k] * lmat[j][k] * d[k]
            lmat[i][j] = t / s
    return sum(1 for x in d if x < 0)


def gershgorin_bracket(rows: Sequence[Sequence[Fraction]]) -> tuple[Fraction, Fraction]:
    """A cheap exact (lo, hi) with lo below and hi above the whole spectrum."""
    n = len(rows)
    lo = hi = None
    for i in range(n):
        radius = sum((abs(rows[i][j]) for j in range(n) if j != i), Fraction(0))
        low, high = rows[i][i] - radius, rows[i][i] + radius
        lo = low if lo is None or low < lo else lo
        hi = high if hi is None or high > hi else hi
    assert lo is not None and hi is not None  # n > 0 is the only supported case
    return lo, hi


def exact_lambda_min(
    rows: Sequence[Sequence[Fraction]],
    iterations: int = 60,
    bracket: tuple[Fraction, Fraction] | None = None,
) -> tuple[Fraction, Fraction]:
    """Bisect `exact_count_below` to isolate the smallest eigenvalue.

    Returns (lo, hi) with lo <= the true smallest eigenvalue <= hi, both
    exact Fractions, narrowing geometrically with `iterations`.
    """
    lo, hi = bracket if bracket is not None else gershgorin_bracket(rows)
    if exact_count_below(rows, lo) != 0:
        raise ValueError("bracket lo is not below the smallest eigenvalue")
    if exact_count_below(rows, hi) < 1:
        raise ValueError("bracket hi is not above the smallest eigenvalue")
    for _ in range(iterations):
        mid = (lo + hi) / 2
        try:
            count = exact_count_below(rows, mid)
        except ZeroDivisionError:
            # Unpivoted LDL^T's one soft spot: `mid` makes some *leading
            # principal submatrix* exactly singular -- not necessarily the
            # full matrix, since pivot j's vanishing only says
            # det(A[:j, :j] - mid*I) == 0. This is not rare in the way an
            # actual eigenvalue coincidence would be: it happens whenever the
            # bracket's lo and hi are dominated by the same row (lo = hi =
            # diag_i +/- radius_i for one i), which makes their average
            # exactly diag_i, and `gershgorin_bracket` does exactly that
            # whenever one row's disc contains every other row's disc.
            # Nudging `mid` and re-deriving the count from scratch is still
            # fully rigorous -- `exact_count_below` returns the true count for
            # whatever beta it is actually given, so the bracket this loop
            # narrows stays sound regardless of which point we chose.
            mid = mid + (hi - lo) / (1 << 40)
            count = exact_count_below(rows, mid)
        if count >= 1:
            hi = mid
        else:
            lo = mid
    return lo, hi
