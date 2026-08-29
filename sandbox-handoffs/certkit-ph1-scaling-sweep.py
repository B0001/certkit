"""certkit-ph1, session 3, part 2: what fraction k/n does a Krylov subspace
need before the block residual eps=||AQ-QT||_2 (the quantity Variant A's
Weyl-counting argument needs below gap/2) actually crosses that threshold?

Sessions 1-2 tested k up to 80 against n up to 4096 and found eps/gap stuck
at O(1)-O(10) throughout -- correctly negative, but that leaves open whether
some k still << n (just bigger than 80) would eventually work, which matters
because the acceptance criterion is "without an O(n^3) dense factorisation":
if the needed k turned out to be, say, O(sqrt(n)) or O(log n), the subspace
route would still beat the dense route asymptotically even though k=80
wasn't enough. This sweeps k as a *fraction* of n, up to k/n=0.95, to see
where (if anywhere) the crossover happens.

Numpy prototype, same discipline as prior sessions' scratch scripts: not
part of the trusted or test tree.
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
    """Lanczos with full reorthogonalization (needed for k approaching n)."""
    rng = np.random.default_rng(seed)
    q = rng.standard_normal(n)
    q /= np.linalg.norm(q)
    Q = [q]
    for _ in range(k - 1):
        w = A @ Q[-1]
        for v in Q:
            w -= (v @ w) * v
        b = np.linalg.norm(w)
        if b < 1e-13:
            break
        Q.append(w / b)
        Q[-1] -= sum((v @ Q[-1]) * v for v in Q[:-1])
        Q[-1] /= np.linalg.norm(Q[-1])
    return np.array(Q).T


def sweep(qbits, field, fracs=(0.03, 0.06, 0.12, 0.25, 0.5, 0.75, 0.9, 0.95)):
    enc = tfim_hamiltonian(qbits, field=field)
    A = dense_matrix(enc)
    n = A.shape[0]
    w_true = np.linalg.eigvalsh(A)
    lam1, lam2 = w_true[0], w_true[1]
    gap = lam2 - lam1
    print(f"--- n={n} field={field} lam1={lam1:.5f} gap={gap:.4f} ---")
    crossed_at = None
    for frac in fracs:
        k = max(2, int(frac * n))
        Q = lanczos_full(A, n, k)
        T = Q.T @ A @ Q
        R = A @ Q - Q @ T
        eps = np.linalg.norm(R, 2)
        ok = eps < gap / 2
        if ok and crossed_at is None:
            crossed_at = frac
        print(f"  k/n={frac:.2f} (k={k:4d}): eps_spec={eps:.4e}  eps/gap={eps/gap:.3e}  "
              f"disjoint_needed(eps<gap/2)={ok}")
    print(f"  => needed k/n to cross threshold: {crossed_at if crossed_at else '>0.95 (not reached)'}")
    print()


if __name__ == "__main__":
    print("=== critical TFIM (field=1.0), n=64 and n=256: does the crossover fraction shrink with n? ===")
    sweep(6, 1.0)
    sweep(8, 1.0)
    print("=== critical TFIM, n=1024: does it get better or worse? ===")
    sweep(10, 1.0, fracs=(0.5, 0.75, 0.9, 0.95))
    print("=== deep-paramagnetic TFIM (field=8.0, large physical gap), n=256: best case for this method ===")
    sweep(8, 8.0)
