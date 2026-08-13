"""Command line: `produce` (untrusted) and `check` (trusted).

The two subcommands are deliberately separable -- `check` needs neither
numpy nor the producer module, so it can be shipped and audited alone.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _cmd_produce(args: argparse.Namespace) -> int:
    import numpy as np

    from .producer import (
        certify_bounds_composed,
        certify_lambda_min,
        certify_lambda_min_backward,
        certify_lambda_min_banded,
        certify_lambda_min_composed,
        certify_lambda_min_matrixfree,
        certify_spectrum_point,
        schrodinger_1d,
        tfim_hamiltonian,
    )

    if args.schrodinger:
        operator = schrodinger_1d(args.schrodinger)
    elif args.tfim:
        operator = tfim_hamiltonian(args.tfim, field=args.field)
    elif args.matrix:
        operator = json.loads(Path(args.matrix).read_text())
    else:
        rng = np.random.default_rng(args.seed)
        m = rng.standard_normal((args.n, args.n))
        operator = ((m + m.T) / 2.0).tolist()

    composed = {
        "temple_ref": certify_lambda_min_composed,
        "temple_sturm": certify_lambda_min_banded,
        "temple_be": certify_lambda_min_backward,
        "combine": certify_bounds_composed,
    }
    simple = {
        "temple_inertia": certify_lambda_min,
        "gershgorin_rayleigh": certify_lambda_min_matrixfree,
        "residual": certify_spectrum_point,
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.rule in composed:
        certs, ops = composed[args.rule](operator)
        (out / "certificate.json").write_text(json.dumps(certs, indent=2))
        (out / "operator.json").write_text(json.dumps(ops[0], indent=2))
        print(f"wrote a {len(certs)}-certificate bundle to {out/'certificate.json'}")
    else:
        cert, op = simple[args.rule](operator)
        (out / "certificate.json").write_text(json.dumps(cert, indent=2))
        (out / "operator.json").write_text(json.dumps(op, indent=2))
        print(f"wrote {out/'certificate.json'} and {out/'operator.json'}")
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    from .checker import bundle_verdict, check, check_bundle

    cert = json.loads(Path(args.certificate).read_text())
    op = json.loads(Path(args.operator).read_text())

    if isinstance(cert, list):
        results = check_bundle(cert, [op])
        for h, v in results.items():
            print(f"  {h[:20]:<22} {v}")
        verdict = bundle_verdict(results)
        print(verdict)
    else:
        verdict = check(cert, op)
        print(verdict)

    if verdict.rederived and args.verbose:
        print(f"  re-derived: [{verdict.rederived[0]!r}, {verdict.rederived[1]!r}]")
    return 0 if verdict.ok else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="certkit")
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("produce", help="emit a certificate (untrusted side)")
    pp.add_argument(
        "--matrix",
        help="JSON file: either a square matrix of numbers or an operator encoding",
    )
    pp.add_argument(
        "--tfim", type=int, metavar="QUBITS",
        help="use a transverse-field Ising Hamiltonian on this many qubits",
    )
    pp.add_argument("--field", type=float, default=1.0, help="TFIM transverse field")
    pp.add_argument(
        "--schrodinger", type=int, metavar="N",
        help="use a discrete 1D Schrodinger operator of this dimension",
    )
    pp.add_argument("--n", type=int, default=8, help="size of a random test matrix")
    pp.add_argument("--seed", type=int, default=0)
    pp.add_argument(
        "--rule",
        choices=[
            "temple_inertia", "gershgorin_rayleigh", "residual",
            "temple_ref", "temple_sturm", "temple_be", "combine",
        ],
        default="temple_inertia",
    )
    pp.add_argument("--out", default="out")
    pp.set_defaults(func=_cmd_produce)

    cp = sub.add_parser("check", help="verify a certificate (trusted side)")
    cp.add_argument("certificate")
    cp.add_argument("operator")
    cp.add_argument("-v", "--verbose", action="store_true")
    cp.set_defaults(func=_cmd_check)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
