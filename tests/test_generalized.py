"""certkit-jn1.2: the generalized eigenproblem A x = lambda S x.

One new rule, `gen_gershgorin_rayleigh` in checker.py, generalizes
`gershgorin_rayleigh` to a pencil (A, S) with S symmetric positive definite:
lambda_min(A, S) in [generalized-Gershgorin floor, generalized-Rayleigh
ceiling]. Two things this file has to show, matching the standard: soundness
against an independently-computed truth (the exact-oracle test), and the same
abstain-not-degrade discipline when the hypothesis the rule needs -- S
provably positive definite from its own Gershgorin discs -- is not available.
"""

from __future__ import annotations

from fractions import Fraction

import numpy as np
import pytest

from certkit.checker import check_bundle
from certkit.operators import encode_dense, operator_ref
from certkit.producer import certify_lambda_min_generalized
from certkit.schema import SCHEMA_VERSION, f2h, seal


def _diag_operator(vals: list[float]) -> dict:
    n = len(vals)
    rows = [[vals[i] if i == j else 0.0 for j in range(n)] for i in range(n)]
    return encode_dense(rows)


def _one_verdict(cert, a_enc, s_enc):
    results = check_bundle([cert], [a_enc, s_enc])
    return next(iter(results.values()))


def test_exact_oracle_diagonal_pencil():
    """A and S diagonal: the generalized eigenvalues are exactly a_i / s_i,
    with no LAPACK step and no rounding anywhere in the ground truth -- every
    value involved is exactly representable in binary, so `Fraction` gives a
    truth with zero error to compare the checker's own enclosure against.
    """
    a_vals = [3.0, -2.0, 7.0, 0.5]
    s_vals = [1.0, 4.0, 2.0, 0.25]
    a_enc = _diag_operator(a_vals)
    s_enc = _diag_operator(s_vals)

    truth = min(Fraction(a) / Fraction(s) for a, s in zip(a_vals, s_vals))
    assert truth == Fraction(-1, 2)

    cert, a_ref, s_ref = certify_lambda_min_generalized(a_enc, s_enc)
    v = _one_verdict(cert, a_ref, s_ref)
    assert v.ok, v.reason
    assert v.rule == "gen_gershgorin_rayleigh"
    lo, hi = v.rederived
    assert Fraction(lo) <= truth <= Fraction(hi)


@pytest.mark.parametrize("seed", range(6))
def test_verified_and_sound_against_numpy_reduction(seed):
    """Dense random pencils: S built diagonally dominant so Gershgorin can
    prove it positive definite, A arbitrary symmetric. Ground truth is the
    standard reduction B = L^-1 A L^-T (S = L L^T), computed independently of
    `certify_lambda_min_generalized`'s own internal use of the same reduction
    -- the thing actually being checked for soundness is `gen_gershgorin_rayleigh`
    in checker.py, which never performs this reduction at all.
    """
    rng = np.random.default_rng(seed)
    n = 5
    m = rng.standard_normal((n, n))
    a = (m + m.T) / 2.0
    perturb = rng.standard_normal((n, n))
    s = np.diag(4.0 + rng.random(n)) + 0.1 * (perturb + perturb.T) / 2.0
    s = (s + s.T) / 2.0

    l = np.linalg.cholesky(s)
    b = np.linalg.solve(l, np.linalg.solve(l, a.T).T)
    b = 0.5 * (b + b.T)
    truth = float(np.linalg.eigvalsh(b)[0])

    a_enc, s_enc = encode_dense(a.tolist()), encode_dense(s.tolist())
    cert, a_ref, s_ref = certify_lambda_min_generalized(a_enc, s_enc)
    v = _one_verdict(cert, a_ref, s_ref)
    assert v.ok, v.reason
    lo, hi = v.rederived
    assert lo <= truth <= hi, (lo, truth, hi)


def test_abstains_when_s_positive_definiteness_is_not_provable_by_gershgorin():
    """S here is the standard 1D-Laplacian-like tridiagonal [[2,-1,0],
    [-1,2,-1],[0,-1,2]]. It genuinely is positive definite (eigenvalues
    2-sqrt2, 2, 2+sqrt2, all > 0) -- but its Gershgorin lower bound is
    exactly 0 (row 1: diag 2, radius 1+1=2), which is not *strictly*
    positive, so the rule cannot certify S is PD from discs alone and must
    abstain rather than assume it. This is the abstain-not-degrade case: the
    rule has no fallback that would let it answer anyway.
    """
    a_enc = _diag_operator([1.0, 1.0, 1.0])
    s_rows = [[2.0, -1.0, 0.0], [-1.0, 2.0, -1.0], [0.0, -1.0, 2.0]]
    s_enc = encode_dense(s_rows)

    s_eigs = np.linalg.eigvalsh(np.array(s_rows))
    assert (s_eigs > 0).all()  # S really is positive definite

    cert = seal({
        "schema": SCHEMA_VERSION,
        "claim": {
            "operator_ref": operator_ref(a_enc),
            "metric_ref": operator_ref(s_enc),
            "kind": "lambda_min_enclosure",
            "enclosure": {"lo": f2h(0.0), "hi": f2h(1.0)},
        },
        "witness": {
            "rule": "gen_gershgorin_rayleigh",
            "vector": [f2h(1.0), f2h(0.0), f2h(0.0)],
        },
    })
    v = _one_verdict(cert, a_enc, s_enc)
    assert not v.ok
    assert "positive definite" in v.reason


def test_abstains_when_metric_operator_is_missing():
    """A bundle that never supplies S at all must abstain, not silently fall
    back to the standard (S = I) rule or crash."""
    a_enc = _diag_operator([1.0, 2.0, 3.0])
    s_enc = _diag_operator([1.0, 1.0, 1.0])
    cert = seal({
        "schema": SCHEMA_VERSION,
        "claim": {
            "operator_ref": operator_ref(a_enc),
            "metric_ref": operator_ref(s_enc),
            "kind": "lambda_min_enclosure",
            "enclosure": {"lo": f2h(0.5), "hi": f2h(1.5)},
        },
        "witness": {
            "rule": "gen_gershgorin_rayleigh",
            "vector": [f2h(1.0), f2h(0.0), f2h(0.0)],
        },
    })
    # Only A supplied -- exactly what a caller of plain `check()` would do
    # without knowing this rule needs a second operator.
    results = check_bundle([cert], [a_enc])
    v = next(iter(results.values()))
    assert not v.ok
    assert "metric operator" in v.reason


def test_tampered_metric_ref_is_caught():
    """The metric operator is referenced by hash like the primary operator.
    Swapping in a different S after the fact must not verify."""
    a_enc = _diag_operator([1.0, 2.0, 3.0])
    s_enc = _diag_operator([1.0, 1.0, 1.0])
    other_s_enc = _diag_operator([100.0, 100.0, 100.0])

    cert, a_ref, s_ref = certify_lambda_min_generalized(a_enc, s_enc)
    # Re-check against a different S than the one referenced in the claim.
    results = check_bundle([cert], [a_ref, other_s_enc])
    v = next(iter(results.values()))
    assert not v.ok
    assert "metric operator" in v.reason
