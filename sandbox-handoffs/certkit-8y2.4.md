# certkit-8y2.4 — Fix pre-existing type-class errors in Soundness.lean

Status: **closed**, evidence below. This session did not write the fix — it
was already in the tree, applied across two earlier sessions — and instead
re-verified it from scratch and closed the bead, which had been left
`in_progress` despite the work being done.

## What this session found on claiming the bead

`bd show certkit-8y2.4` was `in_progress` (started 2026-08-22) with zero
notes and zero comments. `git log --oneline -- Certkit/Soundness.lean`
showed the fix already present, in two layers:

1. A **previous certkit-8y2.4 session** (its handoff is the git history of
   this file, overwritten below) added `[LinearOrder n]` to
   `inertia_count_below` and `open scoped Matrix.Norms.L2Operator in` before
   `weyl_shift`, wired `Certkit.Soundness` into `Certkit.lean`'s import
   list, and reported `lake build Certkit` succeeding at 8770 jobs with 6
   `sorry` warnings. That session apparently ended without running
   `bd close certkit-8y2.4` — the fix landed in the tree but the bead
   didn't reflect it.
2. **Commit `1c509d3`** ("Prove rayleigh_ritz_min, inertia_count_below,
   gershgorin_lower; Euclidean residualNorm"), done under beads
   certkit-8y2.3/8y2.5, discharged the `inertia_count_below` `sorry` itself
   (now a real zero-`sorry` proof, still carrying the `[LinearOrder n]` this
   bead added), bumped the pinned mathlib rev from `67f608e6...` to
   `5ba95124...`, and its own commit message explicitly credits this bead:
   *"inertia_count_below gains `[LinearOrder n]`; weyl_shift opens
   `Matrix.Norms.L2Operator` locally (8y2.4)"*. It reports `lake build
   Certkit` succeeding at 8804 jobs.

So the fix has now been re-verified against a newer mathlib pin than the one
it was first written against, by a session that also proved three of the
theorems it sits next to. Nothing needed re-fixing; I re-ran the acceptance
criteria to confirm it's still true today rather than trusting either
session's claim on faith.

## Re-verification performed this session

```
$ lake build Certkit
⚠ [8802/8804] Replayed Certkit.Soundness
warning: Certkit/Soundness.lean:201:8: declaration uses `sorry`
warning: Certkit/Soundness.lean:226:8: declaration uses `sorry`
warning: Certkit/Soundness.lean:344:8: declaration uses `sorry`
warning: Certkit/Soundness.lean:247:5: Variable name `hd` is not explicitly referenced.
Build completed successfully (8804 jobs).
```

`Certkit.lean` (the default `lake build Certkit` target) still imports
`Certkit.Soundness` (confirmed by reading `lean/Certkit.lean`):

```
import Certkit.Interval
import Certkit.BackwardError
import Certkit.Soundness
```

The two original type-class sites, confirmed present and unchanged in
substance:

- `Certkit/Soundness.lean:246` — `theorem inertia_count_below [LinearOrder n] (β : ℝ) (d : n → ℝ) ...`
  — the fix this bead specified. (This theorem is no longer `sorry` at all
  — `certkit-8y2.3`'s later work discharged it — but the `[LinearOrder n]`
  this bead added is still exactly what makes it type-check.)
- `Certkit/Soundness.lean:318` — `open scoped Matrix.Norms.L2Operator in`
  immediately before `theorem weyl_shift` at line 344 — the fix this bead
  specified, still `sorry` (proving Weyl's inequality itself is
  `certkit-8y2.3`'s scope, not this bead's).

`grep -rn sorry` across `lean/*.lean` (excluding `.lake`) finds exactly
three `sorry` tactic invocations, all in `Soundness.lean`: lines 203
(`residual_encloses_some_eigenvalue`), 232 (`temple_lower`), 346
(`weyl_shift`). That's *fewer* than the "6 that already exist" the
acceptance criteria bound against — `rayleigh_ritz_min`,
`inertia_count_below`, and `gershgorin_lower` were proved out from under
that count by certkit-8y2.3's later work, which is a different bead's
progress, not a regression of this one. No new `sorry` was introduced by
anything in scope here.

## Acceptance criteria, checked

- **"Both type-class errors resolved"** — yes, `[LinearOrder n]` on
  `inertia_count_below` (now moot for that theorem specifically since it's
  proved, but still the correct signature) and the scoped `L2Operator`
  norm open for `weyl_shift`. Confirmed by successful `lake env lean`-style
  compilation (via full `lake build Certkit` above) with zero
  `synthInstanceFailed` errors.
- **"`lake build Certkit` succeeds with Certkit.Soundness imported from
  Certkit.lean"** — yes, verbatim log above, 8804 jobs, exit success.
- **"no new sorry introduced beyond the 6 that already exist as intentional
  specification placeholders"** — 3 remain, not 6; none added.

## Bounds, tolerances, guards, or thresholds touched

None, by me, this session. I made no edits to `Soundness.lean` or any other
file — the fix was already in the tree and I only re-ran the build and
tests to confirm it still holds. The prior sessions' fixes
(`[LinearOrder n]`, the scoped norm open) are type-class/scope
annotations, not numeric constants, and carry their own derivations in the
theorem doc comments at lines 240-245 and 320-343 of `Soundness.lean`.

## Documented limits or hedges

None touched. I did not soften the file's header claim ("Four of the seven
theorems below are real, zero-`sorry` proofs... The other three... are
still `sorry`... Do not read this file as soundness-complete") — it's
accurate as of this session's build, and I left it as-is.

## What I decided not to do, and why

- **Did not touch any of the three remaining `sorry`s**
  (`residual_encloses_some_eigenvalue`, `temple_lower`, `weyl_shift`).
  Discharging them is certkit-8y2.3's scope, not this bead's — this bead is
  specifically the *type-class plumbing* that lets the file compile at all,
  which was already done.
- **Did not re-do or alter the `[LinearOrder n]` / `L2Operator` fix.** It's
  correct as written (verified by the successful build) and re-deriving it
  from scratch would only risk introducing a divergent, unreviewed second
  fix for an already-solved problem.
- **Did not touch the uncommitted working-tree diff on
  `lean/lakefile.toml` / `lean/lake-manifest.json`** (an explicit
  `rev = "5ba95124..."` pin plus the matching `inputRev` field). That's
  live WIP for a separate, currently in-progress bead (`certkit-3py`,
  "lakefile.toml pins mathlib with no rev"), not this one. It doesn't
  change the resolved mathlib revision (the manifest already pinned that
  rev; the diff only makes the pin explicit and reproducible against `lake
  update`), so it didn't affect this session's build or test results
  either way.
- **Did not run `bd export -o issues.jsonl` for anything beyond this
  bead's own close**, since I made no other bead-database edits this
  session.
- **Did not commit or push.** Per repo git policy — there is nothing to
  commit from this session anyway, since no files were changed; the
  `Soundness.lean`/`Certkit.lean` fix is already committed (it landed in
  `1c509d3`, already on `main`).

## What I could not verify

- **Whether the original (first) certkit-8y2.4 session's own handoff
  claims are accurate in every detail** (e.g. its reported job count of
  8770 vs. today's 8804, or its specific line numbers, which have since
  shifted because of later doc-comment and proof insertions). I did not
  need to take that handoff on faith — I independently reproduced the
  acceptance criteria against the current tree — but I did not audit its
  narrative line-by-line beyond confirming its two named fixes are present
  and doing what it says.
- **Whether `1c509d3`'s mathlib bump (67f608e6 → 5ba95124) was itself
  reviewed/intentional** rather than transient `lake update` drift — that's
  exactly what `certkit-3py` (open, in progress, not mine) exists to make
  impossible going forward. Not this bead's concern, but flagging it since
  it's adjacent.
- **`#print axioms` was not run** on `inertia_count_below` or any other
  theorem — out of scope for a type-class-plumbing bead whose evidence is a
  successful build, not a proof audit.

## Final commands and output

```
$ lake build Certkit
⚠ [8802/8804] Replayed Certkit.Soundness
warning: Certkit/Soundness.lean:201:8: declaration uses `sorry`
warning: Certkit/Soundness.lean:226:8: declaration uses `sorry`
warning: Certkit/Soundness.lean:344:8: declaration uses `sorry`
Build completed successfully (8804 jobs).
```

```
$ uv sync --extra dev
Installed 8 packages ...

$ uv run pytest tests
tests/test_backends.py ..............                                    [  8%]
tests/test_backward.py ....................                              [ 20%]
tests/test_banded.py ...............                                     [ 29%]
tests/test_complex_hermitian.py .................                        [ 40%]
tests/test_complex_witness_transcription.py ......                       [ 43%]
tests/test_composition.py ....................                           [ 55%]
tests/test_end_to_end.py ............                                    [ 63%]
tests/test_exact_oracle.py ...........                                   [ 69%]
tests/test_generalized.py ..........                                     [ 75%]
tests/test_interval.py ..................                                [ 86%]
tests/test_sector_scope.py ....                                          [ 89%]
tests/test_tamper.py ..............                                      [ 97%]
tests/test_trust_boundary.py ....                                        [100%]

============================= 165 passed in 23.29s =============================
```

No-dependency checker run: this container has **no system `python3` at
all** (not `/usr/bin/python3`, not a bare uv-managed interpreter outside a
venv — only `.venv`'s and `/tmp/venv`'s own `bin/python3`). That's a
container difference from what the environment notes describe, not
something I could fix. `tests/test_trust_boundary.py` (part of the 165
above) already automates the intended check — it runs the checker via
`sys.executable` in a subprocess with `numpy`/`scipy` blocked at
`sys.meta_path` — and passed. As the closest manual equivalent, I ran the
same meta-path block directly against the project venv's interpreter:

```
$ /tmp/venv/bin/python3 - <<'EOF'
import sys
class Block:
    def find_module(self, name, path=None):
        if name.split('.')[0] in ('numpy', 'scipy'):
            raise ImportError('blocked: ' + name)
sys.meta_path.insert(0, Block())
sys.argv = ['certkit', 'check', 'examples/sample/certificate.json', 'examples/sample/operator.json', '-v']
from certkit.cli import main
raise SystemExit(main())
EOF
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

## Files changed by this session

None. `git status` shows only the pre-existing, unrelated
`lean/lakefile.toml` / `lean/lake-manifest.json` working-tree diff that
belongs to `certkit-3py`. This session's only change is to the bead
database (claim + close of `certkit-8y2.4`) and this handoff file.

## Suggested next commands

```
bd export -o issues.jsonl   # persist the certkit-8y2.4 close into the git-tracked export
git status                  # confirm only issues.jsonl + this handoff are new/changed
```

Nothing to commit on the Lean side — the fix is already on `main` as part
of `1c509d3`. The `lean/lakefile.toml` / `lean/lake-manifest.json` diff
belongs to the separate open bead `certkit-3py`; leave it for that bead's
session to commit or continue.
