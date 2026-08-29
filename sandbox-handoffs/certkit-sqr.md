# certkit-sqr: exact-oracle testing beyond tridiagonal operators

## What changed

Two new files, both test-only (not part of the trust boundary; not imported
by anything under `certkit/`):

- `tests/exact_oracle.py` -- a general, shape-agnostic exact rational oracle:
  `exact_count_below(rows, beta)` does a Fraction-exact LDL^T of `A - beta*I`
  plus Sylvester's law of inertia -- structurally the same algorithm as
  `checker.count_eigenvalues_below`, but over `Fraction` instead of `Iv`, so
  there is no width and nothing to abstain over. It makes no assumption about
  band structure, so it is valid ground truth for a banded matrix exactly as
  for a dense one. `exact_lambda_min(rows, iterations, bracket)` bisects it to
  isolate the smallest eigenvalue to arbitrary precision. `gershgorin_bracket`
  and `operator_to_fraction_rows` / `dense_rows_to_fractions` are the small
  amount of glue around it.

- `tests/test_exact_oracle.py` -- wires the oracle into both shapes the bead
  asked for:
  - `test_dense_inertia_count_matches_exact_rational_oracle` (n=6,12,20):
    `count_eigenvalues_below` (dense `inertia` rule) against
    `exact_count_below`, swept over a beta grid spanning the whole spectrum.
  - `test_dense_lambda_min_enclosure_contains_exact_rational_truth`
    (n=6,12,20): the full `certify_lambda_min` -> `check` enclosure
    (`temple_inertia`) against `exact_lambda_min`.
  - `test_banded_sturm_count_matches_exact_rational_oracle` (bandwidth=2,4,
    n=20): `count_eigenvalues_below_banded` (the `sturm` rule) against
    `exact_count_below`, on genuinely banded (non-tridiagonal) matrices --
    the shape the bead specifically flags as uncovered.
  - `test_banded_lambda_min_enclosure_contains_exact_rational_truth`
    (bandwidth=2,4): the full `certify_lambda_min_banded` bundle
    (`temple_ref`) against `exact_lambda_min`.
  - `test_a_lying_banded_count_is_caught_and_the_exact_oracle_confirms_the_lie`:
    the soundness half. `test_banded.py` already shows a fabricated count
    gets abstained on, but that only proves the checker disagrees with the
    lie -- not that the checker is *right* to. This test confirms, via the
    new independent oracle (no floating point, no shared code with
    `count_eigenvalues_below_banded`), that the true count really is 0 before
    checking that a claimed count of 3 gets rejected.

## Why a new shared module instead of a fourth copy of `exact_lambda_min`

The existing tridiagonal `exact_lambda_min` in `test_banded.py` and
`test_backward.py` bisects the classical two-term Sturm recurrence -- O(n),
which is why it can reach n=1000/n=400. That recurrence only exists because
those matrices are tridiagonal (bandwidth 1); it does not generalize to
bandwidth > 1 or dense. I did not touch either of those functions or the
tests that depend on their O(n) reach (`test_banded_route_verifies_far_
beyond_the_dense_ceiling` at n=1000, etc.) -- generalizing them to O(n^3)
Fraction LDL^T would make those specific tests impractically slow (see
timing note below) and isn't what the bead's gap is.

The repo's normal convention is to duplicate small helpers per test file
rather than share them (`banded_matrix`, `to_csr`, etc. each exist 2-3 times
across `test_banded.py`/`test_backward.py`/my new file). I broke that
convention on purpose for the oracle *algorithm itself*: a Fraction-exact
LDL^T is exactly the kind of code where a second, silently-diverged copy
would undermine the point of having ground truth at all. One implementation,
imported wherever it's used, given pytest's rootdir-based import (no
`__init__.py` under `tests/`, so a plain module there is importable as a
top-level name from any test file -- verified this works before relying on
it).

## A genuine correctness issue found and fixed while writing this

First run of `test_dense_lambda_min_enclosure_contains_exact_rational_truth`
at n=12 hit `ZeroDivisionError: pivot 0 is exactly zero`. Root cause: for
that seed, row 0's Gershgorin disc strictly contains every other row's disc
(`diag_0 - radius_0` is the overall minimum *and* `diag_0 + radius_0` is the
overall maximum), so `gershgorin_bracket`'s (lo, hi) average to `diag_0`
*exactly* on the very first bisection step -- making the 1x1 leading
principal submatrix of `A - beta*I` exactly singular. This is unpivoted
LDL^T's known soft spot: a zero pivot means *some leading principal
submatrix* is singular at that beta, not that beta is an eigenvalue of the
whole matrix -- and it isn't a rare coincidence here, it's a direct
consequence of how `gershgorin_bracket` is built whenever one row's disc
dominates.

Fix (in `exact_oracle.exact_lambda_min`): on `ZeroDivisionError`, nudge the
midpoint by `(hi - lo) / 2^40` and re-evaluate. This is fully rigorous, not a
tolerance fudge: `exact_count_below` returns the *true* exact count for
whatever beta it's actually given, with no rounding, so the bracket the
bisection loop narrows stays sound regardless of which specific point was
evaluated at each step -- there is no version of "the nudge happened to be
wrong" for a function with no error term. I did not add a retry loop or
try/except around the *outer* call sites (the beta-sweep count-matching
tests never hit this, since their beta grid is simple fixed fractions
unrelated to the matrix's own values, not bisection-derived); if a second
nudge also lands on a singular submatrix, it's left to raise rather than
silently retried again, on the theory that stacking coincidences should be
loud, not papered over.

## Tolerances / thresholds touched

None, in the trusted code. `gershgorin_bracket`'s nudge constant (`2^40`) is
in test-only code, not a soundness-relevant tolerance -- it only affects
which exact point gets queried during bisection, never whether the resulting
bracket is valid.

## Test-run output

```
$ uv run pytest tests -q
........................................................................ [ 43%]
........................................................................ [ 87%]
.....................                                                    [100%]
165 passed in 22.88s
```

Note on the baseline: CLAUDE.md documents "106 passed, about 5 seconds" as
the known-green baseline. In this container, with my two new files removed,
the suite is **154 passed in ~17.6s** (verified by moving `tests/exact_
oracle.py` and `tests/test_exact_oracle.py` aside and re-running) -- i.e. the
repo has grown past that documented number already, independent of this
session, and this environment runs measurably slower than "about 5 seconds"
for the existing suite too. My addition is 11 new tests, +154 -> 165 passed,
+17.6s -> +22.9s (~5.3s of that is the new file, confirmed by running it
alone). I'm reporting this rather than silently updating the "106 / 5s"
number in CLAUDE.md, since re-measuring and revising that documented
baseline is outside this bead's scope.

No-dependency checker invocation. This container has no bare `python3` on
`PATH` at all (only via `uv`), so the literal command from the standing
instructions (`python3 -m certkit.cli check ...`) isn't runnable as written.
The closest faithful substitute -- an isolated interpreter with the package
installed but no dev extras, so numpy is genuinely not importable -- confirms
the property:

```
$ uv run --no-project --with . -- python -c "import numpy" # ImportError
numpy not importable - good
$ uv run --no-project --with . -- python -m certkit.cli check \
    examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

`tests/test_trust_boundary.py` (which does its own numpy-blocking, in a
subprocess of `sys.executable`, so it doesn't depend on a bare `python3`
existing) passed as part of the full suite, including
`test_checker_runs_in_a_process_where_numpy_is_unimportable`.

## What I decided not to do

- Did not touch the tridiagonal `exact_lambda_min` in `test_banded.py` /
  `test_backward.py`, or the reach tests built on its O(n) speed. Not what
  this bead's gap is, and generalizing it would cost the n=1000/n=400 reach.
- Did not extend the oracle to Pauli-sum operators, even though the bead's
  description mentions "Pauli" as another uncovered shape. The acceptance
  criteria explicitly says "at least dense and banded", and a Pauli sum
  operator is matrix-free (`Operator.row` synthesizes entries on demand,
  potentially over an exponentially large basis) -- `operator_to_fraction_
  rows` would need `op.n <= a size where materializing every row is
  reasonable`, which is a real design question (what counts as "small
  enough", whether an exact oracle for a Pauli sum should instead work
  directly from the Pauli-string coefficients rather than materializing rows)
  I did not want to answer by expedience. Leaving it uncovered rather than
  bolting on a version I hadn't thought through. Filed as a new bead
  (certkit-9oa, see below) rather than doing it under this one.
- Did not attempt to push the dense/banded oracle test sizes past n≈20-32.
  Benchmarked: n=32 with a 50-step bisection takes ~4s single-threaded
  (O(n^3) per evaluation, Fraction denominators grow with elimination depth).
  That's fine for one test but not for a parametrized sweep across several
  sizes without materially growing suite runtime; n up to 20 keeps the whole
  new file at ~5s.
- Did not silently retry a second time on a repeated `ZeroDivisionError` in
  `exact_lambda_min`'s nudge path (see above) -- left it to raise.

## What I could not verify

- Whether the `2^40` nudge magnitude in `exact_lambda_min` is "big enough" to
  never recur for some future seed/matrix, in the sense of never needing a
  second nudge. I did not prove this in general (it isn't a soundness
  question, only a "does this test ever need a retry loop" one), and did not
  add one since it hasn't been observed to recur across the seeds actually
  exercised (n = 6, 12, 20, seeds 6, 12, 20, 1006, 1012, 1020, and the banded
  seeds 200-204, 300-304). If a future matrix hits it twice, the test will
  fail loudly with a clear `ZeroDivisionError`, not silently misbehave.
- I have not independently re-verified `checker.count_eigenvalues_below` /
  `count_eigenvalues_below_banded`'s own algorithms beyond what these new
  tests exercise (n <= 20, a handful of seeds). This raises confidence, it
  does not constitute the independent human review `certkit-jcb` asks for,
  which I left open and unclaimed per the standing instructions.

## Beads

- Filed `certkit-9oa` ("exact rational oracle for Pauli-sum operators") for
  the scope I deliberately left out -- see "what I decided not to do" above.
  Not started.
- `bd export -o issues.jsonl` run after filing the new bead, so the reasoning
  is in git, not only in the gitignored Dolt directory.

## Handoff commands (not run -- git policy is report, not act)

```
git add tests/exact_oracle.py tests/test_exact_oracle.py issues.jsonl sandbox-handoffs/certkit-sqr.md
git commit -m "Add general dense/banded exact-rational oracle for eigenvalue-count claims (certkit-sqr)"
```

`bd close certkit-sqr` -- to be run after this handoff is written (done, see
below).
