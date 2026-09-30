# certkit-sp1 — Lean formalization of the banded (bandwidth>1) backward-error route

## Outcome

Closed. New Lean file, compiling with zero `sorry`, discharges the two
real-number concerns the bead's acceptance criteria named for the banded
route: `LDL^T` reconstruction-formula correctness and row-sum coverage
(generalizing `sweep_row_bound` from bandwidth 1 to general bandwidth `b`).

## What changed

### 1. New file: `lean/Certkit/BandedBackwardError.lean`

Four things, all in plain `ℕ → ℕ → ℝ` / `ℕ → ℝ` functions rather than
`Matrix n n ℝ` — matching the precedent that `sweep_row_bound` itself is
not machine-linked to `l2_opNorm_le_rowSum_of_isHermitian` by an `exact`
chain, only by the header's prose correspondence table, so nothing here
needed to interface with `Matrix`/`Fintype`/`Hermitian` machinery either:

- `bandedRecon L D i j := ∑ k ∈ Finset.range (min i j + 1), L i k * L j k * D k`
  — the `(i,j)` entry of `L * diag D * Lᵀ`.
- `bandedRecon_diag` / `bandedRecon_offdiag` — unfold the `k = j` term via
  `Finset.sum_range_succ`, using only that `L` has unit diagonal. This is
  `REVIEW-dyi.md` §2's `M_jj` / `M_ij` formulas, proved as a real-number
  identity, closing the "formula correctness" checklist item at the level
  the bead asked for (not the Python loop's transcription of it, which
  stays a separate, already-covered concern).
- `bandedRecon_eq_zero_of_band_lt` / `bandedE_eq_zero_of_band_lt` —
  bandedness of the reconstruction and of the full perturbation `E`, given
  `L` and `A` are both banded with bandwidth `b`.
- `banded_row_err_eq_row_sum` — the main theorem. Given `E` symmetric and
  vanishing outside the band, proves:
  ```
  |E r r|
    + ∑ i ∈ (range n).filter (r < i ∧ dist i r ≤ b), |E i r|
    + ∑ j ∈ (range n).filter (j < r ∧ dist r j ≤ b), |E r j|
  = ∑ c ∈ range n, |E r c|
  ```
  i.e. `sweep_banded`'s double-crediting accumulation scheme (crediting each
  in-band off-diagonal pair to *both* `row_err[i]` and `row_err[j]`, since
  each pair is visited once, not twice) reconstructs the true full row sum
  — the quantity `l2_opNorm_le_rowSum_of_isHermitian` needs. For `b = 1`
  this is exactly `sweep_row_bound`'s three-term shape (diagonal + one
  predecessor + one successor); the proof never special-cases `b`.

  Proof technique: `Finset.add_sum_erase` peels the diagonal term off
  `∑ c ∈ range n`; `Finset.sum_subset` extends each band-restricted filter
  (`dist ≤ b`) out to the full one-sided filter (`< r` / `> r`), with the
  excess terms shown to vanish via the bandedness hypothesis; `hsymm` flips
  `|E i r|` to `|E r i|`; `Finset.sum_union` on the resulting disjoint
  `{i > r} ∪ {j < r}` partition of `range n \ {r}` finishes it.

This route needs **no** analog of `sweep_backward_bound` (the tridiagonal
per-operation rounding-error accumulation): it never counts rounding at
all. `Mtilde` is built from the actual `L`, `D` floats that plain-float
elimination produced, then audited directly against `A`'s exact entries via
`Iv`, whose own soundness contract is already proved in `Interval.lean`.
That's why this bead's Lean gap had a fundamentally different shape from
the tridiagonal one, and why the new theorem set is smaller than
`BackwardError.lean`'s.

### 2. Wiring

- `lean/Certkit.lean` — added `import Certkit.BandedBackwardError`.
- `lean/Certkit/Soundness.lean` — header gained a new paragraph explaining
  the banded route's theorems and why no rounding-model analog is needed,
  plus a new correspondence-table row:
  ```
  backward_error.count_eigenvalues_below_backward_banded
                                                   <->  inertia_count_below
                                                   +   weyl_shift
                                                   +   l2_opNorm_le_rowSum_of_isHermitian
                                                   +   bandedRecon_diag / bandedRecon_offdiag
                                                   +   banded_row_err_eq_row_sum
  ```
- `README.md`'s "Not done yet" section — replaced the stale "Proofs on the
  Lean side for the banded backward-error route (certkit-4ue)" bullet with
  one stating what's now closed and what explicitly remains open (eviction
  safety and `Iv`-loop-faithfulness — see below).

## What is explicitly OUT of scope (per the bead's own scoping language)

Eviction safety (`lmat` discarding an entry before it's read) and whether
`sweep_banded`'s `Iv`-arithmetic loop, in whatever order it actually visits
`(i, j)` pairs, computes an outward-rounded enclosure of the real-number sum
`banded_row_err_eq_row_sum` proves — both are claims about the *Python
loop's* faithfulness to the formula, not about the formula itself. They
stay covered by `REVIEW-dyi.md`'s human/empirical review (its 5000-trial
eviction check) and `tests/test_backward.py`'s banded section, exactly as
`sweep_row_bound`'s own doc comment already excludes the analogous
`Iv`-loop-faithfulness question for the tridiagonal route. This was
confirmed as the bead's intended scope, not a shortcut taken to close it
faster.

## Verdict changes

None. This is pure Lean-side formalization; it does not touch
`certkit/backward_error.py`, `checker.py`, or any other file in the trust
boundary. `certkit/` is untouched by this session.

## Bounds/tolerances/guards/thresholds touched

None. No constant in `certkit/backward_error.py` (`ETA`, `GAMMA`, `TINY`,
`U`, `MAX_REFINEMENTS`) was touched. No numeric constant is transcribed
anywhere in the new Lean file — every bound is derived structurally from
`L`, `D`, `A`'s own entries and the bandwidth hypothesis.

## Documented limits tempted to soften

None encountered.

## Verification (all green)

```
$ cd lean && lake build Certkit
...
✔ [8804/8805] Built Certkit (5.6s)
Build completed successfully (8805 jobs).
```
(Two pre-existing warnings in `Soundness.lean` — unused `hd` binding, unused
`[FiniteDimensional ℝ E]` section variables in two private
`weyl_finrank_span_*` lemmas — both predate this session, line numbers just
shifted from the new header paragraph. No new warnings introduced.)

```
$ grep -n sorry lean/Certkit/*.lean
```
Zero actual `sorry` tactic occurrences (only prose mentions of the word,
consistent with the pre-existing baseline).

```
$ uv run --extra dev pytest tests
============================= 199 passed in 28.50s =============================
```

```
$ uv run python3 -m certkit.cli check examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

## bd state

`certkit-sp1` closed this session. Notes recorded on the issue via
`bd update certkit-sp1 --notes=...` before closing (full derivation summary,
duplicated in this handoff). `bd export -o issues.jsonl` run after the
notes update and again after closing — `issues.jsonl` reflects both.

## Git state — NOT committed, NOT pushed (per policy)

```
$ git status --porcelain
 M CHANGELOG.md            <- pre-existing, not mine
 M README.md               <- MINE ("Not done yet" section only)
 M conformance/README.md   <- pre-existing, not mine
 M conformance/manifest.json  <- pre-existing, not mine
 M issues.jsonl             <- MINE (bd notes + close) + pre-existing prior changes
 M lean/Certkit.lean         <- MINE (one import line)
 M lean/Certkit/Soundness.lean  <- MINE (header paragraph + correspondence-table row only)
?? conformance/cases/abstain_banded_sturm_be_tampered/  <- pre-existing, not mine
?? conformance/cases/verified_banded_sturm_be/          <- pre-existing, not mine
?? lean/Certkit/BandedBackwardError.lean   <- MINE (new file)
?? sandbox-handoffs/certkit-2sc.md         <- pre-existing, not mine
?? sandbox-handoffs/certkit-sp1.md         <- MINE (this file)
```

I verified `git diff README.md` and `git diff lean/Certkit/Soundness.lean`
each show exactly this session's intended hunk and nothing else before
writing this handoff.

### Suggested commands for a human to run

```bash
# Review this session's actual diff:
git diff README.md lean/Certkit.lean lean/Certkit/Soundness.lean
git diff issues.jsonl   # includes this session's bd notes/close plus some pre-existing entries; check before staging whole-file

# If satisfied, stage and commit only this bead's files (leave the
# pre-existing CHANGELOG.md/conformance/*/sandbox-handoffs/certkit-2sc.md
# changes for their own beads/sessions to handle):
git add lean/Certkit/BandedBackwardError.lean lean/Certkit.lean \
        lean/Certkit/Soundness.lean README.md sandbox-handoffs/certkit-sp1.md
git commit -m "certkit-sp1: formalize banded backward-error row-sum coverage in Lean"

# issues.jsonl / dolt sync, if this repo's workflow wants it pushed:
git add issues.jsonl
# (check the diff first — it also carries some pre-existing, unrelated entries)
```

## What could not be verified / was decided not to do

- Did not attempt to prove eviction safety or `Iv`-loop-faithfulness in
  Lean — out of scope per the bead's own scoping language (see above), and
  those are claims about a mutable Python dict's runtime behavior, not
  real-number inequalities.
- Did not touch the pre-existing uncommitted changes in `CHANGELOG.md`,
  `conformance/README.md`, `conformance/manifest.json`, the two new
  `conformance/cases/*` directories, or `sandbox-handoffs/certkit-2sc.md` —
  all present in the tree before this session started, unrelated to this
  bead's scope, not evaluated for correctness here.
- Did not run `#print axioms banded_row_err_eq_row_sum` to double-check for
  unexpected `sorryAx`/`Classical.choice` dependencies beyond what
  `lake build` + `grep sorry` already give strong indirect evidence against.
