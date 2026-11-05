"""certkit-3zr: attacker-controlled JSON gets ABSTAIN, never an exception.

The contract is that check() and check_bundle() always return verdicts. Every
case below used to escape them as an uncaught exception, and the CLI as a
traceback with exit 1, which conformance/run.py could not tell from ABSTAIN.
"""

from __future__ import annotations

import copy
import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from certkit.checker import check, check_bundle
from certkit.operators import encode_dense, encode_dense_hermitian, operator_ref
from certkit.producer import certify_lambda_min, certify_lambda_min_generalized
from certkit.schema import seal

ROOT = Path(__file__).resolve().parents[1]
CERT, OP = certify_lambda_min([[2.0, 0.5, 0.0], [0.5, 3.0, 0.2], [0.0, 0.2, 4.0]])
# Overflows json on every supported Python. The bead's 1000 no longer does on
# 3.12+, whose json limits are higher (3.14's are stack-based).
DEPTH = 100_000


def _deep():
    x = 0
    for _ in range(DEPTH):
        x = [x]
    return x


def _cert(mutate):
    c = copy.deepcopy(CERT)
    mutate(c)
    return seal(c)


def _against(op):
    """A sealed certificate whose operator_ref is `op`'s, so `op` gets decoded."""
    return _cert(lambda c: c["claim"].update(operator_ref=operator_ref(op))), op


def _overflowing_op():
    o = copy.deepcopy(OP)
    o["rows"][0][0] = "0x1p1024"  # 2**1024: float.fromhex raises OverflowError
    return o


# name -> (build (cert, op), substring every refusal's reason must contain)
CASES = {
    "surrogate_in_certificate": (lambda: (dict(CERT, note="\ud800"), OP), "UnicodeEncodeError"),
    "surrogate_in_operator": (lambda: (CERT, dict(OP, note="\ud800")), "operator"),
    "unhashable_witness_rule": (
        lambda: (_cert(lambda c: c["witness"].update(rule=["temple_inertia"])), OP), "TypeError"),
    "unhashable_operator_ref": (
        lambda: (_cert(lambda c: c["claim"].update(operator_ref=["x"])), OP), "TypeError"),
    "unhashable_operator_kind": (
        lambda: _against(dict(OP, kind={"not": "hashable"})), "TypeError"),
    "hex_overflow_in_operator": (lambda: _against(_overflowing_op()), "bad hex float"),
    "hex_overflow_in_enclosure": (
        lambda: (_cert(lambda c: c["claim"]["enclosure"].update(lo="-0x1p1024")), OP), "bad hex float"),
    "deep_nesting_in_certificate": (lambda: (dict(CERT, note=_deep()), OP), "RecursionError"),
    "deep_nesting_in_operator": (lambda: (CERT, dict(OP, note=_deep())), "operator"),
}


def _cli(*args):
    return subprocess.run([sys.executable, "-m", "certkit.cli", *map(str, args)],
                          capture_output=True, text=True, cwd=ROOT)


@pytest.mark.parametrize("name", CASES)
def test_hostile_json_abstains(name, tmp_path):
    build, why = CASES[name]
    cert, op = build()
    v = check(cert, op)
    assert v.status == "ABSTAIN" and why in v.reason, v.reason
    (b,) = check_bundle([cert], [op]).values()
    assert b.status == "ABSTAIN" and why in b.reason, b.reason

    if name.startswith("deep"):
        return  # json.dumps cannot write these; the CLI's deep case is below
    (tmp_path / "c.json").write_text(json.dumps(cert))  # ensure_ascii escapes the surrogate
    (tmp_path / "o.json").write_text(json.dumps(op))
    p = _cli("check", tmp_path / "c.json", tmp_path / "o.json")
    assert p.returncode == 1 and p.stdout.startswith("ABSTAIN") and why in p.stdout, p.stdout + p.stderr


def test_gen_gershgorin_rayleigh_refuses_a_complex_metric():
    """The kind guard in _verify_uncached checks only the primary operator."""
    cert, a_enc, _ = certify_lambda_min_generalized(
        encode_dense([[3.0, 0.1], [0.1, 4.0]]), encode_dense([[2.0, 0.0], [0.0, 2.0]]))
    s = encode_dense_hermitian([[2.0, 0.1j], [-0.1j, 2.0]])
    cert = seal(dict(cert, claim=dict(cert["claim"], metric_ref=operator_ref(s))))
    (v,) = check_bundle([cert], [a_enc, s]).values()
    assert not v.ok and "metric operator kind" in v.reason, v.reason


def test_check_bundle_refuses_a_bundle_that_is_not_a_list():
    for junk in (None, 42, True):
        (v,) = check_bundle(junk, [OP]).values()
        assert not v.ok and "list" in v.reason


def test_cli_exit_status_tells_an_error_from_abstain(tmp_path, monkeypatch, capsys):
    c, o = tmp_path / "c.json", tmp_path / "o.json"
    c.write_text(json.dumps(CERT))
    o.write_text(json.dumps(OP))
    assert _cli("check", c, o).returncode == 0
    assert _cli("check", c).returncode == 2  # usage

    p = _cli("check", tmp_path / "missing.json", o)  # IO
    assert p.returncode == 2 and "FileNotFoundError" in p.stderr and not p.stdout

    # Unparseable is a malformed certificate, so ABSTAIN, not an error.
    for text in ("{not json", "[" * DEPTH + "]" * DEPTH):
        c.write_text(text)
        p = _cli("check", c, o)
        assert p.returncode == 1 and p.stdout.startswith("ABSTAIN   schema:"), p.stdout + p.stderr

    # Internal: anything that escapes is no verdict.
    import certkit.checker
    from certkit.cli import main

    def boom(*_):
        raise RuntimeError("boom")

    monkeypatch.setattr(certkit.checker, "check", boom)
    c.write_text(json.dumps(CERT))
    assert main(["check", str(c), str(o)]) == 2
    assert "RuntimeError: boom" in capsys.readouterr().err


def test_conformance_fails_a_checker_that_gives_no_verdict(tmp_path):
    def run(*checker):
        argv = [sys.executable, str(ROOT / "conformance" / "run.py")]
        if checker:
            argv += ["--checker", shlex.join(checker)]
        return subprocess.run(argv, capture_output=True, text=True, cwd=ROOT)

    cases = json.loads((ROOT / "conformance" / "manifest.json").read_text())["cases"]
    every_reason = " ".join(c.get("reason_contains", "") for c in cases)
    stub = tmp_path / "stub.py"
    # Each stub offers every pinned reason, so only the new rules can fail it:
    # exit 2 is no verdict, and a traceback on stderr is no reason. The second
    # also needs every ABSTAIN case to pin a reason, or a crash would pass it.
    for body in (f"print('ABSTAIN', {every_reason!r}); raise SystemExit(2)",
                 f"raise RuntimeError({every_reason!r})"):
        stub.write_text(body)
        p = run(sys.executable, str(stub))
        assert p.returncode == 1 and f"0/{len(cases)} cases passed" in p.stdout, p.stdout

    p = run()  # the real checker
    assert p.returncode == 0, p.stdout
