#!/usr/bin/env python3
"""certkit conformance suite -- run this against your pinned certkit.

Frozen certificates with expected verdicts. Each case is checked the way the
integration contract says a consumer checks: out of process, over files, via
`certkit check`. Nothing here imports certkit, so a consumer runs it against
whatever release they pin without matching this repo's environment.

    python conformance/run.py                  # uses `python -m certkit.cli`
    python conformance/run.py --checker certkit

Exit status is 0 only if every case matches its expected verdict. A VERIFIED
case that abstains means the pinned checker got stricter or broke; an ABSTAIN
case that verifies means it lost a safety property. Both are release-blocking.
"""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run_case(checker: list[str], case: dict) -> tuple[bool, str]:
    d = ROOT / "cases" / case["name"]
    proc = subprocess.run(
        [*checker, "check", str(d / "certificate.json"), str(d / "operator.json")],
        capture_output=True, text=True,
    )
    got = "VERIFIED" if proc.returncode == 0 else "ABSTAIN"
    output = (proc.stdout + proc.stderr).strip()

    if got != case["expect"]:
        return False, f"expected {case['expect']}, got {got}: {output.splitlines()[0] if output else '(no output)'}"
    # A case may pin *why* it was refused, so a right answer for a wrong reason still fails.
    want = case.get("reason_contains")
    if want and want.lower() not in output.lower():
        return False, f"{got} as expected, but reason did not mention {want!r}: {output.splitlines()[0] if output else '(no output)'}"
    return True, got


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--checker", default=f"{shlex.quote(sys.executable)} -m certkit.cli",
                    help="command that runs the checker (default: this interpreter's certkit.cli)")
    args = ap.parse_args()
    checker = shlex.split(args.checker)

    manifest = json.loads((ROOT / "manifest.json").read_text())
    cases = manifest["cases"]
    failures = []
    for case in cases:
        ok, detail = run_case(checker, case)
        print(f"  {'pass' if ok else 'FAIL'}  {case['name']:<32} {detail}")
        if not ok:
            failures.append(case["name"])

    print(f"\n{len(cases) - len(failures)}/{len(cases)} cases passed"
          f" against schema {manifest['schema']}")
    if failures:
        print("failed: " + ", ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
