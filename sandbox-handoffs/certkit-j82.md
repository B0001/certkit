# certkit-j82 — sandbox-prompt.md test-count/timing baseline is stale

## What this was

Pure documentation correction. The bead's own filing (2026-08-27, commit
39d6ff3) had already confirmed `106 passed` was stale and measured
`154 passed in 18.17s` with `uv sync --extra dev && uv run pytest tests -q`.
The bead explicitly said not to reuse that number blindly and to re-measure
live at close time, since beads land between filing and pickup.

## Live re-measurement (this session)

Working tree at pickup was **not** clean — other in-flight/closed-bead work
(certkit-sqr's `tests/exact_oracle.py` + `tests/test_exact_oracle.py`, plus
two unrelated handoff files) had added more tests since the bead was filed,
exactly as the bead anticipated. Left all of that untouched; out of scope for
this bead.

```
uv sync --extra dev
uv run pytest tests -q
```

Result:

```
165 passed in 24.15s
```

(11 more than the bead's own `154` snapshot, consistent with certkit-sqr's
new test_exact_oracle.py landing after the bead was filed. Used the live
`165`, not the bead's `154`, per its own instruction.)

No-dependency checker run (`python3 -m certkit.cli check
examples/sample/certificate.json examples/sample/operator.json -v`, run via
the bare uv-managed CPython interpreter directly — no venv, no third-party
packages on `sys.path`, confirmed by inspection):

```
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

Clean, as expected — this bead touches no code.

## Changes made

Three-line correction, exactly as the bead's "WHAT WOULD CLOSE THIS" section
specified, no more:

- `sandbox-prompt.md:81` — `106 passed` → `165 passed`
- `sandbox-prompt.md:121` — `# 106 passed, about 5 seconds` → `# 165 passed, about 24 seconds`
- `README.md:448` — `106 tests` → `165 tests` (directory-listing table, `tests/` row)

(Line numbers in the bead description — 66/106 — were already off by the time
this was picked up, because sandbox-prompt.md had grown since the bead was
filed; used the current live line numbers, 81/121, found by grep instead of
trusting the bead's line numbers.)

No code, test, or `certkit/` changes. No bound, tolerance, guard, or threshold
touched. Nothing softened — the "106" was a stale measurement, not a
documented limitation; correcting it doesn't change any conclusion the repo
draws (coverage cliff, DENSE_LIMIT, Gershgorin-as-floor, Lean sorry count are
all untouched and unrelated to this bead).

## Final test-run line (verbatim)

```
165 passed in 24.15s
```

## What I decided not to do, and why

- Did not touch `issues.jsonl`'s pre-existing uncommitted diff (from
  certkit-sqr closing) or the untracked files left by other sessions
  (`tests/exact_oracle.py`, `tests/test_exact_oracle.py`,
  `sandbox-handoffs/certkit-gvg.md`, `sandbox-handoffs/certkit-sqr.md`) — not
  this bead's scope, and disturbing them risks losing another session's
  record.
- Did not re-word or expand the surrounding prose in either file beyond the
  three numbers/timings named — the bead is explicit that this is a
  three-line correction, and adding more would be scope creep on a
  documentation bead.
- Did not chase down whether other files reference "106" (didn't find any
  beyond the two named in the bead via grep across the repo root and
  README.md/sandbox-prompt.md — see below).

## Verification of completeness

```
grep -rn "106 passed\|106 tests" --include="*.md" .
```

returned nothing after the edit (confirmed no other stale copies of the
number survive in markdown).

## What I could not verify

Nothing outstanding — this was a self-contained doc fix and both edits were
verified by direct grep/diff against the live test run's own output.

## Git status at handoff

Per repo git policy: no commit, no push. Tree is ready to commit.

```
git status
```

shows (in addition to this bead's two edits):
- `M  sandbox-prompt.md`
- `M  README.md`
- pre-existing uncommitted state from other sessions (`issues.jsonl` modified,
  `tests/exact_oracle.py`, `tests/test_exact_oracle.py`,
  `sandbox-handoffs/certkit-gvg.md`, `sandbox-handoffs/certkit-sqr.md`
  untracked) — not touched by this bead, left as found.

Suggested commands for a human to run (covering only this bead's files):

```
git add sandbox-prompt.md README.md
git commit -m "docs: refresh stale 106-passed test baseline to live 165 passed (certkit-j82)"
```

(The other modified/untracked files belong to other beads' sessions and
should be reviewed/committed separately.)
