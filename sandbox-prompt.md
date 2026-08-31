You are working autonomously in the certkit repo. Make aggressive, real
progress. Do not stop to ask permission; do not stop early because you are
unsure whether there is work left.

## The standard everything is held to

This repo publishes one guarantee:

> If `check()` returns VERIFIED with enclosure `[lo, hi]`, then the true
> smallest eigenvalue of the operator lies in `[lo, hi]`.

Unconditionally — regardless of what produced the claim, including a producer
that is buggy, non-deterministic, or adversarial. Everything else here is
subordinate to that sentence.

**An unsound VERIFIED is the only unacceptable outcome of your session.** Not
a failing test, not an abstention, not an unfinished bead. If you are ever
choosing between a change that increases coverage and one that preserves
soundness, there is no trade to weigh — soundness wins and the coverage loss
gets reported.

**ABSTAIN is not a bug and must never be "fixed".** It is the correct output
whenever a proof was not produced. Widening a bound, relaxing a tolerance,
loosening a guard, or nudging a threshold so that a case verifies is the
single worst thing you can do in this repo, and it will look like progress
when you do it. If an abstention seems wrong, the honest moves are to prove
the bound is sound and tighten it *with the derivation written down*, or to
file a bead explaining why the case is refused. Never a third.

**The trust boundary is mechanical, not advisory.** The trusted modules
(`interval.py`, `schema.py`, `operators.py`, `banded.py`, `backward_error.py`,
`checker.py`) import the standard library and nothing else — no numpy, no
third-party package, and never anything from `producer.py`.
`tests/test_trust_boundary.py` parses their imports and runs the checker in a
subprocess where numpy is unimportable. If you find yourself wanting to skip,
weaken, or work around that test, stop: it is the load-bearing test in the
suite, and the thing it prevents is the checker quietly leaning on a number
the producer handed it.

**No transcribed constants.** The repo's own rule, from
`backward_error.py`: a constant copied out of a paper is exactly the kind of
trust this design refuses, because getting it slightly wrong yields a
confident wrong answer rather than an abstention. Bounds are computed from the
matrix in front of the checker, in outward-rounded interval arithmetic. Do not
introduce a magic number to make an analysis come out; derive it or abstain.

**The documented limits are measurements and must survive you.** The README
states that coverage falls to zero as the spectral gap closes, that
`DENSE_LIMIT = 256` makes the tight route decline rather than run for an hour,
that Gershgorin is "a floor, not a good bound", and that past n ≈ 10⁴ the
producer's eigenvector is the binding constraint. Those are honest results. If
you improve something, **re-measure and report the new number — do not upgrade
the conclusion.** Softening a stated limitation because a metric moved is a
regression even when every test still passes.

**Do not describe the Lean side as proved.** `lean/Certkit/Soundness.lean`
states seven soundness obligations against mathlib4. Six of them —
`rayleigh_ritz_min`, `residual_encloses_some_eigenvalue`, `temple_lower`,
`inertia_count_below`, `gershgorin_lower`, `weyl_shift` — end in `sorry` and
are a specification of intent, not a verified artifact. The seventh,
`sweep_backward_bound`, is a real, zero-`sorry` proof (formalized under
certkit-8y2.2, closed): it discharges the one-rounding-per-operation model and
the per-step collection into the `eta`/`gamma` factors `backward_error.py`
uses. Do not read that as license to call the other six proved, or this file
"soundness-complete" — and re-grep the file for `sorry` before trusting this
count, since certkit-8y2.3 and certkit-8y2.4 are open/in_progress and may
change it. Of the six still open, `weyl_shift`'s own doc comment flags a
specific, currently uncovered gap — the relation between the entrywise/
row-sum bound `sturm_be` computes at runtime and the L2 operator norm
`weyl_shift` is stated against — which is arguably a better candidate for
"the obligation with the worst failure mode not yet even written down" than
`sweep_backward_bound`, which is finished. Whether `lake build Certkit`
succeeds as a whole is a separate, unsettled question (see certkit-8y2.4 on
pre-existing type-class errors); don't conflate an individual theorem
compiling via `lake env lean` with the whole-file build passing. Saying
otherwise anywhere in the repo is a false claim about the thing this repo
exists to be careful about.

## Known baseline — do not mistake this for your own breakage

The suite is **fully green**: `165 passed`. There is no documented
pre-existing failure to excuse one.

**Any failure at all is yours and must be fixed before you close a bead.**

The one way to get a falsely green run is to invoke pytest without the dev
extra. The checker has no dependencies *by design*, so `uv run pytest tests`
without `--extra dev` has no numpy and no pytest and will not tell you what
you think it did. See Environment below.

## Objectives

Work the queue; `bd ready` is the authority. Some standing context on what is
in it:

- **`certkit-jcb` cannot be done by you.** It asks for a *second human* to
  read `interval.py` and `backward_error.py` against their derivations. A
  worker session reviewing code written by a model is not an independent
  reviewer, and closing it would destroy the only record that the soundness
  argument is unreviewed. Leave it open. Do not claim it.
- **`certkit-ph1` (coverage cliff) is the highest-value executable bead.**
  Past `DENSE_LIMIT` the gap cannot be discharged, so Temple is unavailable
  and the only surviving route gives Ha-scale widths against a 1.6 mHa
  requirement. A counting rule that works matrix-free is what would change
  that. This is real research, not plumbing — if you cannot finish it, leave
  notes and it will come back.
- **`certkit-487` is a scope bug, not a soundness bug.** The checker correctly
  abstained. Read its notes before acting: an earlier framing of it was too
  alarming and was corrected in place.
- The `8y2.*` Lean beads are proof work. Discharging one means the `sorry` is
  gone and the file compiles, not that the statement looks right.

If `bd ready` is empty, that means file new beads, not that you are done.

## Environment

- **Install the dev extra or your test run means nothing:**

  ```
  uv sync --extra dev
  uv run pytest tests          # 165 passed, about 24 seconds
  ```

- **Verify the trust boundary the cheap way** — the checker must run on an
  interpreter with no third-party packages at all:

  ```
  python3 -m certkit.cli check examples/sample/certificate.json \
                               examples/sample/operator.json -v
  ```

  No `uv`, no venv, no install. If that ever needs a dependency, you have
  broken the property the repo is built on.

- The producer side (`producer.py`, the examples) needs numpy. The checker
  must never need it.

- **If `uv run` fails immediately with `Failed to initialize cache at
  /home/node/.cache/uv ... Permission denied`**, that is a container issue,
  not a repo problem — the uv volumes come up root-owned while the session
  runs as `node` (uid 1000). `sandbox.sh` chowns them before dispatching, so
  you should not hit it. If you somehow do, unblock yourself with scratch
  space and file a bead:

  ```
  export UV_CACHE_DIR=/tmp/uv-cache UV_PYTHON_INSTALL_DIR=/tmp/uv-python
  mkdir -p /tmp/uv-cache /tmp/uv-python
  ```

  `/tmp` is not a named volume, so this re-downloads the interpreter and
  wheels for every worker. It is a fallback, not the fix.

- `bd` is the tracker. File a bead per work item with `bd create` before
  writing code, `bd update <id> --claim`, and close only when the evidence the
  bead asks for exists.

## Git policy

Do the work, get the suite green, leave the tree **ready to commit**. Do not
`git commit`, do not `git push`, do not `bd dolt push`. Put the exact commands
in your handoff and let a human run them.

Note that `issues.jsonl` at the repo root is the durable, git-tracked export
of the bead database. If you change beads meaningfully, run
`bd export -o issues.jsonl` and mention it in the handoff so the reasoning
survives in git rather than only in the gitignored Dolt directory.

## What to hand back

**Write this to the handoff path named at the end of this prompt before you
finish, and print it as your final message.** The file is the part that
survives; this container is disposable.

A report a reviewer can check, not a summary of effort:

- The exact verdict change, if any: which inputs verified or abstained before,
  which do now, and the command that shows it.
- Any bound, tolerance, guard, or threshold you touched — with the derivation
  that justifies the new value. If you cannot write the derivation, you should
  not have touched it, and saying so here is the right outcome.
- Any documented limit or hedge you were tempted to soften, with the
  measurement, and what you did instead.
- The final test-run line verbatim, with the pass/fail count, plus the output
  of the no-dependency checker run above.
- What you decided not to do, and why. Empty means you did not look hard.
- What you could not verify. An honest "unverified" beats a confident claim —
  that is the whole thesis of this repo, and it applies to your handoff too.
