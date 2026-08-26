"""certkit-bz5: a real-time Krylov solver's ground-state estimate is complex,
but certkit's witness format is real-only.

`H` is real symmetric, so its ground state can be chosen real, and either the
real or the imaginary part of a complex estimate `psi0` is individually a
usable real trial vector. But the Rayleigh quotient of a *part* of `psi0` is
in general a different number than the Rayleigh quotient of `psi0` itself --
they are different vectors. The finding (from `certkit-jn1.1`, on H2/sto-3g):
an external bridge (not part of this repo) transcribed the bracket it
computed from the complex `psi0` onto a certificate whose witness field
actually carried `Re(psi0)`, and the checker refused it as "claimed interval
is tighter than the re-derived enclosure".

That refusal is the checker doing its job: it re-derives mu and the residual
from whatever vector is actually in the witness field, never from anything
the producer claims about a different vector, so a mismatched (bracket,
witness) pair can only ever be caught, not certified. This file constructs
that exact mismatch and confirms it (a) cannot be made to verify, no matter
how the naive translation is built, and (b) verifies correctly once the
bracket is recomputed on the vector actually being shipped --
`certify_lambda_min_from_witness`, added for this bead, is that recompute
path, callable by any producer (in this repo or outside it) that has its own
externally-computed witness vector.
"""

from __future__ import annotations

import numpy as np

from certkit.checker import check
from certkit.operators import encode_dense, operator_ref
from certkit.producer import certify_lambda_min_from_witness, pad_claim
from certkit.schema import SCHEMA_VERSION, f2h, seal

# A real symmetric H with three well-separated levels: lambda_1 = -2.0,
# lambda_2 = -1.5, lambda_3 = 5.0. e0, e1, e2 (the standard basis vectors)
# are its exact eigenvectors.
DIAG = [-2.0, -1.5, 5.0]


def _h():
    n = len(DIAG)
    rows = [[DIAG[i] if i == j else 0.0 for j in range(n)] for i in range(n)]
    return encode_dense(rows)


def _psi0(a: float, b: float) -> np.ndarray:
    """A complex trial state `a*e0 + i*b*e1`, normalised. Mirrors the bead's
    H2/sto-3g finding, where most of psi0's weight (53%) sat in the
    imaginary part: here the imaginary part alone carries `b**2` of the
    weight, and is set well above half."""
    v = np.array([a, 1j * b, 0.0])
    return v / np.linalg.norm(v)


def _naive_bridge_certificate(enc, psi0: np.ndarray, slack: float = 1e-9):
    """Exactly the bug: compute mu on the *complex* state (the number a real
    solver's own diagnostics would report), then submit a certificate whose
    witness vector is only `Re(psi0)` -- a different vector, with in general
    a different Rayleigh quotient. No numerics the checker is asked to trust;
    the point is that these specific numbers came from `psi0`, not from the
    vector in the witness field.
    """
    diag = np.array(DIAG)
    mu_complex = float(np.sum(np.abs(psi0) ** 2 * diag))  # <psi0|H|psi0>, psi0 normalised
    beta = 0.5 * (DIAG[0] + DIAG[1])  # the true lambda_1/lambda_2 midpoint

    real_part = psi0.real
    # A real bridge would still normalise the part it ships as witness.
    x = real_part / np.linalg.norm(real_part)

    pad = pad_claim(mu_complex, slack, len(diag))
    lo, hi = mu_complex - pad, mu_complex + pad
    cert = seal({
        "schema": SCHEMA_VERSION,
        "claim": {
            "operator_ref": operator_ref(enc),
            "kind": "lambda_min_enclosure",
            "enclosure": {"lo": f2h(lo), "hi": f2h(hi)},
        },
        "witness": {
            "rule": "temple_inertia",
            "vector": [f2h(float(v)) for v in x],
            "beta": f2h(beta),
        },
    })
    return cert, x, mu_complex


def test_transcribed_bracket_does_not_verify():
    """The naive translation: mu computed from the complex psi0 (53% of its
    weight in the imaginary part, on e1), bracket built around that number,
    witness field carries Re(psi0) (which is exactly e0's direction -- the
    true ground eigenvector, mu = -2.0 exactly). The checker must not certify
    the claimed bracket (~-1.735, nowhere near -2.0) just because it was once
    a true statement about a different vector."""
    enc = _h()
    psi0 = _psi0(a=np.sqrt(0.47), b=np.sqrt(0.53))
    cert, x, mu_complex = _naive_bridge_certificate(enc, psi0)

    # Sanity: this is a real mismatch, not a rounding artefact -- psi0's own
    # Rayleigh quotient and the real part's are nowhere near each other.
    assert abs(mu_complex - DIAG[0]) > 0.2
    np.testing.assert_allclose(x, [1.0, 0.0, 0.0])  # Re(psi0) is exactly e0

    v = check(cert, enc)
    assert not v.ok
    assert v.reason == "claimed interval is tighter than the re-derived enclosure"
    # And the re-derivation the checker actually used is centred on the real
    # part's own Rayleigh quotient (-2.0, e0's eigenvalue), not on mu_complex.
    lo, hi = v.rederived
    assert abs(hi - DIAG[0]) < 1e-9


def test_transcribed_bracket_is_false_when_taken_at_face_value():
    """Confirms the claim the checker refused above would have been an
    unsound VERIFIED, not merely an overcautious ABSTAIN: the claimed
    interval does not even contain the true lambda_min."""
    enc = _h()
    psi0 = _psi0(a=np.sqrt(0.47), b=np.sqrt(0.53))
    _, _, mu_complex = _naive_bridge_certificate(enc, psi0)
    pad = pad_claim(mu_complex, 1e-9, len(DIAG))
    lo, hi = mu_complex - pad, mu_complex + pad
    assert not (lo <= DIAG[0] <= hi)


def test_recomputing_on_the_real_witness_verifies_its_own_correct_bracket():
    """The fix the bead's acceptance criteria describes: recompute mean and
    variance on the vector actually being shipped, rather than transcribing
    a bracket from psi0. `certify_lambda_min_from_witness` is exactly that --
    call it directly on `Re(psi0)`, and the resulting certificate verifies,
    correctly, around the real part's own Rayleigh quotient."""
    enc = _h()
    psi0 = _psi0(a=np.sqrt(0.47), b=np.sqrt(0.53))
    real_part = psi0.real

    cert, op = certify_lambda_min_from_witness(enc, real_part)
    v = check(cert, op)
    assert v.ok, v.reason
    lo, hi = v.rederived
    # Re(psi0) is exactly e0's direction here, the true ground eigenvector.
    assert lo <= DIAG[0] <= hi
    assert hi - lo < 1e-9


def test_recomputing_on_the_imaginary_witness_verifies_a_different_bracket():
    """Either part is a usable trial vector (the bead's own framing) -- but
    they are different vectors with different Rayleigh quotients, so they
    must produce different, independently-derived brackets, not the same one
    transcribed twice. Here Im(psi0) is e1's direction, an exact eigenvector
    for the *second* level, not the ground state -- so the checker abstains
    (mu is not provably below beta), which is the honest outcome: this vector
    is not a valid lambda_min witness, and nothing should paper over that."""
    enc = _h()
    psi0 = _psi0(a=np.sqrt(0.47), b=np.sqrt(0.53))
    imag_part = psi0.imag

    cert, op = certify_lambda_min_from_witness(enc, imag_part)
    v = check(cert, op)
    assert not v.ok
    assert v.reason == "Rayleigh quotient is not provably below beta"


def test_witness_dimension_mismatch_is_rejected():
    enc = _h()
    try:
        certify_lambda_min_from_witness(enc, [1.0, 0.0])
        assert False, "expected ValueError"
    except ValueError as e:
        assert "dimension" in str(e)


def test_zero_witness_is_rejected():
    enc = _h()
    try:
        certify_lambda_min_from_witness(enc, [0.0, 0.0, 0.0])
        assert False, "expected ValueError"
    except ValueError as e:
        assert "nonzero" in str(e)
