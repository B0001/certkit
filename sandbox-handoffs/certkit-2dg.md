# certkit-2dg — README's Lean section said "seven", now nine

## Verdict change

None — this is a documentation-only fix. No test verdict (VERIFIED/ABSTAIN)
changes. The bug was that README.md's prose and its architecture-table line
had fallen out of sync with `lean/Certkit/Soundness.lean`'s actual theorem
count.

## What I verified before writing any number down

Per the bead's own instruction not to trust a pinned count:

```
$ grep -n sorry lean/Certkit/Soundness.lean
5:  All nine theorems below are real, zero-`sorry` proofs: `rayleigh_ritz_min`,
21:  Every theorem compiling with no `sorry` is a fact about this file;
45:  zero `sorry`, in `Interval.lean`.
279:    History: this was `sorry` and *false as previously stated*, because
286:    now a real, zero-`sorry` proof.
863:    `Interval.lean`, zero `sorry`) to enclose the exact real result of any
```

No line is an actual `sorry` tactic use — all are prose/doc-comment
occurrences of the word. Confirmed by reading the file header (lines 1–46):
it names nine theorems — `rayleigh_ritz_min`, `inertia_count_below`,
`gershgorin_lower`, `temple_lower`, `weyl_shift`,
`residual_encloses_some_eigenvalue`, `l2_opNorm_le_rowSum_of_isHermitian`,
`sweep_backward_bound`, `sweep_row_bound` — and explains that the last three
jointly close the gap `sweep_backward_bound`'s own doc comment used to flag
(that the runtime row-sum bound `backward_error.sweep` computes actually
dominates the L2 operator norm `weyl_shift` is stated against).

```
$ cd lean && lake build Certkit
...
⚠ [8802/8804] Replayed Certkit.Soundness
warning: ... (two `unusedVariables`/`unusedSectionVars` lint warnings only)
Build completed successfully (8804 jobs).
```

Zero errors, 8804/8804 jobs. This matches this session's fresh count: nine
theorems, zero `sorry`, `lake build Certkit` green.

## What I changed

`README.md`, two spots, both purely descriptive (no bounds, tolerances,
guards, or thresholds touched):

1. **"## The Lean side" section** (was lines 509–515): "seven soundness
   obligations" → "nine", "All seven" → "All nine", added
   `l2_opNorm_le_rowSum_of_isHermitian` and `sweep_row_bound` to the named
   list alongside the existing six, and added one sentence on what those two
   plus `sweep_backward_bound` jointly close (mirroring the derivation
   already written in `Soundness.lean`'s own header, not inventing new
   claims).
2. **Architecture table** (line 483): `7 of 7 proved` → `9 of 9 proved`. This
   wasn't named in the bead's acceptance criteria (which pointed at the "Lean
   side" prose section specifically) but states the exact same fact and was
   left stale by the same prior sessions (`certkit-zm6`, `certkit-62j`) — an
   adjacent table entry contradicting the paragraph two lines below it would
   just recreate the bug this bead exists to fix. Flagging it here rather
   than silently expanding scope.

I did not touch the "## Open problems" or "## Known limits" sections' Lean
references — those were already accurate (or already being handled by other
in-flight, uncommitted work in this tree — see below) and out of this bead's
named scope.

## Pre-existing uncommitted state in this tree (not mine, not touched)

`git status` at claim time showed substantial uncommitted changes already
in the working tree (AGENTS.md, CLAUDE.md, README.md, certkit/*.py,
lean/Certkit/BackwardError.lean, lean/Certkit/Soundness.lean, several
tests, issues.jsonl, plus untracked sandbox-handoffs for certkit-4ue,
certkit-62j, certkit-85m) — this is other beads' finished-but-uncommitted
work per this repo's "leave tree ready to commit, do not commit" policy. I
did not inspect, revert, or take credit for any of it; my diff is scoped to
the two README.md edits described above, layered on top of that existing
state. `git diff README.md` will show more than my two edits because of
this — the `sturm_be` bandwidth prose, the `MAX_BANDWIDTH` known-limits
update, and the 185→199 test count are all pre-existing from that other
work, not from this session.

## Test suite

```
$ uv run --extra dev pytest tests
199 passed in 51.60s
```

Full pass, no failures. (This count reflects the pre-existing uncommitted
work in the tree, not anything this bead's edits changed — README-only
changes don't move test counts.)

## No-dependency checker run

`python3` is not on PATH in this container; used the bare interpreter at
`/tmp/venv/bin/python3` (confirmed no third-party packages: `pip` itself
isn't even installed in it, `sys.path` has only stdlib + its own
site-packages, empty).

```
$ /tmp/venv/bin/python3 -m certkit.cli check examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

Runs with zero third-party imports, as required.

## What I decided not to do, and why

- Did not touch `## Open problems`'s "Proofs on the Lean side" bullet or
  `## Known limits`'s `sturm_be` bullet — those already reflect other
  in-flight (uncommitted) work in this tree that is not this bead's scope,
  and re-deriving or second-guessing that work here would be scope creep.
- Did not re-run or second-guess the pre-existing uncommitted changes
  elsewhere in the tree (certkit-4ue's banded backward-error work,
  certkit-62j's Lean additions, etc.) — verifying those is those beads'
  job, not mine. I only re-verified the specific claim this bead is about
  (theorem count and zero-`sorry` status of `Soundness.lean`).
- Did not touch `issues.jsonl` beyond what `bd close` does automatically —
  no beads meaningfully changed by me beyond this one, so no separate
  `bd export` was needed.

## What I could not verify

- I did not independently re-derive the Lean *mathematical content* of
  `l2_opNorm_le_rowSum_of_isHermitian` or `sweep_row_bound` — I verified
  they compile with no `sorry` and are named in the file's own
  correspondence table, which is what this bead asked for (a doc-sync fix,
  not a proof review). Whether those theorems' statements actually
  correspond to what the Python side does is the open, separate
  correspondence question `certkit-jcb` exists for, and remains unverified
  by this session as it must (`certkit-jcb` cannot be closed by a worker
  session per standing instructions).

## Bead status

Closing `certkit-2dg` — the described staleness is fixed, re-verified
against a fresh `lake build` and `grep`, and the suite is green.

## Suggested commands for a human

```
git add README.md
git commit -m "docs: README Lean section now reflects nine soundness obligations (certkit-2dg)"
```

(Leaving unrelated uncommitted changes in the tree for their own beads to
commit separately, per this repo's git policy.)
