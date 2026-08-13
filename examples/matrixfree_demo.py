"""Two sound routes, one tradeoff.

`temple_inertia` is tight but needs a spectral gap and an O(n^3) factorisation.
`gershgorin_rayleigh` needs neither and works on operators that are never
materialised -- at the cost of a much wider interval.

The table below is the useful artifact: at every size, whichever route reports
VERIFIED gives an enclosure that really does contain the ground state energy.
Where the tight route stops applying, it says so instead of degrading.
"""

from __future__ import annotations

import time

import numpy as np

from certkit.checker import check
from certkit.operators import decode_operator
from certkit.producer import (
    certify_lambda_min,
    certify_lambda_min_matrixfree,
    tfim_hamiltonian,
)

PAULI = {
    "I": np.eye(2, dtype=complex),
    "X": np.array([[0, 1], [1, 0]], dtype=complex),
    "Z": np.diag([1, -1]).astype(complex),
}


def true_ground_energy(enc: dict) -> float:
    q = enc["qubits"]
    m = np.zeros((2**q, 2**q), dtype=complex)
    for t in enc["terms"]:
        c, s = float.fromhex(t["coeff"]), t["string"]
        op = np.array([[1]], dtype=complex)
        for k in range(q):
            op = np.kron(PAULI[s[k]], op)
        m += c * op
    return float(np.linalg.eigvalsh(m.real)[0])


def main() -> None:
    print("Transverse-field Ising ground state, h = J = 1\n")
    header = f"{'qubits':>7} {'dim':>6}  {'route':>20}  {'width':>10}  {'sound':>6}  {'s':>5}"
    print(header)
    print("-" * len(header))

    for q in (4, 6, 8, 10, 11):
        enc = tfim_hamiltonian(q)
        truth = true_ground_energy(enc)
        for label, fn in (
            ("temple_inertia", certify_lambda_min),
            ("gershgorin_rayleigh", certify_lambda_min_matrixfree),
        ):
            t0 = time.time()
            v = check(*fn(enc))
            dt = time.time() - t0
            if v.ok:
                lo, hi = v.rederived
                sound = "yes" if lo <= truth <= hi else "NO"
                print(f"{q:>7} {1 << q:>6}  {label:>20}  {v.width:>10.2e}  {sound:>6}  {dt:>5.1f}")
            else:
                short = "no gap route" if "materialise" in v.reason else "abstain"
                print(f"{q:>7} {1 << q:>6}  {label:>20}  {short:>10}  {'--':>6}  {dt:>5.1f}")
        print()

    n = decode_operator(tfim_hamiltonian(11)).n
    print(
        f"At {n} dimensions the Hamiltonian is never built: the checker only ever\n"
        "applies it and reads its rows, both straight from the Pauli terms."
    )


if __name__ == "__main__":
    main()
