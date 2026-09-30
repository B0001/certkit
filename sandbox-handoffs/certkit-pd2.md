# certkit-pd2 handoff

## Summary

`bd show certkit-pd2` was already `IN_PROGRESS` when this session started, and
`git diff -- sandbox-prompt.md` showed a previous, unfinished worker had
already made the exact edit the bead's "Fix" section asks for — but had not
written a handoff or closed the bead. This session's work was to **verify
that pre-existing uncommitted edit is actually correct** against current repo
state (not assume it), then close the loop. No new edit to
`sandbox-prompt.md` was needed; the file in the working tree today already
satisfies the acceptance criteria.

## Verdict change

None — this bead is docs-only (`sandbox-prompt.md` prose), not
checker/producer code. No VERIFIED/ABSTAIN behavior changed. Nothing in
`interval.py`, `backward_error.py`, `checker.py`, or any bound/tolerance/
threshold was touched.

## What was verified, point by point (against the bead's four claims)

1. **Theorem count.** `grep -n "^theorem " lean/Certkit/Soundness.lean` today
   returns exactly nine: `rayleigh_ritz_min`,
   `residual_encloses_some_eigenvalue`, `temple_lower`, `inertia_count_below`,
   `gershgorin_lower`, `weyl_shift`, `l2_opNorm_le_rowSum_of_isHermitian`,
   `sweep_backward_bound`, `sweep_row_bound`. The working-tree
   `sandbox-prompt.md` paragraph ("Do not overstate the Lean side...") says
   "nine soundness obligations" and points to README's table instead of
   repeating the list inline (the pattern the bead itself recommended as more
   drift-resistant). Matches.

2. **`weyl_shift` doc-comment gap.** Read the live doc comment,
   `lean/Certkit/Soundness.lean:665-679` (immediately above the `theorem
   weyl_shift` line): it says the row-sum/L2 relation is "proved below as
   `l2_opNorm_le_rowSum_of_isHermitian` ... not by this theorem" — i.e.
   closed, not open. The module header (`lean/Certkit/Soundness.lean:5-27`)
   independently confirms the same chain is closed. `sandbox-prompt.md`'s
   working-tree text says exactly this ("is now closed elsewhere in the same
   file, by `l2_opNorm_le_rowSum_of_isHermitian` plus `sweep_row_bound`").
   Matches.

3. **`certkit-jcb` status.** `bd show certkit-jcb` today: `CLOSED`, close
   reason "Completed human soundness sign-off; all 9 checklist items
   verified." `sandbox-prompt.md`'s working-tree Objectives bullet says
   "`certkit-jcb` is closed" and warns against reclaiming/reopening it as if a
   worker review could substitute for the human sign-off. Matches.

4. **`certkit-k2j` status.** `bd show certkit-k2j` today: `CLOSED`,
   infeasible-for-now (QMA-completeness argument + disorder-averaged
   entanglement-growth measurement, full record in
   `sandbox-handoffs/certkit-k2j.md`). `sandbox-prompt.md`'s working-tree
   bullet says "`certkit-k2j`... is **also closed**" and gives the same
   reason. Matches.

No further edits were made to `sandbox-prompt.md` — the existing uncommitted
diff (`git diff -- sandbox-prompt.md`, 37 insertions / 26 deletions) is the
complete fix and is left as-is, ready to commit alongside this bead's
closure.

## Scope discipline: one thing noticed and deliberately NOT fixed

While re-running `cd lean && lake build Certkit` to check the paragraph's
"8805/8805 jobs" claim, the build reported **8806 jobs**, not 8805 — one job
higher than the number currently sitting in `sandbox-prompt.md`. This is real
drift in the same paragraph I was verifying, but I did not touch it, for two
reasons:

- It is not one of the four claims this bead's description and acceptance
  criteria name (theorem count, weyl_shift gap, jcb status, k2j status). The
  bead says "Do only this bead."
- The discrepancy is not obviously stable enough to correct in the same
  breath as the four issues that *are* in scope: the working tree currently
  carries substantial *other* sessions' uncommitted work unrelated to pd2
  (`lean/Certkit/BandedBackwardError.lean`, `lean/Certkit/HermitianInertia.lean`
  untracked; `lean/Certkit/Soundness.lean`, `lean/Certkit.lean` modified;
  `checker.py`, `interval.py`, `operators.py`, `producer.py`,
  `tests/test_complex_hermitian.py` modified; several `sandbox-handoffs/*.md`
  untracked). At least one of those (`BandedBackwardError.lean`, referenced
  from the module header as "`certkit-sp1`") plausibly adds Lean jobs of its
  own. Fixing "8805" to "8806" right now risks pinning a number that moves
  again the moment that unrelated work lands or is reverted — exactly the
  instability the paragraph's own last sentence warns against ("re-run `lake
  build Certkit`... before repeating any of this").

Filing a fresh bead for this was considered but skipped for the same
instability reason — a bead filed today against a number that depends on
which of several *other* in-flight sessions' uncommitted files happen to be
sitting in this container would itself go stale immediately. Recommendation:
the next session that touches this paragraph for any reason should re-grep
the job count then, once the tree is closer to a single coherent commit
boundary.

## Test suite

```
$ uv run --extra dev pytest tests
============================= 229 passed in 28.88s =============================
```

No failures. (Pre-existing baseline per `sandbox-prompt.md`/`CLAUDE.md` was
"181 as of a fresh run" in an earlier session per `certkit-shj`; current
count is 229 — consistent with README's own "229 tests" line, so this is
expected drift from other sessions' landed work, not a regression I
introduced.)

## No-dependency checker run

`python3` is not on `PATH` in this container, so used the raw uv-managed
interpreter directly (not `uv run`, which would activate the project venv):

```
$ /home/node/.local/share/uv/python/cpython-3.12-linux-aarch64-gnu/bin/python3.12 \
    -m certkit.cli check examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

Confirms the checker still runs with zero third-party packages importable.

## What I decided not to do, and why

- Did not touch `README.md`, `CLAUDE.md`, or `AGENTS.md` — the bead
  explicitly excludes them (covered by `tests/test_doc_pass_count.py`,
  already correct).
- Did not re-edit `sandbox-prompt.md` — the pre-existing uncommitted diff
  already satisfies all four acceptance-criteria points, verified above.
- Did not fix the stale Lean build job count (8805 vs. actual 8806) — out of
  this bead's named scope and unstable given other sessions' uncommitted
  work in the same tree (see above).
- Did not run/investigate the other unrelated uncommitted changes in the tree
  (`checker.py`, `producer.py`, new Lean files, etc.) — out of scope for a
  docs-drift bead; they belong to other beads/sessions.
- Did not commit or push. Per git policy, leaving the tree as-is for a human
  to review and commit.

## What I could not verify

- Whether the previous (uncredited) worker who made the `sandbox-prompt.md`
  edit intended to close the bead themselves and was interrupted, or
  intentionally left it for follow-up. No `bd` notes or comments were present
  on `certkit-pd2` to indicate either way.
- Whether the Lean build job-count drift (8805 → 8806) is itself caused by
  the specific untracked files I listed, versus something else — I did not
  bisect it, per the scope reasoning above.

## Suggested commands for a human

```
git add sandbox-prompt.md
git commit -m "docs: fix stale Lean obligation count and jcb/k2j status in sandbox-prompt.md"
```

(All other uncommitted changes in the tree belong to unrelated sessions/beads
and are left for their own review/commit.)

## Bead closure

Closing `certkit-pd2` with evidence: the working-tree diff to
`sandbox-prompt.md` (37 insertions / 26 deletions) corrects all four stale
points named in the bead, each individually re-verified above against
`bd show certkit-jcb`, `bd show certkit-k2j`, and
`lean/Certkit/Soundness.lean` as they stand today (2026-09-29).
