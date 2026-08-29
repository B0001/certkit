"""certkit-ph1, session 4: adaptive matrix-vector query lower bound for exact
eigenvalue counting -- concrete, checkable construction (not just prose).

Sessions 1-3 tried three concrete subspace-based counting methods (plain
Lanczos, shift-invert Lanczos, Chebyshev-filtered subspace) and found, purely
empirically, that all three need the Krylov/subspace dimension k to be a large
constant fraction of n before the global block-residual crosses the threshold
a Weyl-counting argument needs. Session 3 explicitly flagged, as the top
priority next step, constructing an ADVERSARIAL argument for why k = Omega(n)
is *necessary*, not just what those three constructions happen to need.

This script builds and checks that argument in its simplest (non-adaptive)
form: an explicit pair of symmetric operators A0, A1 that

  (a) give IDENTICAL responses to any fixed set of k matrix-vector query
      vectors (k < n), yet
  (b) have DIFFERENT counts of eigenvalues below a chosen beta (1 vs 2),

which means no deterministic function of those k query responses -- i.e. no
algorithm that treats the operator purely as a matrix-vector-product oracle,
which is exactly what op.apply() gives every producer/checker rule in this
kit -- can correctly output "exactly 1 eigenvalue below beta" for both. One of
the two outputs must be wrong. This is not a claim that k=Omega(n) is needed
for every specific realistic Hamiltonian (session 1-3 already measured that,
empirically, on TFIM); it is a claim that WORST-CASE hardness genuinely holds
for this entire query model, independent of which of the three subspace
constructions is used.

Not part of the trusted or test tree. Throwaway numpy prototype, same
discipline as the four scratch scripts from sessions 1-3.
"""

from __future__ import annotations

import numpy as np


def build_adversarial_pair(n: int, k: int, seed: int = 0):
    """A0, A1: symmetric n x n matrices, identical on a fixed k-dim query
    subspace D, differing only on the (n-k)-dim orthogonal complement W.

    D absorbs the query vectors and is given a "boring" large-diagonal block
    with zero cross-terms into W, so any matvec against a vector living in D
    produces an answer entirely determined by the D-block -- W is invisible.
    The W-block is where A0 and A1 actually differ: A0 puts exactly one
    eigenvalue below beta there, A1 puts exactly two.
    """
    rng = np.random.default_rng(seed)
    assert 0 < k < n

    # An orthonormal basis whose first k columns span D (the query subspace)
    # and whose remaining n-k columns span W (the adversary's hidden room).
    q, _ = np.linalg.qr(rng.standard_normal((n, n)))

    d_block = np.diag(rng.uniform(50.0, 100.0, size=k))  # "boring", far above beta

    w0 = np.zeros((n - k, n - k))
    w1 = np.zeros((n - k, n - k))
    # Bulk: identical in both, well above beta=0, so the *only* difference
    # between A0 and A1 is which eigenvalues sit below beta.
    bulk = rng.uniform(5.0, 10.0, size=n - k - 2)
    w0[2:, 2:] = np.diag(bulk)
    w1[2:, 2:] = np.diag(bulk)
    # A0: exactly one eigenvalue below beta=0.
    w0[0, 0], w0[1, 1] = -3.0, 4.0
    # A1: exactly two eigenvalues below beta=0.
    w1[0, 0], w1[1, 1] = -3.0, -1.0

    def assemble(w):
        blocks = np.zeros((n, n))
        blocks[:k, :k] = d_block
        blocks[k:, k:] = w
        return q @ blocks @ q.T

    a0, a1 = assemble(w0), assemble(w1)
    query_vectors = [q[:, i] for i in range(k)]  # orthonormal basis of D
    return a0, a1, query_vectors, q


def count_below(a: np.ndarray, beta: float) -> int:
    return int(np.sum(np.linalg.eigvalsh(a) < beta))


def main() -> None:
    n, k, beta = 40, 12, 0.0
    a0, a1, queries, q = build_adversarial_pair(n, k)

    print(f"n={n}, k={k} query vectors (k/n = {k/n:.2f}), beta={beta}")
    print()

    c0, c1 = count_below(a0, beta), count_below(a1, beta)
    print(f"true count(eigenvalues < beta) for A0: {c0}")
    print(f"true count(eigenvalues < beta) for A1: {c1}")
    assert c0 == 1 and c1 == 2, "construction did not land the intended counts"

    max_diff = 0.0
    for i, v in enumerate(queries):
        r0, r1 = a0 @ v, a1 @ v
        d = float(np.max(np.abs(r0 - r1)))
        max_diff = max(max_diff, d)
    print(f"max |A0 v_i - A1 v_i| over the {k} query vectors: {max_diff:.3e}")
    assert max_diff < 1e-9, "queries should be exactly indistinguishable"

    # Responses stay indistinguishable under repeated application too --
    # i.e. this is not just true for a single matvec per query vector, it
    # holds for the whole Krylov space K_m(A, v_i) built from any of them,
    # for any depth m, as long as the accumulated span stays inside D. Any
    # power of A restricted to D acts exactly as d_block (block-diagonal,
    # zero cross-terms), so Krylov spaces built purely from D-vectors never
    # leave D and never see W. Check depth 5 directly to make the point
    # concrete rather than asserting it.
    v0 = queries[0]
    r0, r1 = v0.copy(), v0.copy()
    max_krylov_diff = 0.0
    for step in range(5):
        r0 = a0 @ r0
        r1 = a1 @ r1
        d = float(np.max(np.abs(r0 - r1)))
        max_krylov_diff = max(max_krylov_diff, d)
        print(f"  depth {step + 1}: |A0^m v0 - A1^m v0| = {d:.3e}")
    assert max_krylov_diff < 1e-6, "Krylov trajectory from a D-vector should stay indistinguishable"

    print()
    print("Any deterministic function of {A v_1, ..., A v_k} -- which is all a")
    print("matrix-vector-product-oracle algorithm (Lanczos, shift-invert,")
    print("Chebyshev-filtered, or any future variant in this family) ever")
    print("sees -- is IDENTICAL on A0 and A1, yet the true eigenvalue count")
    print("below beta differs (1 vs 2). So no such algorithm, restricted to")
    print(f"these {k} = {k/n:.0%} n query vectors, can be a sound source for")
    print("'exactly 1 eigenvalue below beta' in the worst case.")


if __name__ == "__main__":
    main()
