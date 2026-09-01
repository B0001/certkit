# certkit-9oa — exact rational oracle for Pauli-sum operators

## Status: DONE. Built the oracle certkit-sqr deliberately deferred, wired
into `tests/test_exact_oracle.py` the same way as dense/banded.

## The verdict this closes a gap in

No verdict changed. `certify_lambda_min` on a small `tfim_hamiltonian`
already verified via `temple_inertia` before this session
(`tests/test_backends.py::test_small_hamiltonian_takes_the_tight_route`,
pre-existing, unmodified) -- but its only ground truth was
`numpy.linalg.eigvalsh`. `test_exact_oracle.py` exists precisely because
`eigvalsh` is not trustworthy as sole ground truth (its own docstring cites
`test_banded.py::test_the_certified_interval_can_be_narrower_than_lapack_
error`, where the certified enclosure at n=400 is narrower than LAPACK's
backward error). That gap — Pauli-sum operators checked only against
`eigvalsh`, never against an independent exact rational computation — is
what this bead closes. Command showing the new coverage:

```
uv run pytest tests/test_exact_oracle.py -k pauli -v
```

6 new tests, all passing (3 qubit counts x 2 test shapes — count-below
correctness and end-to-end enclosure).

## The design decision certkit-sqr left open, and what I found

certkit-sqr's oracle (`operator_to_fraction_rows`) materialises an
`Operator` as exact `Fraction` rows via `op.row(i)` alone, taking each
entry's `Iv.lo` and asserting `lo == hi` (raising `ValueError` otherwise).
Its docstring claimed this "works across backends (CSR, dense, Pauli-sum,
...)". **That claim was wrong for Pauli-sum and I corrected it** (see below)
— I did not build on top of an unverified assumption.

I tried the direct route first: call `operator_to_fraction_rows` on a
decoded `tfim_hamiltonian`. It raised immediately:

```
ValueError: entry (0, 0) is a non-degenerate interval
[-2.0000000000000004, -1.9999999999999998]; not usable as exact-oracle input
```

Root cause, traced into `certkit/interval.py`: `Iv.__add__` calls
`Iv._widen`, which applies `math.nextafter` outward on *every* addition,
regardless of whether the underlying float sum is exact. So `-1.0 + -1.0`
(mathematically exact, exactly representable as a double) still comes out
non-degenerate as an `Iv`. This is deliberate conservatism in the trusted
module (documented in `operators.py`'s module docstring: "the rows are
intervals, not floats ... a Pauli-sum diagonal entry is a sum of many
coefficients and is not exactly representable") — not a bug to route
around. `PauliSumReal.row` sums same-column contributions from multiple
Pauli terms with this interval addition (e.g. every `ZZ` term touching a
given site lands on the same diagonal entry), so for any Pauli-sum operator
with qubits >= 3, essentially every diagonal entry has >= 2 contributions
and is therefore never `Iv`-degenerate. `operator_to_fraction_rows` would
reject the exact shape the bead asks it to cover.

This is the real design decision the bead asked for. The two honest options
were: (a) pick a narrow special case where `op.row` happens to stay
degenerate (unhelpfully narrow — rules out every qubit count >= 3 for a
connected TFIM chain), or (b) build the oracle directly from the Pauli-string
coefficients, bypassing `Iv` entirely, per the bead description's own
suggested alternative. I built (b): `pauli_sum_to_fraction_rows(enc)` in
`tests/exact_oracle.py` recomputes the identical bit-mask/phase logic
`PauliSumReal.__init__`/`.row` use (mask/zy/Y-count parity -> sign), but sums
directly in `Fraction` from the start. `Fraction(coeff)` is an exact
conversion from a double (a double *is* a dyadic rational), so there is no
rounding anywhere in this path — no `Iv`, no float arithmetic at all after
decoding the hex-encoded coefficients.

**Verification that this new function is actually correct**, not just
internally consistent with itself: cross-checked its output against an
explicit Kronecker-product construction of the same Pauli terms (`dense_pauli`
in `tests/test_backends.py`, built from `numpy.kron` over the literal 2x2
Pauli matrices — a construction with no shared code path with either
`PauliSumReal` or the new function) for qubits 3-6, exact match on every
entry. That check isn't itself part of the committed test suite (it was a
one-off sanity script during development, not re-added as a test, since
`test_backends.py::test_pauli_apply_matches_kronecker_construction` already
covers that `PauliSumReal.apply` matches the Kronecker construction, and the
new function's own docstring records that this cross-check was done).

## What I touched, and why each part is justified

`tests/exact_oracle.py` (test-only support, not trusted — confirmed
unchanged status: still never imported by `certkit/*`, still outside
`test_trust_boundary.py`'s scope):

- Corrected `operator_to_fraction_rows`'s docstring: removed the "works
  across backends ... Pauli-sum" claim (false, as shown above) and added an
  explanation of exactly why it doesn't work for Pauli-sum, pointing at the
  new function. This is a factual correction, not a behavior change — the
  function's code is untouched.
- Added `pauli_sum_to_fraction_rows(enc: dict) -> list[list[Fraction]]`,
  described above.

`tests/test_exact_oracle.py`:

- Added `test_pauli_inertia_count_matches_exact_rational_oracle` and
  `test_pauli_lambda_min_enclosure_contains_exact_rational_truth`,
  parametrized over `qubits in [3, 4, 5]` (n = 8, 16, 32), mirroring the
  existing dense/banded pair structurally (count-below sweep vs. the exact
  oracle, then an end-to-end `certify_lambda_min` enclosure check against
  `exact_lambda_min`'s bisected bracket).
- Used `tfim_hamiltonian(qubits, field=1.5, coupling=1.0)` rather than the
  all-defaults (`field=1.0`) Hamiltonian: the untilted chain has extra Z2 /
  translation symmetry that makes exact rational eigenvalue *coincidences*
  on `_beta_sweep`'s coarse grid more likely than for a random dense/banded
  matrix (measure-zero in general, not measure-zero for a highly symmetric
  fixture) — hit this empirically while developing the test (a `qubits=2`
  probe threw `ZeroDivisionError` partway through a beta sweep). Handled it
  two ways: picked `field=1.5` to detune the degeneracy for the actual test
  fixture, and additionally wrapped the `exact_count_below` call in
  `except ZeroDivisionError: continue` in the count-matching test (the
  existing dense/banded tests only guard the *interval* side with
  `except IntervalError`, since a random matrix essentially never lands
  exactly on a rational eigenvalue; a structured Hamiltonian is a different
  risk profile, so I did not assume the old guard was sufficient here).
- Both `assert op.n <= DENSE_LIMIT` before certifying/oracle-ing, so a future
  edit that raises `DENSE_LIMIT` doesn't silently walk this test into the
  runtime cliff below without a visible assertion failure explaining why.

## Bound/tolerance/threshold changes and their derivation

None. I did not touch `DENSE_LIMIT`, any slack/tolerance parameter, or any
constant in `checker.py`/`interval.py`/`backward_error.py`. The only
"threshold" I introduced is the test-file choice of `qubits in [3, 4, 5]`,
justified purely by measured wall-clock cost (next section) — it is a test
scope decision, not a soundness-relevant bound, and does not appear anywhere
`certkit/*` reads.

## Documented limits I was tempted to touch, and what I measured instead

I benchmarked `qubits=6` (n=64) before picking the parametrize list:
a single 70-iteration `exact_lambda_min` bisection took **~50s** (measured,
`time uv run python3 ...`) — Fraction LDL^T's per-pivot denominator growth
is far more expensive than the analogous float/`Iv` cost the `DENSE_LIMIT`
comment in `operators.py` measures (that comment's ~4.8s/beta figure is for
the *interval* route, not exact `Fraction` arithmetic). I did not round
`DENSE_LIMIT` down, soften any claim about it, or otherwise touch that
constant — it governs the certified/checker route's runtime ceiling, not
this test-only oracle's. I capped the parametrize list at `qubits=5` (n=32,
~2.6s bisect) instead, the same kind of scope decision certkit-sqr made when
it capped dense/banded at n<=20 (documented in its own handoff as "n up to
20 keeps the whole new file at ~5s"). Reported the number rather than
picking a round one and hoping.

I did not touch, and was not tempted to touch, any of the repo's actual
documented limits (the coverage-cliff README language, `DENSE_LIMIT` itself,
the Gershgorin "floor, not a good bound" framing, or anything Lean-side).

## What I decided not to do

- Did not attempt qubits=6 or above in the parametrized tests — measured
  cost (~50s for one bisection) makes it unsuitable for routine suite runs;
  noted the number above rather than silently capping without explanation.
- Did not add a "lying certificate is caught" test analogous to
  `test_a_lying_banded_count_is_caught_and_the_exact_oracle_confirms_the_lie`.
  The bead's acceptance criteria asks for wiring "the same way ... does for
  dense and banded" — the *dense* route (which is what a small Pauli-sum
  operator actually uses, `temple_inertia`) has no such lying-certificate
  test either in this file, so I matched the dense pattern (count-below
  correctness + end-to-end enclosure) rather than inventing a third test
  shape not asked for. If a reviewer wants that coverage too, it would be
  straightforward to add (fabricate a bad Sturm-style count against
  `certify_count_below` for a Pauli operator and confirm the exact oracle
  disagrees), but I didn't add speculative test surface beyond the
  acceptance criteria.
- Did not change `PauliSumReal.row` or its use of `Iv` addition in
  `certkit/operators.py` (trusted module) to try to make it "more exact" —
  its conservative widening is correct and intentional; the fix belongs in
  the test-only oracle, not in trusted code.
- Did not attempt to extend the oracle to a Pauli-sum operator beyond
  `DENSE_LIMIT` (n > 256, i.e. the matrix-free-only regime where
  `certify_lambda_min_matrixfree`/`gershgorin_rayleigh` is the only route).
  `pauli_sum_to_fraction_rows` itself has no size limit baked in (it never
  materialises an n x n dense structure beyond the rows array it returns,
  same O(n^2) memory profile as the dense/banded oracle) — the limiting
  factor is Fraction LDL^T's O(n^3)-with-growing-denominators cost in
  `exact_count_below`/`exact_lambda_min`, identical to why the dense/banded
  oracle already tops out around n=20-32. Nothing about this bead's coverage
  bears on `certkit-ph1` (the coverage-cliff bead, which is about what the
  *certified* route can discharge past `DENSE_LIMIT`, not about test
  ground truth) — did not touch or re-measure anything there.

## What I could not verify

- Whether `pauli_sum_to_fraction_rows`'s agreement with the Kronecker
  construction generalizes past the qubits=3..6 range I spot-checked during
  development (not committed as a test — see above). The bit-mask logic is
  identical to `PauliSumReal.__init__`'s, so I have no reason to expect
  divergence at larger qubit counts, but "no reason to expect" is not a
  proof; I did not attempt one.
- Whether some other Pauli-string configuration (not TFIM-shaped, e.g. terms
  with three or more Pauli operators overlapping on the same site pattern in
  a way TFIM never produces) could hit an edge case in the mask/zy/phase
  logic I copied from `PauliSumReal`. I did not construct an adversarial
  Pauli-sum fixture to stress this; the tests here only exercise
  `tfim_hamiltonian`, which is what the bead's acceptance criteria names as
  the example shape.
- Independent human review of `pauli_sum_to_fraction_rows`'s bit-mask logic
  against its derivation — `certkit-jcb` is still open and unclaimed, and
  this session's self-check (matching a from-scratch Kronecker construction)
  is not that review.

## Test suite

Full suite, with dev extra installed (`uv sync --extra dev`):

```
$ uv run pytest tests
171 passed in 27.34s
```

(was 165 before this session; +6 new Pauli-sum oracle tests, 0 regressions,
0 skips.)

No-dependency checker sanity check (bare interpreter, no uv, no venv — used
`/home/node/.local/share/uv/python/cpython-3.12-linux-aarch64-gnu/bin/
python3.12` directly since plain `python3` was not on `PATH` in this
container; confirmed `import numpy` fails on that interpreter before
trusting the result):

```
$ python3 -m certkit.cli check examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

Trust boundary test specifically:

```
$ uv run pytest tests/test_trust_boundary.py -v
4 passed
```

## Files changed

- `tests/exact_oracle.py` — added `pauli_sum_to_fraction_rows`; corrected
  `operator_to_fraction_rows`'s docstring (see above).
- `tests/test_exact_oracle.py` — added the two Pauli-sum tests, imports,
  module docstring note.

Nothing under `certkit/` touched. No changes to any trusted module.

## Unrelated dirty files noticed in the working tree

`issues.jsonl` and `sandbox-handoffs/certkit-kjy.md` showed as modified in
`git status` before I made any changes — evidently a concurrent session
working on `certkit-kjy` in this shared workspace. Not touched, not part of
this bead's diff; flagging so whoever reviews this doesn't attribute those
changes to certkit-9oa.

## Beads

- `bd export -o issues.jsonl` NOT run by me for this bead's own change,
  since the only in-progress -> closed transition below is the one this
  handoff documents; if the reviewer wants the bead-close reflected in the
  jsonl export from this session specifically (independent of the concurrent
  certkit-kjy session's own pending export), run
  `bd export -o issues.jsonl` after `bd close certkit-9oa`, per project
  convention.
- Closing `certkit-9oa` after writing this handoff, per session instructions
  and since the acceptance criteria (an exact rational oracle for a
  Pauli-sum shape, wired into the test suite the same way as dense/banded)
  is met and evidenced above.

## Handoff commands (not run — git policy is report, not act)

```
git add tests/exact_oracle.py tests/test_exact_oracle.py
bd export -o issues.jsonl
git add issues.jsonl sandbox-handoffs/certkit-9oa.md
git commit -m "certkit-9oa: exact rational oracle for Pauli-sum (TFIM) operators"
```

(`issues.jsonl` and `sandbox-handoffs/certkit-kjy.md` are already modified
by a concurrent, unrelated session — left as-is; the `git add` list above is
scoped to this bead's own files plus the jsonl re-export bd's own workflow
asks for.)
