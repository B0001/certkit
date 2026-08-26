"""certkit-ph1 continuation: does Variant A's global residual eps shrink faster
for a genuinely gapped, low-entanglement Hamiltonian than it did for critical
TFIM?

Scratch/untrusted numpy script. Not wired into certkit/ or pytest. Reuses the
Variant A construction from certkit-ph1-lanczos-experiment.py (same repo,
same session lineage) but sweeps the TFIM field/coupling ratio through the
paramagnetic (h >> J, gapped, near-product ground state), critical (h = J),
and ferromagnetic (h << J, near-degenerate doublet -- expected to be the
worst case) regimes, at fixed q so lam1/lam2/gap are directly comparable.
"""
import numpy as np
from certkit.producer import tfim_hamiltonian, _float_apply


def dense_matrix(enc):
    apply, n = _float_apply(enc)
    A = np.zeros((n, n))
    for i in range(n):
        e = np.zeros(n)
        e[i] = 1.0
        A[:, i] = apply(e)
    return A


def lanczos_full(A, n, k, seed=0):
    rng = np.random.default_rng(seed)
    q = rng.standard_normal(n)
    q /= np.linalg.norm(q)
    Q = [q]
    for j in range(k - 1):
        w = A @ Q[-1]
        for v in Q:
            w -= (v @ w) * v
        b = np.linalg.norm(w)
        if b < 1e-13:
            break
        Q.append(w / b)
    return np.array(Q).T


q_bits = 10
for field, label in ((0.3, "ferromagnetic h<<J"), (1.0, "critical h=J"),
                     (3.0, "paramagnetic h>>J"), (8.0, "deep paramagnetic h>>J")):
    enc = tfim_hamiltonian(q_bits, field=field, coupling=1.0)
    A = dense_matrix(enc)
    n = A.shape[0]
    w_true = np.linalg.eigvalsh(A)
    lam1, lam2 = w_true[0], w_true[1]
    gap = lam2 - lam1
    print(f"--- field={field} ({label}) n={n} lam1={lam1:.4f} lam2={lam2:.4f} gap={gap:.4f} ---")
    for k in (10, 20, 40, 80):
        if k >= n:
            continue
        Q = lanczos_full(A, n, k)
        m = Q.shape[1]
        T = Q.T @ A @ Q
        R = A @ Q - Q @ T
        eps_spec = np.linalg.norm(R, 2)
        theta = np.linalg.eigvalsh(T)
        theta1 = theta[0]
        print(f"  k={m:3d}  theta1={theta1:.6f}  eps_spec={eps_spec:.3e}  "
              f"eps/gap={eps_spec/gap:.3e}  (need eps < gap/2 to ever certify)")
    print()
