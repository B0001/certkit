# certkit-1ta handoff

## Verdict / scope

Doc-only fix. No code touched, no `check()` behavior changed, no bound,
tolerance, guard, or threshold touched. Nothing to derive.

## What was stale and what's true now

The bead was filed against a snapshot where `lean/Certkit/Soundness.lean`
had 6 of 7 theorems proved (`temple_lower` and `weyl_shift` had just closed
under certkit-8y2.3/8y2.6) and one `sorry` remaining
(`residual_encloses_some_eigenvalue`).

By the time this bead was picked up, **certkit-8y2.7 had already landed**
(it's present as a closed bead with its own handoff at
`sandbox-handoffs/certkit-8y2.7.md`) and integrated the last scratch proof.
Re-checking `lean/Certkit/Soundness.lean` fresh this session showed:

- The file's own header comment (lines 1-18) already says "All seven
  theorems below are real, zero-`sorry` proofs" and names all seven:
  `rayleigh_ritz_min`, `inertia_count_below`, `gershgorin_lower`,
  `temple_lower`, `weyl_shift`, `residual_encloses_some_eigenvalue`,
  `sweep_backward_bound`.
- `grep -n "sorry"` in the file returns only prose mentions (the header
  comment explaining the *history* of what used to be `sorry`, and a
  cross-reference to `weyl_shift`'s own doc-comment caveat) — no live
  `sorry` tactic anywhere in the file.
- `lake build Certkit` (run fresh this session, from `/workspace/lean`):
  `Build completed successfully (8804 jobs)`, three unused-variable/
  unused-section-var lint warnings, zero `sorry` warnings.

So the bead's own instruction ("If certkit-8y2.7 ... has landed by the time
this is picked up, update to '7 of 7 proved' / zero sorry instead") applied:
I updated README.md to **7 of 7 / zero sorry**, not the bead's own stale
"6 of 7" numbers, per its explicit re-check instruction.

## Changes made

`README.md`:

- Line 447 (file-inventory table): `4 of 7 proved` → `7 of 7 proved`.
- Lines 471-478 ("## The Lean side" prose): replaced the "Four are real ...
  three are still `sorry`" text with a statement that all seven are real,
  zero-`sorry` proofs, names all seven theorems by their Lean identifiers,
  and folds in the same "compiling with no `sorry` is not the same claim as
  soundness-complete" caveat that's already in the Lean file's own header
  comment (kept for consistency between the two descriptions of the same
  fact). Also names `Interval.lean` as the separate, already-proved
  floating-point-enclosure obligation, matching the file's own header.

No other "sorry" / "N of 7" / "Four are real" / "three are still" strings
remain anywhere in README.md (verified by grep after the edit).

## What I did not touch

- Did not touch `lean/Certkit/Soundness.lean` itself — it was already
  correct; the bug was purely README.md being out of sync with it.
- Did not re-litigate whether `residual_encloses_some_eigenvalue`'s proof
  (or any of the other six) is *actually correct* Lean — that's outside
  this bead's scope (independent review is certkit-jcb's job, not mine,
  and not something a worker session can discharge per sandbox-prompt.md).
  I only verified the mechanical facts: no `sorry` in the file, and
  `lake build Certkit` succeeds.
- Did not touch the "Discharging the last three is a milestone in itself"
  sentence's function — replaced it since there's no "last three" anymore;
  did not invent a new forward-looking claim to replace it with, since I
  have no standing information about what's next on the Lean side beyond
  what's already tracked in beads.

## Verification run this session

Python test suite (from `/workspace`, dev extra installed):

```
============================= 181 passed in 27.56s =============================
```

(Baseline docs mention 165/172; the suite has grown since those numbers were
last written — 181 passing here is not a regression, just a larger count
than the stale references. Not something this bead asked me to reconcile,
noting it only so the number isn't mistaken for a discrepancy.)

No-dependency checker run — this container has no bare `python3` on PATH
(only uv-managed interpreters), so I ran the uv-managed CPython 3.12
interpreter directly (not via `uv run`, which would attach the project venv)
against a `PYTHONPATH` pointing at the repo, with its own empty
site-packages confirmed via `import numpy` failing first:

```
$ PYTHONPATH=/workspace <uv-managed python3.12, no project venv> -m certkit.cli check \
    examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

Lean build (from `/workspace/lean`):

```
$ lake build Certkit
...
Build completed successfully (8804 jobs).
```

(three lint warnings about unused variable/section-var names, no `sorry`
warnings, no errors)

## What I could not verify

- Whether `lake build` (the whole project, not just the `Certkit` target)
  passes cleanly is a separate question this bead doesn't ask about and I
  didn't check it — certkit-8y2.4 notes pre-existing type-class errors
  there. My verification is scoped to `lake build Certkit`, which is what
  README's own text is making a claim about.
- I did not independently re-verify the mathematical content of any of the
  seven Lean proofs — only that they compile with no `sorry`, which is the
  factual claim this bead asked README to state accurately.

## Bead / git status

- `bd update certkit-1ta --claim` done at start of session.
- Closing with `bd close certkit-1ta` now that the acceptance criteria
  (README's Lean-side table + prose match Soundness.lean's fresh state)
  are met.
- `bd export -o issues.jsonl` should be run to persist the claim/close
  before handoff, since bead state changed.
- Per repo git policy: **no commit, no push performed.** Tree is left ready
  to commit. Suggested commands for a human:

  ```
  git add README.md issues.jsonl sandbox-handoffs/certkit-1ta.md
  git commit -m "README: fix stale Lean proof count (4 of 7 -> 7 of 7, zero sorry)"
  ```

- **Note for the human reviewing `git status`:** the working tree also shows
  `lean/Certkit/Soundness.lean` modified and
  `sandbox-handoffs/certkit-8y2.7.md` untracked. I did not touch either —
  they're pre-existing uncommitted work from the certkit-8y2.7 session (the
  one that took the proof count from 6/7 to 7/7, which is what made this
  README fix land at "7 of 7" instead of the bead's own filed "6 of 7").
  That work is out of scope for certkit-1ta; flagging it only so it isn't
  mistaken for something this session produced or silently dropped. `git
  status --short` (needed `-c safe.directory=/workspace` to run at all in
  this container):

  ```
   M README.md
   M issues.jsonl
   M lean/Certkit/Soundness.lean
  ?? sandbox-handoffs/certkit-1ta.md
  ?? sandbox-handoffs/certkit-8y2.7.md
  ```
