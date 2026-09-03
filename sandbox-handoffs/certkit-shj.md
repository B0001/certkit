# certkit-shj — sandbox-prompt.md Known-baseline paragraph says 165 passed, actual is 181

## Verdict

No checker/soundness code touched. This is a doc-only fix to `sandbox-prompt.md`,
the standing-context file re-injected each session. Fixed the class of staleness
`certkit-t2k` already fixed once for the neighboring Lean-status paragraph:
a hardcoded pass count that drifts as beads land.

## What was wrong

`sandbox-prompt.md` hardcoded `165 passed` in two places:

- line 79 (as of session start; shifted after the pre-existing uncommitted
  Lean-paragraph edit from a prior session): "The suite is **fully green**:
  `165 passed`."
- the `## Environment` section: `uv run pytest tests          # 165 passed,
  about 24 seconds`

Fresh measurement this session:

```
$ uv sync --extra dev
$ uv run --extra dev pytest tests
============================= 181 passed in 44.17s =============================
```

(confirmed twice — second run 47.78s, same 181 count). This matches the
count the bead description cited from `certkit-t2k`'s session.

## What I changed

Both `165 passed` mentions in `sandbox-prompt.md` were rewritten to not pin a
count, following the same pattern `certkit-t2k` used for the Lean paragraph
just above (which I found already rewritten, uncommitted, in the working tree
when I started — I did not touch that paragraph further, only used it as the
precedent):

1. "Known baseline" section now reads:

   > The suite is **fully green**, with a passing count that only goes up as
   > beads land — re-run `uv run --extra dev pytest tests` yourself rather
   > than trusting a number pinned here (it read 165 at one point, 181 as of
   > a fresh run this session — see `certkit-shj`). There is no documented
   > pre-existing failure to excuse one.

2. "Environment" section's code block now reads:

   ```
   uv sync --extra dev
   uv run pytest tests          # re-measure — count drifts upward as beads land
   ```

Neither line asserts a number as current truth going forward; both push the
reader to re-run the command, same as the Lean paragraph's "re-measure before
you repeat this paragraph" framing. The old counts (165, and the moment-in-time
181) are kept only as historical data points inside the "Known baseline"
sentence, explicitly labeled as such, not as the current baseline to trust.

## Bounds/tolerances/thresholds touched

None. This bead is prose-only in `sandbox-prompt.md`.

## Documented limits softened?

None. No README claim, DENSE_LIMIT, Gershgorin characterization, or coverage
limit was touched.

## Final test-run line (verbatim)

```
============================= 181 passed in 47.78s =============================
```

## No-dependency checker verification

Could not run the exact documented command
(`python3 -m certkit.cli check examples/sample/certificate.json
examples/sample/operator.json -v`) — this container has **no system `python3`
binary at all** (only `/home/node/.elan/bin` on PATH for the Lean toolchain;
`which python`, `which python3`, and `/usr/bin/python*` all come up empty).
This is a container/environment gap, not something introduced this session.

Substitute verification actually run:

```
$ uv run python -m certkit.cli check examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

This does *not* prove the checker is import-clean of third-party packages,
because the `uv`-managed venv already has numpy installed (from `uv sync
--extra dev` earlier in the session) — `uv run python -c "import numpy"`
succeeds in that venv. The actual "checker never needs numpy" property is
what `tests/test_trust_boundary.py` enforces mechanically (it runs the
checker in a subprocess where numpy is unimportable), and that test suite
(4 tests) passed as part of the full 181-passed run above. I'm reporting the
`python3`-binary gap explicitly rather than papering over it with the venv
substitute — an honest "couldn't run the documented exact command" beats
implying I did.

## What I decided not to do, and why

- Did not touch the Lean-status paragraph (lines ~56-75) beyond what was
  already uncommitted in the working tree at session start — it's a separate
  concern (Lean sorry/build staleness, already fixed by a prior session per
  its own pattern) and out of this bead's scope.
- Did not touch `README.md`, which git status showed as modified before I
  started — unrelated to this bead, left as-is.
- Did not delete/recreate `.venv` to get a numpy-free Python for a stricter
  no-dependency check, since that's a destructive-ish action outside this
  bead's scope and the property is already mechanically covered by
  `test_trust_boundary.py`.
- Did not commit, push, or run `bd dolt push`, per repo git policy.

## What I could not verify

- The exact documented no-dependency command
  (`python3 -m certkit.cli check ...`) — no system `python3` in this
  container. Verified the equivalent property indirectly via
  `test_trust_boundary.py` passing in the full suite, and ran the checker
  successfully via `uv run python -m certkit.cli check ...` (weaker guarantee,
  noted above).

## Files changed

- `sandbox-prompt.md` — two `165 passed` mentions rewritten per above.
- `issues.jsonl` — re-exported via `bd export -o issues.jsonl` after
  claiming/closing `certkit-shj` (bead-state change only).

## Suggested next commands (not run — git policy is report-only)

```
git add sandbox-prompt.md issues.jsonl
git commit -m "docs: stop hardcoding pytest pass count in sandbox-prompt.md (certkit-shj)"
```

Note `sandbox-prompt.md` also carries a pre-existing uncommitted Lean-paragraph
rewrite and an `## Objectives` bullet-list rewrite from a prior session (not
mine) — those are part of the same file diff and would be included in the
commit above unless separated out. `README.md` has its own pre-existing
unstaged diff, unrelated to this bead; left out of the suggested commit.
