"""Composition tests.

A certificate may discharge a hypothesis by referencing another certificate.
The requirement is that this buys modularity without buying a new way to lie:
a dependency that abstains must take its dependents down with it, and no
reference may be satisfied by a certificate about a different operator, a
different beta, or a different claim.
"""

from __future__ import annotations

import copy

import numpy as np
import pytest

from certkit.checker import MAX_DEPTH, bundle_verdict, check, check_bundle
from certkit.operators import decode_operator, encode_dense
from certkit.producer import (
    certify_bounds_composed,
    certify_count_below,
    certify_lambda_min,
    certify_lambda_min_composed,
    tfim_hamiltonian,
)
from certkit.schema import f2h, seal


def _matrix(n=6, seed=1):
    rng = np.random.default_rng(seed)
    m = rng.standard_normal((n, n))
    return ((m + m.T) / 2).tolist()


def _roots(certs, ops):
    return bundle_verdict(check_bundle(certs, ops))


# -- the composed Temple bound -------------------------------------------
def test_composed_temple_verifies_and_matches_the_monolithic_bound():
    rows = _matrix()
    root = _roots(*certify_lambda_min_composed(rows))
    assert root.ok and root.rule == "temple_ref"

    mono = check(*certify_lambda_min(rows))
    assert mono.ok
    assert abs(root.rederived[0] - mono.rederived[0]) < 1e-12
    truth = float(np.linalg.eigvalsh(np.array(rows))[0])
    assert root.rederived[0] <= truth <= root.rederived[1]


def test_every_certificate_in_the_bundle_verifies_on_its_own_terms():
    certs, ops = certify_lambda_min_composed(_matrix())
    results = check_bundle(certs, ops)
    assert len(results) == 2
    assert all(v.ok for v in results.values())
    kinds = {v.claim_kind for v in results.values()}
    assert kinds == {"eigenvalue_count_below", "lambda_min_enclosure"}


def test_dependent_abstains_when_its_dependency_is_missing():
    certs, ops = certify_lambda_min_composed(_matrix())
    count_cert, temple = certs
    results = check_bundle([temple], ops)
    v = next(iter(results.values()))
    assert not v.ok and "not in the bundle" in v.reason


def test_dependent_abstains_when_checked_without_a_bundle():
    certs, ops = certify_lambda_min_composed(_matrix())
    v = check(certs[1], ops[0])
    assert not v.ok and "dependency" in v.reason


def test_a_lying_count_certificate_takes_its_dependent_down():
    """The whole point of composition not being a loophole."""
    rows = _matrix()
    certs, ops = certify_lambda_min_composed(rows)
    count_cert, temple = certs

    bad = copy.deepcopy(count_cert)
    bad["claim"]["count"] = 3  # the matrix does not have 3 eigenvalues below beta
    bad = seal(bad)
    temple["witness"]["gap_ref"] = bad["content_hash"]
    temple = seal(temple)

    results = check_bundle([bad, temple], ops)
    verdicts = list(results.values())
    assert all(not v.ok for v in verdicts)
    assert any("re-derived" in v.reason for v in verdicts)


def test_count_of_two_does_not_satisfy_a_temple_hypothesis():
    """An honest count certificate, but the wrong one."""
    rows = _matrix()
    eigs = np.linalg.eigvalsh(np.array(rows))
    beta = float(0.5 * (eigs[1] + eigs[2]))
    count_cert, enc = certify_count_below(rows, beta, 2)
    assert check(count_cert, enc).ok  # true on its own terms

    certs, ops = certify_lambda_min_composed(rows)
    temple = copy.deepcopy(certs[1])
    temple["witness"]["beta"] = f2h(beta)
    temple["witness"]["gap_ref"] = count_cert["content_hash"]
    temple = seal(temple)

    results = check_bundle([count_cert, temple], ops)
    assert results[count_cert["content_hash"]].ok
    assert not results[temple["content_hash"]].ok
    assert "need exactly 1" in results[temple["content_hash"]].reason


def test_reference_to_a_certificate_about_another_operator_is_rejected():
    other = _matrix(seed=9)
    foreign, foreign_enc = certify_count_below(other, 0.0, 1)

    certs, ops = certify_lambda_min_composed(_matrix())
    temple = copy.deepcopy(certs[1])
    temple["witness"]["gap_ref"] = foreign["content_hash"]
    temple = seal(temple)

    results = check_bundle([foreign, temple], ops + [foreign_enc])
    assert not results[temple["content_hash"]].ok
    assert "different operator" in results[temple["content_hash"]].reason


def test_beta_mismatch_between_temple_and_its_count_is_rejected():
    certs, ops = certify_lambda_min_composed(_matrix())
    count_cert, temple = certs
    temple = copy.deepcopy(temple)
    temple["witness"]["beta"] = f2h(float.fromhex(temple["witness"]["beta"]) + 1e-6)
    temple = seal(temple)
    results = check_bundle([count_cert, temple], ops)
    v = results[temple["content_hash"]]
    assert not v.ok and "different beta" in v.reason


# -- the combine derivation ----------------------------------------------
def test_combine_sandwiches_two_independent_bounds():
    enc = tfim_hamiltonian(6)
    certs, ops = certify_bounds_composed(enc)
    results = check_bundle(certs, ops)
    assert all(v.ok for v in results.values())

    root = bundle_verdict(results)
    assert root.rule == "combine" and len(root.depends_on) == 2

    rows = decode_operator(enc).interval_rows()
    dense = [[0.5 * (v.lo + v.hi) for v in r] for r in rows]
    truth = float(np.linalg.eigvalsh(np.array(dense))[0])
    assert root.rederived[0] <= truth <= root.rederived[1]


def test_combine_has_no_numerics_of_its_own():
    """Remove a half and the derivation has nothing left to stand on."""
    certs, ops = certify_bounds_composed(_matrix())
    floor, ceiling, combined = certs
    results = check_bundle([floor, combined], ops)
    assert not results[combined["content_hash"]].ok
    results = check_bundle([ceiling, combined], ops)
    assert not results[combined["content_hash"]].ok


def test_combine_rejects_a_swapped_reference():
    certs, ops = certify_bounds_composed(_matrix())
    floor, ceiling, combined = certs
    bad = copy.deepcopy(combined)
    bad["witness"]["lower_ref"], bad["witness"]["upper_ref"] = (
        combined["witness"]["upper_ref"],
        combined["witness"]["lower_ref"],
    )
    bad = seal(bad)
    results = check_bundle([floor, ceiling, bad], ops)
    v = results[bad["content_hash"]]
    assert not v.ok and "proves" in v.reason


def test_gershgorin_certificate_needs_no_witness_vector():
    certs, _ = certify_bounds_composed(_matrix())
    assert set(certs[0]["witness"]) == {"rule"}


# -- structural safety ----------------------------------------------------
def test_forged_cycle_is_refused():
    """Content addressing makes cycles infeasible; the check is defence in depth.

    A real cycle would need a hash fixed point, since each certificate's hash
    covers the references inside it. Here the hashes are simply *lies* -- which
    is the only way to build one -- and traversal refuses regardless.
    """
    certs, ops = certify_lambda_min_composed(_matrix())
    a = copy.deepcopy(certs[1])
    b = copy.deepcopy(certs[1])
    a["content_hash"], b["content_hash"] = "ref-a", "ref-b"
    a["witness"]["gap_ref"], b["witness"]["gap_ref"] = "ref-b", "ref-a"
    results = check_bundle([a, b], ops)
    assert all(not v.ok for v in results.values())
    assert any("cyclic" in v.reason or "hash" in v.reason for v in results.values())


def test_self_reference_is_refused():
    certs, ops = certify_lambda_min_composed(_matrix())
    a = copy.deepcopy(certs[1])
    a["content_hash"] = "self"
    a["witness"]["gap_ref"] = "self"
    results = check_bundle([a], ops)
    assert not results["self"].ok


def test_deep_chains_are_bounded():
    assert MAX_DEPTH <= 16  # the traversal must terminate on adversarial input


def test_bundle_verdict_reports_a_failure_reason_rather_than_silence():
    certs, ops = certify_lambda_min_composed(_matrix())
    root = bundle_verdict(check_bundle([certs[1]], ops))
    assert not root.ok and root.reason


def test_operator_missing_from_the_bundle_abstains():
    certs, _ = certify_lambda_min_composed(_matrix())
    results = check_bundle(certs, [])
    assert all(not v.ok for v in results.values())


def test_check_points_a_bundle_at_check_bundle():
    certs, ops = certify_lambda_min_composed(_matrix())
    v = check(certs, ops[0])
    assert not v.ok and "check_bundle" in v.reason


def test_unhashed_certificate_still_gets_a_verdict():
    certs, ops = certify_lambda_min_composed(_matrix())
    stripped = {k: v for k, v in certs[0].items() if k != "content_hash"}
    results = check_bundle([stripped], ops)
    assert len(results) == 1
    assert not next(iter(results.values())).ok


def test_encode_dense_roundtrip_still_matches_after_refactor():
    rows = _matrix(4)
    assert check(*certify_lambda_min(encode_dense(rows))).ok
