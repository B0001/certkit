# certkit-8b8 — regression test for doc-stated pytest pass count

## What this bead asked for

Three prior sessions (certkit-j82, certkit-shj, certkit-bba) each hand-fixed
a doc that pinned a stale pytest pass count. The bead asked to pick one of
two remedies — a test that asserts doc-pinned counts against a live
collection, or reword the doc to stop pinning a number — and apply it
consistently everywhere a count is still pinned, rather than leaving some
docs checked and some not.

## What I found before touching anything

Grepping all four repo-root docs for the count pattern turned up a fourth,
previously unrecorded drift instance that this bead's own description didn't
mention: `AGENTS.md:133` still read `# 172 passing`, three drift-cycles
stale, while `CLAUDE.md` and `README.md` already said 181 (fixed by
certkit-bba) and `sandbox-prompt.md` had already been reworded to
"re-measure yourself" (certkit-shj) and carries no number to check. This is
exactly the recurrence the bead exists to stop, and it confirms the
one-off-manual-fix approach doesn't hold — `AGENTS.md` is a bd-managed
Codex-agent doc that nobody was including in the sweep.

## What I did

**Chose the test approach** (matches the bead's literal title) over the
reword approach, for the two/three docs that state the count as a
present-tense fact (`CLAUDE.md`, `AGENTS.md`, `README.md`). Left
`sandbox-prompt.md` alone — its count is explicit past-tense narrative
("it read 165 at one point, 181 as of a fresh run this session — see
certkit-shj"), not a live claim, so it is already immune to drift by
construction and adding it to the checked set would be wrong: the test
would have to special-case "ignore this specific historical number," which
recreates the exact kind of doc-specific carve-out the bead was written to
stop.

Added `tests/test_doc_pass_count.py`:
- Runs `python -m pytest tests --collect-only -q` in a subprocess (against
  the same interpreter as the test session, via `sys.executable`) and parses
  the `N tests collected` line.
- Parses the pinned-count pattern out of `CLAUDE.md`, `AGENTS.md`, and
  `README.md` via per-file regexes (each doc uses different prose around the
  number — `# N passing` vs `N tests:`).
- Asserts every doc's stated count equals the live collected count; failure
  message lists every mismatching file, not just the first.

**Verified the test actually catches drift, not just passes vacuously**: I
temporarily set `CLAUDE.md`'s count to `999`, reran the test, watched it
fail with `CLAUDE.md: doc says 999, live collection says 182`, then restored
it. (Shown as a tool call in this session's transcript, not asserted from
memory.)

**Fixed all three pinned docs to the live count, which is 182, not 181** —
adding this test file itself changed the collected count by one, so I had to
re-collect *after* writing the test and set every doc to the post-test
number, not the pre-test one:
- `CLAUDE.md`: `181` → `182`
- `AGENTS.md`: `172` → `182`, and added the same
  `(re-measure — count drifts upward as beads land)` hedge `CLAUDE.md`
  already carries, since the underlying problem (a bd-generated doc nobody
  rechecks) is identical.
- `README.md` line 448 (`tests/  N tests: ...`): `181` → `182`.

Also ran `bd export -o issues.jsonl` after claiming the bead, per repo
convention — `issues.jsonl` diff is just the claim/status change on
`certkit-8b8`, not a bead-content edit.

## Verdict changes

None — this bead is docs/tooling only, no producer, checker, or trust
boundary code touched. No VERIFIED/ABSTAIN behavior changed for any input.

## Bounds, tolerances, guards, thresholds touched

None. This is not that kind of bead.

## Documented limits softened

None. I did not touch README's stated limits (coverage cliff, `DENSE_LIMIT`,
Gershgorin-as-floor, n≈10⁴ producer-eigenvector limit) or the Lean
soundness-obligation count — those lines were already correct in the working
tree from a prior, uncommitted session (the Lean section going from "4 of 7
proved" to "7 of 7 proved" was pre-existing dirty state in this checkout when
I started, not something I changed; `git diff README.md` shows both my
one-line count edit and that pre-existing Lean-prose diff together since
both are unstaged against the same last commit).

## Final test-run line (verbatim)

```
============================= 182 passed in 27.36s =============================
```

`tests/test_doc_pass_count.py` is included and passing in that count.

## No-dependency checker run

The container has no bare system `python3` (`which python3` → not found;
`/usr/bin/python3` does not exist) — only the uv-managed venv interpreter at
`/tmp/venv/bin/python3`, which has numpy installed via the dev extra. To
actually exercise the "checker runs with zero third-party packages
importable" property without `uv`, I ran the venv's own interpreter with
`-S` (no site-packages) and `sys.path` stripped of every `site-packages`
entry, then invoked `certkit.cli` via `runpy`:

```
$ /tmp/venv/bin/python3 -S -c "
import sys
sys.path = [p for p in sys.path if 'site-packages' not in p]
sys.path.insert(0, '.')
sys.argv = ['certkit.cli', 'check', 'examples/sample/certificate.json', 'examples/sample/operator.json', '-v']
import runpy
runpy.run_module('certkit.cli', run_name='__main__')
"
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

This is a manual simulation of the no-dependency environment, not the exact
"no uv, no venv" invocation the standing instructions describe — this
container simply doesn't have a bare interpreter to run that literal
command. `tests/test_trust_boundary.py::test_checker_runs_in_a_process_where_numpy_is_unimportable`
(part of the 182-passed run above) exercises the same property more
rigorously via an actual subprocess with a scrubbed environment, and passed.
I'm flagging the manual substitution rather than presenting it as the
canonical check.

## What I decided not to do, and why

- **Did not reword `CLAUDE.md`/`AGENTS.md`/`README.md` to drop the pinned
  number entirely** (the sandbox-prompt.md/certkit-shj pattern), even though
  it's arguably more robust than a test that could bitrot if someone renames
  a doc file. Chose the test because the bead's title asks for exactly that,
  and because a live, present-tense "N passing" number next to the command
  that produces it is more useful to a reader deciding whether their local
  run is healthy than a hedge sentence — as long as something enforces it,
  which now it does.
- **Did not touch `sandbox-prompt.md`'s historical "165... 181..." sentence.**
  It's not a current-state claim; folding it into the checked set would
  require the test to know that one particular number in one particular
  file means something different from the others, which is a special case,
  not a fix.
- **Did not add a pre-commit hook or CI wiring beyond the pytest test.** The
  bead's own suggested remedy list treats "a test" and "a pre-commit/CI
  check" as alternatives; a pytest test runs on every `pytest tests`
  invocation already required by this repo's workflow, which is the
  enforcement surface that matters here — a separate hook would duplicate
  it for no coverage gain.
- **Did not go looking for other docs beyond the four named/discovered
  (`CLAUDE.md`, `AGENTS.md`, `README.md`, `sandbox-prompt.md`).** Grepped
  repo-root `*.md` plus did a broader `grep -rn` for "passing"/"tests:"
  patterns during investigation; nothing else in the tree pins a count.

## What I could not verify

- Whether `AGENTS.md`'s `## Build & Test` section is itself regenerated by
  some `bd setup` tool (the file has clear bd-generated blocks bounded by
  `<!-- BEGIN/END BEADS ... -->` comments elsewhere in the same file). If it
  is regenerated from a template that also hardcodes a count, my fix could
  be overwritten by a future `bd setup codex` re-run. I did not find such a
  template in this repo to check against, and didn't have visibility into
  the `bd` tool's internals to rule it out. Flagging rather than asserting
  either way.
- The no-dependency checker invocation above is a manual approximation, not
  the literal command from the standing instructions, for the reason given.

## Suggested commands for a human

```bash
git add AGENTS.md CLAUDE.md README.md tests/test_doc_pass_count.py issues.jsonl
git commit -m "certkit-8b8: regression-test doc-pinned pytest counts against live collection"
```

(Leaving `lean/Certkit/Soundness.lean`, `sandbox-prompt.md`'s broader diff,
`lean/Certkit/Scratch*.lean`, and the other untracked `sandbox-handoffs/*.md`
files out of this suggested commit — they're pre-existing uncommitted work
from other sessions/beads, not part of certkit-8b8.)
