"""certkit-ph1, session 3: Chebyshev-filtered subspace, the avenue session 2
explicitly flagged as untried and structurally different from both plain
Lanczos (session 1's Variant A) and shift-invert Lanczos (session 2).

Idea: instead of building Q from the dominant Krylov directions of A (which
inevitably captures direction from across the whole spectrum for an
extensive operator), build Q = span{p_m(A) r_i} for random r_i and a degree-m
Chebyshev polynomial p_m that is large on [lam_min, beta] and is suppressed
exponentially in m on [beta, lam_max]. If exponential suppression in the
"bad" eigendirections beats the growth of lam_max with system size, the
block residual eps = ||AQ - QT||_2 that Variant A's Weyl-counting argument
needs might shrink where plain/shift-invert Krylov could not -- this is a
genuinely different subspace, not another Krylov variant.

This is a numpy prototype for the arithmetic only (same discipline as
sessions 1-2's scratch scripts): not part of the trusted or test tree, not
wired into pytest, matrix built dense here purely so eps_spec/eigenvalues
can be computed exactly for diagnosis -- the actual filter application uses
only matrix-vector products (matvecs), matching what a matrix-free operator
would allow.
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


def gershgorin_bounds(A):
    """Matrix-free-representable: diag +/- sum(|off-diag|) per row."""
    d = np.diag(A)
    off = np.sum(np.abs(A), axis=1) - np.abs(d)
    return float(np.min(d - off)), float(np.max(d + off))


def chebyshev_filter_apply(matvec, v, m, lo, hi, target_hi):
    """p_m(A) v via the 3-term Chebyshev recurrence, matrix-free (matvec only).

    Maps [target_hi, hi] -> [-1, 1] (the interval to suppress) and evaluates
    T_m at the image of A. Eigenvalues below target_hi map to x < -1, where
    T_m(x) grows like cosh(m*arccosh(|x|)) -- amplified, not suppressed.
    """
    c = 0.5 * (hi + target_hi)
    e = 0.5 * (hi - target_hi)
    if e <= 0:
        return v
    def scaled_matvec(x):
        return (matvec(x) - c * x) / e
    t0 = v
    t1 = scaled_matvec(v)
    for _ in range(2, m + 1):
        t2 = 2 * scaled_matvec(t1) - t0
        t0, t1 = t1, t2
    return t1


def build_chebyshev_subspace(A, n, k, m, beta, lam_max_est, seed=0):
    rng = np.random.default_rng(seed)
    matvec = lambda x: A @ x
    cols = []
    for i in range(k):
        r = rng.standard_normal(n)
        r /= np.linalg.norm(r)
        filtered = chebyshev_filter_apply(matvec, r, m, None, lam_max_est, beta)
        cols.append(filtered)
    Q0 = np.array(cols).T
    Q, _ = np.linalg.qr(Q0)
    return Q


def run(q_bits, field=1.0, coupling=1.0, k_list=(4, 8, 16), m_list=(5, 20, 80, 320)):
    enc = tfim_hamiltonian(q_bits, field=field, coupling=coupling)
    A = dense_matrix(enc)
    n = A.shape[0]
    w_true = np.linalg.eigvalsh(A)
    lam1, lam2 = w_true[0], w_true[1]
    gap = lam2 - lam1
    g_lo, g_hi = gershgorin_bounds(A)
    # beta must be a value strictly between lam1 and lam2 for the filter to
    # separate the target from the rest -- use the exact midpoint here (a
    # real matrix-free producer would need its own beta estimate, out of
    # scope for this residual-behavior experiment).
    beta = 0.5 * (lam1 + lam2)
    print(f"--- q={q_bits} field={field} n={n} lam1={lam1:.5f} lam2={lam2:.5f} "
          f"gap={gap:.4f} gershgorin=[{g_lo:.2f},{g_hi:.2f}]")
    for k in k_list:
        for m in m_list:
            Q = build_chebyshev_subspace(A, n, k, m, beta, g_hi, seed=0)
            kk = Q.shape[1]
            T = Q.T @ A @ Q
            R = A @ Q - Q @ T
            eps_spec = np.linalg.norm(R, 2)
            theta = np.linalg.eigvalsh(T)
            theta1 = theta[0]
            print(f"  k={k:2d} m={m:4d}: eps_spec={eps_spec:.3e}  eps/gap={eps_spec/gap:.3e}  "
                  f"theta1={theta1:.6f} (lam1 err={abs(theta1-lam1):.2e})  "
                  f"disjoint_needed(eps<gap/2)={eps_spec < gap/2}")
    print()


if __name__ == "__main__":
    print("=== critical TFIM, varying k and Chebyshev degree m ===")
    run(8, field=1.0)
    run(10, field=1.0, k_list=(4, 8, 16), m_list=(5, 20, 80, 320, 1000))

    print("=== deep paramagnetic TFIM (large physical gap) ===")
    run(10, field=8.0, k_list=(4, 8, 16), m_list=(5, 20, 80, 320))
