"""certkit-3ta: complex Hermitian operators.

A minimal, complete vertical slice, not a full parity with real symmetric
operators: a complex interval type (`CIv`, in interval.py), an exact
Hermitian symmetry check (`DenseHermitianComplex.check_symmetric`), and one
matrix-free certification route, `hermitian_gershgorin_rayleigh` -- the
complex analogue of `gershgorin_rayleigh`, generalizing the real inner
product to the Hermitian one. There is deliberately no complex analogue of
the Temple/inertia route here: that needs an interval LDL^T over `CIv`,
which is unimplemented and out of scope for this bead (see README's
"Complex Hermitian operators" section).

What this file has to show, matching the repo's standard: soundness against
an independent oracle (`numpy.linalg.eigvalsh` on the same matrix), the
abstain-not-degrade discipline for a tampered/adversarial witness, exact
rejection of non-Hermitian input, and a clean ABSTAIN (never a crash) when
a rule and an operator kind are mismatched.
"""

from __future__ import annotations

import numpy as np
import pytest

from certkit.checker import check
from certkit.operators import decode_operator, encode_dense, encode_dense_hermitian, operator_ref
from certkit.producer import certify_lambda_min_hermitian
from certkit.schema import SCHEMA_VERSION, SchemaError, f2h, seal


def test_pauli_y_exact_oracle():
    """[[0, -i], [i, 0]] is exactly Hermitian, with exact eigenvalues +-1 --
    no LAPACK rounding anywhere in the ground truth to compare against."""
    rows = [[0, -1j], [1j, 0]]
    enc = encode_dense_hermitian(rows)
    cert, op = certify_lambda_min_hermitian(enc)
    v = check(cert, op)
    assert v.ok, v.reason
    assert v.rule == "hermitian_gershgorin_rayleigh"
    lo, hi = v.rederived
    assert lo <= -1.0 <= hi


@pytest.mark.parametrize("seed", range(8))
def test_verified_and_sound_against_numpy_eigvalsh(seed):
    """Random complex Hermitian matrices: every VERIFIED enclosure must
    actually contain numpy's independently computed smallest eigenvalue."""
    rng = np.random.default_rng(seed)
    n = 6
    m = rng.standard_normal((n, n)) + 1j * rng.standard_normal((n, n))
    a = (m + m.conj().T) / 2.0
    truth = float(np.linalg.eigvalsh(a)[0])

    enc = encode_dense_hermitian(a.tolist())
    cert, op = certify_lambda_min_hermitian(enc)
    v = check(cert, op)
    assert v.ok, v.reason
    lo, hi = v.rederived
    assert lo <= truth <= hi


def test_non_hermitian_matrix_is_rejected_exactly():
    rows = [[0, -1j], [0.5j, 0]]  # off-diagonal entries are not conjugates
    enc = encode_dense_hermitian(rows)
    with pytest.raises(SchemaError):
        decode_operator(enc)


def test_non_real_diagonal_is_rejected():
    rows = [[1e-3j, -1j], [1j, 0]]
    enc = encode_dense_hermitian(rows)
    with pytest.raises(SchemaError):
        decode_operator(enc)


def test_non_hermitian_matrix_abstains_through_check():
    """The same rejection, seen through the public `check()` path: a
    non-Hermitian operator must never reach VERIFIED -- it must ABSTAIN,
    not raise, since `check()` is the boundary a producer actually calls."""
    rows = [[0, -1j], [0.5j, 0]]
    enc = encode_dense_hermitian(rows)
    cert = seal({
        "schema": SCHEMA_VERSION,
        "claim": {
            "operator_ref": operator_ref(enc),
            "kind": "lambda_min_enclosure",
            "enclosure": {"lo": f2h(-1.0), "hi": f2h(1.0)},
        },
        "witness": {
            "rule": "hermitian_gershgorin_rayleigh",
            "vector": [
                {"re": f2h(1.0), "im": f2h(0.0)},
                {"re": f2h(0.0), "im": f2h(1.0)},
            ],
        },
    })
    v = check(cert, enc)
    assert not v.ok


def test_tampered_witness_abstains_rather_than_falsely_verifying():
    """Flip the sign of an imaginary witness component after a real
    certificate was sealed: the checker must recompute mu from the tampered
    vector and refuse, not shrug and trust the sealed bracket."""
    rows = [[0, -1j], [1j, 0]]
    enc = encode_dense_hermitian(rows)
    cert, op = certify_lambda_min_hermitian(enc)

    tampered = dict(cert)
    witness = dict(tampered["witness"])
    vec = [dict(e) for e in witness["vector"]]
    # The honest witness here is (1, -i)/sqrt(2) (eigenvalue -1); flip the
    # imaginary component's sign to (1, +i)/sqrt(2), the *other* eigenvector
    # (eigenvalue +1) -- a real, different vector, not a rounding nudge.
    im = float.fromhex(vec[1]["im"])
    vec[1]["im"] = f2h(-im)
    witness["vector"] = vec
    tampered["witness"] = witness
    tampered.pop("seal", None)
    tampered = seal({k: v for k, v in tampered.items() if k != "seal"})

    v = check(tampered, op)
    assert not v.ok


def test_witness_dimension_mismatch_abstains():
    rows = [[0, -1j], [1j, 0]]
    enc = encode_dense_hermitian(rows)
    cert, op = certify_lambda_min_hermitian(enc)
    witness = dict(cert["witness"])
    witness["vector"] = witness["vector"][:1]  # drop a component
    tampered = {k: v for k, v in cert.items() if k != "seal"}
    tampered["witness"] = witness
    tampered = seal(tampered)

    v = check(tampered, op)
    assert not v.ok


def test_zero_witness_abstains():
    rows = [[0, -1j], [1j, 0]]
    enc = encode_dense_hermitian(rows)
    cert, op = certify_lambda_min_hermitian(enc)
    witness = dict(cert["witness"])
    witness["vector"] = [
        {"re": f2h(0.0), "im": f2h(0.0)},
        {"re": f2h(0.0), "im": f2h(0.0)},
    ]
    tampered = {k: v for k, v in cert.items() if k != "seal"}
    tampered["witness"] = witness
    tampered = seal(tampered)

    v = check(tampered, op)
    assert not v.ok
    assert "zero" in v.reason


def test_complex_rule_against_real_operator_abstains_cleanly():
    """`hermitian_gershgorin_rayleigh` invoked (by a malformed or adversarial
    certificate) against a real operator must not raise -- it must abstain,
    per the cross-kind dispatch guard in `_verify_uncached`."""
    real_enc = encode_dense([[1.0, 0.0], [0.0, 2.0]])
    cert = seal({
        "schema": SCHEMA_VERSION,
        "claim": {
            "operator_ref": operator_ref(real_enc),
            "kind": "lambda_min_enclosure",
            "enclosure": {"lo": f2h(0.0), "hi": f2h(1.0)},
        },
        "witness": {
            "rule": "hermitian_gershgorin_rayleigh",
            "vector": [
                {"re": f2h(1.0), "im": f2h(0.0)},
                {"re": f2h(0.0), "im": f2h(0.0)},
            ],
        },
    })
    v = check(cert, real_enc)
    assert not v.ok
    assert "not compatible" in v.reason


def test_real_rule_against_complex_operator_abstains_cleanly():
    rows = [[0, -1j], [1j, 0]]
    complex_enc = encode_dense_hermitian(rows)
    cert = seal({
        "schema": SCHEMA_VERSION,
        "claim": {
            "operator_ref": operator_ref(complex_enc),
            "kind": "lambda_min_enclosure",
            "enclosure": {"lo": f2h(-1.0), "hi": f2h(1.0)},
        },
        "witness": {
            "rule": "gershgorin_rayleigh",
            "vector": [f2h(1.0), f2h(0.0)],
        },
    })
    v = check(cert, complex_enc)
    assert not v.ok
    assert "not compatible" in v.reason
