# certkit-8y2.6 — Formalize weyl_shift: Courant-Fischer / Cauchy interlacing not in mathlib

**Status: CLOSED.** `weyl_shift` is now proved in `lean/Certkit/Soundness.lean`
with **zero `sorry`**, derived entirely from mathlib primitives. Acceptance
criteria met via route A ("weyl_shift proved with no sorry").

Note on process: the bead was closed via `bd close` slightly before this
handoff file was written, which is out of the specified order (handoff
should be written first). The session did not die in between, so no harm
resulted, but flagging it since the ordering itself was violated.

## What changed

- `lean/Certkit/Soundness.lean`:
  - Added imports: `Mathlib.Analysis.InnerProductSpace.PiL2`,
    `Mathlib.Analysis.CStarAlgebra.Matrix` (needed for the `L²` operator
    norm/`toEuclideanCLM` API and `⟪·,·⟫`/`OrthonormalBasis.toBasis` API).
  - Added `open scoped RealInnerProductSpace` (file-level; only used inside
    the new section and the new lemma/theorem, no interaction with the
    rest of the file's `⬝ᵥ`-based notation elsewhere).
  - Added a new `section CourantFischer ... end CourantFischer` block
    immediately before `weyl_shift`, containing 6 `private` lemmas/theorems
    (all newly written and verified this session, building on one
    already-verified lemma from the prior session):
    - `weyl_inf_ne_bot_of_finrank_lt`, `weyl_finrank_span_Iio_image`,
      `weyl_finrank_span_Iic_image` — dimension bookkeeping.
    - `weyl_courant_fischer_le` — hard direction of Courant-Fischer
      (carried over verbatim from the prior session's verified scratch
      work, renamed to avoid clashing with the file's ambient `n`).
    - `weyl_courant_fischer_ge` — easy direction (new this session).
    - `weyl_eigenvalues_sub_le`, `weyl_shift_abstract` — Loewner-style
      monotonicity and the abstract (non-matrix) form of Weyl's shift
      inequality (new this session).
  - Added `private lemma weyl_abs_inner_toEuclideanLin_le` (Cauchy-Schwarz
    + operator-norm sandwich, new this session) between the section and
    `weyl_shift`.
  - Replaced `weyl_shift`'s `sorry` body with a real proof: instantiate
    `weyl_shift_abstract` at `T := A.toEuclideanLin`, `TWeyl :=
    B.toEuclideanLin`, `c := ‖A - B‖`, using the abstract/concrete
    eigenvalue bridge (see below) and the operator-norm sandwich to
    discharge its hypothesis.
  - Rewrote `weyl_shift`'s doc comment (previously a multi-step "what
    remains" roadmap from four prior investigation sessions) to instead
    document how the completed proof is built, for future readers.
  - Updated the file's header comment: "Five of the seven theorems... are
    real, zero-sorry proofs... [weyl_shift and residual_encloses_some_
    eigenvalue] are still sorry" → "Six of the seven... are real,
    zero-sorry proofs... Only residual_encloses_some_eigenvalue is still
    sorry."
  - Did **not** touch `residual_encloses_some_eigenvalue` or `temple_lower`
    (the latter's proof, and the former's doc-comment wording, are
    pre-existing uncommitted changes from other beads' sessions, confirmed
    present both before and after this session's edits, untouched by me).
- Deleted `lean/Certkit/Scratch.lean` (a scratch/dev file used to build and
  verify the proof incrementally before porting it into `Soundness.lean`;
  it was tracked in git from a prior commit unrelated to this bead — its
  removal shows as a deletion in `git diff --stat` but is intentional
  cleanup, not data loss: its content is fully superseded by the real
  proof now in `Soundness.lean`).
- Deleted `/tmp/checkeig.lean`, `/tmp/checkeig2.lean` (throwaway,
  never part of the repo — used to confirm the abstract/concrete
  eigenvalue bridge is `rfl` before relying on it).
- `issues.jsonl` — updated via `bd export -o issues.jsonl` to reflect the
  closed bead and its notes.

No Python file was touched. No certificate verdict, numeric tolerance, or
documented limit was touched — this is pure Lean formalization work with
zero effect on the runtime checker.

## The mathematical content (for anyone auditing the proof)

`weyl_shift` states: for Hermitian `A B : Matrix n n ℝ` and any index `i`,
`|hA.eigenvalues i - hB.eigenvalues i| ≤ ‖A - B‖` (L² operator norm).

Proof strategy, all from mathlib primitives, no transcribed constants:

1. **Courant-Fischer min-max**, both directions, at the abstract
   `LinearMap.IsSymmetric` / `InnerProductSpace ℝ E` level:
   - Hard direction (`weyl_courant_fischer_le`): any subspace `V` of
     dimension `i₀+1` contains a nonzero `x` with Rayleigh quotient
     `≤ eigenvalues i₀`. Proved via a dimension-pigeonhole argument
     (`Submodule.finrank_sup_add_finrank_inf_eq`) intersecting `V` with the
     orthogonal complement of the span of the bottom `i₀` eigenvectors,
     then a Parseval expansion in the eigenbasis.
   - Easy direction (`weyl_courant_fischer_ge`): any `x` in the span of the
     top `i₀+1` eigenvectors has Rayleigh quotient `≥ eigenvalues i₀`. Uses
     `Module.Basis.mem_span_image` + `OrthonormalBasis.coe_toBasis` /
     `coe_toBasis_repr_apply` / `repr_apply_apply` to get that `x`'s
     coordinates vanish outside the span's index set, then the same
     Parseval expansion.
2. **Loewner-style shift bound** (`weyl_eigenvalues_sub_le`,
   `weyl_shift_abstract`): combining both directions at the same index via
   a witness vector, plus `abs_le`, gives the abstract shift inequality
   `|eigenvalues_T i₀ - eigenvalues_TWeyl i₀| ≤ c` whenever
   `∀ x, |⟪x, (T - TWeyl) x⟫| ≤ c * ⟪x, x⟫`.
3. **Abstract-to-concrete eigenvalue bridge**: `Matrix.IsHermitian.
   eigenvalues` is *definitionally* (`rfl`) equal to the abstract
   `LinearMap.IsSymmetric.eigenvalues` of `Matrix.toEuclideanLin A`, via
   `Matrix.isSymmetric_toEuclideanLin_iff` and `finrank_euclideanSpace` —
   this is exactly how `Matrix.IsHermitian.eigenvalues₀` is itself defined
   in `Mathlib.Analysis.Matrix.Spectrum`. No proof work needed beyond
   correct instantiation; verified with two standalone `rfl`-based scripts
   before relying on it in the real proof.
4. **Operator-norm sandwich** (`weyl_abs_inner_toEuclideanLin_le`):
   Cauchy-Schwarz (`abs_real_inner_le_norm`) plus the operator-norm bound
   (`Matrix.l2_opNorm_toEuclideanCLM` + `ContinuousLinearMap.le_opNorm`)
   gives `|⟪x, (toEuclideanLin M) x⟫| ≤ ‖M‖ * ⟪x,x⟫` for any real matrix
   `M`; instantiated at `M := A - B` (using `map_sub` to commute
   `toEuclideanLin` with subtraction) to discharge `weyl_shift_abstract`'s
   hypothesis with `c := ‖A - B‖`.

## Why this session succeeded where four prior sessions did not

The prior session (documented in the previous version of this handoff)
made real progress on step 1 above but flagged steps 2-4 as of
"unassessed to unknown, possibly largest" difficulty, particularly the
abstract-to-concrete eigenvalue bridge (step 3 in its numbering, step 3
here). This session picked up directly from that verified work and found:

- The "easy direction" (its step 1) required no new mathlib fact beyond
  what a moderately careful search of `OrthonormalBasis`/`Module.Basis`
  API surfaces (`mem_span_image`, `coe_toBasis*`).
- Loewner monotonicity (its step 2) was exactly the sketch it described,
  written out mechanically.
- The abstract-to-concrete bridge (its step 3, flagged as the largest
  unknown) turned out to be free — `rfl`, confirmed with two standalone
  scripts before use.
- The operator-norm sandwich (its step 4) was a direct Cauchy-Schwarz +
  operator-norm-definition combination once the right three mathlib
  lemmas were located.

In short: the prior session's pessimistic size estimates for steps 3-4
did not hold up under actual attempt. No aspect of this required a novel
mathematical idea — it is a mechanical (if intricate) assembly of
mathlib's existing spectral-theory and inner-product-space API.

## Validation run this session

```
$ cd lean && lake env lean Certkit/Soundness.lean
Certkit/Soundness.lean:203:8: warning: declaration uses `sorry`
Certkit/Soundness.lean:306:5: warning: Variable name `hd` is not explicitly referenced. [pre-existing]
Certkit/Soundness.lean:411:8: warning: automatically included section variable(s) unused ... [FiniteDimensional ℝ E] [benign linter warning]
Certkit/Soundness.lean:417:8: warning: automatically included section variable(s) unused ... [FiniteDimensional ℝ E] [benign linter warning]
```
Exactly **one** `sorry` remains: `residual_encloses_some_eigenvalue`
(theorem at line 203, `sorry` at line 205), out of scope for this bead,
unchanged by this session. Zero
errors. (Two benign `unused section variable` linter warnings, same
pattern as the prior session's scratch-file compile — harmless, the
`FiniteDimensional ℝ E` instance is in scope for the section but not
needed by these two specific finrank lemmas.)

```
$ uv sync --extra dev
Installed 8 packages ...

$ uv run pytest tests
============================= 165 passed in 23.26s ==============================

$ uv run python3 -m certkit.cli check examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```
Both match the pre-existing baseline exactly (165 passed, same VERIFIED
output) — this session's changes are Lean-only and have zero effect on
the Python checker's behavior, as expected.

## Bounds, tolerances, verdicts, documented limits

None touched, none tempted. This bead is pure Lean formalization work with
no numeric constants, no certificate verdicts, and no Python code in
scope. Nothing was softened.

## What was deliberately not done

- Did not touch `residual_encloses_some_eigenvalue` (still `sorry`) — out
  of scope for this bead; it is certkit-8y2's other remaining open Lean
  obligation, tracked separately.
- Did not touch `temple_lower`'s proof or its surrounding doc comment,
  which arrived pre-existing and uncommitted in the working tree from
  another bead's session — left exactly as found.
- Did not attempt to generalize, simplify, or "clean up" the six new
  `private` lemmas beyond what was needed to discharge `weyl_shift` — e.g.
  no attempt was made to state Courant-Fischer as a public, reusable
  mathlib-style two-sided theorem, since nothing else in this repo needs
  that generality. If a future bead needs Courant-Fischer for something
  else, these lemmas (currently `private` to `Soundness.lean`) are the
  starting point.
- Did not commit or push, per the conservative git policy below.

## What could not be verified

Nothing of substance. Both the Lean compile and the Python test suite are
fully green, and the checker's sample output matches the documented
baseline byte-for-byte.

## Bead state

`certkit-8y2.6` closed with `--reason` summarizing the discharged proof.
Detailed session notes attached via `bd update --notes` (see bead history
for the full technical account). `bd export -o issues.jsonl` was run to
reflect this in the passive export file.

## Git status at handoff

```
$ git status --porcelain
 M issues.jsonl
 D lean/Certkit/Scratch.lean
 M lean/Certkit/Soundness.lean
 M sandbox-handoffs/certkit-8y2.6.md
```
(This file was already tracked from the prior session's handoff and has
been rewritten, not appended, per the task's instructions.)
(Plus any pre-existing modified/untracked files from other beads' sessions
already in the tree before this session started — not touched, not listed
here; a human running `git status` will see the full picture.)

Suggested commands for a human to run (not run by this session, per the
conservative git policy):
```
git add lean/Certkit/Soundness.lean lean/Certkit/Scratch.lean issues.jsonl sandbox-handoffs/certkit-8y2.6.md
git commit -m "certkit-8y2.6: prove weyl_shift from mathlib Courant-Fischer/Cauchy-Schwarz primitives, zero sorry"
```
(`git add lean/Certkit/Scratch.lean` stages its deletion. This intentionally
does not stage other pre-existing modified/untracked files from other
beads' sessions — a human reviewing the full tree may want to commit those
separately or leave them for their owning sessions.)

## Recommendation for the next session

`certkit-8y2`'s remaining open Lean obligation is
`residual_encloses_some_eigenvalue` (still `sorry` in `Soundness.lean`,
line 203) — not part of this bead, but worth checking whether
`certkit-8y2` has (or needs) a dedicated child bead for it analogous to
this one, the same way `weyl_shift` was split out from `certkit-8y2.3`.
