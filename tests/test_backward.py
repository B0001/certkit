"""Backward-error counting: correctness, reach, and the runtime delta.

The claim being tested is narrow and worth stating plainly. The float Sturm
sweep is an exact factorisation of *some* nearby tridiagonal matrix; the
distance to it is measured from the entries at runtime rather than taken from a
published constant; and two bracketing sweeps turn that into an exact count for
the operator we actually have, or into an abstention.
"""

from __future__ import annotations

import copy
from fractions import Fraction

import numpy as np
import pytest

from certkit.backward_error import (
    NotTridiagonal,
    count_eigenvalues_below_backward,
    sweep,
    tridiagonal_arrays,
)
from certkit.banded import count_eigenvalues_below_banded
from certkit.checker import bundle_verdict, check, check_bundle
from certkit.interval import IntervalError
from certkit.operators import decode_operator, encode_csr
from certkit.producer import (
    certify_count_below,
    certify_count_below_backward,
    certify_count_below_sturm,
    certify_lambda_min_backward,
    certify_lambda_min_composed,
    laplacian_1d,
    schrodinger_1d,
    tfim_hamiltonian,
)
from certkit.schema import seal


def random_tridiagonal(n: int, seed: int, scale: float = 1.0):
    rng = np.random.default_rng(seed)
    d = rng.standard_normal(n) * 2.0 * scale
    e = rng.standard_normal(max(n - 1, 1)) * scale
    indptr, indices, data = [0], [], []
    for i in range(n):
        for j in (i - 1, i, i + 1):
            if 0 <= j < n:
                indices.append(j)
                data.append(float(d[i]) if j == i else float(e[min(i, j)]))
        indptr.append(len(indices))
    dense = np.diag(d) + np.diag(e[: n - 1], 1) + np.diag(e[: n - 1], -1)
    return encode_csr(n, indptr, indices, data), dense


def laplacian_eigs(n: int) -> np.ndarray:
    k = np.arange(1, n + 1)
    return 2.0 - 2.0 * np.cos(k * np.pi / (n + 1))


def exact_lambda_min(enc: dict, iterations: int = 70):
    """Bisect on an exact rational Sturm count. No floating point anywhere."""
    op = decode_operator(enc)
    n = op.n
    diag = [Fraction(op.row(i)[i].lo) for i in range(n)]
    offs = [Fraction(op.row(i)[i + 1].lo) for i in range(n - 1)]

    def count_below(beta: Fraction) -> int:
        d = diag[0] - beta
        c = 1 if d < 0 else 0
        for j in range(1, n):
            if d == 0:
                d = Fraction(1, 10**40)
            d = (diag[j] - beta) - offs[j - 1] * offs[j - 1] / d
            if d < 0:
                c += 1
        return c

    lo, hi = Fraction(-8), Fraction(8)
    for _ in range(iterations):
        mid = (lo + hi) / 2
        if count_below(mid) >= 1:
            hi = mid
        else:
            lo = mid
    return lo, hi


# -- correctness ----------------------------------------------------------
@pytest.mark.parametrize("n", [4, 15, 60])
def test_count_matches_lapack_across_the_spectrum(n):
    enc, dense = random_tridiagonal(n, seed=n)
    op = decode_operator(enc)
    eigs = np.linalg.eigvalsh(dense)
    checked = 0
    for beta in np.linspace(eigs[0] - 1.0, eigs[-1] + 1.0, 40):
        try:
            got = count_eigenvalues_below_backward(op, float(beta))
        except IntervalError:
            continue  # abstention near an eigenvalue is always allowed
        assert got == int((eigs < beta).sum()), (n, beta, got)
        checked += 1
    assert checked > 25


def test_agrees_with_the_interval_route_where_both_apply():
    enc, dense = random_tridiagonal(30, seed=3)
    op = decode_operator(enc)
    eigs = np.linalg.eigvalsh(dense)
    agreed = 0
    for beta in np.linspace(eigs[0] - 0.5, eigs[-1] + 0.5, 25):
        try:
            a = count_eigenvalues_below_backward(op, float(beta))
            b = count_eigenvalues_below_banded(op, float(beta))
        except IntervalError:
            continue
        assert a == b
        agreed += 1
    assert agreed > 10


# -- the runtime delta ----------------------------------------------------
def test_delta_is_measured_not_assumed():
    """Scale the operator and the perturbation bound scales with it.

    A hard-coded constant would not do this. The bound is read off the entries
    of the matrix in front of the checker.
    """
    small, _ = random_tridiagonal(40, seed=1, scale=1.0)
    large, _ = random_tridiagonal(40, seed=1, scale=1e6)
    ds, os_ = tridiagonal_arrays(decode_operator(small))
    dl, ol = tridiagonal_arrays(decode_operator(large))
    delta_small = sweep(ds, os_, 0.0).delta
    delta_large = sweep(dl, ol, 0.0).delta
    assert delta_small > 0.0
    assert 0.5e6 < delta_large / delta_small < 2e6


def test_delta_is_tiny_relative_to_the_operator_norm():
    op = decode_operator(laplacian_1d(500))
    d, o = tridiagonal_arrays(op)
    assert sweep(d, o, -1.0).delta < 1e-14


def test_beta_on_an_eigenvalue_abstains():
    """The bracketing sweeps disagree, so the count is genuinely undetermined."""
    n = 200
    op = decode_operator(laplacian_1d(n))
    with pytest.raises(IntervalError) as exc:
        count_eigenvalues_below_backward(op, float(laplacian_eigs(n)[0]))
    assert "within" in str(exc.value)


def test_non_tridiagonal_is_refused():
    enc, _ = random_tridiagonal(10, seed=2)
    rows = decode_operator(enc)
    with pytest.raises(NotTridiagonal):
        count_eigenvalues_below_backward(decode_operator(tfim_hamiltonian(5)), 0.0)
    assert rows.n == 10


def test_inexact_entries_are_refused():
    """A Pauli diagonal is a sum of coefficients, so there is no single matrix
    the float recurrence would be running on. Refuse rather than pick one."""
    op = decode_operator(tfim_hamiltonian(2))
    with pytest.raises(NotTridiagonal):
        tridiagonal_arrays(op)


def test_non_finite_shift_is_refused():
    d, o = tridiagonal_arrays(decode_operator(laplacian_1d(5)))
    with pytest.raises(IntervalError):
        sweep(d, o, float("inf"))


# -- reach ----------------------------------------------------------------
@pytest.mark.parametrize("n", [40, 200, 2000])
def test_succeeds_on_laplacians_where_the_interval_route_cannot(n):
    op = decode_operator(laplacian_1d(n))
    eigs = laplacian_eigs(n)
    beta = float(0.5 * (eigs[0] + eigs[1]))

    assert count_eigenvalues_below_backward(op, beta) == 1
    if n >= 40:
        with pytest.raises(IntervalError):
            count_eigenvalues_below_banded(op, beta)


def test_certified_pipeline_reaches_large_operators():
    enc = schrodinger_1d(10000)
    root = bundle_verdict(check_bundle(*certify_lambda_min_backward(enc)))
    assert root.ok and root.rule == "temple_ref"


def test_ground_state_eigenvector_is_no_longer_the_binding_constraint():
    """certkit-8q0: past n ~ 10^4, matrix-free Lanczos left the ground-state
    vector unconverged and Temple turned that residual into a wide-but-sound
    enclosure (width 1.6 at n=1e4, measured before this test existed). For a
    tridiagonal encoding, `_ground_state` now reaches for LAPACK's MRRR
    tridiagonal eigensolver (`scipy.linalg.eigh_tridiagonal`, O(n), no dense
    materialisation) instead of a few hundred Lanczos steps, so the residual
    -- and hence the certified width -- drops to machine precision instead of
    O(1). This is a producer-side solver-quality change; nothing in checker.py
    or the trust boundary moved, and `check_bundle` still re-derives this
    enclosure from scratch.
    """
    enc = schrodinger_1d(100_000)
    root = bundle_verdict(check_bundle(*certify_lambda_min_backward(enc)))
    assert root.ok and root.rule == "temple_ref"
    lo, hi = root.rederived
    assert float(hi) - float(lo) < 1e-9


def test_enclosure_contains_the_exact_eigenvalue_on_a_laplacian():
    enc = laplacian_1d(200)
    root = bundle_verdict(check_bundle(*certify_lambda_min_backward(enc)))
    assert root.ok
    lo, hi = exact_lambda_min(enc)
    c_lo, c_hi = root.rederived
    assert Fraction(c_lo) <= lo and hi <= Fraction(c_hi)


# -- interchangeability ---------------------------------------------------
def test_one_temple_certificate_three_counting_rules():
    """The composition claim, now with three independent proofs of the gap.

    `inertia` factorises densely, `sturm` stays inside the band, `sturm_be`
    abandons enclosure for backward error. They share no code path beyond the
    interval primitives, and the Temple node is unedited between them.
    """
    enc = schrodinger_1d(60)
    certs, ops = certify_lambda_min_composed(enc)
    count_inertia, temple = certs
    beta = float.fromhex(temple["witness"]["beta"])

    count_sturm, _ = certify_count_below_sturm(enc, beta, 1)
    count_be, _ = certify_count_below_backward(enc, beta, 1)
    assert {c["witness"]["rule"] for c in (count_inertia, count_sturm, count_be)} == {
        "inertia", "sturm", "sturm_be"
    }
    assert count_inertia["claim"] == count_sturm["claim"] == count_be["claim"]

    results = []
    for dep in (count_inertia, count_sturm, count_be):
        node = copy.deepcopy(temple)
        node["witness"]["gap_ref"] = dep["content_hash"]
        node = seal(node)
        results.append(bundle_verdict(check_bundle([dep, node], ops)))

    assert all(v.ok for v in results)
    assert len({v.rederived for v in results}) == 1


def test_a_lying_backward_certificate_is_caught():
    enc = schrodinger_1d(40)
    bad, _ = certify_count_below_backward(enc, -1.0, 5)
    v = check(bad, enc)
    assert not v.ok and "re-derived" in v.reason


def test_backward_certificate_needs_no_witness_vector():
    cert, _ = certify_count_below_backward(laplacian_1d(20), -1.0, 0)
    assert set(cert["witness"]) == {"rule"}


def test_all_three_count_rules_agree_on_a_shared_problem():
    enc = schrodinger_1d(50)
    for beta, expected in ((-1.0, 0), (1.0, None)):
        certs = [
            certify_count_below(enc, beta, 0)[0] if expected == 0 else None,
            certify_count_below_sturm(enc, beta, 0)[0] if expected == 0 else None,
            certify_count_below_backward(enc, beta, 0)[0] if expected == 0 else None,
        ]
        if expected is None:
            continue
        assert all(check(c, enc).ok for c in certs)
