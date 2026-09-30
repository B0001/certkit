"""certkit-1y7: the complex-Hermitian tight (Temple/inertia) route.

`test_complex_hermitian.py` (certkit-3ta) built a complete but partial
vertical slice for complex Hermitian operators: a complex interval type
(`CIv`), an exact Hermitian symmetry check, and only the matrix-free
`hermitian_gershgorin_rayleigh` route -- explicitly leaving the tight route
unimplemented ("needs an interval LDL^T over CIv, which is unimplemented").

This file covers what closes that gap: `count_eigenvalues_below_hermitian`
(interval LDL^H of `A - beta*I` plus Sylvester's law of inertia for Hermitian
congruence, in checker.py), the `hermitian_temple_inertia` rule built on it,
and `CIv.scale` (interval.py) -- the one new arithmetic primitive the
factorisation needed (multiplication by a real interval scalar, the natural
companion to the division-by-real-interval `CIv.__truediv__` already had).

What this file has to show, matching `test_complex_hermitian.py`'s standard
and `test_exact_oracle.py`'s cross-checking discipline:

- soundness against an independent oracle (`numpy.linalg.eigvalsh`), across
  many random complex Hermitian matrices, not just one hand-picked case;
- exact agreement with the real route (`count_eigenvalues_below`) on
  real-valued matrices embedded as complex -- the two algorithms should be
  indistinguishable when the imaginary part is identically zero, and this
  needs no floating-point ground truth at all, just the real route as an
  independent oracle for the same claim;
- an exact (zero floating-point rounding in the ground truth) case, so the
  comparison is not "close to LAPACK" but "correct";
- that the tight route really is tighter than the matrix-free route on the
  same operator and witness, i.e. it delivers what its name promises, not
  just a second way to reach the same width;
- the same abstain-not-degrade discipline as every other route: a genuinely
  tight gap aborts with an honest ABSTAIN (never a crash, never a falsely
  narrow VERIFIED), a tampered witness is caught, and a rule/operator-kind
  mismatch abstains cleanly;
- the `DENSE_LIMIT` gate on `DenseHermitianComplex.interval_rows()` actually
  refuses to materialise past the limit, exactly like the real dense route.
"""

from __future__ import annotations

import numpy as np
import pytest

from certkit.checker import check, count_eigenvalues_below, count_eigenvalues_below_hermitian
from certkit.interval import IntervalError
from certkit.operators import DENSE_LIMIT, decode_operator, encode_dense_hermitian, operator_ref
from certkit.producer import certify_lambda_min_hermitian, certify_lambda_min_hermitian_temple_inertia
from certkit.schema import SCHEMA_VERSION, f2h, seal


def _random_hermitian(seed: int, n: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    m = rng.standard_normal((n, n)) + 1j * rng.standard_normal((n, n))
    return (m + m.conj().T) / 2.0


def test_exact_oracle_and_tighter_than_matrixfree():
    """[[3, -4i], [4i, -3]] is traceless Hermitian with |off-diag|=4, so its
    exact eigenvalues are +-sqrt(3^2+4^2) = +-5 -- no LAPACK rounding
    anywhere in the ground truth. (Not the more obvious Pauli-Y [[0,-i],[i,0]]:
    its eigenvalues are also exactly +-1, but its zero diagonal makes the
    producer's midpoint beta=0 coincide *exactly* with a pivot, which aborts
    as a genuine gap-too-tight case -- the real route hits the identical
    coincidence on the real-embedded analogue [[0,1],[1,0]]. Nonzero diagonal
    entries here sidestep that without masking it; see
    `test_gap_too_tight_abstains_rather_than_guesses` below for that case
    covered on purpose.)

    Also checks the headline promise of a *tight* route: same operator, same
    witness vector, strictly narrower enclosure than
    `hermitian_gershgorin_rayleigh`.
    """
    rows = [[3, -4j], [4j, -3]]
    enc = encode_dense_hermitian(rows)

    cert, op = certify_lambda_min_hermitian_temple_inertia(enc)
    v = check(cert, op)
    assert v.ok, v.reason
    assert v.rule == "hermitian_temple_inertia"
    lo, hi = v.rederived
    assert lo <= -5.0 <= hi
    tight_width = hi - lo

    loose_cert, loose_op = certify_lambda_min_hermitian(enc)
    lv = check(loose_cert, loose_op)
    assert lv.ok, lv.reason
    llo, lhi = lv.rederived
    loose_width = lhi - llo

    assert tight_width < loose_width


@pytest.mark.parametrize("seed", range(8))
def test_verified_and_sound_against_numpy_eigvalsh(seed):
    """Random complex Hermitian matrices: every VERIFIED enclosure must
    actually contain numpy's independently computed smallest eigenvalue."""
    n = 6
    a = _random_hermitian(seed, n)
    truth = float(np.linalg.eigvalsh(a)[0])

    enc = encode_dense_hermitian(a.tolist())
    cert, op = certify_lambda_min_hermitian_temple_inertia(enc)
    v = check(cert, op)
    assert v.ok, v.reason
    assert v.rule == "hermitian_temple_inertia"
    lo, hi = v.rederived
    assert lo <= truth <= hi


@pytest.mark.parametrize("seed", range(6))
def test_count_matches_real_ldlt_on_real_embedded_matrices(seed):
    """A real symmetric matrix embedded as complex (zero imaginary part
    everywhere) must get *exactly* the same eigenvalue count from the
    complex LDL^H route as from the real LDL^T route, for every beta in a
    sweep -- the two algorithms are independent implementations of the same
    claim, and this needs no floating-point ground truth, just agreement.
    """
    rng = np.random.default_rng(seed)
    n = 6
    m = rng.standard_normal((n, n))
    a_real = (m + m.T) / 2.0
    a_complex = a_real.astype(complex)
    vals = np.linalg.eigvalsh(a_real)

    checked = 0
    for beta in np.linspace(vals.min() - 1.0, vals.max() + 1.0, 41):
        beta = float(beta)
        try:
            want = count_eigenvalues_below(a_real.tolist(), beta)
        except IntervalError:
            continue
        try:
            got = count_eigenvalues_below_hermitian(a_complex.tolist(), beta)
        except IntervalError:
            pytest.fail(f"complex route abstained where the real route did not (beta={beta})")
        assert got == want, (seed, beta, want, got)
        checked += 1
    assert checked > 10


@pytest.mark.parametrize("seed", range(8))
def test_count_matches_numpy_eigvalsh_count(seed):
    n = 6
    a = _random_hermitian(seed, n)
    vals = np.linalg.eigvalsh(a)
    rng = np.random.default_rng(1000 + seed)
    checked = 0
    for _ in range(20):
        beta = float(rng.uniform(vals.min() - 1.0, vals.max() + 1.0))
        try:
            got = count_eigenvalues_below_hermitian(a.tolist(), beta)
        except IntervalError:
            continue
        want = int(np.sum(vals < beta))
        assert got == want, (seed, beta, want, got)
        checked += 1
    assert checked > 5


def test_gap_too_tight_abstains_rather_than_guesses():
    """beta placed exactly on an eigenvalue makes A - beta*I singular: some
    pivot cannot be sign-determined, and the honest outcome is an
    IntervalError, not a guessed count.
    """
    rows = [[0, -1j], [1j, 0]]  # exact eigenvalues -1, +1
    with pytest.raises(IntervalError):
        count_eigenvalues_below_hermitian(rows, 1.0)


def test_tampered_witness_abstains_rather_than_falsely_verifying():
    """Same discipline as `test_complex_hermitian.py`'s analogous test:
    perturbing the witness after sealing must be caught by recomputation,
    not trusted from the sealed bracket."""
    rows = [[0, -1j], [1j, 0]]
    enc = encode_dense_hermitian(rows)
    cert, op = certify_lambda_min_hermitian_temple_inertia(enc)

    tampered = dict(cert)
    witness = dict(tampered["witness"])
    vec = [dict(e) for e in witness["vector"]]
    im = float.fromhex(vec[1]["im"])
    vec[1]["im"] = f2h(-im)  # the other eigenvector, not a rounding nudge
    witness["vector"] = vec
    tampered["witness"] = witness
    tampered = seal({k: v for k, v in tampered.items() if k != "seal"})

    v = check(tampered, op)
    assert not v.ok


def test_lying_gap_claim_abstains():
    """A witness claiming a `beta` that does not actually separate exactly
    one eigenvalue from the rest must be refused, not accepted on the
    producer's word -- the whole point of counting inline instead of
    trusting the witness's beta.
    """
    rows = [[0, -1j], [1j, 0]]  # eigenvalues -1, +1: nothing separates at 5
    enc = encode_dense_hermitian(rows)
    cert, op = certify_lambda_min_hermitian_temple_inertia(enc)

    tampered = dict(cert)
    witness = dict(tampered["witness"])
    witness["beta"] = f2h(5.0)  # both eigenvalues lie below 5: count is 2, not 1
    tampered["witness"] = witness
    tampered = seal({k: v for k, v in tampered.items() if k != "seal"})

    v = check(tampered, op)
    assert not v.ok
    assert "gap parameter not discharged" in v.reason


def test_zero_witness_abstains():
    rows = [[0, -1j], [1j, 0]]
    enc = encode_dense_hermitian(rows)
    cert, op = certify_lambda_min_hermitian_temple_inertia(enc)
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
    from certkit.operators import encode_dense

    real_enc = encode_dense([[1.0, 0.0], [0.0, 2.0]])
    cert = seal({
        "schema": SCHEMA_VERSION,
        "claim": {
            "operator_ref": operator_ref(real_enc),
            "kind": "lambda_min_enclosure",
            "enclosure": {"lo": f2h(0.0), "hi": f2h(1.0)},
        },
        "witness": {
            "rule": "hermitian_temple_inertia",
            "vector": [
                {"re": f2h(1.0), "im": f2h(0.0)},
                {"re": f2h(0.0), "im": f2h(0.0)},
            ],
            "beta": f2h(1.5),
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
            "rule": "temple_inertia",
            "vector": [f2h(1.0), f2h(0.0)],
            "beta": f2h(0.0),
        },
    })
    v = check(cert, complex_enc)
    assert not v.ok
    assert "not compatible" in v.reason


def test_dense_limit_gates_interval_rows():
    """Past `DENSE_LIMIT`, `interval_rows()` must refuse to materialise,
    exactly like the real dense backend -- the whole reason
    `hermitian_temple_inertia` has a "backend will not materialise"
    abstention path at all."""
    n = DENSE_LIMIT + 1
    rows = [[1.0 + 0j if i == j else 0j for j in range(n)] for i in range(n)]
    enc = encode_dense_hermitian(rows)
    op = decode_operator(enc)
    assert op.n == n
    assert op.interval_rows() is None
