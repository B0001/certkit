"""End-to-end: the enclosure must be verified AND must actually contain
the true eigenvalue, on matrices of varying difficulty.

The second half is the interesting one: on hard inputs (degenerate ground
state, huge condition number) the kit is required to ABSTAIN rather than
return a bound it cannot justify.
"""

from __future__ import annotations

import numpy as np
import pytest

from certkit.checker import check, count_eigenvalues_below
from certkit.producer import certify_lambda_min, certify_spectrum_point


def _sym(rng, n, scale=1.0):
    m = rng.standard_normal((n, n)) * scale
    return ((m + m.T) / 2.0).tolist()


def _from_spectrum(rng, eigs):
    n = len(eigs)
    q, _ = np.linalg.qr(rng.standard_normal((n, n)))
    a = q @ np.diag(eigs) @ q.T
    return ((a + a.T) / 2.0).tolist()


@pytest.mark.parametrize("n", [2, 3, 5, 8, 16, 32])
def test_lambda_min_verified_and_sound(n):
    rng = np.random.default_rng(n)
    for _ in range(5):
        rows = _sym(rng, n)
        cert, op = certify_lambda_min(rows)
        v = check(cert, op)
        assert v.ok, v.reason
        truth = float(np.linalg.eigvalsh(np.array(rows))[0])
        lo, hi = v.rederived
        assert lo <= truth <= hi, (lo, truth, hi)


def test_enclosure_is_tight_enough_to_be_useful():
    rng = np.random.default_rng(11)
    rows = _from_spectrum(rng, [-3.0, -1.0, 0.5, 2.0, 7.0])
    cert, op = certify_lambda_min(rows)
    v = check(cert, op)
    assert v.ok
    lo, hi = v.rederived
    assert hi - lo < 1e-10, f"enclosure width {hi - lo}"


def test_spectrum_point_rule_needs_no_gap():
    rng = np.random.default_rng(3)
    rows = _from_spectrum(rng, [1.0, 1.0, 1.0, 4.0])  # degenerate: no gap at all
    cert, op = certify_spectrum_point(rows, index=3)
    v = check(cert, op)
    assert v.ok
    assert v.claim_kind == "spectrum_contains"


def test_degenerate_ground_state_abstains():
    rng = np.random.default_rng(5)
    rows = _from_spectrum(rng, [2.0, 2.0, 5.0, 9.0])  # lambda_1 == lambda_2
    cert, op = certify_lambda_min(rows)
    v = check(cert, op)
    assert not v.ok
    assert "gap" in v.reason or "pivot" in v.reason


def test_near_degenerate_ground_state_abstains_rather_than_guesses():
    rng = np.random.default_rng(6)
    rows = _from_spectrum(rng, [1.0, 1.0 + 1e-15, 3.0, 6.0])
    v = check(*certify_lambda_min(rows))
    assert not v.ok


def test_inertia_count_matches_lapack():
    rng = np.random.default_rng(42)
    for n in (2, 4, 9):
        rows = _sym(rng, n)
        eigs = np.linalg.eigvalsh(np.array(rows))
        for beta in np.linspace(eigs[0] - 1.0, eigs[-1] + 1.0, 17):
            expected = int((eigs < beta).sum())
            try:
                got = count_eigenvalues_below(rows, float(beta))
            except Exception:
                continue  # abstention near an eigenvalue is allowed
            assert got == expected, (n, beta, got, expected)


def test_scaled_operator_still_verified():
    rng = np.random.default_rng(9)
    base = _from_spectrum(rng, [-2.0, 1.0, 4.0, 8.0])
    for scale in (1e-6, 1.0, 1e6):
        rows = (np.array(base) * scale).tolist()
        v = check(*certify_lambda_min(rows))
        assert v.ok, (scale, v.reason)
        truth = float(np.linalg.eigvalsh(np.array(rows))[0])
        assert v.rederived[0] <= truth <= v.rederived[1]
