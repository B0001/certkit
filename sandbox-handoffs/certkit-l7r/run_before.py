"""Run the H4-shaped n=256 case against the *unmodified* certkit
(DENSE_LIMIT=160) to record the baseline verdict before touching anything."""
import json
import os
import sys
import time

sys.path.insert(0, "/workspace")

from certkit.checker import check
from certkit.operators import DENSE_LIMIT
from certkit.producer import certify_lambda_min

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "operator.json")) as f:
    enc = json.load(f)
with open(os.path.join(HERE, "truth.json")) as f:
    truth = json.load(f)

print(f"DENSE_LIMIT = {DENSE_LIMIT}")
print(f"operator n = {1 << enc['qubits']}, true gap = {truth['gap']:.6e}")

t0 = time.time()
cert, op_enc = certify_lambda_min(enc)
v = check(cert, op_enc)
dt = time.time() - t0

print(f"verdict: {'VERIFIED' if v.ok else 'ABSTAIN'}  rule={v.rule}  time={dt:.2f}s")
if not v.ok:
    print(f"reason: {v.reason}")
else:
    print(f"enclosure: {v.rederived}  width={v.width:.3e}")
