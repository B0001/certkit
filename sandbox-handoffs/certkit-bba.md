# certkit-bba handoff

## Verdict change

None. This bead is documentation-only: no code, tolerance, guard, threshold,
or checker behavior was touched, so there is no verdict to change and no
derivation to write. Confirmed no soundness-relevant files are in the diff:

```
$ git diff --stat CLAUDE.md README.md sandbox-prompt.md
 CLAUDE.md         |  2 +-
 README.md         | 20 ++++++++-----
 sandbox-prompt.md | 90 +++++++++++++++++++++++++++++++------------------------
 3 files changed, 65 insertions(+), 47 deletions(-)
```
(The README.md and sandbox-prompt.md diffs are larger than this bead's own
edit because both files already carried uncommitted changes from two prior,
already-closed sessions — see "What I found already done" below. My own edit
to each is one line.)

## What the bead asked for vs. what I found already in the tree

The bead named four stale locations. Before touching anything I checked
`git status` (required by the repo's own safety protocol before touching
files with uncommitted state) and found the working tree already carried
**uncommitted, unpushed** changes from two other closed beads:

- `certkit-shj` (closed, "Fixed: rewrote both hardcoded pass-count mentions
  in sandbox-prompt.md to point at re-measuring instead of pinning a
  number...") had already fixed both of the bead's cited sandbox-prompt.md
  lines (the old lines 81 and 121). Current text no longer pins a stale
  number — it says "re-run `uv run --extra dev pytest tests` yourself rather
  than trusting a number pinned here (it read 165 at one point, 181 as of a
  fresh run this session — see `certkit-shj`)" and "# re-measure — count
  drifts upward as beads land". I verified this was already correct and left
  it untouched.
- `certkit-t2k` (closed) had already rewritten the Lean-status paragraph in
  both sandbox-prompt.md and README.md (unrelated to the pass-count, not in
  this bead's scope — left untouched).

So two of the bead's four cited locations were already fixed by prior
sessions but never committed. The two still stale were:

- `CLAUDE.md:64` — was `uv run --extra dev pytest tests     # 172 passing`
- `README.md:448` — was `tests/                165 tests: fuzz, backends, composition, counting, adversarial, boundary`

## Fresh measurement (per the bead's design section — do not reuse "181" blindly)

Ran the full suite twice, fresh, at the start and again right before closing:

```
$ time uv run --extra dev pytest tests -q
........................................................................ [ 39%]
........................................................................ [ 79%]
.....................................                                    [100%]
181 passed in 27.16s

real	0m27.276s
user	0m39.039s
sys	0m0.646s
```

Both runs (first: 27.91s, second/final: 27.16s) agree at **181 passed**,
matching the number already embedded in sandbox-prompt.md from certkit-shj's
fix. No new tests landed between claim and close, so 181 is current.

## Edits made

- `CLAUDE.md:64` → `uv run --extra dev pytest tests     # 181 passing, ~28s (re-measure — count drifts upward as beads land)`
- `README.md:448` → `tests/                181 tests: fuzz, backends, composition, counting, adversarial, boundary`

All four locations now agree at 181:

```
$ grep -n "181\|165\|172" sandbox-prompt.md CLAUDE.md README.md
sandbox-prompt.md:81:a number pinned here (it read 165 at one point, 181 as of a fresh run this
CLAUDE.md:64:uv run --extra dev pytest tests     # 181 passing, ~28s (re-measure — count drifts upward as beads land)
README.md:448:tests/                181 tests: fuzz, backends, composition, counting, adversarial, boundary
```

## Acceptance criteria check

"All four locations state the pass count from a fresh run at close time, and
the four numbers agree with each other and with a live `uv run --extra dev
pytest tests` run." — Satisfied: 181 everywhere, matching the live run above.

## Permanent-fix idea (per design section: "flag even if not implemented")

This is the **second** recurrence in this exact file set (certkit-j82:
106→165; then a drift back to stale before certkit-shj/certkit-bba caught
165→181 and 172→181). Filed `certkit-8b8` to decide on one of:

1. A test/CI check that parses the doc-stated count and asserts it equals a
   live `pytest --collect-only` count, or
2. Applying certkit-shj's "reword to say re-measure yourself" pattern
   everywhere instead of CLAUDE.md/README.md's current pinned-number style,
   which is immune to drift by construction.

Did not implement either in this session — it's new code/CI surface, out of
this bead's stated scope ("update all four locations... Consider whether...
flag that idea... even if not implemented"), and the instructions for this
session say to file new-scope work as a separate bead rather than do it now.

## What I did not do, and why

- Did not touch sandbox-prompt.md — both cited lines were already fixed by
  certkit-shj (uncommitted but correct). Editing further would have been
  redundant and risked reintroducing a pinned number where certkit-shj had
  deliberately moved to a self-updating phrasing.
- Did not touch the unrelated uncommitted changes already in the tree
  (`issues.jsonl`, `lean/Certkit/Soundness.lean`, the Lean-paragraph parts of
  README.md/sandbox-prompt.md, or the untracked `lean/Certkit/Scratch*.lean`
  and other `sandbox-handoffs/*.md` files) — they belong to other, already-
  closed beads and are outside this bead's scope. Left them exactly as
  found.
- Did not implement the permanent anti-drift fix itself — filed `certkit-8b8`
  instead, per the bead's own design section treating this as optional/
  flag-only.

## What I could not verify

- Whether the uncommitted changes from certkit-shj/certkit-t2k sitting in the
  tree are otherwise ready to commit as-is (e.g. whether `issues.jsonl` and
  the Lean file diffs are internally consistent with the bead notes that
  produced them) — out of scope for certkit-bba, not independently checked
  beyond confirming they don't touch the four pass-count locations I was
  responsible for.

## Final test-run line (verbatim, at close time)

```
181 passed in 27.16s
```

## No-dependency checker run (trust boundary)

```
$ /home/node/.local/share/uv/python/cpython-3.12-linux-aarch64-gnu/bin/python3.12 -m certkit.cli check examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```
(Ran directly against the bare uv-managed CPython interpreter, bypassing
`uv run`/the venv, so no numpy/scipy/pytest are importable — confirms the
checker still needs zero third-party packages. The shell's usual `python3`
was not on PATH in this container; found the interpreter via `uv python
find`.)

## Git status at handoff (not committed/pushed, per repo git policy)

```
$ git status
On branch main
Your branch is ahead of 'origin/main' by 2 commits.
Changes not staged for commit:
	modified:   README.md
	modified:   issues.jsonl
	modified:   lean/Certkit/Soundness.lean
	modified:   sandbox-prompt.md
Untracked files:
	lean/Certkit/Scratch.lean
	lean/Certkit/Scratch2.lean
	sandbox-handoffs/certkit-1ta.md
	sandbox-handoffs/certkit-8y2.7.md
	sandbox-handoffs/certkit-93j.md
	sandbox-handoffs/certkit-k2j-entanglement-experiment.py
	sandbox-handoffs/certkit-k2j.md
	sandbox-handoffs/certkit-shj.md
	sandbox-handoffs/certkit-t2k.md
```
`CLAUDE.md` (my edit) shows modified but isn't listed above in this excerpt
timing — re-run `git status` to see the current full list; my two edits
(CLAUDE.md, README.md's line 448) are part of the "modified" set alongside
the pre-existing unrelated diffs. Suggested commands for a human to run
(not run by me, per git policy):

```
bd export -o issues.jsonl   # already reflects the certkit-8b8 creation and this bead's close; re-run if beads changed further
git add CLAUDE.md README.md sandbox-prompt.md issues.jsonl lean/Certkit/Soundness.lean
git commit -m "..."
git push
```
I did not stage or commit anything myself.
