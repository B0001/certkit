import numpy as np
from certkit.producer import tfim_hamiltonian, _float_apply
from certkit.operators import decode_operator

def dense_matrix(enc):
    apply, n = _float_apply(enc)
    A = np.zeros((n, n))
    for i in range(n):
        e = np.zeros(n); e[i] = 1.0
        A[:, i] = apply(e)
    return A

def lanczos_full(A, n, k, seed=0):
    rng = np.random.default_rng(seed)
    q = rng.standard_normal(n); q /= np.linalg.norm(q)
    Q = [q]
    for j in range(k - 1):
        w = A @ Q[-1]
        for v in Q:
            w -= (v @ w) * v
        b = np.linalg.norm(w)
        if b < 1e-13:
            break
        Q.append(w / b)
    return np.array(Q).T  # n x m

for q_bits in (6, 8, 10):
    enc = tfim_hamiltonian(q_bits)
    A = dense_matrix(enc)
    n = A.shape[0]
    w_true = np.linalg.eigvalsh(A)
    lam1, lam2 = w_true[0], w_true[1]

    for k in (10, 20, 40, min(80, n)):
        Q = lanczos_full(A, n, k)
        m = Q.shape[1]
        G = Q.T @ Q
        T = Q.T @ A @ Q
        R = A @ Q - Q @ T
        eps_spec = np.linalg.norm(R, 2)
        eps_fro = np.linalg.norm(R, 'fro')
        delta_gram = np.linalg.norm(G - np.eye(m), 2)
        theta = np.linalg.eigvalsh(T)
        theta1, theta2 = theta[0], theta[1] if m > 1 else theta[0] + 1

        beta = theta1 + eps_spec
        gap_ok = beta < theta2 - eps_spec
        # true check
        n_below_beta = int((w_true < beta).sum())
        print(f"q={q_bits} n={n} k={m}: theta1={theta1:.6f} lam1={lam1:.6f} "
              f"eps_spec={eps_spec:.3e} eps_fro={eps_fro:.3e} delta_gram={delta_gram:.2e} "
              f"beta={beta:.6f} gap_disjoint={gap_ok} true_count_below_beta={n_below_beta} "
              f"lam2-beta={lam2-beta:.3e}")
    print()

print("=== per-Ritz-pair residuals (not matrix norm) ===")
for q_bits in (6, 8, 10):
    enc = tfim_hamiltonian(q_bits)
    A = dense_matrix(enc)
    n = A.shape[0]
    w_true = np.linalg.eigvalsh(A)
    lam1, lam2 = w_true[0], w_true[1]
    for k in (10, 20, 40):
        Q = lanczos_full(A, n, k)
        m = Q.shape[1]
        T = Q.T @ A @ Q
        theta, S = np.linalg.eigh(T)
        theta1, theta2 = theta[0], theta[1]
        y1 = Q @ S[:, 0]; y2 = Q @ S[:, 1]
        rho1 = np.linalg.norm(A @ y1 - theta1 * y1)
        rho2 = np.linalg.norm(A @ y2 - theta2 * y2)
        beta = theta1 + rho1
        disjoint = (theta1 + rho1) < (theta2 - rho2)
        n_below = int((w_true < beta).sum())
        print(f"q={q_bits} k={m}: theta1={theta1:.5f} rho1={rho1:.2e} theta2={theta2:.5f} rho2={rho2:.2e} "
              f"disjoint={disjoint} beta={beta:.5f} true_count_below_beta={n_below} lam2={lam2:.5f}")
    print()
