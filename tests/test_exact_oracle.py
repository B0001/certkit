"""certkit-sqr: an exact rational oracle beyond the tridiagonal shape.

`test_banded.py::exact_lambda_min` and `test_backward.py::exact_lambda_min`
bisect the classical two-term Sturm recurrence over `Fraction` -- exact, but
only because those matrices are tridiagonal. It already caught a real
disagreement (`test_banded.py::test_the_certified_interval_can_be_narrower_
than_lapack_error`: the certified enclosure at n=400 is narrower than LAPACK's
own backward error, so `eigvalsh` falls outside it). Every existing test of a
genuinely banded (bandwidth > 1) or dense operator only checks the certified
enclosure against `eigvalsh` -- the same library whose own rounding the
tridiagonal case demonstrates can be the thing that's wrong.

This file wires `exact_oracle.py` (a general Fraction-exact LDL^T + Sylvester
inertia count, O(n^3), no band assumption) into both shapes: the dense
`inertia` route (`certify_lambda_min` / `count_eigenvalues_below`) and the
banded `sturm` route (`certify_lambda_min_banded` /
`count_eigenvalues_below_banded`) on matrices that are not tridiagonal.

certkit-9oa adds the third shape `certkit-sqr` deliberately left out: a
Pauli-sum operator (`pauli_sum_real`, e.g. `producer.tfim_hamiltonian`).
That shape needs its own ground-truth path rather than reusing
`operator_to_fraction_rows` -- see `exact_oracle.pauli_sum_to_fraction_rows`
for why -- but once that path exists, it is wired into the dense `inertia`
route the same way, since a small enough Pauli-sum operator (`n <=
DENSE_LIMIT`) takes that exact route already (`test_backends.py::
test_small_hamiltonian_takes_the_tight_route`).
"""

from __future__ import annotations

import math
from fractions import Fraction

import numpy as np
import pytest

from certkit.banded import count_eigenvalues_below_banded
from certkit.checker import bundle_verdict, check, check_bundle, count_eigenvalues_below
from certkit.interval import IntervalError
from certkit.operators import DENSE_LIMIT, decode_operator, encode_csr
from certkit.producer import (
    certify_count_below_sturm,
    certify_lambda_min,
    certify_lambda_min_banded,
    tfim_hamiltonian,
)

from exact_oracle import (
    dense_rows_to_fractions,
    exact_count_below,
    exact_lambda_min,
    gershgorin_bracket,
    operator_to_fraction_rows,
    pauli_sum_to_fraction_rows,
)


def _beta_sweep(fq_rows, steps_per_unit: int = 4):
    """A grid of exact rationals spanning the whole spectrum, plus margin."""
    lo, hi = gershgorin_bracket(fq_rows)
    a, b = math.floor(lo) - 1, math.ceil(hi) + 1
    return [Fraction(k, steps_per_unit) for k in range(a * steps_per_unit, b * steps_per_unit + 1)]


def _dense_symmetric(seed: int, n: int) -> list[list[float]]:
    rng = np.random.default_rng(seed)
    m = rng.standard_normal((n, n))
    return ((m + m.T) / 2.0).tolist()


def _banded_matrix(n: int, bandwidth: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    a = np.zeros((n, n))
    for i in range(n):
        for j in range(i, min(n, i + bandwidth + 1)):
            v = float(rng.standard_normal()) + (4.0 if i == j else 0.0)
            a[i, j] = a[j, i] = v
    return a


def _to_csr(a: np.ndarray) -> dict:
    n = a.shape[0]
    indptr, indices, data = [0], [], []
    for i in range(n):
        for j in range(n):
            if a[i, j] != 0.0:
                indices.append(j)
                data.append(float(a[i, j]))
        indptr.append(len(indices))
    return encode_csr(n, indptr, indices, data)


# -- dense: count-below correctness ---------------------------------------
@pytest.mark.parametrize("n", [6, 12, 20])
def test_dense_inertia_count_matches_exact_rational_oracle(n):
    rows = _dense_symmetric(seed=n, n=n)
    fq_rows = dense_rows_to_fractions(rows)
    checked = 0
    for beta in _beta_sweep(fq_rows):
        try:
            got = count_eigenvalues_below(rows, float(beta))
        except IntervalError:
            continue  # abstention near an eigenvalue is allowed
        assert got == exact_count_below(fq_rows, beta), (n, beta, got)
        checked += 1
    assert checked > 10


# -- dense: end-to-end enclosure against the exact eigenvalue -------------
@pytest.mark.parametrize("n", [6, 12, 20])
def test_dense_lambda_min_enclosure_contains_exact_rational_truth(n):
    rows = _dense_symmetric(seed=1000 + n, n=n)
    v = check(*certify_lambda_min(rows))
    assert v.ok, v.reason
    assert v.rule == "temple_inertia"
    c_lo, c_hi = v.rederived

    fq_rows = dense_rows_to_fractions(rows)
    lo, hi = exact_lambda_min(fq_rows, iterations=70)
    assert Fraction(c_lo) <= lo and hi <= Fraction(c_hi)


# -- banded (bandwidth > 1): count-below correctness -----------------------
@pytest.mark.parametrize("bandwidth", [2, 4])
def test_banded_sturm_count_matches_exact_rational_oracle(bandwidth):
    a = _banded_matrix(20, bandwidth, seed=200 + bandwidth)
    enc = _to_csr(a)
    op = decode_operator(enc)
    fq_rows = operator_to_fraction_rows(op)
    checked = 0
    for beta in _beta_sweep(fq_rows):
        try:
            got = count_eigenvalues_below_banded(op, float(beta))
        except IntervalError:
            continue  # abstention near an eigenvalue is allowed
        assert got == exact_count_below(fq_rows, beta), (bandwidth, beta, got)
        checked += 1
    assert checked > 10


# -- banded (bandwidth > 1): end-to-end enclosure --------------------------
@pytest.mark.parametrize("bandwidth", [2, 4])
def test_banded_lambda_min_enclosure_contains_exact_rational_truth(bandwidth):
    a = _banded_matrix(20, bandwidth, seed=300 + bandwidth)
    enc = _to_csr(a)
    certs, ops = certify_lambda_min_banded(enc)
    root = bundle_verdict(check_bundle(certs, ops))
    assert root.ok, root.reason
    assert root.rule == "temple_ref"
    c_lo, c_hi = root.rederived

    op = decode_operator(enc)
    fq_rows = operator_to_fraction_rows(op)
    lo, hi = exact_lambda_min(fq_rows, iterations=70)
    assert Fraction(c_lo) <= lo and hi <= Fraction(c_hi)


def test_a_lying_banded_count_is_caught_and_the_exact_oracle_confirms_the_lie():
    """Not just that the checker abstains on a fabricated count -- that it is
    right to.

    `test_banded.py::test_a_lying_sturm_certificate_is_caught_like_any_other`
    already shows a fabricated count gets abstained on. It does not show that
    the fabrication really was wrong independent of the interval LDL^T
    implementation the checker used to catch it -- if `count_eigenvalues_
    below_banded` had the same bug as the fabricator, it would agree with the
    lie instead of catching it. The exact rational oracle supplies that
    independent confirmation: no floating point, no shared code path with
    `count_eigenvalues_below_banded`.
    """
    a = _banded_matrix(16, 3, seed=42)
    enc = _to_csr(a)
    op = decode_operator(enc)
    fq_rows = operator_to_fraction_rows(op)
    beta = -100.0  # certainly below the whole spectrum
    true_count = exact_count_below(fq_rows, Fraction(beta))
    assert true_count == 0

    bad_cert, _ = certify_count_below_sturm(enc, beta, true_count + 3)
    v = check(bad_cert, enc)
    assert not v.ok and "re-derived" in v.reason


# -- Pauli-sum (matrix-free, but small enough for the tight route) --------
# `field=1.5` (rather than the default 1.0) breaks the extra Z2/translation
# degeneracy an un-tilted TFIM chain has, which otherwise makes it *more*
# likely than a random dense/banded matrix to put an exact grid point of
# `_beta_sweep` exactly on an eigenvalue of some leading principal submatrix.
# qubits is capped at 5 (n=32): exact Fraction LDL^T's bit-growth-per-pivot
# makes n=64 (6 qubits) take ~50s for a single 70-iteration bisection, well
# past what belongs in this suite -- see `operators.DENSE_LIMIT`'s own
# comment on the analogous (much cheaper) float/Iv cost, which does not
# transfer to exact Fraction arithmetic.
@pytest.mark.parametrize("qubits", [3, 4, 5])
def test_pauli_inertia_count_matches_exact_rational_oracle(qubits):
    enc = tfim_hamiltonian(qubits, field=1.5, coupling=1.0)
    op = decode_operator(enc)
    assert op.n <= DENSE_LIMIT
    rows = op.dense_rows()
    fq_rows = pauli_sum_to_fraction_rows(enc)
    checked = 0
    for beta in _beta_sweep(fq_rows):
        try:
            got = count_eigenvalues_below(rows, float(beta))
        except IntervalError:
            continue  # abstention near an eigenvalue is allowed
        try:
            want = exact_count_below(fq_rows, beta)
        except ZeroDivisionError:
            continue  # beta hit an exact eigenvalue of a leading submatrix
        assert got == want, (qubits, beta, got)
        checked += 1
    assert checked > 10


# -- Pauli-sum: end-to-end enclosure against the exact eigenvalue ---------
@pytest.mark.parametrize("qubits", [3, 4, 5])
def test_pauli_lambda_min_enclosure_contains_exact_rational_truth(qubits):
    enc = tfim_hamiltonian(qubits, field=1.5, coupling=1.0)
    op = decode_operator(enc)
    assert op.n <= DENSE_LIMIT
    v = check(*certify_lambda_min(enc))
    assert v.ok, v.reason
    assert v.rule == "temple_inertia"
    c_lo, c_hi = v.rederived

    fq_rows = pauli_sum_to_fraction_rows(enc)
    lo, hi = exact_lambda_min(fq_rows, iterations=70)
    assert Fraction(c_lo) <= lo and hi <= Fraction(c_hi)
