"""certkit-ph1 continuation: shift-invert Lanczos, the avenue the previous
session flagged as untried ("shift-invert Lanczos -- but that needs solving
(A - sigma I) x = b matrix-free ... which I have not derived").

Idea: use the existing matrix-free Gershgorin floor (rigorous, cheap, already
in certkit/producer.py) as sigma. Since sigma <= lam1 always (Gershgorin is a
true lower bound), A - sigma*I is positive semi-definite, so CG applies
safely without needing to know lam1 in advance. Build a Krylov subspace of
(A - sigma I)^-1 via CG solves (matrix-free, only op.apply-equivalent calls),
hoping the resulting subspace is a much better approximate invariant subspace
for the bottom of the spectrum than plain Lanczos, which would shrink
Variant A's block residual eps = ||AQ - QT||_2 (the quantity that did NOT
shrink with plain Lanczos, per certkit-ph1-lanczos-experiment.py and
certkit-ph1-gapped-experiment.py).

Scratch/untrusted numpy script. Not wired into certkit/ or pytest.
"""
import numpy as np
from certkit.producer import tfim_hamiltonian, _float_apply
from certkit.interval import Iv
from certkit.operators import decode_operator


def dense_matrix(enc):
    apply, n = _float_apply(enc)
    A = np.zeros((n, n))
    for i in range(n):
        e = np.zeros(n)
        e[i] = 1.0
        A[:, i] = apply(e)
    return A


def gershgorin_floor(enc):
    """Same computation as certify_lambda_min_matrixfree's floor, in plain
    float (untrusted, matches the trusted rule's arithmetic in spirit)."""
    op = decode_operator(enc)
    lower = float("inf")
    for i in range(op.n):
        entries = op.row(i)
        diag = entries.get(i, Iv.exact(0.0)).lo
        radius = sum(v.mag_ub for j, v in entries.items() if j != i)
        lower = min(lower, diag - radius)
    return lower


def cg_solve(A, b, x0=None, tol=1e-10, maxiter=2000):
    x = np.zeros_like(b) if x0 is None else x0.copy()
    r = b - A @ x
    p = r.copy()
    rs_old = r @ r
    for _ in range(maxiter):
        Ap = A @ p
        alpha = rs_old / (p @ Ap)
        x += alpha * p
        r -= alpha * Ap
        rs_new = r @ r
        if np.sqrt(rs_new) < tol * np.linalg.norm(b):
            break
        p = r + (rs_new / rs_old) * p
        rs_old = rs_new
    return x


def shift_invert_lanczos(A, sigma, n, k, seed=0):
    """Krylov subspace of (A - sigma I)^-1, built by CG solves (matrix-free
    in principle -- here using the dense A only because this is a numpy
    prototype; a real implementation would use op.apply inside CG's matvec).
    """
    Ashift = A - sigma * np.eye(n)
    rng = np.random.default_rng(seed)
    q = rng.standard_normal(n)
    q /= np.linalg.norm(q)
    Q = [q]
    for j in range(k - 1):
        w = cg_solve(Ashift, Q[-1])
        for v in Q:
            w -= (v @ w) * v
        b = np.linalg.norm(w)
        if b < 1e-12:
            break
        Q.append(w / b)
    return np.array(Q).T


for q_bits in (6, 8, 10):
    enc = tfim_hamiltonian(q_bits)
    A = dense_matrix(enc)
    n = A.shape[0]
    w_true = np.linalg.eigvalsh(A)
    lam1, lam2 = w_true[0], w_true[1]
    gap = lam2 - lam1
    sigma = gershgorin_floor(enc)
    print(f"--- q={q_bits} n={n} lam1={lam1:.4f} lam2={lam2:.4f} gap={gap:.4f} "
          f"gershgorin_sigma={sigma:.4f} (sigma<=lam1: {sigma <= lam1}) ---")
    for k in (5, 10, 20, min(40, n - 1)):
        Q = shift_invert_lanczos(A, sigma, n, k)
        m = Q.shape[1]
        T = Q.T @ A @ Q
        R = A @ Q - Q @ T
        eps_spec = np.linalg.norm(R, 2)
        theta = np.linalg.eigvalsh(T)
        theta1 = theta[0]
        print(f"  k={m:3d}  theta1={theta1:.6f}  eps_spec={eps_spec:.3e}  "
              f"eps/gap={eps_spec/gap:.3e}")
    print()
