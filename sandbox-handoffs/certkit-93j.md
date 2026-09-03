# certkit-93j — sandbox-prompt.md Objectives section referenced closed beads as open

## What was wrong

`sandbox-prompt.md`'s `## Objectives` section (lines 91-113 at session start)
told every worker session that `certkit-ph1` was "the highest-value
executable bead" and that `certkit-487` needed its notes "read before
acting". Both were closed:

- `certkit-ph1`: closed 2026-08-31, "Closed infeasible-for-now after 6 worker
  sessions ... every proposed matrix-free counting rule is ruled out."
- `certkit-487`: closed 2026-08-22, "Constructed the deliberate adversarial
  sector-scope case; confirmed it can only ever ABSTAIN, never falsely
  verify."

A worker reading the prompt verbatim would try to claim `certkit-ph1` (a
no-op/error against a closed bead) or spend time reading `certkit-487`'s
notes for a bug with no action left.

## Verdict / soundness

No change to `check()` behavior, `interval.py`, `backward_error.py`, or any
trusted module. This is a prompt-doc fix only. No bound, tolerance, guard,
or threshold was touched — nothing to derive.

## What I changed

`sandbox-prompt.md`, `## Objectives` section, rewritten based on a fresh
`bd show`/`bd ready`/`bd list` run at close time (commands and output are in
the session transcript, not reproduced here):

- `certkit-ph1` bullet: now states it's closed, summarizes why (six sessions,
  every concretely-named matrix-free counting rule ruled out), and points to
  `certkit-k2j` ("Evaluate certified tensor-network/MPO methods as a
  matrix-free eigenvalue counting rule (certkit-ph1 follow-up)") — the one
  thread ph1's close notes named as genuinely untried, and which was open in
  `bd ready` at close time. This follows the bead's own DESIGN note: "If
  certkit-ph1's close notes' one open thread ... has been turned into a new
  bead by then, point to that bead instead of certkit-ph1 directly." It has.
- `certkit-487` bullet: now states it's closed as a scope bug (not soundness
  bug), the checker correctly abstains, and the fix is documented (README,
  `checker.py`'s `_temple()` docstring) and regression-tested
  (`tests/test_sector_scope.py`). No action needed.
- `certkit-jcb` bullet: left substantively unchanged (still open work, still
  "leave it open, do not claim it") but reworded to not assert a specific
  status, since `bd show certkit-jcb` currently reports `in_progress` rather
  than `open` — the guidance not to claim it holds regardless of that status
  word, so I made the bullet robust to that distinction instead of hardcoding
  it.
- New finding beyond the bead's literal ask: the `certkit-8y2` epic (the
  bullet about "`8y2.*` Lean beads are proof work") is now **entirely
  closed** too (`bd show certkit-8y2` — all 7 sub-beads closed as of
  2026-08-31). That bullet was stale in the same way ph1/487 were, so I
  updated it to say the epic is closed and to point at filing a fresh bead
  for any new Lean gap rather than assuming an `8y2.*` ID is open. I did
  this inline rather than as a separate bead because it's the same
  paragraph, same failure mode, and the bead's acceptance criteria says the
  section should "match a fresh `bd ready` / `bd list` run at close time" —
  not just the two IDs named in the bead's title.
- Added one sentence at the top of the Objectives section telling future
  readers to verify bead IDs against `bd show` before trusting this file,
  and naming `certkit-t2k`/`certkit-bba` as the open beads tracking this
  exact recurring staleness problem elsewhere in the same file. I did not
  touch the paragraphs those two beads own (the Lean-`sorry`-count paragraph
  under "Do not describe the Lean side as proved", and the "165 passed"
  baseline numbers in `## Known baseline` / `## Environment`) — that is
  their scope, not this bead's, and I did not want two sessions editing the
  same lines.

## What I decided not to do

- Did not touch `README.md`, `issues.jsonl`, or `lean/Certkit/Soundness.lean`
  — these show as modified in `git status` from a prior, unrelated session's
  work and are not part of this bead's scope. Left as found.
- Did not update the "165 passed" pass-count mentions in `sandbox-prompt.md`
  (`## Known baseline`, `## Environment`) even though the actual run below
  shows 181 — that staleness is `certkit-bba`'s scope, not this bead's, and
  the bead's own text says the count is 165 as background, which is a
  separate factual claim from the Objectives-section bead-status claim this
  bead is about.
- Did not touch the Lean-`sorry`-count paragraph — that's `certkit-t2k`'s
  scope.
- Did not re-litigate whether `certkit-ph1` should stay closed or whether
  `certkit-k2j` is well-scoped — out of scope for a doc-accuracy bead.

## Verification

Test suite:

```
uv run --extra dev pytest tests
```
```
181 passed in 27.64s
```

No-dependency checker run (python3 isn't on PATH in this container directly;
used the uv-managed interpreter binary directly, bypassing uv/venv, which is
equivalent to the documented check — no `-m certkit` install, no venv
activation, just the bare interpreter):

```
/home/node/.local/share/uv/python/cpython-3.12-linux-aarch64-gnu/bin/python3.12 \
  -m certkit.cli check examples/sample/certificate.json examples/sample/operator.json -v
```
```
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```
Matches the documented baseline enclosure exactly.

## What I could not verify

- I did not independently re-verify `certkit-ph1`'s or `certkit-487`'s
  underlying technical conclusions (the six-session research exhaustion, the
  sector-scope regression test's correctness) — I trusted their close
  reasons and notes as the record of that work, since re-litigating a closed
  bead's substance is out of this bead's scope. If those closures are
  themselves wrong, that's a different bug than this one.
- `certkit-k2j`'s own scope/acceptance criteria I read but did not audit for
  quality — I'm only vouching that it exists, is open, and textually matches
  the "certified tensor-network/MPO methods" thread ph1's notes named.

## Files changed

- `sandbox-prompt.md` — Objectives section rewritten (see diff in session
  transcript).
- `issues.jsonl` — re-exported via `bd export -o issues.jsonl` after
  claiming/closing `certkit-93j` (bead-DB-meaningful change, per repo
  convention).

## Handoff / git policy

Per repo git policy: did not `git commit`, did not `git push`, did not
`bd dolt push`. Suggested commands for a human to run:

```
git add sandbox-prompt.md issues.jsonl sandbox-handoffs/certkit-93j.md
git commit -m "docs(sandbox-prompt): fix Objectives section referencing closed beads certkit-ph1/certkit-487 as open (certkit-93j)"
```

Note `git status` at session start already showed unrelated pending changes
to `README.md`, `issues.jsonl`, `lean/Certkit/Soundness.lean`, and two
untracked `sandbox-handoffs/*.md` files from prior sessions — those are not
part of this commit and are a separate human decision.
