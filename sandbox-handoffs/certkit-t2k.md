# certkit-t2k handoff

## What this bead was

`sandbox-prompt.md`'s "Do not describe the Lean side as proved" paragraph
(lines 56-77 at claim time) was stale: it said six of seven theorems in
`lean/Certkit/Soundness.lean` end in `sorry`, and that whether `lake build
Certkit` succeeds as a whole is "unsettled" pending `certkit-8y2.4`. Both
claims were wrong — `certkit-8y2.7` closed earlier this session (before I
claimed this bead) and ported in the last proof, and `certkit-8y2.3` /
`certkit-8y2.4` were already closed. This is the same class of drift
`certkit-gvg` fixed once before (2026-08-27: "7 of 7 sorry" -> "6 of 7").

## What I verified fresh, this session, repo state at claim time

Working tree already had uncommitted changes from a prior worker
(`certkit-8y2.7`'s proof port into `lean/Certkit/Soundness.lean`, plus an
unrelated `README.md` change and an already-updated Objectives section of
`sandbox-prompt.md` — none of that is mine, I left it alone).

```
$ grep -n "^\s*sorry\s*$\|:= sorry\|by sorry\| sorry$" lean/Certkit/Soundness.lean
(no output — zero actual `sorry` tactic occurrences)
```

The only remaining hits for the bare word `sorry` in the file are inside doc
comments describing history (e.g. "this was `sorry` and *false as previously
stated*... now a real, zero-`sorry` proof"), not live obligations.

```
$ cd lean && lake build Certkit
⚠ [8802/8804] Replayed Certkit.Soundness
warning: ... unused-variable / unused-section-variable lints only ...
Build completed successfully (8804 jobs).
```

Zero errors, zero `sorry` warnings, only cosmetic unused-binder lints.

Cross-checked the beads the old paragraph cited as blocking the "unsettled"
claim:

```
$ bd show certkit-8y2.3   -> CLOSED (2026-08-31)
$ bd show certkit-8y2.4   -> CLOSED (2026-08-30)
```

## What I changed

`sandbox-prompt.md`, the "Do not describe the Lean side as proved" paragraph
only. New text:

- States that all seven obligations (`rayleigh_ritz_min`,
  `residual_encloses_some_eigenvalue`, `temple_lower`, `inertia_count_below`,
  `gershgorin_lower`, `weyl_shift`, `sweep_backward_bound`) compile with zero
  `sorry`, and `lake build Certkit` succeeds as a whole — both re-measured
  this session, commands given above.
- Keeps the load-bearing caveat: a compiling proof is not the same claim as
  "the checker is proved sound end-to-end" (that also needs the Python side
  to implement what each theorem states), and keeps the specific gap
  `weyl_shift`'s own doc comment names (entrywise/row-sum bound vs. L2
  operator norm) as still open and not resolved by compilation.
- Replaces the hardcoded-count failure mode itself: instead of asserting a
  number that will drift again, it tells the next reader to re-grep for an
  actual `sorry` tactic (not the word in a doc comment) and re-run `lake
  build Certkit` before repeating the paragraph's numbers, and to check `bd
  show` on any cited bead rather than trust the status baked in here. This
  mirrors the self-aware instruction the old paragraph already had ("re-grep
  before trusting this count") which is exactly the instruction that went
  unfollowed long enough to produce this bead.

I did not touch the Objectives section (already updated by a prior
uncommitted change, not part of this bead) or the "Known baseline" section's
hardcoded `165 passed` (now stale too, actual is 181 — filed as a separate
bead, `certkit-shj`, since it's out of this bead's scope).

## No bounds, tolerances, guards, or thresholds touched

This bead is documentation-only (a `.md` status paragraph). Nothing in
`interval.py`, `backward_error.py`, `checker.py`, or any other trusted module
changed. No transcribed constants introduced.

## Documented limits: nothing softened

Not applicable — no numeric claim in the repo's stated limitations (coverage
cliff, `DENSE_LIMIT`, Gershgorin-as-floor, n ≈ 10⁴ eigenvector binding
constraint) was touched. The Lean paragraph's new text is *stricter* than
before in one sense: it explicitly separates "compiles with zero sorry" from
"the checker is proved sound end-to-end," which the old paragraph did too but
now states with the correct count instead of an inflated one.

## Test suite

```
$ uv run --extra dev pytest tests
...
181 passed in 27.67s
```

(181, not the README/sandbox-prompt.md's stale 165 — this run reflects
`certkit-8y2.7`'s prior-session test additions, not anything from this bead.)

No-dependency checker run (this container's `python3` is not on `PATH`;
used the interpreter `uv` actually manages, following the precedent in
`sandbox-handoffs/certkit-8y2.7.md`):

```
$ /home/node/.local/share/uv/python/cpython-3.12-linux-aarch64-gnu/bin/python3.12 -c "import numpy"
ModuleNotFoundError: No module named 'numpy'

$ /home/node/.local/share/uv/python/cpython-3.12-linux-aarch64-gnu/bin/python3.12 -m certkit.cli check examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

Trust boundary holds: the checker runs and verifies with no third-party
package importable.

## What I decided not to do, and why

- Did not fix the "165 passed" staleness in the same file's "Known baseline"
  section, even though I noticed it and it's the same failure mode. It's a
  different paragraph, outside this bead's stated acceptance criteria
  (which names the Lean-status paragraph specifically), and the prompt's own
  rules say discovered out-of-scope work gets filed, not done inline. Filed
  as `certkit-shj`.
- Did not touch the uncommitted `README.md` or `lean/Certkit/Soundness.lean`
  changes already sitting in the working tree from the prior `certkit-8y2.7`
  session — verifying them isn't this bead's job, and I re-derived their
  factual claims (sorry count, build status) independently rather than
  trusting them, which is what let me confirm they're consistent with what I
  found.
- Did not rewrite the paragraph to a static "zero sorry, build succeeds"
  claim without the re-measure instruction. The whole reason this bead
  exists is that a static claim in standing context goes stale the moment
  another Lean bead lands; baking in *how to re-check* rather than just a
  fresher number is meant to make the next drift self-correcting instead of
  requiring another `certkit-t2k`-style bead.

## What I could not verify

- Whether `certkit-8y2.7`'s uncommitted proof port (sitting in the working
  tree, not mine) is itself correct beyond "compiles and lints clean" — I
  didn't review the proof content, only confirmed the build/sorry-count
  facts my paragraph asserts. That review is `certkit-8y2.7`'s concern, not
  this bead's, and `certkit-8y2.7` is already closed with its own handoff.
- Whether any *other* file in the repo (beyond `sandbox-prompt.md`) still
  repeats the stale "6 sorry" / "unsettled build" claim. I grepped
  `sandbox-prompt.md` itself for recurrences (none) but did not grep the
  whole repo; the bead's acceptance criteria is scoped to
  `sandbox-prompt.md` specifically.

## Git status — tree is NOT committed, per policy

```
Changes not staged for commit:
  modified:   README.md              <- NOT mine, from certkit-8y2.7
  modified:   issues.jsonl           <- mine (bd export), + certkit-8y2.7's bead updates
  modified:   lean/Certkit/Soundness.lean  <- NOT mine, from certkit-8y2.7
  modified:   sandbox-prompt.md      <- mine (this bead) + pre-existing Objectives edit (not mine)

Untracked:
  sandbox-handoffs/certkit-1ta.md    <- NOT mine
  sandbox-handoffs/certkit-8y2.7.md  <- NOT mine
  sandbox-handoffs/certkit-93j.md    <- NOT mine
  sandbox-handoffs/certkit-t2k.md    <- this file
```

Suggested commands for a human to review and run:

```
git add sandbox-prompt.md issues.jsonl sandbox-handoffs/certkit-t2k.md \
        README.md lean/Certkit/Soundness.lean \
        sandbox-handoffs/certkit-1ta.md sandbox-handoffs/certkit-8y2.7.md \
        sandbox-handoffs/certkit-93j.md
git commit -m "certkit-t2k: fix stale Lean-status paragraph in sandbox-prompt.md

Re-measured lean/Certkit/Soundness.lean: zero sorry (all seven theorems
compile), lake build Certkit succeeds as a whole (8804/8804 jobs). Old
paragraph said 6/7 sorry and called the whole-build question unsettled,
citing certkit-8y2.3/certkit-8y2.4 as open -- both are closed. Rewrote to
state the fresh numbers and to instruct re-measurement instead of trusting
a hardcoded count next time.

Also carries forward certkit-8y2.7's uncommitted proof port and unrelated
handoff files that were sitting in the working tree at claim time."
git status
```

I did not run any of the above — git policy for this session is
report-only.
