"""certkit-k2j scratch experiment (numpy/scipy allowed -- this is producer-side
style, not trusted code; nothing here touches certkit/, tests/, or examples/).

Question: does the entanglement entropy of a near-ground-state eigenvector of
a PauliSumReal-shaped operator, across a balanced qubit bipartition, saturate
(area law -- MPS/MPO bond dimension bounded) or grow with q (volume law --
bond dimension requirement grows unboundedly), as a function of the operator's
*interaction geometry*?

Two families, same term-count budget per qubit (bounded, 2-local), same coeff
scale, differing only in whether interactions are geometrically local (matches
examples/sample/pauli_operator.json's structure) or unrestricted (which
PauliSumReal's schema permits -- see certkit/operators.py:199, `terms:
list[tuple[float, str]]`, no locality check anywhere in operators.py or
schema.py).

Ground states are found by Lanczos (scipy.sparse.linalg.eigsh) against a
matrix-free matvec identical in structure to producer.py's `_float_apply`
for `pauli_sum_real` (same mask/phase-parity logic, reimplemented here rather
than imported so this script has no certkit import at all -- pure numpy).
"""

import numpy as np
from scipy.sparse.linalg import LinearOperator, eigsh


def compile_terms(q, terms):
    idx = np.arange(1 << q, dtype=np.int64)
    compiled = []
    for c, s in terms:
        mask = zy = ny = 0
        for k, p in enumerate(s):
            if p in "XY":
                mask |= 1 << k
            if p in "ZY":
                zy |= 1 << k
            if p == "Y":
                ny += 1
        c *= -1.0 if (ny // 2) % 2 else 1.0
        src = idx ^ mask
        sign = 1.0 - 2.0 * (np.bitwise_count(src & zy) & 1)
        compiled.append((c, src, sign))
    return compiled


def make_matvec(q, terms):
    compiled = compile_terms(q, terms)
    n = 1 << q

    def matvec(x):
        out = np.zeros(n)
        for c, src, sign in compiled:
            out += c * sign * x[src]
        return out

    return LinearOperator((n, n), matvec=matvec, dtype=np.float64)


def entanglement_entropy(state, q, cut):
    """Von Neumann entropy of the reduced state on the first `cut` qubits,
    for a bipartition into {0..cut-1} vs {cut..q-1}. Exact, via SVD of the
    state reshaped as a (2**cut, 2**(q-cut)) matrix -- standard, only used
    here to measure a property of the ground state, not to certify anything.
    """
    psi = state.reshape(1 << cut, 1 << (q - cut))
    s = np.linalg.svd(psi, compute_uv=False)
    p = s ** 2
    p = p[p > 1e-14]
    p = p / p.sum()
    return float(-(p * np.log(p)).sum())


def _z_field_terms(q, rng, scale):
    """Small random longitudinal field, same for both families at a given
    seed/scale. Breaks the global Z2 spin-flip symmetry (P = prod_i X_i,
    which commutes with any sum-of-ZZ + sum-of-X Hamiltonian) explicitly, so
    the ground state is not forced into a symmetric/antisymmetric cat
    combination of two classically-degenerate sectors -- that degeneracy
    produces a spurious S -> log(2) plateau *independent of bulk geometry*
    (confirmed by the first run of this script, see the handoff) and would
    otherwise swamp the geometry comparison this experiment is trying to
    make.
    """
    terms = []
    for i in range(q):
        s = ["I"] * q
        s[i] = "Z"
        terms.append((scale * rng.uniform(-1.0, 1.0), "".join(s)))
    return terms


def tfim_chain_terms(q, seed, J=1.0, h=1.0, hz_scale=0.1):
    """Matches examples/sample/pauli_operator.json's structure: nearest-
    neighbor ZZ + uniform transverse field, at h=J (the chain's critical
    point -- the regime with the *most* entanglement a 1D-local gapless
    point can produce, since it is where the area law is weakest: S grows
    like (c/6) log(subsystem size), not O(1), but still sub-linearly).
    """
    rng = np.random.default_rng(seed)
    terms = []
    for i in range(q - 1):
        s = ["I"] * q
        s[i] = "Z"
        s[i + 1] = "Z"
        terms.append((-J, "".join(s)))
    for i in range(q):
        s = ["I"] * q
        s[i] = "X"
        terms.append((-h, "".join(s)))
    terms += _z_field_terms(q, rng, hz_scale)
    return terms


def all_to_all_terms(q, seed, J=1.0, h=1.0, hz_scale=0.1):
    """Same 2-local-ZZ + local-X + local-Z term *shape* as tfim_chain_terms,
    but geometrically unrestricted -- which is exactly what PauliSumReal's
    schema permits (certkit/operators.py:199, `terms: list[tuple[float,
    str]]`, no locality check anywhere) and the chain case does not
    exercise. NOT the same term *count*: O(q^2) ZZ terms here vs O(q) in the
    chain -- but that quadratic blow-up is itself representative of what
    this repo's own motivating PauliSumReal instances look like (JW-mapped
    two-body chemistry Hamiltonians are already all-to-all after the
    Jordan-Wigner transform; see sandbox-handoffs/certkit-ph1.md's own
    `jw_two_body` family), not an artificial padding to make this experiment
    look worse.

    J_ij ~ J/sqrt(q) is the standard SK-model normalisation so total
    per-spin interaction energy stays O(1) as q grows (an unnormalised O(1)
    J_ij here would make total coupling energy grow like q, silently
    changing the physical regime -- ordered-vs-critical-vs-paramagnetic --
    as q increases, confounding any comparison across q).
    """
    rng = np.random.default_rng(seed)
    terms = []
    j_scale = J / np.sqrt(q)
    for i in range(q):
        for j in range(i + 1, q):
            s = ["I"] * q
            s[i] = "Z"
            s[j] = "Z"
            coeff = j_scale * rng.choice([-1.0, 1.0])
            terms.append((coeff, "".join(s)))
    for i in range(q):
        s = ["I"] * q
        s[i] = "X"
        terms.append((-h, "".join(s)))
    terms += _z_field_terms(q, rng, hz_scale)
    return terms


def ground_state(q, terms):
    op = make_matvec(q, terms)
    n = 1 << q
    if n <= 4096:
        # cross-check small cases against dense eigh
        dense = np.zeros((n, n))
        e = np.eye(n)
        for k in range(n):
            dense[:, k] = op.matvec(e[:, k])
        assert np.allclose(dense, dense.T, atol=1e-10)
        w, v = np.linalg.eigh(dense)
        return w[0], v[:, 0]
    w, v = eigsh(op, k=1, which="SA", maxiter=20000)
    return w[0], v[:, 0]


def main():
    print("family        q      n   E0          S(balanced cut)   S/S_max")
    for q in range(4, 15):
        n = 1 << q
        cut = q // 2
        s_max = min(cut, q - cut) * np.log(2)

        e0, v0 = ground_state(q, tfim_chain_terms(q, seed=1))
        s_chain = entanglement_entropy(v0, q, cut)
        print(f"chain_1d      {q:3d} {n:6d}  {e0:10.5f}  {s_chain:8.5f}          {s_chain / s_max:6.3f}")

        e0, v0 = ground_state(q, all_to_all_terms(q, seed=1))
        s_a2a = entanglement_entropy(v0, q, cut)
        print(f"all_to_all    {q:3d} {n:6d}  {e0:10.5f}  {s_a2a:8.5f}          {s_a2a / s_max:6.3f}")

    # push all_to_all further (chain already visibly saturating; skip it here
    # to save wall-clock) -- is the growth still accelerating, or turning over?
    for q in (16, 18):
        n = 1 << q
        cut = q // 2
        s_max = min(cut, q - cut) * np.log(2)
        e0, v0 = ground_state(q, all_to_all_terms(q, seed=1))
        s_a2a = entanglement_entropy(v0, q, cut)
        print(f"all_to_all    {q:3d} {n:6d}  {e0:10.5f}  {s_a2a:8.5f}          {s_a2a / s_max:6.3f}")


def main_disorder_averaged():
    """The single-seed run above has a lot of realisation-to-realisation
    noise in the all_to_all family (it's one frustrated instance per q, not
    an ensemble) -- e.g. the single-seed table shows S dropping from 0.837
    (q=14) to 0.412 (q=16) then rising to 1.021 (q=18), which looks like it
    could be non-monotonic physics but is just sample noise (confirmed:
    residual norms at q=14/16/18 are all ~1e-13/1e-14, so it is not an
    eigsh-convergence artifact either -- see the handoff). Average over 5
    seeds per q to separate the trend from the noise.
    """
    print("family        q   mean(S)  std(S)   mean(S)/q   frac_of_max")
    for q in (8, 10, 12, 14):
        cut = q // 2
        s_max = min(cut, q - cut) * np.log(2)
        for label, terms_fn in (("chain_1d", tfim_chain_terms), ("all_to_all", all_to_all_terms)):
            vals = np.array([
                entanglement_entropy(ground_state(q, terms_fn(q, seed=seed))[1], q, cut)
                for seed in range(1, 6)
            ])
            print(f"{label:12s}  {q:2d}  {vals.mean():7.4f}  {vals.std():6.4f}   {vals.mean() / q:8.5f}   {vals.mean() / s_max:6.3f}")


if __name__ == "__main__":
    main()
    print()
    main_disorder_averaged()
