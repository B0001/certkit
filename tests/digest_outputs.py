#!/usr/bin/env python3
"""Cross-architecture digest of certkit checker output on the conformance cases.

    python digest_outputs.py [REPO_ROOT] [--dump]

REPO_ROOT defaults to the current directory. For each case in
conformance/manifest.json this captures:

  1. the CLI, invoked out of process exactly as conformance/run.py does
     (`<python> -m certkit.cli check certificate.json operator.json`), plus -v so
     the re-derived bounds are printed: exit code, stdout, stderr;
  2. the full in-process Verdict(s) from certkit.checker (check / check_bundle,
     mirroring cli._cmd_check), every field, every float as float.hex().

The CLI runs with cwd = the case directory and relative filenames, and the
repo root is replaced by <ROOT> in its output, so no machine path reaches the
digest. Each case is run twice and any difference is reported as NONDETERMINISTIC.
Prints `<case> <sha256>` per case, then `OVERALL <sha256>` over those lines.
--dump also prints each raw blob so two machines' outputs can be diffed.
"""
import dataclasses
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def canon(o):
    if isinstance(o, float):
        return o.hex()
    if isinstance(o, (list, tuple)):
        return [canon(x) for x in o]
    if isinstance(o, dict):
        return {str(k): canon(v) for k, v in o.items()}
    return o


def in_process(case_dir):
    from certkit.checker import bundle_verdict, check, check_bundle

    try:
        cert = json.loads((case_dir / "certificate.json").read_text())
        op = json.loads((case_dir / "operator.json").read_text())
        if isinstance(cert, list):
            results = check_bundle(cert, [op])
            out = {"bundle": {h: dataclasses.asdict(v) for h, v in results.items()},
                   "verdict": dataclasses.asdict(bundle_verdict(results))}
        else:
            out = {"verdict": dataclasses.asdict(check(cert, op))}
    except Exception as e:  # recorded, not hidden: an exception is itself output
        out = {"exception": f"{type(e).__name__}: {e}"}
    return json.dumps(canon(out), sort_keys=True, separators=(",", ":"))


def cli(root, case_dir):
    env = dict(os.environ, PYTHONPATH=str(root), PYTHONHASHSEED="0")
    p = subprocess.run(
        [sys.executable, "-m", "certkit.cli", "check", "certificate.json", "operator.json", "-v"],
        cwd=case_dir, env=env, capture_output=True, text=True,
    )
    scrub = lambda s: s.replace(str(root), "<ROOT>")
    return f"exit={p.returncode}\n--stdout--\n{scrub(p.stdout)}--stderr--\n{scrub(p.stderr)}"


def blob(root, case_dir):
    return f"== cli ==\n{cli(root, case_dir)}\n== verdict ==\n{in_process(case_dir)}\n"


def main():
    args = [a for a in sys.argv[1:] if a != "--dump"]
    dump = "--dump" in sys.argv[1:]
    root = Path(args[0] if args else ".").resolve()
    sys.path.insert(0, str(root))
    manifest = json.loads((root / "conformance" / "manifest.json").read_text())
    lines, bad = [], 0
    for case in manifest["cases"]:
        d = root / "conformance" / "cases" / case["name"]
        b1, b2 = blob(root, d), blob(root, d)
        if b1 != b2:
            bad += 1
            print(f"NONDETERMINISTIC {case['name']}")
        if dump:
            print(f"----- {case['name']} -----\n{b1}", end="")
        lines.append(f"{case['name']} {hashlib.sha256(b1.encode()).hexdigest()}")
    if dump:
        print("----- digests -----")
    print("\n".join(lines))
    print("OVERALL " + hashlib.sha256(("\n".join(lines) + "\n").encode()).hexdigest())
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
