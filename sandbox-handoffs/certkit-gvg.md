# certkit-gvg — sandbox-prompt.md misdescribed the Lean proof status

## Verdict change

None — this is a documentation-only fix to `sandbox-prompt.md` (the standing
prompt template every worker session reads), not to `certkit/` or `lean/`.
No `check()` behavior, rule, tolerance, or test changed. No soundness
surface.

## What was wrong

`sandbox-prompt.md` lines 56-62 said:

> `lean/Certkit/Soundness.lean` states seven obligations against mathlib4 and
> every one ends in `sorry`. The file has never been compiled here. One of
> the seven, `sweep_backward_bound`, is currently stated as `True` — the
> obligation with the worst failure mode is not yet even written down.

This was stale. Read `lean/Certkit/Soundness.lean` directly (current HEAD,
commit `39d6ff3`):

- The file's own header docstring (lines 1-10) already says six of seven are
  `sorry`, and the seventh (`sweep_backward_bound`) is "a real, compiled,
  zero-`sorry` proof."
- `sweep_backward_bound`'s body (lines 146-152) is not `sorry` and not a bare
  `True` — it's discharged by `sweep_step_backward_bound hu hu1 h0 h1 h2 h3`,
  a real lemma imported from `Certkit.BackwardError`, landed under
  certkit-8y2.2 (closed, commit 508caf2 and later).
- `grep -n sorry lean/Certkit/Soundness.lean` at close time confirms exactly
  six `sorry`s, on: `rayleigh_ritz_min`, `residual_encloses_some_eigenvalue`,
  `temple_lower`, `inertia_count_below`, `gershgorin_lower`, `weyl_shift`.

The stale text traces to certkit-8y2.2 landing without a matching update to
sandbox-prompt.md's guardrail paragraph, which every future worker reads as
ground truth. Left uncorrected it risks a session either overclaiming the
Lean side is proved, redoing `sweep_backward_bound` as duplicate work, or
missing that `weyl_shift`'s own doc comment (Soundness.lean lines 104-123)
flags a real, currently-uncovered gap (the entrywise/row-sum bound
`sturm_be` actually computes at runtime vs. the L2 operator norm
`weyl_shift` is stated against) — arguably now a better fit for "the
obligation with the worst failure mode not yet written down" than
`sweep_backward_bound`, which is finished.

## What changed

Rewrote sandbox-prompt.md's "Do not describe the Lean side as proved"
paragraph (previously lines 56-62) to:

- Name the six still-`sorry` theorems explicitly instead of an aggregate "all
  seven."
- Correctly describe `sweep_backward_bound` as a real, zero-`sorry` proof
  (formalized under certkit-8y2.2, closed), and what it does and doesn't
  cover (one-rounding-per-operation model + eta/gamma collection; not the
  row-sum-dominates-operator-norm argument, which stays under `weyl_shift`).
- Point at `weyl_shift`'s doc comment as the more honest "worst failure mode
  not yet written down" candidate, per the bead's own reasoning.
- Add a forward-looking instruction to re-grep for `sorry` rather than trust
  a hardcoded count, since certkit-8y2.3 and certkit-8y2.4 are open/
  in_progress and may change it before this text is read again.
- Explicitly decouple "does an individual theorem check via `lake env lean`"
  from "does `lake build Certkit` succeed as a whole" (the latter is what
  certkit-8y2.4, still open, is about) rather than repeat the old text's flat
  "never compiled here" claim, which I could not verify either way this
  session (see Unverified below) and which conflates the two questions.

No other file in the repo repeats the stale wording (`grep -rn` across
`*.md` for the old phrasing found nothing left after the edit).

## Bounds/tolerances/thresholds touched

None. This bead has no soundness surface — confirmed by re-reading the bead
description before starting.

## Documented limits I did not touch

None relevant here. (Did not touch the separate `106 passed` stale-baseline
text in sandbox-prompt.md lines 66/106 or README.md:448 — that's a distinct,
already-filed bead, certkit-j82, out of scope for certkit-gvg. My own test
run below shows 154 passed, consistent with that bead's finding; I did not
"fix" that number since it's not this bead's scope.)

## Test run (verbatim)

```
$ uv sync --extra dev
Resolved 20 packages in 1ms
Installed 8 packages in 465ms
...

$ uv run pytest tests
tests/test_backends.py ..............                                    [  9%]
tests/test_backward.py ....................                              [ 22%]
tests/test_banded.py ...............                                     [ 31%]
tests/test_complex_hermitian.py .................                        [ 42%]
tests/test_complex_witness_transcription.py ......                       [ 46%]
tests/test_composition.py ....................                           [ 59%]
tests/test_end_to_end.py ............                                    [ 67%]
tests/test_generalized.py ..........                                     [ 74%]
tests/test_interval.py ..................                                [ 85%]
tests/test_sector_scope.py ....                                          [ 88%]
tests/test_tamper.py ..............                                      [ 97%]
tests/test_trust_boundary.py ....                                        [100%]

============================= 154 passed in 20.07s =============================
```

(154, not the sandbox-prompt.md-documented 106 — that mismatch is
certkit-j82's finding, not new, and not this bead's scope.)

## No-dependency checker run

**Could not run.** This container has no bare `python3` on `PATH` (only
`/tmp/venv/bin/python3` and `/workspace/.venv/bin/python3`, both of which
have numpy installed via the dev extra, which defeats the point of the
check). `which python3` / `python3 -m certkit.cli ...` fails with "command
not found". This is an environment gap, not something this bead's change
caused or could verify around — it is a pure text edit to a `## ...`
markdown paragraph, touches zero files under `certkit/`, and
`tests/test_trust_boundary.py` (which runs the checker in a subprocess where
numpy is unimportable, in-repo) passed as part of the 154 above, which is
the load-bearing version of this check.

## What I decided not to do, and why

- Did not attempt to get `lake build Certkit` compiling as a whole, or
  investigate whether it currently does. Tried `lake env lean
  Certkit/Soundness.lean` once, out of curiosity while verifying the sorry
  count; it failed trying to `git clone` mathlib (no network egress /
  no local package cache in this container), which is orthogonal to
  certkit-8y2.4's actual type-class-error scope. Did not chase this further
  — it's certkit-8y2.4's bead, not mine, and my bead's evidence
  (`grep -n sorry`) doesn't require a successful build.
- Did not touch sandbox-prompt.md's `106 passed` baseline (lines 66, 106) or
  README.md:448's `106 tests` figure, despite noticing they're also stale
  (154 now). Already filed as certkit-j82 by an earlier session; fixing it
  here would be scope creep into another bead's acceptance criteria.
- Did not close or otherwise touch certkit-8y2.3 / certkit-8y2.4 (both
  in_progress, owned by other work) even though my corrected paragraph now
  references their open status as a reason to re-grep rather than trust a
  hardcoded count.

## What I could not verify

- Whether `lake build Certkit` succeeds as a whole in a from-scratch
  container right now (mathlib cache/network unavailable to me this
  session; certkit-8y2.3's notes from 2026-08-26 claim it did succeed then,
  but certkit-8y2.4 — the type-class-error bead — is still open, so I did
  not rely on that claim for anything in the rewritten paragraph beyond
  pointing at certkit-8y2.4 as the place that question lives).
- The no-dependency checker invocation from sandbox-prompt.md's own
  Environment section (`python3 -m certkit.cli check ...`) — no bare
  `python3` binary exists in this container. Substituted
  `tests/test_trust_boundary.py`'s in-repo equivalent, which passed.

## Files changed

- `sandbox-prompt.md` — rewrote the "Do not describe the Lean side as
  proved" paragraph (documentation only).
- `issues.jsonl` — re-exported via `bd export -o issues.jsonl` to capture
  this bead's claim/close state and an unrelated prior session's addition
  of certkit-gvg and certkit-j82 to the tracker (both were already present
  in the Dolt DB but not yet exported to the git-tracked file at session
  start — `git status` showed `M issues.jsonl` before I touched anything).

## Suggested commands for a human to run

```
git status
git diff sandbox-prompt.md
git add sandbox-prompt.md issues.jsonl
git commit -m "docs: correct sandbox-prompt.md's stale Lean proof-status paragraph (certkit-gvg)"
```

Not run — git policy for this session is conservative (no commit/push
without explicit authority).
