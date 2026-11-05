"""certkit-1vm: a VERIFIED answers one question -- a claim kind, an operator
and, for a pencil A x = lambda S x, its metric S -- and a caller can require it.

Each case here printed VERIFIED, and the CLI exited 0, for a true claim that
answers a different question from the one a caller reads into it:

1. Any kind: on an operator whose lambda_min is 1, 'some eigenvalue lies near
   50' (residual), 'lambda_min <= 1e300' (rayleigh) and 'every eigenvalue is
   at least -1e300' (gershgorin).
2. A pencil with S = A, whose eigenvalues are all 1, read as lambda_min(A).
3. bundle_verdict handing a pencil caller lambda_min(S), the tightest VERIFIED
   in a bundle that also proves things about S.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from certkit.checker import bundle_verdict, check, check_bundle
from certkit.cli import main
from certkit.operators import encode_dense, operator_ref
from certkit.producer import (
    certify_lambda_min,
    certify_lambda_min_composed,
    certify_lambda_min_generalized,
    certify_spectrum_point,
)
from certkit.schema import SCHEMA_VERSION, f2h, seal

ONE = encode_dense([[1.0, 0.0], [0.0, 50.0]])  # lambda_min = 1

# A pencil whose lambda_min (about 48) is neither A's (about 100) nor S's (about 2).
A_ROWS = [[100.0, 0.5, 0.0], [0.5, 120.0, 0.3], [0.0, 0.3, 150.0]]
S_ROWS = [[2.0, 0.01, 0.0], [0.01, 2.5, 0.02], [0.0, 0.02, 3.0]]
A, S = encode_dense(A_ROWS), encode_dense(S_ROWS)
PENCIL_MIN = min(np.linalg.eigvals(np.linalg.solve(S_ROWS, A_ROWS)).real)


def _one_sided(kind, rule, bound, **witness):
    return seal({
        "schema": SCHEMA_VERSION,
        "claim": {"operator_ref": operator_ref(ONE), "kind": kind, "bound": f2h(bound)},
        "witness": {"rule": rule, **witness},
    })


OTHER_KINDS = {
    "residual": lambda: certify_spectrum_point(ONE, index=1)[0],
    "rayleigh": lambda: _one_sided("lambda_min_upper_bound", "rayleigh", 1e300,
                                   vector=[f2h(1.0), f2h(1.0)]),
    "gershgorin": lambda: _one_sided("spectrum_lower_bound", "gershgorin", -1e300),
}


def _cli(tmp_path, capsys, cert, op, *flags):
    (tmp_path / "c.json").write_text(json.dumps(cert))
    (tmp_path / "o.json").write_text(json.dumps(op))
    code = main(["check", str(tmp_path / "c.json"), str(tmp_path / "o.json"), *flags])
    return code, capsys.readouterr().out


@pytest.mark.parametrize("name", OTHER_KINDS)
def test_require_kind_refuses_a_true_claim_of_another_kind(name, tmp_path, capsys):
    cert = OTHER_KINDS[name]()
    v = check(cert, ONE)
    assert v.ok and v.claim_kind != "lambda_min_enclosure"
    assert (v.operator_ref, v.metric_ref) == (operator_ref(ONE), None)

    code, out = _cli(tmp_path, capsys, cert, ONE)  # true, and labelled with its kind
    assert code == 0 and out.startswith(f"VERIFIED  {v.claim_kind} "), out
    code, out = _cli(tmp_path, capsys, cert, ONE, "--require-kind", "lambda_min_enclosure")
    assert code == 1 and out.startswith("ABSTAIN   scope:") and v.claim_kind in out, out
    assert _cli(tmp_path, capsys, cert, ONE, "--require-kind", v.claim_kind)[0] == 0


def test_cli_scope_options_bind_single_certificates_and_bundles(tmp_path, capsys):
    rows = [[2.0, 0.5, 0.0], [0.5, 3.0, 0.2], [0.0, 0.2, 4.0]]
    certs, (op,) = certify_lambda_min_composed(rows)
    for cert in (certify_lambda_min(rows)[0], certs):
        assert _cli(tmp_path, capsys, cert, op, "--operator-ref", operator_ref(op))[0] == 0
        code, out = _cli(tmp_path, capsys, cert, op, "--operator-ref", operator_ref(ONE))
        assert code == 1 and operator_ref(ONE) in out.splitlines()[-1], out
        code, out = _cli(tmp_path, capsys, cert, op, "--require-kind", "spectrum_contains")
        assert code == 1 and "spectrum_contains" in out.splitlines()[-1], out


def test_a_pencil_with_s_equal_to_a_is_scoped_to_the_pencil(tmp_path, capsys):
    """Every eigenvalue of (B, B) is 1; lambda_min(B) is about 99.95."""
    b = encode_dense([[100.0, 1.0], [1.0, 120.0]])
    ref = operator_ref(b)
    cert, _, _ = certify_lambda_min_generalized(b, b)
    v = check(cert, b)
    assert v.ok and v.enclosure[1] < 2  # true of the pencil, false of B
    assert (v.operator_ref, v.metric_ref) == (ref, ref)
    assert f"metric_ref {ref}" in str(v)

    for c in (cert, [cert]):  # one operator file: never an answer about B
        code, out = _cli(tmp_path, capsys, c, b)
        assert code == 1 and f"metric_ref {ref}" in out, out

    results = check_bundle([cert], [b])
    assert not bundle_verdict(results, operator_ref=ref).ok
    assert bundle_verdict(results, operator_ref=ref, metric_ref=ref).ok


def test_bundle_verdict_answers_only_the_operator_or_pencil_asked_about():
    a, s = operator_ref(A), operator_ref(S)
    s_cert, _ = certify_lambda_min(S)
    p_cert, _, _ = certify_lambda_min_generalized(A, S)
    results = check_bundle([s_cert, p_cert], [A, S])
    assert all(v.ok for v in results.values())

    pencil = bundle_verdict(results, operator_ref=a, metric_ref=s)
    assert pencil.rule == "gen_gershgorin_rayleigh"
    assert pencil.rederived[0] <= PENCIL_MIN <= pencil.rederived[1]
    # What a kind-only filter used to hand the pencil caller: tighter, and wrong.
    on_s = bundle_verdict(results, operator_ref=s)
    assert on_s.rule == "temple_inertia" and on_s.width < pencil.width
    assert on_s.enclosure[1] < PENCIL_MIN
    assert not bundle_verdict(results, operator_ref=a).ok  # nothing proves lambda_min(A)


def test_a_metric_ref_the_rule_never_reads_binds_nothing():
    """temple_inertia proves lambda_min(A), about 100, whatever the claim says
    about S. Read off the claim, metric_ref would make it a false VERIFIED of
    lambda_min(A, S), which is about 48."""
    cert, _ = certify_lambda_min(A)
    cert = seal(dict(cert, claim=dict(cert["claim"], metric_ref=operator_ref(S))))
    results = check_bundle([cert], [A, S])
    (v,) = results.values()
    assert v.ok and v.metric_ref is None and v.rederived[0] > PENCIL_MIN + 50
    assert not bundle_verdict(results, operator_ref=operator_ref(A), metric_ref=operator_ref(S)).ok
    assert bundle_verdict(results, operator_ref=operator_ref(A)).ok
