"""Measure runtime + memory for the dense (existing) inertia route at n=256,
on the H4-shaped JW-two-body operator, for both a single beta and a
several-beta workload (the bead's acceptance criteria explicitly calls out
"not just one beta"). Patches certkit.operators.DENSE_LIMIT in-process (not
the source file) so this script can be re-run standalone to reproduce the
numbers quoted in the handoff.
"""
import json
import resource
import sys
import time

sys.path.insert(0, "/workspace")

import certkit.operators as operators
operators.DENSE_LIMIT = 256

from certkit.checker import check, count_eigenvalues_below
from certkit.operators import decode_operator
from certkit.producer import certify_lambda_min

with open("sandbox-handoffs/certkit-l7r/operator.json") as f:
    enc = json.load(f)
with open("sandbox-handoffs/certkit-l7r/truth.json") as f:
    truth = json.load(f)

op = decode_operator(enc)
print(f"n = {op.n}, DENSE_LIMIT patched to {operators.DENSE_LIMIT}")

# -- single-beta end-to-end verification, via the real producer/checker path
t0 = time.time()
cert, op_enc = certify_lambda_min(enc)
v = check(cert, op_enc)
dt_single = time.time() - t0
rss_after_single = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0  # MB on Linux

print(f"\nsingle-beta certify+check: verdict={'VERIFIED' if v.ok else 'ABSTAIN'} "
      f"rule={v.rule} time={dt_single:.2f}s peak_rss={rss_after_single:.1f}MB")
if v.ok:
    lo, hi = v.rederived
    print(f"  enclosure=[{lo!r}, {hi!r}]  width={v.width:.3e}")
    print(f"  sound: {lo <= truth['lam0'] <= hi}  (true lambda_0={truth['lam0']!r})")
    print(f"  width vs 1.6e-3 chemical accuracy: {v.width / 1.6e-3:.3e}x")

# -- several-beta workload: count_eigenvalues_below directly, at 12 betas
# spanning the low end of the spectrum (mirrors certkit-cpo's "12 betas each"
# measurement style, and the bead's explicit "not just one beta" ask).
rows = op.interval_rows()
assert rows is not None, "DENSE_LIMIT patch did not take effect"

betas = [truth["lam0"] + k * (truth["lam1"] - truth["lam0"]) / 11 for k in range(12)]
t0 = time.time()
counts = []
for b in betas:
    try:
        counts.append(count_eigenvalues_below(rows, b))
    except Exception as e:  # pivot straddle -> abstain, honest outcome
        counts.append(f"ABSTAIN({e})")
dt_batch = time.time() - t0
rss_after_batch = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0

print(f"\n12-beta count_eigenvalues_below batch: total_time={dt_batch:.2f}s "
      f"({dt_batch/12:.3f}s/beta)  peak_rss={rss_after_batch:.1f}MB")
print(f"  counts: {counts}")
