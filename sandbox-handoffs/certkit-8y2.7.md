# certkit-8y2.7 — Integrate the zero-sorry `residual_encloses_some_eigenvalue` proof into Soundness.lean

**Status: CLOSED.** `residual_encloses_some_eigenvalue` is now proved in
`lean/Certkit/Soundness.lean` with **zero `sorry`**, ported from the
untracked scratch file `lean/ScratchSTRATEGYKEY.lean` left by a prior
session. All seven soundness obligations in `Soundness.lean` now compile
with no `sorry` anywhere in the file.

Handoff written before `bd close`, per the ordering the prompt asks for.

## What changed

- `lean/Certkit/Soundness.lean`:
  - Replaced the `sorry` body of `residual_encloses_some_eigenvalue`
    (previously lines 203-205) with the direct/forward proof ported from
    `ScratchSTRATEGYKEY.lean`'s `CertkitScratch.residual_encloses_some_eigenvalue`,
    as the bead's DESIGN section recommended (shortest of the four scratch
    proofs, structure matches the file's own style: pick the closest
    eigenvalue by `Finset.exists_min_image`, then bound directly via the
    unitary eigendecomposition and Rayleigh quotient algebra).
  - Dropped the scratch file's local `private lemma shift_eq` (a copy of
    `sub_smul_one_eq_mul_diagonal_mul_transpose`, duplicated only because
    private lemmas aren't importable across files) and called
    `sub_smul_one_eq_mul_diagonal_mul_transpose hA` directly, since the
    proof now lives in the same file as that lemma (already present at
    `Soundness.lean:88-108`, used by three other theorems in the file).
    This is the only substantive change from the scratch file — everything
    else in the proof body is verbatim.
  - Updated the header doc comment (lines 1-11 originally): changed "Six of
    the seven theorems below are real, zero-sorry proofs... Only
    residual_encloses_some_eigenvalue is still sorry" to state all seven are
    zero-sorry, while keeping — and slightly sharpening — the
    "soundness-complete" hedge: it now explicitly says that a theorem
    compiling with no `sorry` is a fact about the Lean file, not the same
    claim as "the checker is proved sound end-to-end" (that also needs the
    Python correspondence table below it to hold, and needs `lake build
    Certkit` to succeed as a whole, which is checked separately). It also
    forwards a pointer to `weyl_shift`'s own doc comment about the
    entrywise/row-sum-vs-L2-operator-norm gap, per the bead's step 7 (see
    "Explicitly out of scope" below — I did not touch that gap itself).
- Deleted the five untracked scratch files per the bead's step 4 and the
  `certkit-8y2.6` precedent ("nothing scratch-only survives in the repo"):
  `lean/Chk.lean`, `lean/ScratchPosDefContradiction.lean`,
  `lean/ScratchSTRATEGYKEY.lean`, `lean/ScratchSTRATEGYKEY_mathlib.lean`,
  `lean/VerifyPsdShift.lean`. None were ever committed (all showed as
  untracked in `git status` at session start), so this is not a git
  deletion, just cleanup of the working tree.
- `issues.jsonl`: re-exported via `bd export -o issues.jsonl` to capture the
  claim/close of this bead in the durable git-tracked export.

## Verdict / evidence

Before this session: `lake build Certkit` succeeded as a whole (8804 jobs)
with exactly one `sorry` warning, at `Certkit/Soundness.lean:203:8`
(`residual_encloses_some_eigenvalue`). This was independently re-confirmed
at the start of this session.

After this session:

```
$ cd lean && lake build Certkit
⚠ [8802/8804] Built Certkit.Soundness (7.3s)
warning: Certkit/Soundness.lean:362:5: Variable name `hd` is not explicitly referenced. [...]
warning: Certkit/Soundness.lean:467:8: automatically included section variable(s) unused [...]
warning: Certkit/Soundness.lean:473:8: automatically included section variable(s) unused [...]
✔ [8803/8804] Built Certkit (5.1s)
Build completed successfully (8804 jobs).
```

Zero `sorry` warnings. The three remaining warnings are pre-existing lint
notes (unused binder name in `inertia_count_below` at line 362, unused
`[FiniteDimensional ℝ E]` section variables in two `private` lemmas from the
`certkit-8y2.6` session at lines 467/473) — none in the ported proof, none
new, all cosmetic (unused-name/unused-typeclass-argument lints, not
soundness-relevant).

`grep -n sorry lean/Certkit/Soundness.lean` after the change: the only
remaining hits are inside prose (doc comments referring to the word
"sorry" historically — the file's own header, the `temple_lower` doc
comment's incident history, and `sweep_backward_bound`'s doc comment
pointing at `weyl_shift`'s note) — no `sorry` tactic anywhere in the file.

Re-ran `lake build Certkit` a second time after deleting the five scratch
files to confirm their removal doesn't affect the build (it doesn't —
`Soundness.lean` never imported any of them; `Certkit.Soundness` replayed
from cache, `Certkit` rebuilt clean, same 8804/8804 jobs, same three
pre-existing warnings).

Independently confirmed axiom hygiene on the scratch file before deleting
it (this was already done by the previous session and re-checked here):
`#print axioms residual_encloses_some_eigenvalue` in `ScratchSTRATEGYKEY.lean`
reports only `[propext, Classical.choice, Quot.sound]` — the three standard
mathlib axioms, no `sorryAx`, no extra axioms.

## Bounds/tolerances/thresholds touched

None. This bead is pure Lean proof-porting; no numeric constant, bound, or
threshold was introduced, widened, or changed anywhere.

## Documented limits softened?

None softened. I was careful with the header doc comment specifically
*not* to let "all seven theorems are zero-sorry" read as "the checker is
proved sound end-to-end" — see the updated wording above, which adds an
explicit caveat distinguishing "this Lean file has no sorry" from "the
Python-Lean correspondence and the whole-project `lake build` are also
established" (the whole-project build point already holds per this
session's evidence, but the correspondence-table point is a standing
claim this doc comment doesn't newly assert and shouldn't).

## Test suite

Pure Lean work; no Python files touched. Re-ran the Python suite per the
bead's step 5 to confirm no regression:

```
$ uv sync --extra dev  # confirms deps are current
$ uv run --extra dev pytest tests
============================= 181 passed in 27.65s ==============================
```

(181, not the 165/172 figures quoted elsewhere in this repo's standing
docs — those are stale counts from earlier sessions; 181 is what this
session observed both as a baseline check and unaffected by this bead's
changes, since nothing under `tests/` or `src/` was touched.)

No-dependency checker run (this container's `python3` is not on `PATH` at
all — a container quirk, not a repo problem, see below — so I used the
bare interpreter uv keeps outside the project venv, which has no
third-party packages installed, satisfying the same "no dependency"
property the prompt's exact command is checking for):

```
$ /home/node/.local/share/uv/python/cpython-3.12-linux-aarch64-gnu/bin/python3.12 -c "import numpy"
ModuleNotFoundError: No module named 'numpy'
$ /home/node/.local/share/uv/python/cpython-3.12-linux-aarch64-gnu/bin/python3.12 -m certkit.cli check examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

## What I decided not to do, and why

- Did **not** touch `Soundness.lean:642`'s stale cross-reference to
  `weyl_shift`'s "own sorry" (weyl_shift has been zero-sorry since
  `certkit-8y2.6` closed). The bead's step 7 explicitly says not to
  silently fix this as part of 8y2.7 since it's a distinct piece of work
  tracked separately — I did not touch those lines and did not go looking
  for the separate bead that's supposed to track it (out of scope for this
  session; whoever picks that up should `bd ready`/search for it rather
  than assume I filed it, since I did not).
- Did **not** port any of the other three scratch proofs
  (`ScratchPosDefContradiction.lean`, `ScratchSTRATEGYKEY_mathlib.lean`,
  `VerifyPsdShift.lean`) — the bead's DESIGN section recommends
  `ScratchSTRATEGYKEY.lean` specifically as shortest and closest in style,
  and one proof of the obligation is sufficient; porting redundant proofs
  of the same statement would add nothing.
- Did close the parent epic `certkit-8y2`. Its own acceptance criterion is
  literally "Soundness.lean compiles against mathlib4 with no sorry," which
  this bead's evidence directly satisfies, and `bd show certkit-8y2`
  confirmed all 6 sibling children (`8y2.1` through `8y2.6`) were already
  ✓ before this session — this bead was the only remaining ◐. The bead's
  own step 6 explicitly names this as in-scope ("consider closing the epic
  in the same session if nothing else is left under it"), so I did not
  treat it as scope creep.

## What I could not verify

- I did not independently re-derive the mathematical proof by hand beyond
  reading it — I verified it compiles (which is the actual soundness
  guarantee: Lean's kernel checked it, not my reading of it) and verified
  the axiom list is the standard three. I did not attempt to find an
  alternative, independent proof to cross-check against, the way
  `certkit-jcb` (still correctly open, untouched by me) asks a human
  reviewer to eventually do for the Python side.

## Commands for a human to run

```
git add lean/Certkit/Soundness.lean issues.jsonl
git status   # confirm the five untracked scratch files are gone, nothing else changed
git commit -m "certkit-8y2.7: integrate residual_encloses_some_eigenvalue proof, zero sorry in Soundness.lean; close certkit-8y2 epic"
```

## Bonus: closed the parent epic

`certkit-8y2` (Discharge the Lean soundness obligations) is now closed too
— all 7 children complete, acceptance criterion ("Soundness.lean compiles
against mathlib4 with no sorry") met. See `bd show certkit-8y2` for the
close reason. `issues.jsonl` was re-exported after this to capture both
closes.

I did not run these — git policy for this session is report-only.
