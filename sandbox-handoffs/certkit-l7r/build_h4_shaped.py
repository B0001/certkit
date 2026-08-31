"""
Build the n=256 (M=8 qubit) JW-two-body-shaped Pauli sum used to test
certkit-l7r (raise DENSE_LIMIT from 160 to 256).

Why this shape and not tfim_hamiltonian(8): certkit-ph1's session 7 handoff
(sandbox-handoffs/certkit-ph1.md, Result 10) explicitly separates the toy TFIM
shape from "the H4/N2 chemistry shape", which it identifies with the JW
two-body family (one- and two-body fermionic terms after Jordan-Wigner). This
script reuses the from-scratch, numpy-free JW transform written for
certkit-ph1 session 5 (sandbox-handoffs/certkit-ph1-jw-termcount-experiment.py)
to build an actual Hamiltonian (not just count its terms), so the test case
here is the same family the bead's own evidence measured, not a stand-in.

There is no real H4 molecular-integral fixture anywhere in this repo (every
ph1/487/bz5 session says so explicitly) -- "H4" throughout certkit-l7r means
"the JW-two-body-shaped, n=256 (M=8 qubit) case", exactly as certkit-ph1's
Result 10 used it, not a literal quantum-chemistry calculation.

Output: writes operator.json (pauli_sum_real, M=8, n=256) and truth.json
(independently-computed lambda_0, lambda_1, gap, via a from-scratch complex
dense construction -- NOT certkit code, so it is a genuine independent check)
into this directory.
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
import random
import sys

sys.path.insert(0, "/workspace")

HERE = os.path.dirname(os.path.abspath(__file__))
_jw_path = os.path.join(
    os.path.dirname(HERE), "certkit-ph1-jw-termcount-experiment.py"
)
_spec = importlib.util.spec_from_file_location("certkit_ph1_jw_termcount_experiment", _jw_path)
_jw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_jw)

from certkit.operators import encode_pauli  # trusted encoder, not a numeric routine


def build_jw_two_body_terms(M: int, seed: int, target_gap: float):
    """Return a list of (coeff, string) real Pauli terms, JW two-body shaped,
    plus the independently-computed (lambda_0, lambda_1) after rescaling the
    whole Hamiltonian so lambda_1 - lambda_0 ~= target_gap.
    """
    rng = random.Random(seed)

    # Reuse _jw's h1/two-body construction logic directly rather than only its
    # term-count wrapper, so we get the actual (string -> coeff) dict.
    acc: dict[tuple, complex] = {}

    h1 = [[0.0] * M for _ in range(M)]
    for p in range(M):
        for q in range(p, M):
            v = rng.uniform(-1, 1)
            h1[p][q] = v
            h1[q][p] = v
    for p in range(M):
        for q in range(M):
            if h1[p][q] == 0.0:
                continue
            terms = _jw.mul_terms(_jw.jw_ladder(p, M, True), _jw.jw_ladder(q, M, False))
            _jw.add_into(acc, terms, h1[p][q])

    # NOTE: the upstream ph1-session-5 script (which this reuses the ladder
    # algebra from) restricts its loop to only two representatives per
    # canonical class -- fine for *counting* terms, but it drops the (r,s,p,q)
    # partner needed to make the sum an actual Hermitian operator, and its
    # canon key does not even pair (p,q,r,s) with (r,s,p,q). Diagonalizing
    # that construction gave a non-Hermitian matrix (see the assertion this
    # fixes). h.c. of term (p,q,r,s) [= a_p^d a_q^d a_r a_s] is exactly term
    # (r,s,p,q): a_s^d a_r^d a_q a_p, and each fermionic-ladder swap
    # (a_s^d a_r^d = -a_r^d a_s^d, a_q a_p = -a_p a_q) contributes a sign, and
    # the two signs cancel. So assigning h_pqrs = h_rspq (same random draw for
    # both orderings) and summing over *every* ordered quadruple -- not just
    # two representatives -- makes the sum exactly self-adjoint termwise.
    seen: dict[tuple, float] = {}
    for p in range(M):
        for q in range(M):
            if p == q:
                continue
            for r in range(M):
                for s in range(M):
                    if r == s:
                        continue
                    canon = min((p, q, r, s), (r, s, p, q))
                    if canon not in seen:
                        seen[canon] = rng.uniform(-1, 1)
                    v = seen[canon]
                    terms = _jw.mul_terms(
                        _jw.mul_terms(_jw.jw_ladder(p, M, True), _jw.jw_ladder(q, M, True)),
                        _jw.mul_terms(_jw.jw_ladder(r, M, False), _jw.jw_ladder(s, M, False)),
                    )
                    _jw.add_into(acc, terms, 0.5 * v)

    # Sanity: this construction is Hermitian by design (h1 symmetric, two-body
    # canonicalised the same way both papers/openfermion use), which for a
    # *real*-orbital JW mapping forces every surviving term to have real
    # coefficient and even Y-count. Check both rather than assume them --
    # PauliSumReal.check_symmetric rejects odd-Y strings outright, and a
    # nonzero imaginary part here would mean this Hamiltonian isn't actually
    # Hermitian-real, which would make the whole exercise meaningless.
    terms = []
    max_imag = 0.0
    odd_y_mass = 0.0
    for s, c in acc.items():
        max_imag = max(max_imag, abs(c.imag))
        y_count = s.count("Y")
        if y_count % 2:
            odd_y_mass = max(odd_y_mass, abs(c))
            continue
        if abs(c.real) < 1e-12:
            continue
        terms.append((c.real, "".join(s)))

    return terms, max_imag, odd_y_mass


def dense_matrix_from_terms(M: int, terms):
    """Independent (non-certkit) construction of the 2^M x 2^M complex matrix,
    for ground-truth diagonalisation. Deliberately does not reuse
    certkit.operators.PauliSumReal -- this is the check *on* that code."""
    import numpy as np

    PAULI = {
        "I": np.eye(2, dtype=complex),
        "X": np.array([[0, 1], [1, 0]], dtype=complex),
        "Y": np.array([[0, -1j], [1j, 0]], dtype=complex),
        "Z": np.diag([1, -1]).astype(complex),
    }
    n = 1 << M
    mat = np.zeros((n, n), dtype=complex)
    for c, s in terms:
        op = np.array([[1]], dtype=complex)
        for k in range(M):
            op = np.kron(PAULI[s[k]], op)
        mat += c * op
    return mat


def main():
    import numpy as np

    M = 8
    n = 1 << M
    terms, max_imag, odd_y_mass = build_jw_two_body_terms(M, seed=1, target_gap=1.46e-3)
    print(f"M={M} n={n} raw term count={len(terms)} max|imag|={max_imag:.3e} odd-Y mass={odd_y_mass:.3e}")
    assert max_imag < 1e-9, "Hamiltonian is not real -- construction bug"
    assert odd_y_mass < 1e-9, "odd-Y terms survived -- construction bug"

    mat = dense_matrix_from_terms(M, terms)
    assert np.allclose(mat, mat.conj().T), "not Hermitian"
    assert np.allclose(mat.imag, 0.0, atol=1e-9), "not real"

    w = np.linalg.eigvalsh(mat.real)
    lam0_raw, lam1_raw = float(w[0]), float(w[1])
    gap_raw = lam1_raw - lam0_raw
    print(f"raw ground-state gap = {gap_raw:.6e}  (lam0={lam0_raw:.6f} lam1={lam1_raw:.6f})")

    # Rescale the whole Hamiltonian (every eigenvalue scales linearly) so the
    # ground-state gap sits at the chemical-accuracy scale certkit-l7r's
    # description cites (1.46e-3, matching certkit-ph1 Result 10's own
    # figure for its H4 case).
    target_gap = 1.46e-3
    scale = target_gap / gap_raw
    scaled_terms = [(c * scale, s) for c, s in terms]

    mat2 = dense_matrix_from_terms(M, scaled_terms)
    w2 = np.linalg.eigvalsh(mat2.real)
    lam0, lam1 = float(w2[0]), float(w2[1])
    gap = lam1 - lam0
    print(f"scaled ground-state gap = {gap:.6e}  (lam0={lam0:.6f} lam1={lam1:.6f})  scale={scale:.6e}")

    enc = encode_pauli(M, scaled_terms)
    with open(os.path.join(HERE, "operator.json"), "w") as f:
        json.dump(enc, f)
    with open(os.path.join(HERE, "truth.json"), "w") as f:
        json.dump({"lam0": lam0, "lam1": lam1, "gap": gap, "n": n, "qubits": M,
                    "term_count": len(scaled_terms)}, f, indent=2)
    print(f"wrote operator.json ({len(scaled_terms)} terms) and truth.json")


if __name__ == "__main__":
    main()
