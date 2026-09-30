# certkit-ljk handoff

## Task

TCB.md section 4 item 2 described the sweep row-sum bookkeeping obligation as
still open ("the single largest hole in the chain"), but `certkit-62j`
(closed 2026-09-27) proved `sweep_row_bound` in `lean/Certkit/Soundness.lean`,
closing exactly that gap. TCB.md was not updated when that bead closed. Fix:
rewrite TCB.md section 4 item 2 to reflect the current state, cross-checked
against README.md's Lean section and Soundness.lean's own header, and leave
CHANGELOG.md's dated 0.2.0 entry untouched.

## What changed

`TCB.md`, section "4. The Lean proofs prove the mathematics, not this
Python", item 2, rewritten (diff below). No other files changed — this bead
is docs-only, no code or tests touched.

```diff
-2. **One named, still-uncovered obligation.** `sweep_backward_bound`'s own doc
-   comment flags it: that the row-sums `backward_error.sweep` accumulates at
-   runtime actually dominate `‖A − Ã‖_∞` is an `Iv`-bookkeeping fact about a
-   Python loop, and is not a Lean obligation. The norm-inequality half is
-   closed by `l2_opNorm_le_rowSum_of_isHermitian`; this half is not. It is
-   tracked as its own piece of work and is the single largest hole in the
-   chain.
+2. **The row-sum step is proved.** `sweep_backward_bound`'s doc comment used
+   to name this as the last open link; `sweep_row_bound` (`certkit-62j`)
+   closes it: given the `eta`/`gamma` per-step bounds `sweep_backward_bound`
+   proves, it shows `ETA*|p| + two_u*(|b_prev|+|b_next|)` — the quantity
+   `backward_error.sweep` accumulates at runtime — dominates the true row sum
+   of `‖A − Ã‖_∞`. Combined with `l2_opNorm_le_rowSum_of_isHermitian`
+   (`‖·‖_∞` dominates the `‖·‖_2` `weyl_shift` needs), both norm-inequality
+   halves are now closed. What remains is narrower and, by
+   `sweep_row_bound`'s own doc comment, explicitly *not* a Lean obligation:
+   that `backward_error.sweep`'s `Iv`-arithmetic loop computes an
+   outward-rounded enclosure of the real-number bound the theorem proves —
+   a fact about `Interval.lean`'s already-proved soundness contract applied
+   to a specific expression, checked by the Python test suite, not by this
+   file.
```

The item-1 framing ("Two gaps sit between the two, and both are trusted")
was left as-is: item 2's remaining content (Python-loop-faithfulness to the
now-proved real-number bound) is still, accurately, a trusted-not-proved gap
— just a narrower one than before. No other wording in section 4 needed to
change.

## Verification performed before writing the new text

- `grep -n 'sweep_row_bound' lean/Certkit/Soundness.lean` — confirms the
  theorem exists (line 888) and read its full doc comment (lines 843-877) and
  the module header (lines 1-41), both of which state the row-sum step is now
  proved and explicitly scope what's *not* covered (the Python loop's
  faithfulness to the real-number bound, a test-suite obligation).
- `grep -n sorry lean/Certkit/Soundness.lean` — all six matches are in doc
  comments (words "sorry"/"zero-sorry" in prose), none is a live `sorry`
  tactic use.
- `cd lean && lake build Certkit` — succeeded, **8805/8805** jobs (one more
  than the 8804 figure quoted in this session's standing prompt — normal
  drift, not a regression; only unused-variable/section-var lint warnings,
  zero errors).
- Read README.md lines 507-526 ("## The Lean side") — already states the
  same closed conclusion this TCB.md edit now mirrors; used as the framing
  reference the bead asked for.
- Confirmed CHANGELOG.md:54 ("`sweep_backward_bound`'s runtime row-sum
  bookkeeping remains uncovered") is under the dated "0.2.0 — 2026-09-05"
  heading and left it untouched per the bead's explicit instruction —
  changelogs are frozen historical snapshots, not living docs.
- `bd show certkit-62j` — read its close reason and description in full to
  confirm what was actually proved (three sub-obligations: diagonal scaled
  against rounded `p`, off-diagonal sqrt bound via
  `sqrt_one_add_sub_one_abs_le`, `Atilde` symmetric by construction) before
  summarizing it in TCB.md.

## Test suite / no-dependency checker

```
$ uv run --extra dev pytest tests
============================= 199 passed in 27.71s =============================
```

No-dependency checker run (system had no bare `python3`; used
`/tmp/venv/bin/python3.12 -S` with site-packages explicitly stripped from
`sys.path` so numpy/scipy — both present in that venv — are unimportable,
equivalent to the prompt's `python3 -m certkit.cli` no-dependency check):

```
$ /tmp/venv/bin/python3.12 -S -c "
import sys
sys.path = [p for p in sys.path if 'site-packages' not in p]
sys.path.insert(0, '.')
import certkit.cli
sys.argv = ['certkit', 'check', 'examples/sample/certificate.json', 'examples/sample/operator.json', '-v']
certkit.cli.main()
"
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

## Verdict changes

None. This bead touches no code, no bounds, no tolerances, no thresholds —
docs only.

## What I decided not to do

- Did not touch CHANGELOG.md:54 — explicitly out of scope per the bead
  (frozen historical release note under a dated heading).
- Did not touch README.md — already correct, used only as the cross-check
  reference.
- Did not re-derive or second-guess `sweep_row_bound`'s Lean proof itself —
  that verification was `certkit-62j`'s job; this bead's job is only to make
  TCB.md's prose match the now-closed state, which I checked directly
  against the theorem's own doc comment and a fresh `lake build`.

## What I could not verify

- I did not independently re-check `sweep_row_bound`'s proof term for
  mathematical correctness beyond reading its statement and doc comment —
  that's the scope of `certkit-62j` (already closed) and `certkit-jcb` (the
  standing, deliberately-unclaimed human-review bead), not this one.

## Commands for a human to run

```
git add TCB.md sandbox-handoffs/certkit-ljk.md
git commit -m "Update TCB.md: sweep row-sum step is proved (certkit-62j), not open"
```

(Per repo git policy, I did not run these myself.)

## Bead status

Claimed and closing as done: `bd update certkit-ljk --claim` (done at start),
`bd close certkit-ljk` (after this handoff is written). No beads database
changes beyond this issue's own status — `bd export -o issues.jsonl` run to
keep the JSONL export in sync.
