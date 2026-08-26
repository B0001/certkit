# certkit-3ta — Complex Hermitian operators

## Verdict

Closing. Built a complete, sound, minimal vertical slice for complex
Hermitian operators: the complex interval type (found already in place from
an earlier session on this same bead, audited and reused as-is), an exact
Hermitian symmetry check, one fully working matrix-free certification route
(`hermitian_gershgorin_rayleigh`), producer support, and tests (fuzz +
exact-oracle + adversarial). Full suite is green at 154 passed (baseline
127, +27 new tests, 0 regressions, 0 new skips). Deliberately did **not**
build a complex analogue of the Temple/inertia (interval-LDL^T) route — see
"What I chose not to do" below — so this bead closes with a documented,
honest limitation rather than false parity with the real-symmetric side.

## What's new, by file

### `certkit/interval.py` — found already in place, not written by me this session

`CIv` (complex interval rectangle `re + i*im`, built from `Iv`), `CZERO`,
`cdot` (Hermitian inner product `sum_i conj(u_i) v_i`), `csqnorm` (direct
real non-negative enclosure of `sum |u_i|^2`). This was sitting uncommitted
in the tree when I claimed the bead (claimed 2026-08-24 by a prior session,
per `bd show`). I did not assume it was correct — I read it end to end and
checked, by hand, before building anything on top of it:

- `CIv.__mul__`'s formula `(ac-bd) + (ad+bc)i` is the standard complex
  product, built from already-sound `Iv` ops, so it inherits soundness.
- `CIv.mag_ub` computes `max(|re.lo|,|re.hi|)`, `max(|im.lo|,|im.hi|)`
  (each a sound per-axis bound), then `sqrt(re_mag^2+im_mag^2).hi` in
  outward-rounded `Iv` arithmetic — a sound upper bound on `|z|` for every
  point in the rectangle (the true per-point modulus is dominated by the
  per-axis bounds, so the combined bound can only be equal or larger).
- `cdot`'s conjugate-linear-in-first-argument convention (`<u|v> :=
  sum conj(u_i) v_i`) is internally consistent with `csqnorm` (`cdot(x,x)`
  and `csqnorm(x)` agree on the real part, up to interval width).
- It had **zero test coverage** anywhere in the suite before this session —
  no file referenced `CIv`/`cdot`/`csqnorm`. That gap is now closed (see
  below). I found no bugs in it; every property I checked by hand also
  checked out under 3000-trial fuzzing against `fractions.Fraction` as an
  exact oracle.

I did not modify this file.

### `certkit/operators.py` — new this session

- `DenseHermitianComplex(Operator)`: stores explicit `(re, im)` rows,
  pre-converts them to `CIv` once at construction. `apply`/`row` are
  matrix-free-shaped (loop over stored `CIv` rows) but the backend itself
  is dense storage, mirroring `DenseSymmetric`'s role for the real side.
  `check_symmetric` requires **exact** equality: every diagonal entry's
  imaginary part must be `== 0.0`, and every off-diagonal pair `(a_ij,
  a_ji)` must satisfy `re_ij == re_ji and im_ij == -im_ji` — not
  approximately, the same discipline `DenseSymmetric.check_symmetric`
  already holds the real case to. `interval_rows`/`dense_rows` are left at
  the base class's `None`: there is no interval-LDL^T route for this
  backend (see "What I chose not to do"), so the base class not
  implementing them is honest, not an oversight.
- `encode_dense_hermitian` / `_decode_dense_hermitian`, registered in
  `_DECODERS` under `"dense_hermitian_complex"`. Encoding uses the same
  `f2h` hex-float scheme the rest of the schema uses, per-component
  (`re`/`im` each independently hex-encoded) — no new encoding mechanism
  invented.
- Module docstring updated to list the fourth backend.

### `certkit/checker.py` — new this session (mixed in the diff with
`certkit-jn1.2`'s `gen_gershgorin_rayleigh`/`_gershgorin_upper`, already
in the tree before I started — see "What I did not touch")

- `_gershgorin_lower_complex(op) -> Iv`: the Gershgorin floor for a complex
  Hermitian operator. Disc radius is a modulus sum (`CIv.mag_ub` per
  off-diagonal entry) rather than an absolute-value sum; the "smallest
  disc's left endpoint is a sound global floor" argument transfers
  verbatim from the real case because Hermitian diagonal entries and
  Hermitian eigenvalues are both exactly real (a standard fact I checked
  independently, not transcribed from anywhere: for Hermitian A, `x^H A x`
  real for all x forces every eigenvalue real, by taking x an eigenvector).
- `_cwitness_vector(witness, op) -> list[CIv]`: decodes a witness vector of
  `{"re": hex, "im": hex}` objects into `CIv`s, mirroring `_witness_vector`.
- `_rule_hermitian_gershgorin_rayleigh`: the complex analogue of
  `gershgorin_rayleigh`. Full derivation is in its docstring; summary,
  since this is the load-bearing part of the bead:
  - **Upper bound**: `mu(x) := Re<x|Ax>/<x|x>`. Rayleigh-Ritz for
    self-adjoint operators holds in the Hermitian inner product exactly as
    it does in the real Euclidean one (real-symmetric is the zero-imaginary
    special case). `<x|Ax>` is provably real whenever `A` is Hermitian:
    `conj(<x|Ax>) = <Ax|x> = x^H A^H x = x^H A x = <x|Ax>` (using `A^H = A`,
    which `check_symmetric` enforces exactly before any rule ever runs), so
    `<x|Ax>` equals its own conjugate and is real — meaning `cdot(x,ax).re`
    is a sound `Iv` enclosure of that real value, and nothing is being
    silently discarded by only using `.re`.
  - **Lower bound**: `_gershgorin_lower_complex`, unconditional and
    witness-free, exactly as `_gershgorin_lower` alone is the floor in
    `gershgorin_rayleigh`.
  - Same "Gershgorin floor exceeds Rayleigh ceiling" inconsistent-witness
    abstain and zero-witness abstain as the real rule.
- Registered as `"hermitian_gershgorin_rayleigh"` in `RULES` under claim
  kind `lambda_min_enclosure`.
- **Cross-kind dispatch guard** (`COMPLEX_RULES`, `COMPLEX_OPERATOR_KINDS`,
  and the `is_complex_op != is_complex_rule` check added to
  `_verify_uncached`): without it, invoking `hermitian_gershgorin_rayleigh`
  against a real (`Iv`-based) operator, or any real rule against a complex
  operator, would raise an uncaught `AttributeError`/`TypeError` from
  mixing `Iv` and `CIv` arithmetic, since `_verify_uncached`'s existing
  `try/except` only catches `Unresolved`/`SchemaError`/`IntervalError`.
  This is not itself a false-VERIFIED risk (a crash produces no verdict at
  all, not a wrong one), but it is exactly the kind of "this rule and this
  operator were never meant to meet" situation the repo's ABSTAIN
  philosophy says should degrade to ABSTAIN, not to an unhandled exception.
  Verified directly (not just via the test suite) — see "Exact verdict
  changes" below.

### `certkit/producer.py` — new this session (mixed in the diff with
`certkit-jn1.2`'s `certify_lambda_min_generalized` and `certkit-bz5`'s
`certify_lambda_min_from_witness`, already in the tree — see "What I did
not touch")

- `_as_encoding_hermitian`: accepts either an already-encoded
  `dense_hermitian_complex` dict or a plain list-of-lists / ndarray of
  Python `complex`, mirroring `_as_encoding`'s flexibility on the real side.
- `certify_lambda_min_hermitian(operator, *, slack=1e-9)`: the untrusted
  producer half. Uses `numpy.linalg.eigh` (LAPACK's Hermitian eigensolver)
  to find a trial ground vector, computes its own Rayleigh quotient and
  Gershgorin floor as a sanity padding target, and emits a certificate
  witnessing `hermitian_gershgorin_rayleigh`. Exactly like
  `certify_lambda_min_matrixfree` on the real side, a bad/unconverged trial
  vector here only ever costs coverage — the checker recomputes everything
  from the operator and the witness vector alone, never trusts anything
  the producer says about `mu` or the floor.

### `tests/test_interval.py` — extended this session

Added (import line updated to pull in `CIv`/`cdot`/`csqnorm`; 10 new test
functions, 3 of them parametrized so 18 total collected items in the file,
up from 8):

- `test_civ_binary_ops_enclose_exact_result` (add/sub/mul): exhaustive
  corner-point fuzzing against `Fraction`-based exact complex arithmetic,
  3000 trials each, mirroring the existing `Iv` binary-op test's structure.
- `test_civ_conj_negates_imaginary_part_only`.
- `test_civ_mag_ub_is_a_sound_upper_bound`: for every sampled point in the
  rectangle, `re^2+im^2 <= mag_ub^2` as an exact `Fraction` comparison (no
  float sqrt in the test itself).
- `test_civ_exact_round_trips_a_python_complex`.
- `test_civ_division_by_straddling_real_interval_abstains`.
- `test_cdot_encloses_the_hermitian_inner_product`: compares `cdot`'s
  enclosure against a hand-computed exact conjugate-linear inner product.
- `test_cdot_of_a_vector_with_itself_is_real`: `cdot(x,x).im.contains_zero`
  for every sampled `x`.
- `test_csqnorm_encloses_sum_of_squared_magnitudes_and_is_nonnegative`.

### `tests/test_complex_hermitian.py` — new file this session (17 tests)

- `test_pauli_y_exact_oracle`: `[[0,-i],[i,0]]`, exact eigenvalues ±1 (no
  LAPACK rounding in the ground truth), verified via `certify_lambda_min_
  hermitian` + `check()`.
- `test_verified_and_sound_against_numpy_eigvalsh` (8 seeds): random 6x6
  complex Hermitian matrices, every VERIFIED enclosure checked to actually
  contain `numpy.linalg.eigvalsh`'s independently computed smallest
  eigenvalue.
- `test_non_hermitian_matrix_is_rejected_exactly` /
  `test_non_real_diagonal_is_rejected`: `decode_operator` (which calls
  `check_symmetric`) raises `SchemaError` on an exactly-non-Hermitian input.
- `test_non_hermitian_matrix_abstains_through_check`: the same rejection,
  through the public `check()` path — ABSTAIN, not a raised exception,
  since that's the boundary an actual producer/verifier calls.
- `test_tampered_witness_abstains_rather_than_falsely_verifying`: flips the
  sign of one imaginary witness component after sealing (the honest
  eigenvector for eigenvalue -1 becomes the *other*, real, different
  eigenvector for eigenvalue +1) — confirmed to ABSTAIN, not silently
  re-verify the old bracket.
- `test_witness_dimension_mismatch_abstains`, `test_zero_witness_abstains`.
- `test_complex_rule_against_real_operator_abstains_cleanly` /
  `test_real_rule_against_complex_operator_abstains_cleanly`: the dispatch
  guard in both directions, asserting on the specific "not compatible"
  reason string, not just `not v.ok`.

### `README.md` — new this session

- New row in the "Operators, not matrices" table for `dense_hermitian_complex`.
- New row in the "Two sound routes, one tradeoff" table for
  `hermitian_gershgorin_rayleigh`.
- New "## Complex Hermitian operators" section (after "The generalized
  eigenproblem", before "Counting without a dense factorisation"),
  documenting the derivation summary and explicitly stating the Temple/
  inertia gap.
- **"## Not done yet"**: replaced the old blanket "Complex Hermitian
  operators." line with a narrower, accurate one: "A tight (Temple/inertia)
  route for complex Hermitian operators — only the matrix-free Gershgorin +
  Rayleigh route exists... It needs an interval LDL^T over `CIv`, which is
  unimplemented." This is the "documented limits must survive" rule in
  practice: the old line was about to become false (something *was* built),
  but I did not delete it outright — I re-scoped it to the part that is
  still genuinely true, rather than upgrading to "done" or softening it
  into vagueness.

## Exact verdict changes, with commands demonstrating them

Before this session, no certificate involving a complex Hermitian operator
could be checked at all (no backend, no rule existed). After:

```
$ uv run python -c "
from certkit.checker import check
from certkit.operators import encode_dense_hermitian
from certkit.producer import certify_lambda_min_hermitian
enc = encode_dense_hermitian([[0, -1j], [1j, 0]])
cert, op = certify_lambda_min_hermitian(enc)
v = check(cert, op)
print(v.status, v.rule, v.rederived)
"
VERIFIED hermitian_gershgorin_rayleigh (-1.0000000000000009, -0.9999999999999983)
```

Tampered-witness case, confirmed ABSTAIN (not a stale VERIFIED):

```
$ uv run python -c "
from certkit.checker import check
from certkit.operators import encode_dense_hermitian
from certkit.producer import certify_lambda_min_hermitian
from certkit.schema import f2h, seal
enc = encode_dense_hermitian([[0, -1j], [1j, 0]])
cert, op = certify_lambda_min_hermitian(enc)
w = dict(cert['witness']); vec = [dict(e) for e in w['vector']]
vec[1]['im'] = f2h(-float.fromhex(vec[1]['im']))
w['vector'] = vec
t = dict(cert); t['witness'] = w
t = seal({k: v for k, v in t.items() if k != 'seal'})
print(check(t, op).status, check(t, op).reason)
"
ABSTAIN claimed interval is tighter than the re-derived enclosure
```

Cross-kind dispatch guard, confirmed ABSTAIN not crash (a rule built for
`CIv` invoked against a real operator):

```
ABSTAIN rule 'hermitian_gershgorin_rayleigh' is not compatible with operator kind 'dense_symmetric_real'
```

(All three transcribed verbatim from actual runs this session, not
hand-written expected output.)

## Every bound/tolerance/threshold touched, with derivation

- `_gershgorin_lower_complex`'s disc radius: `sum(v.mag_ub for off-diagonal
  v)`, derived from the Gershgorin circle theorem generalized to complex
  matrices (disc of radius = row's off-diagonal modulus sum, centered at
  the diagonal entry) — not transcribed from a paper, derived from
  `CIv.mag_ub`'s already-proven per-entry bound plus the standard real-case
  argument this repo already uses in `_gershgorin_lower`.
- `certify_lambda_min_hermitian`'s `slack=1e-9` default: copied from the
  same default already used by every other `certify_*` function in
  `producer.py` (`certify_lambda_min`, `certify_lambda_min_matrixfree`,
  etc.) for consistency, not independently derived — it is producer-side
  padding on the untrusted side, not a soundness-relevant constant; the
  checker never sees or trusts it, it only recomputes from the witness.
  Flagging this explicitly per the "no transcribed constants" rule: this
  one constant is a convention match, not a matrix-derived bound, and I
  want that distinction visible rather than glossed over.
- No other numeric constant was added or touched.

## Documented limits: none softened, one narrowed honestly

The only pre-existing documented limit this bead's work touches is "Not
done yet: Complex Hermitian operators." I did not delete it or claim full
parity — I re-measured what actually changed (a matrix-free route now
exists; a tight route does not) and rewrote the line to say exactly that,
per "What I touched" above. I did not touch any other documented limit in
"Known limits" or "Not done yet" (DENSE_LIMIT=160, sturm_be
tridiagonal-only, Gershgorin's general weakness, etc.) — none of those are
affected by this bead's scope.

## What I chose not to do, and why

- **No complex analogue of `temple_inertia`/`sturm`.** That needs an
  interval-LDL^T factorization over `CIv` (complex pivoting, complex
  Sylvester's-law-of-inertia bookkeeping) — a materially different,
  unimplemented piece of numerical work, not a small extension of the
  existing real banded solver. Standing repo context frames the real-vs-
  complex interval-LDL^T gap as "real research, not plumbing," reserved for
  a different bead (certkit-ph1 territory). Attempting it here would have
  meant either rushing an unreviewed factorization (unacceptable for a
  soundness-critical component) or silently degrading the bead's scope
  without saying so. I did neither — I built the one honest, complete route
  that was tractable in scope, and documented the gap explicitly instead of
  hiding it.
- **No complex banded/backward-error/Sturm variants**, for the same reason
  — they all bottom out in the same missing complex factorization.
- **No general complex/complex division on `CIv`.** The type (from the
  prior session) already documents this as an intentional restriction —
  `__truediv__` only accepts a real `Iv` divisor, which is all any rule
  here needs (normalizing by a positive squared norm). I did not extend it,
  since a sound general complex division is materially trickier and
  genuinely unused.
- **Did not touch `certkit-jn1.2`/`certkit-bz5`'s already-uncommitted code**
  mixed into the same files (`gen_gershgorin_rayleigh`,
  `certify_lambda_min_generalized`, `certify_lambda_min_from_witness`,
  `_witness_vector`), beyond reading enough of the surrounding file to place
  my additions correctly and reusing existing helpers (`_enclosure`,
  `_implies`, `_abstain`, `h2f`) rather than duplicating them.

## What I could not verify

- I did not independently re-derive numpy's `eigh` (LAPACK's Hermitian
  eigensolver) correctness — it is untrusted producer-side machinery by
  design, and the checker never relies on it being right; the fuzz test
  (`test_verified_and_sound_against_numpy_eigvalsh`) uses it only as an
  oracle to compare the *checker's* sound enclosure against, which is the
  standard this repo's other exact-oracle/numpy-oracle tests already use.
- I did not stress-test extreme dimensions (the complex route has no
  `DENSE_LIMIT`-style cap because it is matrix-free application/row-access
  only, same as `PauliSumReal`/`SparseCSRSymmetric` — but I did not run a
  large-n timing/soundness sweep the way `certkit-8q0`'s handoff describes
  for the real tridiagonal case; out of scope for a first vertical slice,
  and nothing in this bead's acceptance criteria asked for it).
- I did not run a large adversarial fuzz sweep beyond the 8-seed
  `test_verified_and_sound_against_numpy_eigvalsh` parametrization and the
  3000-trial `CIv`/`cdot`/`csqnorm` arithmetic fuzz in `test_interval.py`.
  If a reviewer wants a bigger sweep (hundreds of random Hermitian matrices
  against `eigvalsh`, as `certkit-jn1.2`'s handoff ran ad hoc for the
  generalized pencil), it's cheap to add — I judged 8 seeds + exhaustive
  arithmetic-level fuzzing sufficient for this vertical slice, consistent
  with this repo's existing per-rule test sizes (e.g.
  `test_generalized.py` also uses `seed in range(6)`).

## What I did not touch (other beads' uncommitted work, found already in
## the shared tree when I claimed this bead)

Per `certkit-jn1.2`'s own handoff (`sandbox-handoffs/certkit-jn1.2.md`),
this tree is shared across concurrent sessions/beads and was already
carrying uncommitted work before I started:

- `examples/banded_demo.py`, `pyproject.toml`, `tests/test_backward.py`,
  `tests/test_banded.py`, `uv.lock` — `certkit-8q0` (producer-side
  eigensolver improvements).
- `tests/test_generalized.py` (untracked) — `certkit-jn1.2`.
- `tests/test_complex_witness_transcription.py` (untracked) —
  `certkit-bz5`.
- The `gen_gershgorin_rayleigh` rule and `_gershgorin_upper` helper in
  `checker.py`, and `certify_lambda_min_generalized`/
  `certify_lambda_min_from_witness` in `producer.py` — `certkit-jn1.2` and
  `certkit-bz5` respectively, mixed into the same files as my additions.
- `issues.jsonl` shows as modified in `git status` from bead-tracking
  activity across this shared tree, not specifically from this session's
  bead updates until I ran `bd close` below.

I left all of it exactly as found. I did not review it for correctness
(each belongs to its own bead), and it is not this handoff's claim one way
or the other about its soundness.

## Final test-run line (verbatim)

```
$ uv run pytest tests -q
........................................................................ [ 46%]
........................................................................ [ 93%]
..........                                                               [100%]
154 passed in 16.43s
```

(Baseline at session start, before any of my changes: 127 passed — measured
directly by running the suite before touching any code, not taken from the
task prompt's stated 106. +27 new tests this session: 10 in
`test_interval.py`, 17 in `test_complex_hermitian.py`. 0 regressions, 0 new
skips.)

Trust boundary, re-confirmed after adding imports to `checker.py`/
`operators.py`/`producer.py` (all new imports are from `.interval`, already
stdlib-only):

```
$ uv run pytest tests/test_trust_boundary.py -v
tests/test_trust_boundary.py::test_trusted_modules_do_not_import_the_producer PASSED
tests/test_trust_boundary.py::test_trusted_modules_import_only_stdlib_and_each_other PASSED
tests/test_trust_boundary.py::test_checker_runs_in_a_process_where_numpy_is_unimportable PASSED
tests/test_trust_boundary.py::test_witness_carries_no_producer_computed_bound PASSED
4 passed in 0.11s
```

No-dependency checker run:

```
$ uv run python3 -m certkit.cli check examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

## Git state at handoff

Not committed, per this repo's git policy — the tree contains other beads'
uncommitted work alongside mine (see above). Suggested commands for
whoever reviews and decides how to split this:

```
git status
git diff certkit/interval.py            # pre-existing (CIv/cdot/csqnorm), not written by me
git diff certkit/operators.py           # certkit-3ta: DenseHermitianComplex + encode/decode
git diff certkit/checker.py             # mixed: hermitian_gershgorin_rayleigh (3ta)
                                          #   + gen_gershgorin_rayleigh (jn1.2, pre-existing)
git diff certkit/producer.py            # mixed: certify_lambda_min_hermitian (3ta)
                                          #   + certify_lambda_min_generalized (jn1.2)
                                          #   + certify_lambda_min_from_witness (bz5)
git diff tests/test_interval.py         # certkit-3ta: CIv/cdot/csqnorm fuzz tests
git diff README.md                      # certkit-3ta: docs
git add tests/test_complex_hermitian.py # certkit-3ta: new end-to-end test file
git add tests/test_generalized.py               # jn1.2, not mine
git add tests/test_complex_witness_transcription.py  # bz5, not mine
bd export -o issues.jsonl               # run after bd close below; re-run if beads change again before commit
```

I did not run `git add`, `git commit`, `git push`, or `bd dolt push` —
against this repo's git policy without explicit instruction, and this tree
holds multiple beads' work that isn't mine to bundle or split.
