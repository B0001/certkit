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

**Do not overstate the Lean side, but re-measure before you repeat this
paragraph.** `lean/Certkit/Soundness.lean` states seven soundness obligations
against mathlib4. As of a fresh check this session (`grep -n sorry
lean/Certkit/Soundness.lean` for an actual `sorry` tactic, plus `cd lean &&
lake build Certkit`), all seven — `rayleigh_ritz_min`,
`residual_encloses_some_eigenvalue`, `temple_lower`, `inertia_count_below`,
`gershgorin_lower`, `weyl_shift`, `sweep_backward_bound` — compile with zero
`sorry`, and `lake build Certkit` succeeds as a whole (8804/8804 jobs; only
unused-variable/section lints, no errors). That is a fact about this file,
not the claim "the checker is proved sound end-to-end" — that also requires
the Python side to actually implement what each theorem states, which is a
separate, ongoing correspondence question. In particular `weyl_shift`'s own
doc comment flags a specific, currently uncovered gap — the relation between
the entrywise/row-sum bound `sturm_be` computes at runtime and the L2
operator norm `weyl_shift` is stated against — that a compiling proof does
not resolve. Do not trust this paragraph's numbers either: re-grep the file
for `sorry` (matching only an actual tactic use, not the word in a doc
comment) and re-run `lake build Certkit` before repeating them, and check
`bd show` on any bead cited here rather than assuming the status printed at
the time this paragraph was last edited still holds.

## Known baseline — do not mistake this for your own breakage

The suite is **fully green**, with a passing count that only goes up as beads
land — re-run `uv run --extra dev pytest tests` yourself rather than trusting
a number pinned here (it read 165 at one point, 181 as of a fresh run this
session — see `certkit-shj`). There is no documented pre-existing failure to
excuse one.

**Any failure at all is yours and must be fixed before you close a bead.**

The one way to get a falsely green run is to invoke pytest without the dev
extra. The checker has no dependencies *by design*, so `uv run pytest tests`
without `--extra dev` has no numpy and no pytest and will not tell you what
you think it did. See Environment below.

## Objectives

Work the queue; `bd ready` is the authority. Run it yourself — the bullets
below are standing context, not a substitute, and can go stale between
sessions (they have before: see `certkit-t2k`, `certkit-bba`). Verify any
bead ID mentioned here against `bd show` before trusting its status.

- **`certkit-jcb` cannot be done by you.** It asks for a *second human* to
  read `interval.py` and `backward_error.py` against their derivations. A
  worker session reviewing code written by a model is not an independent
  reviewer, and closing it would destroy the only record that the soundness
  argument is unreviewed. Leave it open — do not claim it, regardless of
  whether `bd show certkit-jcb` currently reports it open or in_progress.
- **`certkit-ph1` (coverage cliff) is closed**, infeasible-for-now after six
  worker sessions ruled out every concretely-named matrix-free counting rule
  (adversarial subspace-oracle impossibility, term-count exploitation,
  banded/Sturm, FEAST/contour-integral, fill-reducing sparse LDL^T — see its
  close notes and `sandbox-handoffs/certkit-ph1.md`). Do not reopen or
  reattempt it from scratch. The one thread it left genuinely untried —
  certified tensor-network/MPO methods with interval-bounded truncation
  error — is now its own bead, `certkit-k2j`; work that one instead if you
  want to continue this line.
- **`certkit-487` (sector-scope bug) is closed.** It was a scope bug, not a
  soundness bug — the checker correctly abstains on a sector-local claim that
  doesn't separate the full spectrum. The invariant is documented (README,
  `checker.py`'s `_temple()` docstring) and permanently regression-tested
  (`tests/test_sector_scope.py`). No action needed.
- The `certkit-8y2` epic (all `8y2.*` Lean beads) is closed as of this
  writing — see "Do not describe the Lean side as proved" above for what
  that does and does not mean about the file's soundness status. If a new
  Lean gap surfaces (`weyl_shift`'s doc comment names a specific uncovered
  one), file a fresh bead rather than assuming an `8y2.*` ID is still open.

If `bd ready` is empty, that means file new beads, not that you are done.

## Environment

- **Install the dev extra or your test run means nothing:**

  ```
  uv sync --extra dev
  uv run pytest tests          # re-measure — count drifts upward as beads land
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
