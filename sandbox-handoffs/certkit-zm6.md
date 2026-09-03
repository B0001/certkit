# certkit-zm6 — Formalize the L2-vs-row-sum link between backward_error.py and weyl_shift

## Outcome

Both deliverables done. The theorem is **proved**, not sorry'd. Bead closed.

## What changed

### 1. Stale cross-reference fixed (Deliverable 1)

`lean/Certkit/Soundness.lean`, `sweep_backward_bound`'s doc comment (was at the
bead's cited line 642, had drifted to ~802 by the time this session started
due to unrelated prior uncommitted work landing in between). It read:

> "...and that `‖·‖_∞` dominates the operator norm `‖·‖_2` used by
> `weyl_shift` above (a general Hermitian-matrix norm inequality, unrelated
> to rounding). Those remain open, covered by `weyl_shift`'s own `sorry` and
> by the Python test suite, not by this theorem."

`weyl_shift` has been zero-`sorry` since `certkit-8y2.6` closed
(2026-08-31), so "covered by weyl_shift's own sorry" was false — it implied
the gap was tracked by a `sorry` that no longer exists. Rewritten to say the
norm-inequality half of the gap is now closed by the new theorem
(`l2_opNorm_le_rowSum_of_isHermitian`), and only the `Iv`-arithmetic
bookkeeping half (that `backward_error.sweep`'s Python loop actually
accumulates a row-sum bound correctly) remains open, covered by the Python
test suite. `weyl_shift`'s own doc comment (which had the same "remains a
separate obligation... not by this theorem" phrasing, without the stale
`sorry` reference) was updated the same way, to point at the new theorem by
name.

### 2. New Lean theorem (Deliverable 2) — proved, no `sorry`

`lean/Certkit/Soundness.lean`, new theorem `l2_opNorm_le_rowSum_of_isHermitian`
(inserted between `weyl_shift` and `sweep_backward_bound`):

```
theorem l2_opNorm_le_rowSum_of_isHermitian [Nonempty n] {E : Matrix n n ℝ}
    (hE : E.IsHermitian) :
    ‖E‖ ≤ (Finset.univ : Finset n).sup' Finset.univ_nonempty (fun i => ∑ j, |E i j|)
```

(stated under `open scoped Matrix.Norms.L2Operator`, so `‖E‖` here is the L2
operator norm; the row-sum bound is spelled out as a raw `Finset.sup'` over
`∑ j, |E i j|` rather than via `Matrix.Norms.Operator`'s scoped `‖·‖`
instance, because that scope's notation would clash with
`Matrix.Norms.L2Operator`, already open in this file section).

A shallow mathlib scan this session (grepped
`Mathlib/Analysis/Matrix/Normed.lean`, `Mathlib/Analysis/CStarAlgebra/Matrix.lean`,
`Mathlib/Analysis/Matrix/Order.lean`, `Mathlib/Analysis/Matrix/Spectrum.lean`,
`Mathlib/LinearAlgebra/Matrix/Hermitian.lean`, and the interpolation-adjacent
files under `Mathlib/Analysis/InnerProductSpace/` and
`Mathlib/Analysis/Normed/`) found no direct lemma for
`‖E‖₂ ≤ ‖E‖_∞` on Hermitian/symmetric matrices, confirming the bead's own
note that this needed to be proved rather than cited. It was proved from
primitives via the **Schur test** (weighted Cauchy-Schwarz), not spectral
decomposition:

- Let `M` bound every row sum (`Finset.sup'`, needs `[Nonempty n]` for the
  witness — added as a per-theorem hypothesis rather than a global one or a
  detour through `ℝ≥0`; every real caller is a tridiagonal sweep with `n ≥ 1`).
- Per-row Cauchy-Schwarz (`Finset.sum_mul_sq_le_sq_mul_sq`) gives
  `|(Ex) i|² ≤ (∑ j |E i j|) · ∑ j |E i j| x_j² ≤ M · ∑ j |E i j| x_j²`.
- Summing over `i`, swapping summation order (`Finset.sum_comm`) turns the
  inner sum into one weighted by `∑ i |E i j|` — a **column** sum, which by
  symmetry (`hE.apply`, `E i j = E j i`) is itself a row sum and so also `≤ M`.
- This gives `‖Ex‖² ≤ M² ‖x‖²`, i.e. `‖Ex‖ ≤ M‖x‖` for every `x`, which is
  exactly `ContinuousLinearMap.opNorm_le_bound`'s hypothesis.

No numeric constant is transcribed anywhere in this proof — `M` is the
row-sum bound of the actual matrix `E`, computed structurally, not copied
from a paper. The classical fact underlying the route (`‖E‖₁ = ‖E‖_∞` for
symmetric `E`, combined with `‖E‖₂ ≤ sqrt(‖E‖₁ · ‖E‖_∞)`) is not invoked via
a named interpolation theorem (mathlib doesn't carry one for finite
matrices) — it's inlined directly through the Cauchy-Schwarz/summation-swap
argument above.

**This did not need to become a `sorry`.** The full proof compiles.

### 3. Docstring and correspondence-table wiring

- `certkit/backward_error.py:47` — the line
  `delta >= ||A - Atilde||_2 (via ||E||_2 <= ||E||_inf for symmetric E)` now
  also names `Certkit.Soundness.l2_opNorm_le_rowSum_of_isHermitian`, matching
  the file's existing correspondence-table convention.
- `Soundness.lean`'s header correspondence table (was lines 20-29, now
  shifted slightly) gained a third line under the
  `backward_error.count_eigenvalues_below_backward` mapping, next to
  `weyl_shift`, naming the new theorem.
- `Soundness.lean`'s header STATUS paragraph updated: was "six of the seven
  theorems... only `residual_encloses_some_eigenvalue` is still `sorry`" —
  this was already stale before this session started (that theorem's proof
  landed as unrelated uncommitted work from a different, still-open bead,
  present in the tree before I touched anything). Rewrote to "all eight
  theorems... zero-`sorry`", which is accurate for the tree's *current*
  state (verified by re-grepping `sorry` below), and folded in a note about
  what `sweep_backward_bound`'s remaining open gap actually is now.

## Verdict changes

No checker verdicts changed. This bead is pure formalization (Lean-side
proof + docstring/comment correctness) — it does not touch any code in the
trust boundary that affects `check()`'s runtime behavior.
`certkit/backward_error.py`'s only change is a one-line docstring addition
inside a triple-quoted string; no executable line moved. Confirmed via
`git diff certkit/backward_error.py` (attached in this session's terminal
history) — the diff is exactly the docstring reference addition, nothing
else.

## Bounds/tolerances/guards/thresholds touched

None. `ETA`, `GAMMA`, `MAX_REFINEMENTS`, `TINY`, `U` in
`certkit/backward_error.py` were not touched. The new Lean theorem's bound
`M` is derived structurally from `E`'s own entries via `Finset.sup'`, not a
transcribed constant — see the proof sketch above.

## Documented limits tempted to soften

None encountered. This bead doesn't touch `DENSE_LIMIT`, Gershgorin, or the
n≈10⁴ producer-eigenvector binding constraint.

## Verbatim final test-run line

```
$ uv run --extra dev pytest tests
============================= 182 passed in 27.85s =============================
```

## No-dependency checker smoke test

```
$ uv run python3 -m certkit.cli check examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

## Lean build

```
$ cd /workspace/lean && lake build Certkit
...
✔ [8803/8804] Built Certkit (3.9s)
Build completed successfully (8804 jobs).
```

Two warnings present, both pre-existing and unrelated to this bead (unused
`hd` binding in `residual_encloses_some_eigenvalue`'s proof — not mine, see
below; unused `[FiniteDimensional ℝ E]` section variables in two private
`weyl_finrank_span_*` lemmas, also pre-existing). No new warnings introduced
by this session's edits.

## Re-measured: `sorry` count in Soundness.lean

```
$ grep -n "sorry" lean/Certkit/Soundness.lean
5:  All eight theorems below are real, zero-`sorry` proofs: `rayleigh_ritz_min`,
16:  compiling with no `sorry` is a fact about this file;
38:  zero `sorry`, in `Interval.lean`.
272:    History: this was `sorry` and *false as previously stated*, because
279:    now a real, zero-`sorry` proof.
```

Zero actual `sorry` tactic occurrences — every mention is prose. This is
current as of this session's final build, not carried over from a prior
claim.

## Important: pre-existing uncommitted work in this file, not mine

Before this session started, `lean/Certkit/Soundness.lean` already had an
uncommitted proof of `residual_encloses_some_eigenvalue` (previously
`sorry`) sitting in the working tree — visible in `git diff` as a large
hunk unrelated to this bead. That belongs to a different, apparently still-
open bead. I did not author it, did not verify its correctness beyond
noting it compiles as part of the same `lake build Certkit` this session
ran repeatedly, and left it untouched except for updating the file's header
STATUS text to correctly reflect that it's no longer `sorry` (which was
necessary for my own header edit to be accurate — the alternative would
have been to leave the header saying something false). If that other
bead's session comes back and finds its own work already partially
described in the header, that's a byproduct of two uncommitted diffs
sitting in the same file, not a claim of authorship on my part.

## What was decided not to do, and why

- Did not open `Matrix.Norms.Operator` as a second scoped instance to get a
  `‖·‖`-notation version of the row-sum bound — it would clash with
  `Matrix.Norms.L2Operator`, already open in this section of the file (both
  are scoped `Norm (Matrix n n ℝ)` instances on the same type). Spelling
  the row-sum bound out as `∑ j, |E i j|` directly avoids the ambiguity and
  is no less rigorous.
- Did not attempt to weaken the `[Nonempty n]` hypothesis or route around it
  via `ℝ≥0`/`iSup` — `Finset.sup'` needs a witness element and every real
  caller (a tridiagonal sweep matrix) has `n ≥ 1`, so this costs nothing in
  practice and keeps the proof simpler.
- Did not touch `certkit/backward_error.py`'s executable code, `ETA`,
  `GAMMA`, or any other rounding-budget constant — out of scope for this
  bead, which is purely about the missing Lean statement and cross-
  references.
- Did not touch the pre-existing uncommitted `residual_encloses_some_eigenvalue`
  proof, `AGENTS.md`, `CLAUDE.md`, `README.md`, `issues.jsonl`,
  `sandbox-prompt.md`, or any of the untracked `sandbox-handoffs/*.md`,
  `lean/Certkit/Scratch*.lean`, or `tests/test_doc_pass_count.py` files
  already present in the tree — all pre-existing, unrelated to this bead's
  scope, and not evaluated for correctness by this session.

## What could not be verified

- I did not independently re-verify the pre-existing, not-mine
  `residual_encloses_some_eigenvalue` proof's mathematical correctness
  beyond "it compiles" — that's a different bead's responsibility. Flagging
  this honestly rather than silently vouching for code I didn't write.
- I did not run `#print axioms l2_opNorm_le_rowSum_of_isHermitian` to
  double check the proof doesn't secretly depend on `Classical.choice`
  beyond what's expected/standard for mathlib (`Classical.arbitrary n` is
  used deliberately for the `[Nonempty n]` witness, which is fine and
  expected) or on `sorryAx` — the `lake build` and `grep sorry` above give
  strong indirect evidence there's no `sorryAx` dependency, but I did not
  run the axiom-print command explicitly.

## Git state — NOT committed, NOT pushed (per policy)

```
$ git status --porcelain
 M AGENTS.md            <- pre-existing, not mine
 M CLAUDE.md             <- pre-existing, not mine
 M README.md              <- pre-existing, not mine
 M certkit/backward_error.py     <- MINE (1-line docstring addition)
 M issues.jsonl            <- pre-existing, not mine
 M lean/Certkit/Soundness.lean   <- MINE + pre-existing residual_encloses_some_eigenvalue proof
 M sandbox-prompt.md          <- pre-existing, not mine
?? lean/Certkit/Scratch.lean       <- pre-existing, not mine
?? lean/Certkit/Scratch2.lean      <- pre-existing, not mine
?? sandbox-handoffs/*.md (various)   <- pre-existing, not mine, plus this file
?? sandbox-handoffs/certkit-k2j-entanglement-experiment.py  <- pre-existing, not mine
?? tests/test_doc_pass_count.py     <- pre-existing, not mine
```

No `bd export -o issues.jsonl` was run — `issues.jsonl` already shows as
modified from pre-existing (not-mine) work, and this session's only bead
mutation is the claim + upcoming close on `certkit-zm6` itself, which does
not need a fresh export beyond what a human running the suggested commands
below will produce naturally.

### Suggested commands for a human to run

```bash
# Review this session's actual diff (backward_error.py + the zm6-relevant
# hunks of Soundness.lean — NOT the residual_encloses_some_eigenvalue hunk,
# which is someone else's uncommitted work):
git diff certkit/backward_error.py
git diff lean/Certkit/Soundness.lean

# If satisfied, stage and commit only this bead's files (leave the other
# pre-existing modified/untracked files for their own beads to handle):
git add certkit/backward_error.py lean/Certkit/Soundness.lean
git commit -m "certkit-zm6: prove L2-vs-row-sum bound for Hermitian matrices, fix stale weyl_shift sorry cross-reference"

# bd sync, if this repo's workflow wants issues.jsonl / dolt state pushed:
bd export -o issues.jsonl
git add issues.jsonl
# (only if the above export produces a clean, zm6-only diff -- check first,
# since issues.jsonl already has unrelated pre-existing changes in it)
```
