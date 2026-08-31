"""Does RCM's LOCAL exponent keep climbing past q=12, or plateau below 2.9?

Claim under test: rcm x {hypercube_tfim, chain_1d_nn} fitted 2.82/2.84 globally
only because convergence to 3 is from below and pre-asymptotic. If the local
exponent log2(ops(q+1)/ops(q)) keeps rising toward 3, the claim holds; if it
plateaus below ~2.9, there may be a real sub-cubic effect.

Uses the bitset eliminator (_amb_fastelim), which reproduces
harness.eliminate_with_perm exactly (see that file's self-check), because the
set-based harness cannot reach q=14 in reasonable time.
Recorded q<=12 numbers are re-derived here and compared to sweep.json/amb.json.
"""
import json
import math
import sys
import time

import families
import ord_rcm
from _amb_fastelim import eliminate_bits

MAXQ = int(sys.argv[1]) if len(sys.argv) > 1 else 14
FAMS = ("hypercube_tfim", "chain_1d_nn")

recorded = {}
for f in ("sweep.json", "amb.json"):
    for r in json.load(open(f)):
        if r["ordering"] == "rcm" and "ops" in r:
            recorded[(r["family"], r["q"])] = r["ops"]

for fam in FAMS:
    print(f"=== rcm x {fam} ===")
    print(f"{'q':>3} {'n':>7} {'ops':>16} {'recorded':>16} {'match':>6} "
          f"{'ops/n^3':>9} {'ops*log2n/n^3':>14} {'local alpha':>12} "
          f"{'ratio':>7} {'q/(q+1)':>8} {'secs':>7}")
    prev = None
    for q in range(6, MAXQ + 1):
        n, masks = families.FAMILIES[fam](q)
        t0 = time.time()
        perm = ord_rcm.order(n, masks, time_budget_s=100000.0)
        assert sorted(perm) == list(range(n))
        fill, ops, maxd, done, steps = eliminate_bits(n, masks, perm)
        secs = time.time() - t0
        rec = recorded.get((fam, q))
        match = "-" if rec is None else ("YES" if rec == ops else "MISMATCH")
        loc = rat = ""
        if prev is not None:
            loc = f"{math.log2(ops / prev[1]) / math.log2(n / prev[0]):.3f}"
            rat = f"{(ops / n**3) / (prev[1] / prev[0]**3):.3f}"
        print(f"{q:>3} {n:>7} {ops:>16} {str(rec):>16} {match:>6} "
              f"{ops / n**3:>9.5f} {ops * math.log2(n) / n**3:>14.4f} {loc:>12} "
              f"{rat:>7} {(q - 1) / q if prev else '':>8} {secs:>7.1f}")
        sys.stdout.flush()
        prev = (n, ops)
    print()
