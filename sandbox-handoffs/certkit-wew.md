# Handoff: certkit-wew (correct session 6's inflated 13x-38x dense-comparison constants)

## Outcome

**Bead resolved and closed.** This is documentation/notes cleanup only — no
code, test, threshold, or bound in `certkit/` touched. Nothing in this bead
changes a verdict, a tolerance, or anything soundness-relevant.

## What the bug was

`certkit-ph1` session 6 (`sandbox-handoffs/certkit-ph1.md`) measured
minimum-degree fill-reducing LDL^T elimination on Pauli-sum sparsity graphs
and reported the op-count proxy (`sum of pivot-degree^2`) against a literal
`n^3` dense baseline, concluding "a roughly constant 13x-38x reduction versus
literal dense O(n^3)". That baseline is wrong: the same proxy evaluated on a
genuinely dense graph is `sum_k (n-1-k)^2 = n^3/3 - n^2/2 + n/6`
(`0.33321*n^3` at n=4096), not `n^3`. Dividing by `n^3` instead of the correct
same-proxy dense value inflates every "Nx under dense" figure by exactly 3x.
Corrected: `ops/n^3 = 0.026` is `0.078` of same-proxy dense = **12.8x**, not
38x; `ops/sector = 0.08` is `0.24` of same-proxy dense-per-sector = **4.2x**,
not 12.5x. `certkit-cpo` (session 7) found this, derived the correction
(Result 2, `sandbox-handoffs/certkit-ph1.md`), and filed this bead to sweep
up any place the uncorrected figure had leaked to and not yet been annotated.

This never touched a soundness claim or any code — it is purely a reported
performance constant in scratch research write-ups and bd metadata.

## What I found and what I did

Searched the whole repo (`grep -rn "13x\|38x"` over `*.md/*.py/*.json/*.txt`,
excluding the Lean package vendor tree) plus every currently open/in-progress
bead in the Dolt DB. Four occurrences existed of the "13x/38x"-family figure:

1. **`sandbox-handoffs/certkit-ph1.md`, "Session 6" section (original text,
   lines ~148-159).** Left **intact**, as the bead's acceptance criteria
   requires ("the session-6 section itself left intact as a historical
   record"). This section is already preceded by an explicit superseding
   note (added by session 7, lines 37-53 of the file) that names the 3x
   error, gives the corrected ~4x-13x range, and points to Result 2 before a
   reader reaches "Session 6". No further action needed — this was already
   done correctly before this bead was filed.

2. **`sandbox-handoffs/certkit-ph1.md`, "Session 7" section (Result 2,
   Result 4, Result 10).** Already states the corrected numbers throughout
   (`12.8x`, `12.5x`->`12.7x` refined, `4.2x`, explicit "not 38x" callouts).
   No action needed — this is the corrected version the other occurrences
   now point to.

3. **`certkit-ph1`'s bd `notes` field (issue is CLOSED).** The session-6
   summary copied into bd notes at the time repeated the uncorrected
   "13x-38x reduction vs. literal dense O(n^3)" conclusion, with no pointer
   to the later correction — unlike the markdown file, this copy had no
   superseding note anywhere near it, and a reader of `bd show certkit-ph1`
   alone would see only the wrong figure. **Fixed**: appended a correction
   note via `bd update certkit-ph1 --append-notes=...` stating the 3x error,
   the corrected 12.8x/4.2x figures, that the growth-order conclusion is
   unaffected, and pointing to `certkit-cpo` session 7 Result 2.

4. **`certkit-kjy`'s bd `description` field (issue is OPEN/IN_PROGRESS —
   "prove the separator/treewidth lower bound").** The description, written
   when the bead was filed off session 6, quotes "only a 13-38x
   constant-factor win over dense" as motivating context. **Fixed**: appended
   a correction note via `bd update certkit-kjy --append-notes=...` with the
   same correction, and an explicit statement that this bead's actual task
   (proving/refuting an `Omega(n/polylog n)` separator lower bound — a
   growth-order question) is unaffected by the constant-factor error.

`README.md` and every other project doc: no occurrence of the figure —
confirmed by grep, nothing to fix there. The bead's description speculated
README might have it; it does not.

I did not edit the description text of `certkit-ph1` or `certkit-kjy`
in place (only appended notes). Description fields are usually treated as
the as-filed record of what was asked/found at creation time; overwriting
them would erase the history of what session 6 actually said, which is the
same "leave the wrong-but-historical record intact, annotate instead of
rewrite" principle the bead's own acceptance criteria applies to the
session-6 section of the markdown file. I judged that principle should
apply uniformly across bd fields too, not just the one markdown section the
acceptance criteria happens to name.

## Bound/tolerance/threshold changes

**None.** This bead touches no code, no derivation, no numeric guard
anywhere in `certkit/`. The only "numbers" touched are the reported
performance-comparison constants in research notes, and those were corrected
by pointing at session 7's already-derived, already-verified correction —
nothing here is a new derivation.

## Documented limits touched

**None.** No README limit, no `DENSE_LIMIT`-style cap, no coverage claim was
softened or strengthened. This is unrelated to `certkit-ph1`'s coverage-cliff
conclusion, which stands as closed (infeasible-for-now) independent of this
constant-factor correction.

## Test suite

```
$ uv sync --extra dev
Resolved 20 packages in 1ms
Installed 7 packages in 266ms
 + numpy==2.5.2, scipy==1.18.1, pytest==9.1.1 ... (7 packages)
$ uv run pytest tests
============================= 165 passed in 22.77s =============================
```

No-dependency trust-boundary check (no system `python3` in this container;
used the established fallback — block numpy/scipy via `sys.meta_path` in a
`uv run --no-project python3` subprocess, since `uv run python3 -m
certkit.cli` alone would still see the project's numpy):

```
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

Unchanged from every prior session's reconfirmation, as expected since no
trusted code changed.

## What I decided not to do, and why

- **Did not rewrite the "Session 6" section of `sandbox-handoffs/certkit-ph1.md`.**
  The acceptance criteria explicitly requires it stay intact as a historical
  record. It already has a pointer to Result 2 immediately above it (added
  by session 7) — I judged that pointer sufficient and did not duplicate it
  inline inside the section itself, since doing so would blur the boundary
  between "what session 6 actually concluded" (wrong) and "what a later
  session found" (right), which is exactly the distinction the acceptance
  criteria is protecting.
- **Did not overwrite the `description` fields of `certkit-ph1` or
  `certkit-kjy`.** Appended corrections as notes instead, for the reason
  given above — treating bd `description` as an as-filed historical record,
  the same way the bead treats the markdown session-6 section.
- **Did not touch `certkit-cpo`'s close reason or notes.** It already states
  the corrected figures throughout and explicitly says "Filed certkit-wew"
  for this exact cleanup — it was already the source of truth, not a place
  the error had leaked to.
- **Did not investigate or touch the unrelated uncommitted working-tree
  changes found in `certkit/operators.py`, `README.md`,
  `examples/banded_demo.py`, `sandbox-prompt.md`, and the new
  `sandbox-handoffs/certkit-l7r*` files.** These belong to a different,
  already-closed bead (`certkit-l7r`, "Raise DENSE_LIMIT from 160 to 256")
  that was apparently worked in this same container outside this bead's
  scope. Left exactly as found, per the instruction to only do this bead's
  work and file anything else as a new bead — there is nothing new to file
  here since `certkit-l7r` already exists and is closed with its own
  evidence trail.

## What I could not verify

- Whether any occurrence of the figure exists in a location this repo's
  tooling can't grep (e.g. Dolt commit-message history, or bd `comment`
  entries rather than `description`/`notes` — `comment_count` was 0 on both
  issues I touched, so there was nothing there to check).
- Nothing else — this was a closed, mechanically-checkable search (grep +
  full read of the one file the bead names) and both remaining occurrences
  found are now annotated.

## Working tree

```
$ git status --short
 M README.md                          <- pre-existing, certkit-l7r's work, not mine
 M certkit/operators.py                <- pre-existing, certkit-l7r's work, not mine
 M examples/banded_demo.py             <- pre-existing, certkit-l7r's work, not mine
 M issues.jsonl                        <- mine (bd notes on certkit-ph1 + certkit-kjy) + certkit-l7r's already-closed bead state, re-exported together
 M sandbox-prompt.md                   <- pre-existing, certkit-l7r's work, not mine
?? sandbox-handoffs/certkit-l7r.md     <- pre-existing, certkit-l7r's work, not mine
?? sandbox-handoffs/certkit-l7r/       <- pre-existing, certkit-l7r's work, not mine
?? sandbox-handoffs/certkit-wew.md     <- mine (this file)
```

`issues.jsonl` was re-exported via `bd export -o issues.jsonl` after this
session's two `--append-notes` calls, since notes changed meaningfully. The
export necessarily also picked up `certkit-l7r`'s bead-state changes (that
bead was closed in the Dolt DB before this session started but had not yet
been exported to the git-tracked jsonl) — that is expected behavior of
`bd export` (it dumps the whole DB), not something this session did to that
bead.

## Suggested next commands (none run — git policy)

```
git add sandbox-handoffs/certkit-wew.md issues.jsonl
git commit -m "certkit-wew: annotate the two remaining leaks of session 6's inflated 13x-38x constant (bd notes on certkit-ph1, certkit-kjy)"
```

The five pre-existing modified/untracked files from `certkit-l7r` are a
separate session's uncommitted work and are intentionally not included in
the suggested add above — a human should review and commit them (or not)
under that bead's own record, not bundled into this one.

## bd state

`certkit-wew` is closed. `certkit-ph1` (closed) and `certkit-kjy`
(open/in_progress) both got an appended correction note; neither's status,
priority, or ownership changed. `bd export -o issues.jsonl` was run.
