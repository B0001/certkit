"""Composition: a certificate may discharge a hypothesis by reference.

Two bundles are built below. The first splits the Temple bound into a
standalone eigenvalue-count certificate plus a Temple node that references it.
The second sandwiches an independent Gershgorin floor and Rayleigh ceiling with
a `combine` node that performs no arithmetic of its own.

Then the count certificate is made to lie, and the bundle is re-checked. The
useful thing to watch is that the dependent does not degrade, hedge, or report
a wider interval -- it stops answering.
"""

from __future__ import annotations

import copy

import numpy as np

from certkit.checker import bundle_verdict, check_bundle
from certkit.producer import (
    certify_bounds_composed,
    certify_lambda_min_composed,
)
from certkit.schema import seal


def show(title: str, certs, ops) -> None:
    print(title)
    results = check_bundle(certs, ops)
    for h, v in results.items():
        print(f"  {h[:18]:<20} {v}")
    print(f"  root: {bundle_verdict(results)}\n")


def main() -> None:
    rng = np.random.default_rng(7)
    m = rng.standard_normal((8, 8))
    rows = ((m + m.T) / 2).tolist()
    truth = float(np.linalg.eigvalsh(np.array(rows))[0])
    print(f"true ground eigenvalue: {truth!r}\n")

    certs, ops = certify_lambda_min_composed(rows)
    show("Temple, with the gap split out into its own certificate:", certs, ops)

    show("Gershgorin floor + Rayleigh ceiling, joined by a derivation node:",
         *certify_bounds_composed(rows))

    # Now corrupt the dependency: claim a gap the matrix does not have.
    count_cert, temple = copy.deepcopy(certs)
    count_cert["claim"]["count"] = 2
    count_cert = seal(count_cert)
    temple["witness"]["gap_ref"] = count_cert["content_hash"]
    temple = seal(temple)
    show("The same bundle, with the count certificate made to lie:",
         [count_cert, temple], ops)

    print(
        "The Temple node is untouched and its arithmetic is still correct. It\n"
        "abstains because the thing it leaned on stopped holding -- which is the\n"
        "only behaviour that makes references safe to use."
    )


if __name__ == "__main__":
    main()
