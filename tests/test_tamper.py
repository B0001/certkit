"""Adversarial tests.

Each of these is a *lie the producer could tell*. The requirement is not
that the checker detect the lie by pattern -- it is that no lie can survive
re-derivation. Every case must ABSTAIN.
"""

from __future__ import annotations

import copy
import json

import numpy as np
import pytest

from certkit.checker import check
from certkit.producer import certify_lambda_min
from certkit.schema import f2h, seal


def _case(seed=1, n=6):
    rng = np.random.default_rng(seed)
    m = rng.standard_normal((n, n))
    rows = ((m + m.T) / 2).tolist()
    cert, op = certify_lambda_min(rows)
    assert check(cert, op).ok
    return cert, op, rows


def test_baseline_verifies():
    cert, op, _ = _case()
    assert check(cert, op).ok


def test_shrunk_enclosure_is_rejected():
    cert, op, _ = _case()
    bad = copy.deepcopy(cert)
    lo = float.fromhex(bad["claim"]["enclosure"]["lo"])
    hi = float.fromhex(bad["claim"]["enclosure"]["hi"])
    mid = 0.5 * (lo + hi)
    bad["claim"]["enclosure"] = {"lo": f2h(mid), "hi": f2h(mid)}  # a point claim
    v = check(seal(bad), op)
    assert not v.ok and "tighter" in v.reason


def test_shifted_enclosure_is_rejected():
    cert, op, _ = _case()
    bad = copy.deepcopy(cert)
    lo = float.fromhex(bad["claim"]["enclosure"]["lo"])
    hi = float.fromhex(bad["claim"]["enclosure"]["hi"])
    bad["claim"]["enclosure"] = {"lo": f2h(lo + 10.0), "hi": f2h(hi + 10.0)}
    assert not check(seal(bad), op).ok


def test_unsealed_mutation_is_caught_by_the_hash():
    cert, op, _ = _case()
    bad = copy.deepcopy(cert)
    bad["claim"]["enclosure"]["lo"] = f2h(-1e9)  # generous, but not re-sealed
    v = check(bad, op)
    assert not v.ok and "hash" in v.reason


def test_witness_vector_tampering_is_rejected():
    cert, op, _ = _case()
    bad = copy.deepcopy(cert)
    bad["witness"]["vector"][0] = f2h(float.fromhex(bad["witness"]["vector"][0]) + 0.3)
    v = check(seal(bad), op)
    assert not v.ok  # a perturbed vector has a larger residual than claimed


def test_operator_substitution_is_rejected():
    cert, op, _ = _case()
    other_rows = (np.eye(6) * 3.0).tolist()
    from certkit.operators import encode_dense as encode_operator

    v = check(cert, encode_operator(other_rows))
    assert not v.ok and "operator" in v.reason


def test_operator_entry_tampering_is_rejected():
    cert, op, _ = _case()
    bad_op = copy.deepcopy(op)
    bad_op["rows"][0][0] = f2h(float.fromhex(bad_op["rows"][0][0]) - 5.0)
    v = check(cert, bad_op)
    assert not v.ok


def test_inflated_beta_is_not_taken_on_faith():
    """The classic Temple mistake: claim a gap you do not have.

    Pushing beta above lambda_2 makes the Temple bound look far tighter.
    The inertia count refuses it.
    """
    cert, op, rows = _case()
    eigs = np.linalg.eigvalsh(np.array(rows))
    bad = copy.deepcopy(cert)
    beta = float(0.5 * (eigs[2] + eigs[3]))  # three eigenvalues now below beta
    bad["witness"]["beta"] = f2h(beta)
    v = check(seal(bad), op)
    assert not v.ok and "discharged" in v.reason


def test_beta_landing_on_an_eigenvalue_abstains():
    """A gap parameter that is itself (nearly) an eigenvalue leaves the
    inertia undetermined. Abstain, do not round the pivot to a sign."""
    cert, op, rows = _case()
    eigs = np.linalg.eigvalsh(np.array(rows))
    bad = copy.deepcopy(cert)
    bad["witness"]["beta"] = f2h(float(eigs[1]))
    assert not check(seal(bad), op).ok


def test_nonsymmetric_operator_is_rejected():
    cert, op, rows = _case()
    bad_op = copy.deepcopy(op)
    bad_op["rows"][0][1] = f2h(float.fromhex(bad_op["rows"][0][1]) + 1.0)
    v = check(cert, bad_op)
    assert not v.ok


def test_rule_claim_mismatch_is_rejected():
    cert, op, _ = _case()
    bad = copy.deepcopy(cert)
    bad["claim"]["kind"] = "spectrum_contains"
    v = check(seal(bad), op)
    assert not v.ok and "match" in v.reason


def test_unknown_rule_is_rejected():
    cert, op, _ = _case()
    bad = copy.deepcopy(cert)
    bad["witness"]["rule"] = "trust_me"
    v = check(seal(bad), op)
    assert not v.ok


def test_garbage_inputs_abstain_rather_than_crash():
    _, op, _ = _case()
    for junk in (None, 42, [], {}, {"schema": "certkit/1"}, "{}"):
        v = check(junk, op)
        assert not v.ok


def test_certificate_survives_json_roundtrip():
    cert, op, _ = _case()
    assert check(json.loads(json.dumps(cert)), json.loads(json.dumps(op))).ok
