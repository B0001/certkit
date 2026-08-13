"""Backend tests: sparse CSR and matrix-free Pauli sums.

Two things are being established here. First, that the new backends compute
what they claim to (the Pauli `apply` is checked against an explicit Kronecker
construction). Second, and more importantly, that a backend which *refuses* to
materialise gets an honest abstention on the route that needs a matrix, and a
verified -- if much looser -- bound on the route that does not.
"""

from __future__ import annotations

import numpy as np
import pytest

from certkit.checker import check
from certkit.interval import Iv
from certkit.operators import (
    DENSE_LIMIT,
    decode_operator,
    encode_csr,
    encode_dense,
    encode_pauli,
)
from certkit.producer import (
    certify_lambda_min,
    certify_lambda_min_matrixfree,
    tfim_hamiltonian,
)
from certkit.schema import SchemaError

P = {
    "I": np.eye(2, dtype=complex),
    "X": np.array([[0, 1], [1, 0]], dtype=complex),
    "Y": np.array([[0, -1j], [1j, 0]], dtype=complex),
    "Z": np.diag([1, -1]).astype(complex),
}


def dense_pauli(qubits: int, terms) -> np.ndarray:
    m = np.zeros((2**qubits, 2**qubits), dtype=complex)
    for c, s in terms:
        op = np.array([[1]], dtype=complex)
        for k in range(qubits):
            op = np.kron(P[s[k]], op)  # qubit k is bit k
        m += c * op
    assert np.allclose(m.imag, 0.0)
    return m.real


def tridiag(n: int, diag: float = 2.0, off: float = -1.0):
    indptr, indices, data = [0], [], []
    for i in range(n):
        for j in (i - 1, i, i + 1):
            if 0 <= j < n:
                indices.append(j)
                data.append(diag if j == i else off)
        indptr.append(len(indices))
    return encode_csr(n, indptr, indices, data)


# -- Pauli backend correctness -------------------------------------------
def test_pauli_apply_matches_kronecker_construction():
    q = 4
    terms = [(0.7, "ZZII"), (-1.3, "XIXI"), (0.5, "YYII"), (2.0, "IIIZ")]
    op = decode_operator(encode_pauli(q, terms))
    a = dense_pauli(q, terms)

    rng = np.random.default_rng(0)
    for _ in range(5):
        x = rng.standard_normal(2**q)
        got = op.apply([Iv.exact(v) for v in x])
        want = a @ x
        for g, w in zip(got, want):
            assert g.lo <= w <= g.hi or abs(0.5 * (g.lo + g.hi) - w) < 1e-12


def test_pauli_rows_match_dense():
    q = 3
    terms = [(1.1, "XZI"), (-0.4, "IYY"), (0.25, "ZZZ")]
    op = decode_operator(encode_pauli(q, terms))
    a = dense_pauli(q, terms)
    for i in range(2**q):
        row = op.row(i)
        for j in range(2**q):
            v = row.get(j)
            expected = a[i, j]
            if v is None:
                assert abs(expected) < 1e-15
            else:
                assert abs(0.5 * (v.lo + v.hi) - expected) < 1e-12


def test_odd_y_count_is_rejected_as_non_real():
    with pytest.raises(SchemaError):
        decode_operator(encode_pauli(2, [(1.0, "YI")]))


def test_malformed_pauli_string_is_rejected():
    with pytest.raises(SchemaError):
        decode_operator(encode_pauli(2, [(1.0, "QI")]))
    with pytest.raises(SchemaError):
        decode_operator(encode_pauli(3, [(1.0, "ZZ")]))


# -- sparse backend -------------------------------------------------------
def test_sparse_tridiagonal_verifies_and_is_sound():
    enc = tridiag(30)
    v = check(*certify_lambda_min(enc))
    assert v.ok, v.reason
    rows = decode_operator(enc).dense_rows()
    truth = float(np.linalg.eigvalsh(np.array(rows))[0])
    assert v.rederived[0] <= truth <= v.rederived[1]


def test_sparse_matches_dense_on_the_same_matrix():
    enc = tridiag(24)
    rows = decode_operator(enc).dense_rows()
    vs = check(*certify_lambda_min(enc))
    vd = check(*certify_lambda_min(rows))
    assert vs.ok and vd.ok
    assert abs(vs.rederived[0] - vd.rederived[0]) < 1e-9


def test_unpivoted_ldlt_growth_shows_up_as_abstention():
    """A real limitation, behaving correctly.

    Interval LDL^T without pivoting accumulates width across eliminations. On a
    1D Laplacian the ground state gap shrinks like 1/n^2, and by n = 40 the
    accumulated width swallows a pivot, so the inertia is no longer determined.
    The kit abstains. It does not round the pivot to a sign and report a bound.

    The fix is a Sturm-sequence route that exploits banded structure; see the
    README. Until that exists, this is the honest behaviour.
    """
    v = check(*certify_lambda_min(tridiag(40)))
    assert not v.ok and "pivot" in v.reason


def test_asymmetric_sparse_is_rejected():
    enc = encode_csr(2, [0, 2, 4], [0, 1, 0, 1], [1.0, 2.0, 3.0, 4.0])
    with pytest.raises(SchemaError):
        decode_operator(enc)


def test_malformed_csr_is_rejected():
    for bad in (
        encode_csr(2, [0, 1], [0], [1.0]),                      # short indptr
        encode_csr(2, [0, 1, 5], [0, 1], [1.0, 1.0]),           # indptr overruns
        encode_csr(2, [0, 1, 2], [0, 7], [1.0, 1.0]),           # column out of range
    ):
        with pytest.raises(SchemaError):
            decode_operator(bad)


def test_encodings_of_the_same_matrix_have_different_refs():
    """The reference binds the *encoding*, not the abstract operator.

    Deliberate: the checker must reason about the object it was handed, and a
    value-based reference would require canonicalising every backend into one
    representation -- which is exactly the sort of trusted preprocessing this
    design refuses.
    """
    enc = tridiag(6)
    cert, _ = certify_lambda_min(enc)
    rows = decode_operator(enc).dense_rows()
    v = check(cert, encode_dense(rows))
    assert not v.ok and "operator" in v.reason


# -- the matrix-free route ------------------------------------------------
def test_small_hamiltonian_takes_the_tight_route():
    enc = tfim_hamiltonian(6, field=1.5)
    v = check(*certify_lambda_min(enc))
    assert v.ok and v.rule == "temple_inertia"
    truth = float(np.linalg.eigvalsh(dense_pauli(6, _terms(enc)))[0])
    assert v.rederived[0] <= truth <= v.rederived[1]
    assert v.width < 1e-9


def test_large_hamiltonian_refuses_the_tight_route():
    enc = tfim_hamiltonian(11)
    assert decode_operator(enc).n > DENSE_LIMIT
    v = check(*certify_lambda_min(enc))
    assert not v.ok
    assert "materialise" in v.reason and "gershgorin" in v.reason


def test_large_hamiltonian_verifies_matrix_free():
    q = 11
    enc = tfim_hamiltonian(q)
    v = check(*certify_lambda_min_matrixfree(enc))
    assert v.ok and v.rule == "gershgorin_rayleigh"
    truth = float(np.linalg.eigvalsh(dense_pauli(q, _terms(enc)))[0])
    assert v.rederived[0] <= truth <= v.rederived[1]
    # Loose, and honest about it: Gershgorin cannot see the gap.
    assert v.width > 1.0


def test_matrix_free_route_is_sound_but_wider_than_temple():
    enc = tfim_hamiltonian(6)
    tight = check(*certify_lambda_min(enc))
    loose = check(*certify_lambda_min_matrixfree(enc))
    assert tight.ok and loose.ok
    assert loose.width > tight.width
    assert loose.rederived[0] <= tight.rederived[0]


def _terms(enc):
    return [(float.fromhex(t["coeff"]), t["string"]) for t in enc["terms"]]
