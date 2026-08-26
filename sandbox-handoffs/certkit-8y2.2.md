# certkit-8y2.2 — Formalize sweep_backward_bound

Status: **closed**, evidence below. This bead's own theorem is a real, compiled,
zero-`sorry` proof over standard axioms only. It does not, and was never asked
to, discharge the whole `sweep_backward_bound` obligation as originally framed
in the epic — see "What's not proved" below.

## What was proved

New file `lean/Certkit/BackwardError.lean`:

- `eta_of e2 e3 := (1 + e2) * (1 + e3) - 1` and
  `gamma_of e0 e1 e3 := (1 + e0) * (1 + e1) * (1 + e3) - 1` — the exact
  aggregate relative-error factors `backward_error.py`'s docstring names `eta`
  and `gamma`.
- `eta_bound`: `|e2| ≤ u`, `|e3| ≤ u`, `u ≤ 1/10` ⟹ `|eta_of e2 e3| ≤ 2.1 * u`.
- `gamma_bound`: `|e0| ≤ u`, `|e1| ≤ u`, `|e3| ≤ u`, `u ≤ 1/32` ⟹
  `|gamma_of e0 e1 e3| ≤ 3.1 * u`.
- `sweep_step_backward_bound`: the one-rounding-per-operation model applied to
  one Sturm-sweep pivot step —

  ```
  (((a - beta) * (1 + e2) - (bprev^2 * (1 + e0) / dprev) * (1 + e1)) * (1 + e3))
    = (a - beta) * (1 + eta_of e2 e3) - bprev^2 * (1 + gamma_of e0 e1 e3) / dprev
  ```

  proved by `field_simp; ring` (an unconditional algebraic identity — holds
  even at `dprev = 0`, where both sides reduce to the same thing via
  `div_zero`), packaged together with the two bounds above into one theorem
  matching the bead's exact ask: "the one-rounding-per-operation model
  formalized, then the per-step collection of factors into eta and gamma."

Wired into `lean/Certkit/Soundness.lean`: the placeholder
`theorem sweep_backward_bound : True := by trivial` is replaced with a real
statement (the same identity plus both bounds, phrased over `beta`/`a` instead
of the helper's `bprev`/`dprev` naming) whose proof is
`sweep_step_backward_bound hu hu1 h0 h1 h2 h3` — i.e. the file's own
`sweep_backward_bound` obligation is now literally an instance of the
`BackwardError.lean` theorem, not a restatement.

### The `u ≤ 1/32` threshold

Not arbitrary and not tuned to make a tactic succeed: `1/32` is the largest
convenient round threshold for which `u² ≤ u/32` and `u³ ≤ u²/32` (used inside
`gamma_bound` to fold the `u²`/`u³` second-order terms into the `0.1 * u` of
headroom the `2.1`/`3.1` constants carry over the naive `2`/`3`). The real
value is `u = 2^-53 ≈ 1.11e-16`, so `u ≤ 1/32` is true with enormous slack —
the threshold exists so the *proof* is a clean, checkable inequality rather
than a numeric substitution, not because `1/32` is where the bound would
actually break.

### Axiom check (no `sorry`, standard axioms only)

```
'Certkit.eta_bound' depends on axioms: [propext, Classical.choice, Quot.sound]
'Certkit.gamma_bound' depends on axioms: [propext, Classical.choice, Quot.sound]
'Certkit.sweep_step_backward_bound' depends on axioms: [propext, Classical.choice, Quot.sound]
'Certkit.abs_mul_le_sq' depends on axioms: [propext, Classical.choice, Quot.sound]
'Certkit.abs_mul_mul_le_cube' depends on axioms: [propext, Classical.choice, Quot.sound]
```

### Build evidence

```
$ lake build Certkit
Build completed successfully (8767 jobs).
```

(default target: `Certkit.lean` imports `Certkit.Interval` and
`Certkit.BackwardError` only — see "What was deliberately not done" below for
why `Certkit.Soundness` isn't in this target.)

```
$ lake env lean Certkit/Soundness.lean
Certkit/Soundness.lean:51:8: warning: declaration uses `sorry`   -- rayleigh_ritz_min
Certkit/Soundness.lean:59:8: warning: declaration uses `sorry`   -- residual_encloses_some_eigenvalue
Certkit/Soundness.lean:66:8: warning: declaration uses `sorry`   -- temple_lower
Certkit/Soundness.lean:80:32: error: failed to synthesize instance of type class LT n      -- inertia_count_below, PRE-EXISTING, unrelated
Certkit/Soundness.lean:91:8: warning: declaration uses `sorry`   -- gershgorin_lower
Certkit/Soundness.lean:105:44: error: failed to synthesize instance of type class Norm (Matrix n n ℝ)  -- weyl_shift, PRE-EXISTING, unrelated
```

Note what's absent: no warning or error is reported for `sweep_backward_bound`
(line 129) — it type-checks cleanly against a file that otherwise has 2
pre-existing, unrelated compile errors and 4 other `sorry`s.

## What's proved vs. not proved

Proved: the one-rounding-per-operation model, and the per-step collection of
the four per-operation rounding errors into the two aggregate factors `eta`
and `gamma`, with `|eta| ≤ 2.1u` and `|gamma| ≤ 3.1u` — matching
`backward_error.py`'s `ETA`/`GAMMA` constants exactly, derived rather than
transcribed.

**Not proved** (both explicitly out of scope for this bead, per its own doc
comment on `sweep_backward_bound` in `Soundness.lean`):

1. That the row sums `backward_error.sweep` actually accumulates from `eta`/
   `two_u` dominate `||A - Atilde||_inf`. This is `Iv`-arithmetic bookkeeping
   over `sweep`'s Python loop (summing `eta * |p| + two_u * (|b_left| +
   |b_right|)` per row), not part of the one-rounding algebra this bead's
   acceptance criterion asks for. It remains covered by the Python test suite
   (`tests/test_backward.py`), not by a Lean proof.
2. That `||·||_inf` dominates the operator norm `||·||_2` `weyl_shift` uses.
   General Hermitian-matrix norm inequality, unrelated to rounding. Remains
   `weyl_shift`'s own `sorry`.

So: the runtime bound's *soundness* (does `delta` really dominate
`||A - Atilde||_2`, so that `weyl_shift` can be trusted to carry the count
back to the true operator) is not fully closed by this bead — only the
per-step rounding-collection piece the acceptance criterion names is. This is
called out in-file (`Soundness.lean`'s doc comment on `sweep_backward_bound`
and its top-of-file STATUS block) so nobody downstream mistakes "one theorem
is proved" for "the counting rule is proved."

## What was deliberately not done, and why

- **Did not wire `Certkit.Soundness` into `Certkit.lean`'s default build
  target.** Attempted it to see whether the new theorem could be checked via
  the aggregate `lake build Certkit` target rather than a direct `lake env
  lean` invocation; this surfaced the two pre-existing errors above
  (`inertia_count_below`'s `BlockTriangular id` needs an `LT n` instance not
  available for the generic `n`; `weyl_shift`'s `‖A - B‖` needs a `Norm
  (Matrix n n ℝ)` instance). Both predate this session — they are why the
  file's own header already said "has not been compiled in the environment
  where the Python kit was built" — and are unrelated to rounding/backward
  error. Fixing them is real, separate work (picking the right norm instance
  for `Matrix n n ℝ`, adding an explicit order/finiteness assumption for the
  inertia theorem), so I filed **certkit-8y2.4** for it and reverted
  `Certkit.lean` to import only `Certkit.Interval` and `Certkit.BackwardError`,
  keeping the default build green. Verified the target theorem independently
  via direct `lake env lean Certkit/Soundness.lean` instead (output above).
- **Did not touch `backward_error.py`.** The bead is a formalization task; no
  Python behavior, threshold, or constant needed to change, and none did.
- **Did not attempt the row-sum/norm-domination or ℓ∞-vs-ℓ2 obligations.**
  Explicitly out of scope per the bead's own framing of what "collection of
  factors into eta and gamma" means vs. the rest of the counting-rule
  argument; those are separate obligations under the same epic
  (`weyl_shift`'s `sorry`, and whatever bead eventually covers the `sweep`
  row-sum bookkeeping).
- **No documented limit in README was touched or tempted to be softened** —
  this bead has no interaction with README claims.

## What could not be verified

- The overall `sweep_backward_bound` *epic-level* obligation (runtime bound
  actually dominates `||A - Atilde||`) is still open — see "not proved" above.
  Its own `sorry` sits in `weyl_shift` plus the untouched row-sum reasoning in
  `sweep`'s Python implementation.
- Whether the two `Soundness.lean` type-class errors are the *only* problems
  remaining once fixed (i.e. whether `inertia_count_below` and `weyl_shift`'s
  proofs themselves will go through once the instances resolve) is unknown —
  out of scope, left for certkit-8y2.4.

## Python suite

```
$ uv run pytest tests
============================= test session starts ==============================
platform linux -- Python 3.14.7, pytest-9.1.1, pluggy-1.6.0
rootdir: /workspace
configfile: pyproject.toml
collected 110 items

tests/test_backends.py ..............                                    [ 12%]
tests/test_backward.py ...................                               [ 30%]
tests/test_banded.py ...............                                     [ 43%]
tests/test_composition.py ....................                           [ 61%]
tests/test_end_to_end.py ............                                    [ 72%]
tests/test_interval.py ........                                          [ 80%]
tests/test_sector_scope.py ....                                          [ 83%]
tests/test_tamper.py ..............                                      [ 96%]
tests/test_trust_boundary.py ....                                        [100%]

============================= 110 passed in 5.44s ==============================
```

110 passed (up from the 106 baseline mentioned in the task — the extra 4 are
`tests/test_sector_scope.py`, added in a prior session, already tracked in
git status as untracked before this session started). Zero failures, zero
skips. This is Lean-only work; the Python suite could not have regressed, but
was run and confirmed green rather than assumed.

## No-dependency trust-boundary check

This sandbox has no bare system `python3` — confirmed absent from
`/usr/bin`, `/usr/local/bin`, and PATH entirely; `/tmp/venv` is the interpreter
`uv sync --extra dev` created (same finding as certkit-8y2.1's handoff). Ran
the checker CLI directly via that interpreter's binary (not `uv run`, so no
project-level activation/shims are in the loop) to confirm the trust-boundary
modules import with nothing beyond stdlib available at runtime:

```
$ /tmp/venv/bin/python3 -m certkit.cli check examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

Matches certkit-8y2.1's handoff output exactly — no regression from this
session's Lean-only changes, as expected.

## Beads / sync

- Claimed and closed `certkit-8y2.2`.
- Filed `certkit-8y2.4` (P1, child of epic `certkit-8y2`) for the two
  pre-existing `Soundness.lean` type-class errors discovered while wiring this
  bead's work in.
- Ran `bd export -o issues.jsonl` (20 issues exported) — `issues.jsonl` now
  reflects both changes.

## Files changed this session

- `lean/Certkit/BackwardError.lean` — new file, the proof itself.
- `lean/Certkit/Soundness.lean` — import fix
  (`Mathlib.LinearAlgebra.Matrix.Spectrum` → `Mathlib.Analysis.Matrix.Spectrum`,
  which had never resolved in this mathlib revision), added
  `import Certkit.BackwardError`, updated top-of-file STATUS block, replaced
  the `sweep_backward_bound` placeholder with the real theorem + doc comment.
- `lean/Certkit.lean` — imports `Certkit.Interval` and `Certkit.BackwardError`
  only, with a comment explaining why `Certkit.Soundness` isn't (yet) in the
  default target.
- `issues.jsonl` — re-exported.

## Proposed git commands (not run — conservative profile, no commit/push authority this session)

```
git add lean/Certkit/BackwardError.lean lean/Certkit/Soundness.lean lean/Certkit.lean issues.jsonl sandbox-handoffs/certkit-8y2.2.md
git commit -m "Formalize sweep_backward_bound's per-step rounding collection in Lean

Prove eta/gamma aggregate rounding-error bounds (2.1u/3.1u, matching
backward_error.py's ETA/GAMMA exactly) and the one-rounding-per-operation
pivot identity in a new Certkit/BackwardError.lean, zero sorry, standard
axioms only. Wire the result into Soundness.lean's sweep_backward_bound
placeholder. Files certkit-8y2.4 for two unrelated pre-existing type-class
errors (inertia_count_below, weyl_shift) that keep the rest of
Soundness.lean from compiling."
git status
```

(There are other pre-existing untracked/modified files in the working tree
from prior sessions — e.g. `README.md`, `certkit/checker.py`, `tests/`,
`lean/lake-manifest.json`, `.gitignore` etc. — not touched this session and
not included in the `git add` above; a human should review those separately
before deciding what else to commit.)
