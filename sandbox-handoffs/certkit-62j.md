# Handoff: certkit-62j — row sums dominate ||A - Atilde||_inf

## Verdict

**Proved, not sorry'd.** `lean/Certkit/Soundness.lean` gains a ninth
zero-`sorry` theorem, `sweep_row_bound`, which is exactly the claim the bead
asked for: `backward_error.sweep`'s per-row accumulation `ETA*|p| +
two_u*(|b_prev|+|b_next|)` dominates the true row sum of `|A - Atilde|`. Two
supporting lemmas, `diag_perturbation_le` and `sqrt_one_add_sub_one_abs_le`,
land in `lean/Certkit/BackwardError.lean` next to `eta_bound`/`gamma_bound`.
`sweep_backward_bound`'s doc comment no longer describes the row-sum gap as
open; it now names `sweep_row_bound` as the theorem that closes it.

`lake build Certkit`: **8804/8804 jobs, success**, no new warnings beyond the
two pre-existing linter notes (unused section variable, unused binder name —
same ones present before this session, just shifted line numbers). `grep -n
sorry` on both files: zero matches for an actual `sorry` tactic (only the
word inside doc-comment prose, e.g. "zero `sorry`").

Python suite: **199 passed** (unchanged from session start — I did not touch
any Python logic, only docstring/comment citations). No-dependency checker
run below.

## What I found on claiming this bead

It was already `in_progress` (claimed same day it was filed, 2026-09-03,
apparently by the session that wrote and closed `certkit-zm6`). It left
behind two **untracked, uncommitted** files: `lean/Certkit/Scratch.lean` and
`lean/Certkit/Scratch2.lean`. `Scratch.lean` contained a near-complete draft
of exactly this bead's math (`sqrt_one_add_sub_one_abs_le`,
`diag_perturbation_le`, and a combination theorem
`sweep_row_perturbation_bound`) — but it **did not compile**:
`lake build Certkit.Scratch` failed with "don't know how to synthesize
implicit argument `beta`" in the combination theorem, because
`diag_perturbation_le` was invoked without pinning its implicit `a`/`beta`
arguments, which Lean cannot infer from the goal shape alone. So the
previous session's partial work was mathematically on the right track but
not actually finished or verified — I did not take its correctness on faith;
I re-derived the two key inequalities by hand first (below), then fixed and
integrated the draft.

`Scratch2.lean` is an unrelated exploratory snippet (an `example` computing
`toEuclideanCLM`'s inner-product formula) with no doc comment tying it to
this bead. I left it in place — not in scope for me to judge or delete
someone else's untracked exploration, and it isn't picked up by `lake build
Certkit` (confirmed: the default build only compiles what
`Certkit.lean` imports; `Scratch.lean` needed an explicit
`lake build Certkit.Scratch` invocation to even attempt, which is how I
found it didn't compile). I deleted `Scratch.lean` once its content was
migrated into the real files, since leaving a broken, unbuildable scratch
file with the same theorem names as the real ones in the tree seemed more
confusing than helpful. `Scratch2.lean` is still there, untouched, still
untracked.

## The derivation, made exact (this is the load-bearing part)

The bead's own writeup uses asymptotic bounds (`|eta| <= 2u + O(u^2)`,
`u <= 0.05`) to argue sub-obligation 1 is fine "with enormous margin." I did
not transcribe that hand-wave into Lean. Instead:

**Sub-obligation 1 (diagonal, the one with real content).** The runtime code
scales `ETA` by `|p|` where `p = fl(a_j - beta) = (a_j-beta)(1+e2)` is the
*rounded* value, not the exact `a_j - beta`. Soundness needs
`|a_j-beta|*|eta| <= ETA*|p| = ETA*|a_j-beta|*|1+e2|`, i.e. (scaling both
sides by `|a_j-beta|` instead of dividing, to sidestep the `a_j-beta = 0`
case) `|eta_of e2 e3| <= (2.1u)*|1+e2|`, exactly.  This is `eta_of e2 e3 =
e2+e3+e2*e3` expanded with `|e2|,|e3| <= u`. I checked by hand, exactly (not
asymptotically), which bound on `u` this needs: the binding case is
`e2=e3=-u` (both at their most negative), giving `|eta| = 2u-u^2` against a
required RHS of `2.1u*(1-u) = 2.1u-2.1u^2`; the inequality `2u-u^2 <=
2.1u-2.1u^2` reduces to `u <= 1/31 ≈ 0.0323`. The file's existing standard
hypothesis `u <= 1/32` (used everywhere else in `BackwardError.lean`,
including `gamma_bound` and `sweep_step_backward_bound`) is comfortably
inside that, so I reused it rather than introducing a new threshold — no new
magic number. Lean's `diag_perturbation_le` proves the multiplied-through
form `|a-beta|*|eta_of e2 e3| <= (2.1u)*|(a-beta)*(1+e2)|` directly via
`nlinarith`, same technique `eta_bound` already uses (bound the cross term
`|e2*e3| <= u^2`, `linarith`/`nlinarith` the rest) — not by asymptotics.

**Sub-obligation 2 (off-diagonal, "closest to already-checked" per the
bead).** Need `|sqrt(1+gamma)-1| <= 2u` given `|gamma| <= 3.1u` (`GAMMA`).
By hand: this needs `(1-2u)^2 <= 1+gamma <= (1+2u)^2`. The upper side is
free (`3.1u <= 4u+4u^2` always). The lower side needs `-3.1u >= -4u+4u^2`,
i.e. `4u^2 <= 0.9u`, i.e. `u <= 0.225` — again comfortably inside `u <=
1/32`. Proved in Lean via `Real.sqrt`'s monotonicity (`Real.le_sqrt`,
`Real.sqrt_le_left`) rather than a transcribed Taylor coefficient. This
matches the 60-digit-decimal figure already on record in `bd recall
backward-error-mechanism` (`|sqrt(1±GAMMA)-1| = 1.550000u` exactly, `0.45u`
slack under the `2u` budget) — I did not re-derive that number, I derived
the *inequality that number empirically confirmed*, which is the thing
actually load-bearing for soundness (an empirical decimal check isn't a
proof; this closes the gap between them).

**Sub-obligation 3 (Atilde symmetric).** Handled by *statement shape*, not a
separate proof: `sweep_row_bound`'s off-diagonal terms name one `bprev` and
one `bnext` — real numbers, not per-side copies. The mirror instance of the
same theorem for row `j-1` reads its own `bnext` as the literal same real
number this instance calls `bprev`, because `backward_error.sweep` reads
`off[j-1]` once and only once per pair. There is no second, independently-
perturbed value for a symmetry proof to have to reconcile against, so I
documented this in the doc comment rather than building an actual `Matrix
n n ℝ` and proving `.IsHermitian` for it generically — building that matrix
runs into a real wrinkle (indexing "row j's right neighbour" with `Fin n`
addition wraps around at the boundary, so a generic from-sequences
construction needs `ℕ`-based side conditions, not `Fin n` arithmetic, to
actually mean "tridiagonal" — a correct but nontrivial detour the bead's own
design section explicitly says not to take: "Do NOT try to formalize
`backward_error.sweep`'s Python loop itself.").

## What `sweep_row_bound` states and does not state

```
theorem sweep_row_bound
    {u e0 e1 e2 e3 gnext a beta bprev bnext : ℝ}
    (hu : 0 ≤ u) (hu1 : u ≤ 1 / 32)
    (h0 : |e0| ≤ u) (h1 : |e1| ≤ u) (h2 : |e2| ≤ u) (h3 : |e3| ≤ u)
    (hgnext : |gnext| ≤ 3.1 * u) :
    |(a - beta) * eta_of e2 e3|
        + |bprev * (Real.sqrt (1 + gamma_of e0 e1 e3) - 1)|
        + |bnext * (Real.sqrt (1 + gnext) - 1)|
      ≤ (2.1 * u) * |(a - beta) * (1 + e2)| + (2 * u) * |bprev| + (2 * u) * |bnext|
```

LHS is `|E_jj| + |E_{j,j-1}| + |E_{j,j+1}|` — the three nonzero entries of
tridiagonal row `j` of `E = A - Atilde` — and RHS is exactly
`ETA*|p| + two_u*(|b_prev|+|b_next|)`, `sweep`'s runtime formula. Two
independent gamma hypotheses (`gamma_of e0 e1 e3` for the `bprev` pair,
`gnext` for the `bnext` pair) because those two off-diagonal perturbations
come from two different pivot steps of the sweep, not one shared value.

It does **not** formalize `backward_error.sweep`'s Python loop, its `Iv`
accumulation, or construct an actual `n×n` `Atilde` matrix — per the bead's
own design note, that stays a Python-test obligation, already covered by
`interval.py`'s own already-proved soundness contract (`Iv` encloses the
exact real value of any `+`/`-`/`*` expression). What remained genuinely
open before this bead (the *mathematical* row-sum inequality) is now proved;
what was never in scope (the *Python loop's* faithfulness to that math)
still isn't, and I said so in the new doc comment rather than blurring the
two.

## Bounds/tolerances touched, with derivation

I did not change `ETA`, `GAMMA`, `two_u`, or the `GAMMA/2 > 2*U` runtime
guard in `backward_error.py` — no Python constant changed. The only new
Lean-side threshold is reusing the file's existing `u <= 1/32` hypothesis for
two new lemmas; I checked by hand (above) that both needed inequalities
(`u <= 1/31` and `u <= 0.225`) are satisfied with margin by `u <= 1/32`, so
no new constant was introduced — I deliberately did not invent a tighter or
looser threshold to make anything "come out."

## Documented limits I did not touch

None of README's stated limits (coverage cliff, `DENSE_LIMIT`, Gershgorin as
floor-not-bound, producer eigenvector past n≈10⁴) are affected by this bead;
I didn't re-measure or touch any of them.

## What I found but left alone (filed instead)

`README.md`'s "## The Lean side" section still says "seven soundness
obligations" — stale before this session (it was already one behind after
`certkit-zm6` added `l2_opNorm_le_rowSum_of_isHermitian` as an eighth without
updating README), and now two behind after this bead's ninth
(`sweep_row_bound`). I filed `certkit-2dg` for this rather than editing
README myself, since it's outside this bead's stated scope and the task
instructions say to file rather than fix drive-by work.

`lean/Certkit/Scratch2.lean` (untracked, unrelated to this bead) — left in
place, not part of my task, doesn't affect `lake build Certkit`.

## Final verbatim runs

```
$ uv run --extra dev pytest tests
============================= test session starts ==============================
...
============================== 199 passed in 63.17s (0:01:03) ========================

$ /home/node/.local/share/uv/python/cpython-3.12.13-linux-aarch64-gnu/bin/python3.12 \
    -m certkit.cli check examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]

$ cd lean && lake build Certkit
...
Build completed successfully (8804 jobs).

$ grep -n "sorry" lean/Certkit/Soundness.lean lean/Certkit/BackwardError.lean
(only doc-comment mentions of the word "sorry"; no `sorry` tactic use)
```

Note on the no-dependency checker run: this container has no bare `python3`
on `$PATH` at all (a container property, not something this session
changed) — `uv`-managed venvs only. I used the venv-free interpreter uv
itself downloads to `~/.local/share/uv/python/cpython-3.12.13-.../bin/
python3.12` (confirmed via `sys.path` that it has no site-packages beyond
its own stdlib) as the equivalent of "no `uv`, no venv, no install." If a
reviewer wants a stricter check, any bare CPython 3.x with an empty
site-packages will do.

## What I could not verify

I did not attempt to independently re-verify `Real.le_sqrt` and
`Real.sqrt_le_left`'s exact mathlib semantics beyond reading their source
(`lean/.lake/packages/mathlib/Mathlib/Analysis/Real/Sqrt.lean:224,240`) and
letting `lake build` typecheck the proof — that's the standard level of
trust this repo places in mathlib itself (per `Interval.lean`'s own stance),
not a gap specific to this bead.

I have not attempted `certkit-jcb` (the human-review bead) or reopened
`certkit-ph1`/`certkit-487` — out of scope, left as documented in CLAUDE.md.

## Handback

```
git status
# modified (mine, this bead):
#   lean/Certkit/BackwardError.lean
#   lean/Certkit/Soundness.lean
#   certkit/backward_error.py   (docstring + comment citations only, no logic change)
#   issues.jsonl                (bd export, includes certkit-62j close + certkit-2dg new bead)
# deleted (mine): lean/Certkit/Scratch.lean (broken draft, migrated into the real files)
# also present (NOT mine, pre-existing uncommitted work from other sessions/beads
# certkit-4ue, certkit-85m, certkit-jcb review): AGENTS.md, README.md, CLAUDE.md,
# certkit/__init__.py, certkit/checker.py, tests/*, REVIEW-jcb.md, sandbox-handoffs/*.md,
# lean/Certkit/Scratch2.lean — left untouched, not part of this bead
```

Per the repo's git policy I did not commit or push. Suggested commands for a
human:

```
git add lean/Certkit/BackwardError.lean lean/Certkit/Soundness.lean \
        certkit/backward_error.py issues.jsonl
git rm lean/Certkit/Scratch.lean
git commit -m "Prove sweep's row-sum bound dominates ||A - Atilde||_inf (certkit-62j)"
```

(left as separate suggested commands from the other uncommitted work in the
tree, which belongs to different beads and different sessions.)
