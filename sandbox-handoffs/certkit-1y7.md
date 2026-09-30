# certkit-1y7: complex-Hermitian tight (Temple/inertia) route

**Outcome: implemented, not infeasible.** `hermitian_temple_inertia`, the
complex analogue of `temple_inertia`, is landed with tests
(`tests/test_complex_temple_inertia.py`, 30 tests, all passing) and the full
suite is green at 229 tests. This closes the gap `certkit-3ta` deliberately
left open ("No complex Temple/inertia analog ... needs unimplemented interval
LDL^T over CIv").

## What changed, and how to reproduce it

### The math: interval LDL^H + Sylvester's law of inertia for Hermitian congruence

`certkit/checker.py`: new `count_eigenvalues_below_hermitian(rows, beta)` —
the complex analogue of the pre-existing `count_eigenvalues_below`. For
Hermitian `A`, unit-lower-triangular complex `L`, and real diagonal `D` with
`A = L D L^H`:

```
D[j]    = A[j][j] - sum_{k<j} |L[j][k]|^2 D[k]
L[i][j] = (A[i][j] - sum_{k<j} L[i][k] D[k] conj(L[j][k])) / D[j]
```

— exactly the real LDL^T recurrence with `conj(...)` inserted. Sylvester's
law of inertia extends to Hermitian congruence (same argument
`count_eigenvalues_below`'s docstring already makes for the real case: `L`
invertible ⇒ congruence by `L` cannot change the signature). So the count of
negative `D[j]` is the count of negative eigenvalues of `A - beta*I`, i.e.
eigenvalues of `A` strictly below `beta`, whenever every pivot is
sign-determined. If a pivot's interval straddles zero, the function raises
`IntervalError` — the honest ABSTAIN outcome, never a guess.

Reproduction:

```
uv run --extra dev python3 -c "
from certkit.checker import count_eigenvalues_below_hermitian
rows = [[3, -4j], [4j, -3]]  # exact eigenvalues +-5
print(count_eigenvalues_below_hermitian(rows, 0.0))   # -> 1
print(count_eigenvalues_below_hermitian(rows, -6.0))  # -> 0
print(count_eigenvalues_below_hermitian(rows, 6.0))   # -> 2
"
```

Built on top: `_hermitian_rayleigh_and_residual` (complex analogue of
`_rayleigh_and_residual`), `_temple_complex` (complex analogue of `_temple`),
and `_rule_hermitian_temple_inertia`, registered in `RULES` (claim kind
`lambda_min_enclosure`, `needs_vector=True`) and in `COMPLEX_RULES` (so the
existing cross-kind dispatch guard in `_verify_uncached` treats it as
complex-only and aborts cleanly rather than crashing if misapplied to a real
operator).

`certkit/interval.py`: one new primitive on the trusted `CIv` type,
`CIv.scale(self, r: Iv) -> CIv` — multiplication by a *real* interval scalar
(`(a+bi)*r = a*r + (b*r)i`). This is the real-scalar sibling of the
pre-existing `CIv.__truediv__`'s restriction to real divisors: general
complex×complex multiplication is `CIv.__mul__`, but scaling by a value
already known to be real (a Sylvester-law pivot, a Rayleigh quotient) is a
strictly simpler, exact-in-form operation that doesn't need it. Used for the
LDL^H off-diagonal update (`L[i][k].scale(D[k])`) and for the residual
computation in `_hermitian_rayleigh_and_residual` (`x[i].scale(mu)`).

`certkit/operators.py`: `DenseHermitianComplex.interval_rows()` — returns
`CIv` rows gated by `DENSE_LIMIT` (`== 256`), exactly mirroring
`DenseSymmetric.interval_rows`. `dense_rows()` is left at the base class's
`None`: nothing needs a float materialization of a complex operator today.

`certkit/producer.py`: `_temple_inertia_bracket_hermitian` (complex analogue
of `_temple_inertia_bracket`) and `certify_lambda_min_hermitian_temple_inertia`
(complex analogue of `certify_lambda_min`) — the untrusted producer side:
picks `beta = 0.5*(lam1+lam2)` from `numpy.linalg.eigh`, same strategy as the
real route, same "a bad guess only costs coverage, never soundness" property,
since the checker discharges the gap by its own inline inertia count.

### Soundness argument for the one genuinely new piece: the off-diagonal pivot-correction term

The one place a naive port could have introduced unsoundness: the diagonal
pivot correction term needs `|L[j][k]|^2`, a real, provably-nonnegative
quantity, from a complex `CIv` value. The naive route — `CIv` multiplication
by its own conjugate (`z * z.conj()`) and taking `.re`, trusting that the
imaginary part's interval arithmetic happens to produce an interval
containing zero — would work in practice but requires a new "trust me, it
cancels" argument on top of what's already proven. Instead,
`count_eigenvalues_below_hermitian` computes `sqnorm([ljk.re, ljk.im])`, using
the *existing*, already-proven-nonnegative `sqnorm` helper (the same one
`csqnorm`/the rest of the codebase already relies on for magnitude-squared
computations). So every pivot `D[j]` is built entirely from real `Iv`
arithmetic, and its sign is exactly as well-defined as any real pivot in
`count_eigenvalues_below` — no new soundness argument was introduced, an
existing one was reused.

**No constants were transcribed.** Every bound above (`|L[j][k]|^2 D[k]`
subtracted at each step, the pivot sign test, the Temple inequality's
`mu - rho^2/(beta-mu)`) is derived inline from the LDL^H recurrence and from
`_temple`'s pre-existing real-valued derivation, generalized with `conj(...)`
and `Re<.>` where the complex inner product requires it — not copied from a
paper. `DENSE_LIMIT` (256) is an unchanged, pre-existing runtime cap, not a
new constant.

### No documented limit was softened

The only documented limit this bead touched was the README's "Not done yet"
bullet stating the complex Temple/inertia route doesn't exist — replaced,
since it's now false, not softened. No existing ABSTAIN threshold, tolerance,
or bound in the real-valued code was touched or loosened. The new route's own
abstention conditions (gap-too-tight pivot, `below != 1` gap-not-discharged,
`op.interval_rows() is None` backend-can't-materialize) are exact
mathematical conditions, not tunable thresholds — there is nothing there to
loosen.

One near-miss worth recording, because it looked at first like a bug: the
exact-oracle test originally used the Pauli-Y matrix `[[0,-i],[i,0]]`
(eigenvalues exactly ±1). With the producer's `beta = 0.5*(lam1+lam2) = 0`,
the very first pivot is `A[0][0] - beta = 0 - 0 = 0` exactly — a genuine
"gap too tight" (well, "pivot exactly zero") abstention, *not* a bug in the
new code. Confirmed this is not new: the identical real-embedded matrix
`[[0,1],[1,0]]` hits the exact same abstention through the pre-existing real
`count_eigenvalues_below([[0,1],[1,0]], 0.0)`. This is an inherent property
of `beta = midpoint` occasionally landing exactly on a pivot by coincidence
of matrix structure, present in both the real and complex routes, not
something introduced or fixed here. The exact-oracle test now uses
`[[3,-4i],[4i,-3]]` (traceless, off-diagonal magnitude 4, exact eigenvalues
±5) instead, which doesn't hit the coincidence, and the coincidence itself is
covered on purpose by `test_gap_too_tight_abstains_rather_than_guesses`
(`beta` placed exactly on a Pauli-Y eigenvalue).

## Tests added

`tests/test_complex_temple_inertia.py` (30 tests):

- `test_exact_oracle_and_tighter_than_matrixfree` — zero-rounding-error
  ground truth (`[[3,-4i],[4i,-3]]`, exact eigenvalues ±5), and confirms the
  headline promise: same operator, same witness, strictly narrower enclosure
  than `hermitian_gershgorin_rayleigh`.
- `test_verified_and_sound_against_numpy_eigvalsh` (×8 seeds) — random
  complex Hermitian matrices, enclosure must contain `numpy.linalg.eigvalsh`'s
  true smallest eigenvalue.
- `test_count_matches_real_ldlt_on_real_embedded_matrices` (×6 seeds, ×~15-40
  beta values each) — real symmetric matrix embedded as complex must get
  *exactly* the same count from `count_eigenvalues_below_hermitian` as from
  `count_eigenvalues_below`, across a beta sweep. Two independent
  implementations of the same claim, no floating-point ground truth needed.
- `test_count_matches_numpy_eigvalsh_count` (×8 seeds) — count agrees with
  `numpy.linalg.eigvalsh`-derived counts on random betas.
- `test_gap_too_tight_abstains_rather_than_guesses` — `beta` on an exact
  eigenvalue raises `IntervalError`.
- `test_tampered_witness_abstains_rather_than_falsely_verifying`,
  `test_lying_gap_claim_abstains`, `test_zero_witness_abstains` — adversarial
  witness tampering after sealing must be caught by recomputation.
- `test_complex_rule_against_real_operator_abstains_cleanly`,
  `test_real_rule_against_complex_operator_abstains_cleanly` — cross-kind
  dispatch guard.
- `test_dense_limit_gates_interval_rows` — `DenseHermitianComplex.interval_rows()`
  actually refuses to materialize past `DENSE_LIMIT`.

`tests/test_complex_hermitian.py`: module docstring updated to remove the
now-false "deliberately no complex Temple/inertia analogue" claim and point
to the new test file.

## Documentation updated

- `README.md`: route table (new `hermitian_temple_inertia` row), "Complex
  Hermitian operators" section (new paragraph describing the route, replacing
  the "what is not here" paragraph that described it as unimplemented
  research), "Not done yet" section (replaced the complex-Temple-inertia
  bullet with a bullet for the still-open Lean-formalization follow-up,
  `certkit-v3e`), and the pinned test count `199 → 229` (`tests/                229
  tests: ...`).
- `CLAUDE.md`, `AGENTS.md`: pinned test count `199 → 229`
  (`uv run --extra dev pytest tests     # 229 passing, ...`) — re-measured via
  `uv run --extra dev pytest tests --collect-only -q`, not copied from a
  prior paragraph. `tests/test_doc_pass_count.py` enforces this three-way
  consistency and was failing before this edit (`doc says 199, live
  collection says 229`) and passes after.
- `CHANGELOG.md`: new "Unreleased" entry, `certkit-1y7`.

## Follow-up bead filed

`certkit-v3e` — Lean formalization of the two soundness obligations this
route's docstring currently only argues in prose (LDL^H reconstruction
correctness; Sylvester's law of inertia for Hermitian congruence), following
the `certkit-sp1` precedent for the banded backward-error route. Filed as a
separate bead per this bead's own scope note ("a case for Lean formalization
filed separately if warranted") and per the standing instruction not to do
out-of-scope work in this session. `bd export -o issues.jsonl` was run after
filing it.

## What was decided not to do, and why

- **Not extending `tests/exact_oracle.py` (Fraction-exact ground truth) to
  complex/Gaussian rationals.** The existing `test_complex_hermitian.py`
  already sets precedent of using `numpy.linalg.eigvalsh` as its oracle
  rather than `exact_oracle.py`; matching that precedent keeps this bead's
  scope to what it asked for (a Temple/inertia route + tests at the standard
  this repo already applies to complex Hermitian code), not a second,
  larger, orthogonal feature (a Gaussian-rational exact arithmetic layer).
  The one *exactly*-verifiable case in the new test file
  (`[[3,-4i],[4i,-3]]`, eigenvalues exactly ±5) covers the "not just close to
  LAPACK" property that `exact_oracle.py` exists to provide, without needing
  the larger machinery.
- **Not adding a `conformance/` case for the new route.** `conformance/`
  already had in-flight, uncommitted changes from other sessions
  (`verified_banded_sturm_be`, `abstain_banded_sturm_be_tampered`) present in
  the tree before this session started; adding another case here was not
  required by this bead's acceptance criteria and risked scope creep into
  work this bead didn't ask for. Left for a future bead if wanted.
- **Not implementing the Lean proof itself in this session.** Filed as
  `certkit-v3e` instead, per this bead's own scope note and the standing
  "discover work outside scope → file a bead, don't do it now" instruction.

## What could not be verified

- No cross-check against an independent complex-eigensolver implementation
  besides `numpy.linalg.eigvalsh` (e.g. an independent from-scratch complex
  QR algorithm) was available in this environment; `numpy.linalg.eigvalsh`
  (LAPACK `zheevd`/similar) is treated as ground truth for the randomized
  tests, consistent with how `test_complex_hermitian.py` already treats it.
  The zero-floating-point-rounding exact case (`[[3,-4i],[4i,-3]]`, ±5)
  covers the gap this leaves.
- Performance/scaling behavior of `count_eigenvalues_below_hermitian` near
  `DENSE_LIMIT` (n=256) was not benchmarked — only that the gate itself
  fires correctly at n=257 with a trivial (near-diagonal) matrix, cheap to
  construct. The real dense LDL^T route's O(n^3) performance at n=256 is a
  pre-existing, unchanged characteristic this bead didn't need to
  re-measure.

## Final verbatim test-run line

```
$ uv run --extra dev pytest tests -q
........................................................................ [ 31%]
........................................................................ [ 62%]
........................................................................ [ 94%]
.............                                                            [100%]
229 passed in 36.41s
```

Trust boundary re-confirmed after all edits to `interval.py`, `operators.py`,
`checker.py`:

```
$ uv run --extra dev pytest tests/test_trust_boundary.py -q
....                                                                     [100%]
4 passed in 0.18s
```

No-dependency CLI sanity check (unrelated sample certificate, confirms the
CLI/checker pipeline as a whole is unbroken by these changes):

```
$ /tmp/venv/bin/python3 -m certkit.cli check examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

(This environment has no bare `python3` on `PATH` — only `uv run python3` and
a pre-existing `/tmp/venv`, which does have numpy installed, so this run does
not by itself demonstrate the checker's zero-dependency property; that
property is what `tests/test_trust_boundary.py` verifies mechanically, via a
subprocess with numpy made unimportable, and it passed above.)

## Git status at handoff (not committed, per conservative git policy)

```
$ git status --short
 M AGENTS.md
 M CHANGELOG.md
 M CLAUDE.md
 M README.md
 M TCB.md                              (pre-existing, not from this bead)
 M certkit/checker.py
 M certkit/interval.py
 M certkit/operators.py
 M certkit/producer.py
 M conformance/README.md               (pre-existing, not from this bead)
 M conformance/manifest.json           (pre-existing, not from this bead)
 M issues.jsonl
 M lean/Certkit.lean                   (pre-existing, not from this bead)
 M lean/Certkit/Soundness.lean         (pre-existing, not from this bead)
 M sandbox-prompt.md                   (pre-existing, not from this bead)
 M tests/test_complex_hermitian.py
?? conformance/cases/...               (pre-existing, not from this bead)
?? lean/Certkit/BandedBackwardError.lean  (pre-existing, not from this bead)
?? sandbox-handoffs/certkit-2sc.md     (pre-existing, not from this bead)
?? sandbox-handoffs/certkit-ljk.md     (pre-existing, not from this bead)
?? sandbox-handoffs/certkit-sp1.md     (pre-existing, not from this bead)
?? tests/test_complex_temple_inertia.py
```

Files this bead actually changed: `AGENTS.md`, `CHANGELOG.md`, `CLAUDE.md`,
`README.md`, `certkit/checker.py`, `certkit/interval.py`,
`certkit/operators.py`, `certkit/producer.py`, `issues.jsonl`,
`tests/test_complex_hermitian.py` (docstring only),
`tests/test_complex_temple_inertia.py` (new). The remaining modified/
untracked paths (`TCB.md`, `conformance/*`, `lean/*` other than the two
edits above being unrelated bookkeeping, `sandbox-prompt.md`, other
`sandbox-handoffs/*.md`) were already present in the working tree at session
start (per the initial `git status` this session was handed) and were left
untouched.

Suggested commands for a human to run (not executed by this session):

```
git add AGENTS.md CHANGELOG.md CLAUDE.md README.md \
        certkit/checker.py certkit/interval.py certkit/operators.py certkit/producer.py \
        issues.jsonl tests/test_complex_hermitian.py tests/test_complex_temple_inertia.py
git commit -m "certkit-1y7: complex-Hermitian tight (Temple/inertia) route (hermitian_temple_inertia)"
```

(Left as separate hunks/files from the other pre-existing uncommitted work in
the tree so a reviewer can commit or discard them independently.)
