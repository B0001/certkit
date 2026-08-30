"""
Scratch experiment for certkit-ph1 (session 5).

Checks a question none of the prior 4 sessions asked directly: the repo
already has an O(n*b^2) counting route (`sturm`/`sturm_be`, via
`certkit.banded.band_structure`) that works on ANY `Operator`, including
matrix-free `PauliSumReal` -- so why doesn't it already close this bead?

Answer, verified below against the repo's own trusted `certkit.banded`
module (stdlib-only, safe to run directly) and its own sample fixture
(`examples/sample/pauli_operator.json`, an 11-qubit nearest-neighbor
TFIM-shaped Hamiltonian -- physically local): the bandwidth in
*computational-basis index space* of a single-qubit Pauli term on qubit k
is exactly 2^k (a bit-flip mask), not the qubit's distance to its physical
neighbors. `MAX_BANDWIDTH=64` is already exceeded by any term touching a
qubit at bit-position >= 6, and reordering qubits does not fix this: it only
decides *which* physical qubit lands on a high bit, and any Hamiltonian
where every qubit carries some term (true of essentially all physical
multi-qubit Hamiltonians) guarantees whichever qubit ends up on the top bit
contributes bandwidth ~n/2 regardless of how "local" the original problem
is. This is a structural mismatch between qubit-graph locality and
basis-index locality, not a fixable implementation gap.

Run from the repo root: `uv run python sandbox-handoffs/certkit-ph1-bandwidth-check-experiment.py`
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from certkit.banded import band_structure
from certkit.interval import IntervalError
from certkit.operators import PauliSumReal, decode_operator

REPO_ROOT = Path(__file__).resolve().parents[1]

with open(REPO_ROOT / "examples/sample/pauli_operator.json") as f:
    obj = json.load(f)
op = decode_operator(obj)
print("qubits:", op.qubits, "n:", op.n, "num terms:", len(op.terms))

rows, bw = band_structure(op, max_bandwidth=10**9)
print("actual bandwidth (unbounded probe):", bw)

try:
    band_structure(op)
    print("fits default MAX_BANDWIDTH=64")
except IntervalError as e:
    print("default MAX_BANDWIDTH=64 rejects:", e)

print()
print("mechanism: single-qubit X term on qubit k -> row(0) nonzero column")
for k in range(12):
    s = "I" * k + "X" + "I" * (11 - k)
    test = PauliSumReal(12, [(1.0, s)])
    row0 = test.row(0)
    print(f"  qubit {k}: columns {list(row0.keys())}  (bandwidth {2**k})")
