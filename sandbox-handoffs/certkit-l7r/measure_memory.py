"""Isolate the incremental memory of the dense route itself (tracemalloc),
separate from process/import baseline, which resource.getrusage's peak-RSS
conflates in measure.py."""
import json
import sys
import tracemalloc

sys.path.insert(0, "/workspace")

import certkit.operators as operators
operators.DENSE_LIMIT = 256

from certkit.checker import count_eigenvalues_below
from certkit.operators import decode_operator

with open("sandbox-handoffs/certkit-l7r/operator.json") as f:
    enc = json.load(f)
with open("sandbox-handoffs/certkit-l7r/truth.json") as f:
    truth = json.load(f)

op = decode_operator(enc)
beta = 0.5 * (truth["lam0"] + truth["lam1"])

tracemalloc.start()
rows = op.interval_rows()
snap1 = tracemalloc.take_snapshot()
count = count_eigenvalues_below(rows, beta)
snap2 = tracemalloc.take_snapshot()
current, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()

print(f"n={op.n} count={count}")
print(f"peak traced memory (interval_rows + one count_eigenvalues_below): {peak / 1e6:.2f} MB")
