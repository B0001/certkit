"""Banded counting, and the first real test of the composition claim.

The architectural bet made when references were introduced was that a rule
should not care how its hypothesis was established. `test_temple_accepts_either
_count_certificate` is that bet cashed in: one Temple certificate, byte-identical
except for which count it points at, verified against two counting routes that
share no code path.
"""

from __future__ import annotations

import copy

import numpy as np
import pytest

from certkit.banded import MAX_BANDWIDTH, count_eigenvalues_below_banded
from certkit.checker import bundle_verdict, check, check_bundle, count_eigenvalues_below
from certkit.interval import IntervalError
from certkit.operators import decode_operator, encode_csr
from certkit.producer import (
    certify_count_below,
    certify_count_below_sturm,
    certify_lambda_min,
    certify_lambda_min_banded,
    certify_lambda_min_composed,
    schrodinger_1d,
    tfim_hamiltonian,
)
from certkit.schema import seal


def banded_matrix(n: int, bandwidth: int, seed: int = 0):
    rng = np.random.default_rng(seed)
    a = np.zeros((n, n))
    for i in range(n):
        for j in range(i, min(n, i + bandwidth + 1)):
            v = float(rng.standard_normal()) + (4.0 if i == j else 0.0)
            a[i, j] = a[j, i] = v
    return a


def to_csr(a: np.ndarray) -> dict:
    n = a.shape[0]
    indptr, indices, data = [0], [], []
    for i in range(n):
        for j in range(n):
            if a[i, j] != 0.0:
                indices.append(j)
                data.append(float(a[i, j]))
        indptr.append(len(indices))
    return encode_csr(n, indptr, indices, data)


def tridiag_encoding(n: int, diag: float = 2.0, off: float = -1.0) -> dict:
    indptr, indices, data = [0], [], []
    for i in range(n):
        for j in (i - 1, i, i + 1):
            if 0 <= j < n:
                indices.append(j)
                data.append(diag if j == i else off)
        indptr.append(len(indices))
    return encode_csr(n, indptr, indices, data)


# -- correctness of the count --------------------------------------------
@pytest.mark.parametrize("bandwidth", [1, 2, 4])
def test_banded_count_matches_lapack(bandwidth):
    a = banded_matrix(25, bandwidth, seed=bandwidth)
    op = decode_operator(to_csr(a))
    eigs = np.linalg.eigvalsh(a)
    checked = 0
    for beta in np.linspace(eigs[0] - 1.0, eigs[-1] + 1.0, 21):
        try:
            got = count_eigenvalues_below_banded(op, float(beta))
        except IntervalError:
            continue  # abstention near an eigenvalue is allowed
        assert got == int((eigs < beta).sum()), (bandwidth, beta, got)
        checked += 1
    assert checked > 10


def test_banded_and_dense_routes_agree():
    a = banded_matrix(20, 2, seed=5)
    op = decode_operator(to_csr(a))
    eigs = np.linalg.eigvalsh(a)
    beta = float(0.5 * (eigs[3] + eigs[4]))
    assert count_eigenvalues_below_banded(op, beta) == count_eigenvalues_below(
        op.interval_rows(), beta
    )


def test_non_banded_operator_is_refused_by_the_banded_route():
    # A Pauli string that flips a high qubit reaches 2^k columns away, so a
    # Hamiltonian is banded only in the trivial small cases.
    op = decode_operator(tfim_hamiltonian(9))
    with pytest.raises(IntervalError) as exc:
        count_eigenvalues_below_banded(op, 0.0)
    assert "bandwidth" in str(exc.value)


def test_bandwidth_limit_is_enforced():
    a = banded_matrix(12, 6, seed=2)
    op = decode_operator(to_csr(a))
    with pytest.raises(IntervalError):
        count_eigenvalues_below_banded(op, 0.0, max_bandwidth=3)
    assert MAX_BANDWIDTH >= 8  # the default should not be uselessly tight


# -- reach ----------------------------------------------------------------
def test_banded_route_verifies_far_beyond_the_dense_ceiling():
    n = 1000
    enc = schrodinger_1d(n)
    root = bundle_verdict(check_bundle(*certify_lambda_min_banded(enc)))
    assert root.ok and root.rule == "temple_ref"

    diag = [decode_operator(enc).row(i)[i].lo for i in range(n)]
    m = np.diag(diag) + np.diag([-1.0] * (n - 1), 1) + np.diag([-1.0] * (n - 1), -1)
    truth = float(np.linalg.eigvalsh(m)[0])
    assert root.rederived[0] <= truth <= root.rederived[1]


def test_dense_route_declines_the_same_problem():
    v = check(*certify_lambda_min(schrodinger_1d(1000)))
    assert not v.ok and "materialise" in v.reason


def test_gap_not_size_is_the_limiting_factor():
    """A 1D Laplacian's gap shrinks like 1/n^2 and defeats both routes early.

    The Schrodinger well above is far larger and succeeds. Size is not what
    stops the banded route; an ill-separated ground state is.
    """
    op = decode_operator(tridiag_encoding(400))
    eigs = np.linalg.eigvalsh(
        np.diag([2.0] * 400) + np.diag([-1.0] * 399, 1) + np.diag([-1.0] * 399, -1)
    )
    with pytest.raises(IntervalError):
        count_eigenvalues_below_banded(op, float(0.5 * (eigs[0] + eigs[1])))


# -- against an oracle with no rounding at all ---------------------------
def exact_lambda_min(enc: dict, iterations: int = 70):
    """Bisect on an exact rational Sturm count. No floating point anywhere.

    The diagonal entries are doubles, hence exact rationals, and the
    off-diagonals are -1, so `Fraction` gives a reference with no error term at
    all -- unlike LAPACK, whose own error is larger than the interval this kit
    certifies at n = 400.
    """
    from fractions import Fraction

    op = decode_operator(enc)
    n = op.n
    diag = [Fraction(op.row(i)[i].lo) for i in range(n)]

    def count_below(beta: "Fraction") -> int:
        d = diag[0] - beta
        c = 1 if d < 0 else 0
        for j in range(1, n):
            if d == 0:
                d = Fraction(1, 10**40)
            d = (diag[j] - beta) - 1 / d
            if d < 0:
                c += 1
        return c

    lo, hi = Fraction(0), Fraction(1)
    for _ in range(iterations):
        mid = (lo + hi) / 2
        if count_below(mid) >= 1:
            hi = mid
        else:
            lo = mid
    return lo, hi


def test_enclosure_contains_the_exact_eigenvalue():
    from fractions import Fraction

    enc = schrodinger_1d(120)
    root = bundle_verdict(check_bundle(*certify_lambda_min_banded(enc)))
    assert root.ok
    lo, hi = exact_lambda_min(enc)
    c_lo, c_hi = root.rederived
    assert Fraction(c_lo) <= lo and hi <= Fraction(c_hi)


def test_the_certified_interval_can_be_narrower_than_lapack_error():
    """Not a stunt -- the reason a checker is worth having.

    At this size the certified enclosure is tighter than LAPACK's own backward
    error, so `numpy.linalg.eigvalsh` lands outside it. The exact rational
    oracle confirms the enclosure, not the library.
    """
    from fractions import Fraction

    enc = schrodinger_1d(120)
    root = bundle_verdict(check_bundle(*certify_lambda_min_banded(enc)))
    assert root.ok
    c_lo, c_hi = root.rederived

    lo, hi = exact_lambda_min(enc)
    assert Fraction(c_lo) <= lo and hi <= Fraction(c_hi)

    op = decode_operator(enc)
    n = op.n
    diag = [op.row(i)[i].lo for i in range(n)]
    m = np.diag(diag) + np.diag([-1.0] * (n - 1), 1) + np.diag([-1.0] * (n - 1), -1)
    lapack = float(np.linalg.eigvalsh(m)[0])
    # LAPACK may or may not land inside; what must hold is that the exact value
    # does, and that any disagreement is on LAPACK's side of the ledger.
    if not (c_lo <= lapack <= c_hi):
        assert abs(Fraction(lapack) - lo) > (Fraction(c_hi) - Fraction(c_lo)) / 2


# -- the composition payoff ----------------------------------------------
def test_temple_accepts_either_count_certificate():
    """One Temple certificate, two independent ways of proving its hypothesis.

    The Temple node is not edited between the two bundles -- only the hash it
    points at changes. Nothing in the Temple rule knows that `sturm` exists.
    """
    enc = schrodinger_1d(60)
    certs, ops = certify_lambda_min_composed(enc)
    count_dense, temple_dense = certs
    beta = float.fromhex(temple_dense["witness"]["beta"])

    count_sturm, _ = certify_count_below_sturm(enc, beta, 1)
    assert count_sturm["witness"]["rule"] == "sturm"
    assert count_dense["witness"]["rule"] == "inertia"

    temple_sturm = copy.deepcopy(temple_dense)
    temple_sturm["witness"]["gap_ref"] = count_sturm["content_hash"]
    temple_sturm = seal(temple_sturm)

    a = bundle_verdict(check_bundle([count_dense, temple_dense], ops))
    b = bundle_verdict(check_bundle([count_sturm, temple_sturm], ops))
    assert a.ok and b.ok
    assert a.rederived == b.rederived  # identical conclusion, different provenance

    diff = {
        k for k in temple_dense["witness"]
        if temple_dense["witness"][k] != temple_sturm["witness"][k]
    }
    assert diff == {"gap_ref"}
    assert temple_dense["claim"] == temple_sturm["claim"]


def test_sturm_and_inertia_certificates_are_interchangeable_claims():
    enc = schrodinger_1d(40)
    beta = -1.0  # below the whole spectrum: an easy, well-conditioned count
    dense_cert, _ = certify_count_below(enc, beta, 0)
    sturm_cert, _ = certify_count_below_sturm(enc, beta, 0)
    vd, vs = check(dense_cert, enc), check(sturm_cert, enc)
    assert vd.ok and vs.ok
    assert vd.claim_kind == vs.claim_kind == "eigenvalue_count_below"
    assert dense_cert["claim"] == sturm_cert["claim"]  # same claim, different witness


def test_a_lying_sturm_certificate_is_caught_like_any_other():
    enc = schrodinger_1d(40)
    bad, _ = certify_count_below_sturm(enc, -1.0, 7)
    v = check(bad, enc)
    assert not v.ok and "re-derived" in v.reason


def test_sturm_certificate_needs_no_witness_vector():
    cert, _ = certify_count_below_sturm(schrodinger_1d(20), -1.0, 0)
    assert set(cert["witness"]) == {"rule"}
