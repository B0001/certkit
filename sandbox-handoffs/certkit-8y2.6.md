# certkit-8y2.6 — Formalize weyl_shift: Courant-Fischer / Cauchy interlacing not in mathlib

**Status: left open.** Genuine partial progress this session; acceptance
criteria ("weyl_shift proved with no sorry, OR a documented mathlib-native
alternate route is found and used instead") not met. `weyl_shift` remains
`sorry` in `lean/Certkit/Soundness.lean`.

## What changed

Only `lean/Certkit/Soundness.lean` was touched, and only its `weyl_shift`
doc comment — the theorem statement and its `sorry` body are byte-for-byte
unchanged. No other file in the repo was modified by this session. (The
working tree has other modified/untracked files from other beads' sessions;
none of those are mine and none were touched.)

Verify the diff is comment-only:
```
git -c safe.directory=/workspace diff lean/Certkit/Soundness.lean
```
The change is entirely inside a `/-- ... -/` doc comment block preceding
`theorem weyl_shift`.

## What was accomplished

This is the fourth session to investigate this theorem (three previously
under certkit-8y2.3, which recommended splitting it into its own bead — this
one). Prior sessions only produced research notes ("mathlib lacks X, checked
route Y, rejected"). This session went further: it built and **verified
compiling** (zero `sorry`, `lake env lean Certkit/Scratch.lean` clean,
reproduced twice from a fresh write of the file) the "hard direction" of the
Courant-Fischer min-max theorem, at the abstract `LinearMap.IsSymmetric` /
`InnerProductSpace ℝ E` level (not yet the concrete `Matrix.IsHermitian`
level `weyl_shift` is actually stated at — see step 3 below).

Statement proved:
```
theorem courant_fischer_le (hT : T.IsSymmetric) (hn : Module.finrank ℝ E = n)
    (V : Submodule ℝ E) (i₀ : Fin n) (hV : Module.finrank ℝ V = i₀.val + 1) :
    ∃ x ∈ V, x ≠ 0 ∧ ⟪x, T x⟫ ≤ hT.eigenvalues hn i₀ * ⟪x, x⟫
```
i.e. any subspace of dimension `i₀.val + 1` contains a nonzero vector whose
Rayleigh quotient is at most the `i₀`-th (sorted-decreasing) eigenvalue.

The full working code — this lemma plus two support lemmas (a dimension
pigeonhole argument via `Submodule.finrank_sup_add_finrank_inf_eq`, and a
finrank-of-orthonormal-span computation via `OrthonormalBasis.span` +
`Fin.card_Iio`) — is now preserved verbatim in `weyl_shift`'s doc comment in
`Soundness.lean` as a copy-pasteable block. To reproduce: paste it into a
throwaway `lean/Certkit/Scratch.lean` and run (from `lean/`):
```
lake env lean Certkit/Scratch.lean
```
Expect clean output modulo one harmless `unused section variable` linter
warning.

This lemma was **not** integrated into `Soundness.lean` as a real
(non-scratch) declaration, because on its own it does not discharge
`weyl_shift` — see "What remains" below. Landing a lemma that doesn't
connect to anything would just be unused code; the doc-comment form keeps it
available without pretending it's load-bearing.

## What remains (in order attempted/assessed, not necessarily in order of size)

1. **Easy direction** (companion lemma; expected tractable, not attempted).
   For `x` in the span of the *top* `i₀.val + 1` eigenvectors
   (`b 0, ..., b i₀`), need `eigenvalues i₀ * ⟪x,x⟫ ≤ ⟪x, T x⟫`. Same
   Parseval-expansion technique as `courant_fischer_le`'s proof, but needs
   "`x ∈ span (b '' s)` implies `⟪b k, x⟫ = 0` for `k ∉ s`" as a side fact.
   Searched `Mathlib.Analysis.InnerProductSpace.{PiL2,Orthogonal,Basic}`
   this session for a ready-made version of this — nothing found under
   `orthogonal_span`, `mem_span` + orthogonality combinations searched.
   Should be derivable directly from `Submodule.mem_span_finset` (or
   equivalent) plus `Orthonormal`'s pairwise-orthogonality component, but
   this exact derivation was not written or checked.

2. **Loewner monotonicity.** Combine both directions: for symmetric
   `T_A, T_B : E →ₗ[ℝ] E` with `T_A - T_B` positive semidefinite,
   `eigenvalues_B i₀ ≤ eigenvalues_A i₀` for every `i₀`. Worked-out sketch
   (standard textbook argument, not yet written in Lean): apply
   `courant_fischer_le` to `T_A` at `V = span` of `B`'s top `i₀+1`
   eigenvectors to get a witness `x*`, with
   `⟪x*, T_A x*⟫ ≤ eigenvalues_A i₀ * ⟪x*,x*⟫`; combine with
   `⟪x*, T_B x*⟫ ≤ ⟪x*, T_A x*⟫` (from `T_A - T_B` PSD) and the easy
   direction applied to `T_B` at the same `x*`
   (`eigenvalues_B i₀ * ⟪x*,x*⟫ ≤ ⟪x*, T_B x*⟫`) to chain the inequality
   through. Depends on step 1.

3. **Bridge to `Matrix.IsHermitian`.** `weyl_shift` is stated over
   `Matrix n n ℝ` / `hA.eigenvalues : n → ℝ` (defined via `eigenvalues₀`
   reindexed by `Fintype.equivOfCardEq`, per `Mathlib.Analysis.Matrix.
   Spectrum`), not the abstract `LinearMap.IsSymmetric.eigenvalues` used in
   steps 1-2 above. **Not checked this session**: whether these two
   eigenvalue functions provably agree under the `Matrix.toEuclideanLin` /
   `EuclideanSpace ℝ n` identification mathlib uses internally to define
   the matrix-level `eigenvalues` in the first place. This could be a short
   `simp`-able coincidence-of-definitions lemma, or could itself be a
   nontrivial multi-step project — genuinely unknown difficulty, and
   plausibly the largest remaining unknown.

4. **Operator-norm sandwich.** Even granting 1-3, `weyl_shift`'s stated form
   is the shift inequality `|λ_i(A) - λ_i(B)| ≤ ‖A-B‖`, not raw Loewner
   monotonicity. Getting from one to the other needs
   `B - t•1 ⪯ A ⪯ B + t•1` for `t = ‖A-B‖`, i.e. that the `L²` operator norm
   of a Hermitian matrix bounds every eigenvalue in absolute value. Only
   `norm_eq_iSup_rayleighQuotient` (operator norm as a sup over *all*
   vectors, not indexed by eigenvalue) was located this session in
   `Mathlib.Analysis.InnerProductSpace.Rayleigh`; connecting it to a single
   indexed eigenvalue's absolute value is itself unproven work.

## Mathlib state re-confirmed this session

`grep -rl weyl|courant|minimax` across `Mathlib/` still turns up nothing on
point, confirmed against mathlib commit
`5ba95124681110751345e9bd360994de8541027c` (2026-08-28, tag
`master-2026-08-27-18-g5ba9512468`) — a newer snapshot than any prior
session checked. This is the fourth independent confirmation.

## Bounds, tolerances, verdicts

None touched. This is pure Lean formalization work in a doc comment; no
Python code, no certificate verdicts, no numeric tolerances were changed.
The Python side is entirely unaffected by this session.

## Validation run this session

```
$ cd /workspace/lean && lake env lean Certkit/Soundness.lean
Certkit/Soundness.lean:201:8: warning: declaration uses `sorry`
Certkit/Soundness.lean:304:5: warning: Variable name `hd` is not explicitly referenced. [pre-existing]
Certkit/Soundness.lean:547:8: warning: declaration uses `sorry`
```
Two `sorry`s (residual_encloses_some_eigenvalue, weyl_shift) — same two as
before this session, no new ones, no errors.

```
$ uv sync --extra dev
Installed 8 packages ...

$ uv run pytest tests
============================= 165 passed in 23.11s ==============================

$ uv run python3 -m certkit.cli check examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

## Bead state

`certkit-8y2.6` left `in_progress` (owner `certkit`, assignee `sandbox`),
with detailed session notes attached via `bd update --notes`. `bd export -o
issues.jsonl` was run to reflect this in the passive export file.

## Git status at handoff

Only `lean/Certkit/Soundness.lean` and `issues.jsonl` (via `bd export`) were
modified by this session. `sandbox-handoffs/certkit-8y2.6.md` (this file) is
new/untracked. All other modified/untracked files in the working tree
predate this session and belong to other beads — not touched.

Suggested commands for a human to run (not run by this session, per the
conservative git policy):
```
git add lean/Certkit/Soundness.lean issues.jsonl sandbox-handoffs/certkit-8y2.6.md
git commit -m "certkit-8y2.6: document verified Courant-Fischer hard-direction lemma, roadmap remaining steps"
```
(This intentionally does not stage the other pre-existing modified/untracked
files from other beads' sessions — a human reviewing the full tree may want
to commit those separately or leave them for their owning sessions.)

## Recommendation for the next session

Pick up at step 1 (easy direction) using the verified `courant_fischer_le`
code above as a direct template — the proof structure should mirror it
closely. Once steps 1-2 land, step 3 (the abstract-to-concrete bridge)
should be scoped first before attempting it, since it's the step with the
least visibility into its actual size; if it turns out to be large on its
own, it may be worth splitting into its own bead the same way this one was
split from certkit-8y2.3.
