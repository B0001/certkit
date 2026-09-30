# certkit-v3e — Lean formalization of the complex-Hermitian tight route's soundness obligations

## What was done

Formalized, from first principles, the two soundness obligations that
`count_eigenvalues_below_hermitian`'s docstring (in `certkit/checker.py`)
currently only argues in prose, matching the style/rigor of the existing
real-case `Soundness.inertia_count_below` and the banded-route
`BandedBackwardError.lean` precedents:

1. **LDL^H reconstruction correctness** — for Hermitian `A`, unit-lower-triangular
   complex `L`, and real diagonal `D` with `A = L D Lᴴ`, the pivot recurrences the
   checker computes actually reproduce `A` when multiplied back out.
   (`hermitianRecon`, `hermitianRecon_conj_symm`, `hermitianRecon_diag`,
   `hermitianRecon_offdiag`.)

2. **Sylvester's law of inertia for Hermitian congruence** — `A` and
   `D = L⁻¹ A (Lᴴ)⁻¹` have the same number of negative eigenvalues, since `L`
   is invertible. mathlib has no complex/Hermitian analog of Sylvester's law
   (only `QuadraticForm.sigNeg_of_equiv_weightedSumSquares` for real quadratic
   forms under `[LinearOrder R]`), so this was built from scratch as an
   elementary "maximal negative subspace" argument:
   `quadCongr`, `quadCongr_diagonal`, `finrank_map_eq_of_injective`,
   `card_neg_le_of_congr`, `congr_symm_of_isUnit`, `card_neg_eq_of_congr`,
   `sub_smul_one_eq_mul_diagonal_mul_star`, culminating in
   `hermitian_inertia_count_below`, which ties the LDL^H factorization used by
   the checker (via a shift `A - β•I`) directly to
   `{i | hA.eigenvalues i < β}.ncard`.

No transcribed constants — every lemma used was verified by grepping the
vendored mathlib source for its exact name/signature (e.g. namespace
capitalization gotcha `unitary`/`Unitary`, and the rfl-equal-but-not-
syntactically-identical bridges `starRingEnd_apply` and
`RCLike.ofReal_eq_complex_ofReal`).

## Files changed

- **New**: `lean/Certkit/HermitianInertia.lean` (323 lines). Fully self-contained
  proof, zero `sorry`.
- **Modified**: `lean/Certkit.lean` — added `import Certkit.HermitianInertia`
  (2-line diff, confirmed via `git diff --stat -- lean/Certkit.lean
  lean/Certkit/HermitianInertia.lean`):
  ```
  lean/Certkit.lean | 2 ++
  1 file changed, 2 insertions(+)
  ```

No other files were touched this session. The working tree has substantial
unrelated modified/untracked files from concurrent bead activity (see below) —
none of that was created or edited by this session's work.

## Verdict / bound / threshold changes

None. This is a Lean-only addition of a soundness proof for machinery that
already exists and is already tested in Python
(`tests/test_complex_hermitian.py`, `tests/test_complex_temple_inertia.py`).
No checker behavior, tolerance, or documented limit changed. No README claim
was softened or strengthened.

## Evidence

**Lean build** (zero errors, zero `sorry`):
```
$ lake build Certkit
# succeeded — only cosmetic lint warnings (unused section variables
# [DecidableEq n] on quadCongr, [Fintype n] [DecidableEq n] on
# finrank_map_eq_of_injective; unused simp args on two calls, already
# trimmed; one mathlib deprecation notice for Set.mem_setOf_eq — not
# actionable, deprecation is inside mathlib itself)
$ grep -n sorry lean/Certkit/HermitianInertia.lean
# (no output)
```

**Python test suite** (unaffected, confirms no regression from touching only
Lean files):
```
$ uv run --extra dev pytest tests
229 passed in 65.90s (0:01:05)
```

**Checker sanity check** (unaffected, ran to confirm end-to-end health):
```
$ uv run python -m certkit.cli check ...
VERIFIED lambda_min_enclosure via temple_inertia [-3.095316431033709, -3.0953164248430762]
# re-derived independently: [-3.0953164279384016, -3.095316427938384]
```

## Deliberate non-fixes

Left two cosmetic `omit [DecidableEq n]` / `omit [Fintype n] [DecidableEq n]`
lint hints unaddressed on `quadCongr` and `finrank_map_eq_of_injective`.
These are Lean linter suggestions that the section variables are unused by
those particular declarations — purely cosmetic, zero soundness impact, and
touching them post-hoc on an already-clean build was judged not worth the
marginal risk of introducing an unrelated compile break. Did fix two other
simp-arg lint warnings (dropped unused `Matrix.diagonal_apply`,
`Matrix.one_apply`, `Pi.sub_apply` from two `simp`/`simp only` calls) and
re-confirmed `lake build Certkit` stayed clean afterward.

## What could not be verified

Nothing outstanding — build, `sorry` grep, Python test suite, and checker
sanity check all passed.

## Git status / proposed commands

Not committed or pushed, per repo policy. This session's changes are exactly:

```
git add lean/Certkit.lean lean/Certkit/HermitianInertia.lean
git commit -m "Add Lean soundness proof for complex-Hermitian LDL^H inertia counting (certkit-v3e)"
```

**Do not** sweep in other files — `git status` shows a substantial set of
modified/untracked files from concurrent, unrelated bead work (e.g.
`AGENTS.md`, `CHANGELOG.md`, `README.md`, `TCB.md`, `certkit/checker.py`,
`certkit/interval.py`, `certkit/operators.py`, `certkit/producer.py`,
`conformance/*`, `issues.jsonl`, `lean/Certkit/Soundness.lean`,
`lean/Certkit/BandedBackwardError.lean`, `sandbox-prompt.md`,
`tests/test_complex_hermitian.py`, `tests/test_complex_temple_inertia.py`,
other `sandbox-handoffs/*.md`) that this session did not create or modify and
has no context to vouch for.

`issues.jsonl` already shows as modified in git status from that concurrent
activity — no additional `bd export` was needed for `certkit-v3e` specifically
beyond the normal `bd close` bookkeeping.
