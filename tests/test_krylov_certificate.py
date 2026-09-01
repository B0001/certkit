"""The one certificate in this repo that this repo did not produce.

certkit-jn1's premise was that a format nobody outside the project emits into
has not been tested against the thing it was built for. `examples/sample/
h2_sto3g_*.json` closes that: a QKSD `QuantumKrylovSolver` in a separate project
emitted it from a pyscf-built H2/sto-3g Hamiltonian (R = 0.74 A, Jordan-Wigner,
4 qubits, 15 Pauli terms, dimension 16). Nothing here can regenerate it.

That is exactly why it is worth a test. The pair is self-contained -- checking
it needs neither the producing project nor pyscf, qiskit, or numpy -- so the
claim "an unmodified checker verifies a real solver's bound" stops being a
sentence in a closed issue and becomes something a stranger can re-run.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from certkit.checker import check
from certkit.operators import decode_operator, operator_ref

SAMPLE = Path(__file__).resolve().parent.parent / "examples" / "sample"


def _load():
    cert = json.loads((SAMPLE / "h2_sto3g_certificate.json").read_text())
    op = json.loads((SAMPLE / "h2_sto3g_operator.json").read_text())
    return cert, op


def test_the_krylov_certificate_verifies_under_an_unmodified_checker():
    cert, op = _load()
    v = check(cert, op)
    assert v.ok, v.reason
    assert v.rule == "temple_inertia"

    # The exact FCI ground state for this Hamiltonian. The enclosure is the
    # producer's claim; that it brackets the true value is the whole point.
    lo, hi = (float(x) for x in v.rederived)
    assert lo <= -1.8523881735695890 <= hi
    assert hi - lo < 1e-8


def test_the_certificate_is_bound_to_this_operator_by_hash():
    """A certificate that could be re-pointed at a friendlier operator would
    prove nothing about this one."""
    cert, op = _load()
    assert operator_ref(op) == cert["claim"]["operator_ref"]


def test_the_operator_is_a_pauli_sum_not_a_materialised_matrix():
    """certkit-jn1.3: summing the terms into CSR makes (i,j) and (j,i)
    accumulate in different float orders -- asymmetric by 8.3e-17 at H4 scale,
    which the checker refuses. The Pauli backend avoids the question."""
    _, op = _load()
    assert op["kind"] == "pauli_sum_real"
    assert decode_operator(op).n == 16


def test_a_tampered_krylov_certificate_is_rejected():
    """The sample is only evidence if the checker would have caught a lie in it."""
    cert, op = _load()
    cert["claim"]["enclosure"]["lo"] = float.hex(-1.9)
    v = check(cert, op)
    assert not v.ok


@pytest.mark.parametrize("field", ["operator_ref", "kind"])
def test_a_certificate_pointing_elsewhere_is_rejected(field):
    cert, op = _load()
    cert["claim"][field] = "blake2b16:" + "0" * 32 if field == "operator_ref" else "nonsense"
    v = check(cert, op)
    assert not v.ok
