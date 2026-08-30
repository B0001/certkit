"""
Scratch experiment for certkit-ph1 (session 5), resolving session 3/4's
flagged-but-unconfirmed FEAST/contour-integral soundness objection.

Claim to check: matrix-free contour-integral eigenvalue counting (FEAST,
Sakurai-Sugiura, and relatives) estimates the eigenvalue count in a window
as Tr(P) for a spectral projector P built from a contour integral of the
resolvent. Getting Tr(P) without O(n) resolvent solves (which would cost as
much as the O(n^3) dense route this bead exists to avoid) requires
*stochastic* trace estimation (Hutchinson-style: Tr(P) ~ (1/S) sum z_s^T P
z_s over S << n random probe vectors). This experiment demonstrates, for
the best possible case (P computed *exactly*, no contour-quadrature error
at all), that the stochastic estimator gives the WRONG integer count for a
non-negligible fraction of random seeds when S is small enough to be
matrix-free-cheap -- i.e. that "probably right" is the ceiling this
technique offers, not "certifiably right for this realization", which is
what an unconditional VERIFIED needs.

No numpy needed.
"""
import random

def hutchinson_trace_estimate(rank, n, S, rng):
    # P = diag(1,...,1 [rank times], 0,...,0) -- an EXACT idempotent
    # projector, the best case for the estimator (no numerical error in P
    # itself, only the stochastic estimation of its trace).
    total = 0.0
    for _ in range(S):
        z = [rng.choice([-1.0, 1.0]) for _ in range(n)]
        # z^T P z = sum of z_i^2 over the first `rank` coordinates = rank
        # exactly, for a diagonal 0/1 projector and any +-1 vector z.
        # To make this a genuine test of the ESTIMATOR (not a degenerate
        # case where diagonal P makes Rademacher probes exact), apply P in
        # a random orthonormal basis instead of the computational one.
        pass
    return total  # placeholder, real logic below

def random_orthonormal_basis(n, rng):
    # Gram-Schmidt on n random vectors -- pure Python, no numpy.
    vecs = []
    for _ in range(n):
        v = [rng.gauss(0, 1) for _ in range(n)]
        for u in vecs:
            dot = sum(a * b for a, b in zip(v, u))
            v = [a - dot * b for a, b in zip(v, u)]
        norm = sum(a * a for a in v) ** 0.5
        v = [a / norm for a in v]
        vecs.append(v)
    return vecs

def apply_projector(basis, rank, x):
    # P = sum_{i<rank} |e_i><e_i|, e_i = basis[i]
    out = [0.0] * len(x)
    for i in range(rank):
        e = basis[i]
        coeff = sum(a * b for a, b in zip(e, x))
        for k in range(len(x)):
            out[k] += coeff * e[k]
    return out

def trial(n, rank, S, master_seed):
    rng = random.Random(master_seed)
    basis = random_orthonormal_basis(n, rng)
    # exact trace is `rank`, by construction -- ground truth
    est_total = 0.0
    for _ in range(S):
        z = [rng.choice([-1.0, 1.0]) for _ in range(n)]
        pz = apply_projector(basis, rank, z)
        est_total += sum(a * b for a, b in zip(z, pz))
    return est_total / S

if __name__ == "__main__":
    n, rank = 50, 3
    for S in (5, 10, 20, 50):
        wrong = 0
        errs = []
        trials = 300
        for seed in range(trials):
            est = trial(n, rank, S, seed)
            errs.append(abs(est - rank))
            if round(est) != rank:
                wrong += 1
        max_err = max(errs)
        print(f"S={S:>3}  wrong-integer-count in {wrong}/{trials} seeds "
              f"({100*wrong/trials:.1f}%)  max|est-true|={max_err:.3f}")
