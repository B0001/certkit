"""certkit-487: does a sector-local witness survive translation into a claim
about the whole operator?

An external Krylov solver (the chem bridge, not anything in this repo) may
restrict its search to one symmetry sector -- particle number, spin, whatever
block-diagonalises the Hamiltonian -- and hand certkit a witness vector and a
gap parameter that are only meaningful *within that sector*. If a lower-lying
sector exists that the solver never explored, the naive translation is a claim
about the whole operator built from a premise that was only ever checked
against a slice of it.

The question is not whether such a producer can be sloppy -- it can, that is
the whole point of the trust boundary -- but whether the checker can be made
to certify the resulting false claim. It cannot, and this file is the
deliberately constructed case the certkit-487 notes asked for: build an
operator with a lower sector the witness never saw, translate its local Ritz
data exactly the way a naive bridge would, and confirm the checker refuses.

Every case here is built directly from the public certificate schema (not
`certkit.producer`, which always looks at the whole operator) because the bug
under test is specifically what happens when a *different* producer sends a
sector-scoped witness through the same door.
"""

from __future__ import annotations

import numpy as np

from certkit.checker import check
from certkit.operators import encode_dense, operator_ref
from certkit.producer import certify_lambda_min
from certkit.schema import SCHEMA_VERSION, f2h, seal


def _diag_operator(diag: list[float]) -> dict:
    n = len(diag)
    rows = [[diag[i] if i == j else 0.0 for j in range(n)] for i in range(n)]
    return encode_dense(rows)


def _sector_witness_cert(enc: dict, vector: list[float], beta: float, lo: float, hi: float) -> dict:
    """Exactly what a naive bridge would submit: local Ritz vector and gap,
    claimed as a bound on the whole operator. No numerics the checker is
    asked to trust -- mu/rho/the inertia count are all re-derived."""
    return seal({
        "schema": SCHEMA_VERSION,
        "claim": {
            "operator_ref": operator_ref(enc),
            "kind": "lambda_min_enclosure",
            "enclosure": {"lo": f2h(lo), "hi": f2h(hi)},
        },
        "witness": {
            "rule": "temple_inertia",
            "vector": [f2h(v) for v in vector],
            "beta": f2h(beta),
        },
    })


# Sector A: what the restricted solver can see. Local ground a1, local first
# excited a2 -- the "self-mode" and its own internal gap.
A_GROUND, A_FIRST_EXCITED, A_REST = -1.0, 3.0, 5.0


def _sector_case(b_ground: float, b_rest: float):
    """Two decoupled sectors as a block-diagonal operator (indices 0-2 are
    sector A, 3-4 are sector B). The solver only ever looked at A: its
    witness vector is the exact A-ground eigenvector padded with zeros, and
    its beta is the midpoint of A's own two lowest levels."""
    diag = [A_GROUND, A_FIRST_EXCITED, A_REST, b_ground, b_rest]
    enc = _diag_operator(diag)
    n = len(diag)
    x = [1.0 if i == 0 else 0.0 for i in range(n)]  # exact eigvec, eigenvalue A_GROUND
    beta = 0.5 * (A_GROUND + A_FIRST_EXCITED)
    # Diagonal operator, exact eigenvector: mu = A_GROUND, residual = 0 exactly,
    # so the naive Temple translation is a *point* claim -- as confident as a
    # false claim can be made to look.
    return enc, x, beta, diag


def test_lower_lying_sector_makes_the_naive_translation_abstain():
    """The dramatic case from the bead: a sector ground that is not the
    global minimum. Sector B's ground (-4.0) sits well below A's (-1.0) and
    below A's local beta (1.0) too, so the true operator has two eigenvalues
    below beta, not one -- and the checker must refuse the point claim
    [-1.0, -1.0], which is false (true lambda_min is -4.0)."""
    enc, x, beta, diag = _sector_case(b_ground=-4.0, b_rest=2.0)
    cert = _sector_witness_cert(enc, x, beta, A_GROUND, A_GROUND)

    truth = min(diag)
    assert truth < A_GROUND  # the claim [-1.0, -1.0] would be false if VERIFIED

    v = check(cert, enc)
    assert not v.ok
    assert "need exactly 1" in v.reason


def test_small_violation_of_the_premise_is_still_caught():
    """Detection must not depend on the violation being dramatic (H2's 1.02
    Ha). Put sector B's ground only 0.01 below A's local beta and confirm the
    inertia count still refuses -- it is a count, not a tolerance."""
    enc, x, beta, diag = _sector_case(b_ground=A_GROUND - 0.01, b_rest=2.0)
    cert = _sector_witness_cert(enc, x, beta, A_GROUND, A_GROUND)

    truth = min(diag)
    assert truth < A_GROUND

    v = check(cert, enc)
    assert not v.ok
    assert "need exactly 1" in v.reason


def test_sector_ground_that_is_also_the_global_minimum_verifies():
    """Contrast case, matching the bead's H2/H4 empirical finding: when the
    sector the solver explored happens to hold the true global minimum, and
    beta genuinely separates the full spectrum, the same translation is
    honest and the checker verifies it -- exactly, since the witness is an
    exact eigenvector here."""
    enc, x, beta, diag = _sector_case(b_ground=4.0, b_rest=6.0)
    truth = min(diag)
    assert truth == A_GROUND  # sector ground IS the global minimum this time

    # A real producer pads its claim against the checker's own interval
    # widening (certkit-kj6); an unpadded point claim would be rejected as
    # "tighter than the re-derived enclosure" even though it is true.
    pad = 1e-9
    cert = _sector_witness_cert(enc, x, beta, A_GROUND - pad, A_GROUND + pad)
    v = check(cert, enc)
    assert v.ok
    lo, hi = v.rederived
    assert lo <= A_GROUND <= hi


def test_full_space_producer_finds_the_true_minimum_on_the_same_operator():
    """The mitigation, demonstrated rather than asserted: certkit's own
    producer never restricts itself to a sector -- `_ground_state` runs a
    full dense/Lanczos solve over the *whole* operator -- so on the exact
    matrix that defeats the naive sector translation above, the full-space
    route finds the real minimum instead of abstaining or lying."""
    enc, _, _, diag = _sector_case(b_ground=-4.0, b_rest=2.0)
    truth = min(diag)

    cert, op = certify_lambda_min(enc)
    v = check(cert, op)
    assert v.ok
    lo, hi = v.rederived
    assert lo <= truth <= hi
