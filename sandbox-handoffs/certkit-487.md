# Handoff: certkit-487 — Krylov sector scope does not survive translation to lambda_min_enclosure

## Verdict

**Closed, not fixed by a code change.** Investigation (deliberately constructing
the adversarial case the prior session's notes asked for, rather than assuming
it's safe) confirms the checker cannot be made to emit a false VERIFIED by a
sector-scoped witness. No rule in `checker.py` or `producer.py` was changed.

No verdict *changed* for any existing input — no bead moved from ABSTAIN to
VERIFIED or vice versa. What changed is that the residual risk flagged in the
bead's notes ("worth constructing such a case deliberately rather than
assuming it cannot happen") has now been constructed, exercised, and turned
into a permanent regression test.

## The constructed case

`tests/test_sector_scope.py` builds a 5-dimensional block-diagonal operator
with two decoupled sectors (mirroring the H2/H4 shape from the bead: a
"reachable" sector A and an unreachable lower sector B):

- diag = `[-1.0, 3.0, 5.0, b_ground, b_rest]` — indices 0-2 are sector A,
  3-4 are sector B.
- The simulated naive bridge only ever looked at sector A: its witness vector
  is `e_0` (A's *exact* local ground eigenvector, zero-padded into B), and its
  beta is `0.5*(-1.0 + 3.0) = 1.0` — the midpoint of sector A's own two lowest
  levels, i.e. exactly the "self-mode" translation described in the bead.
- Because the vector is an exact eigenvector of the (decoupled) full operator
  too, the naive Temple translation is a **point claim**, `[-1.0, -1.0]` — as
  confident as a false claim can be made to look, with zero residual to hide
  behind.

Four cases, built directly against the public certificate schema (not
`certkit.producer`, since the bug is specifically about a *different*,
hypothetical producer submitting sector-local data through the same door):

1. `test_lower_lying_sector_makes_the_naive_translation_abstain` — sector B's
   ground is -4.0 (true lambda_min), well below A's local beta of 1.0. The
   point claim `[-1.0, -1.0]` is false (true min is -4.0). `check()`
   **ABSTAIN**s: `"2 eigenvalues lie below beta, need exactly 1"`.
2. `test_small_violation_of_the_premise_is_still_caught` — sector B's ground
   is only 0.01 below A's ground (not H2's dramatic 1.02 Ha). Still
   **ABSTAIN**s, same reason — confirming detection is a count, not a
   tolerance, and isn't magnitude-dependent.
3. `test_sector_ground_that_is_also_the_global_minimum_verifies` — contrast
   case matching the bead's own H2/H4 empirical finding: sector B's ground is
   well above A's, so A's ground genuinely is the global minimum and beta
   genuinely separates the full spectrum. With a realistically padded claim
   (unpadded point claims get refused as "tighter than the re-derived
   enclosure" purely from the checker's own interval widening — a producer
   is expected to pad, per certkit-kj6), `check()` **VERIFIES**.
4. `test_full_space_producer_finds_the_true_minimum_on_the_same_operator` —
   on the exact matrix that defeats the naive sector translation in case 1,
   `certkit.producer.certify_lambda_min` (which always solves the *whole*
   operator via `_ground_state`, never a sector) correctly finds and
   verifies the true minimum of -4.0. This is the "full-space route" the
   acceptance criteria asked for, and it already existed.

Command showing the core result:
```
uv run pytest tests/test_sector_scope.py -v
# 4 passed
```

## Why this is structurally impossible to break, not just empirically absent

`_rule_temple_inertia` / `_rule_temple_ref` (checker.py) discharge beta by
calling `count_eigenvalues_below` against `op.interval_rows()` — rows decoded
from the operator the *certificate itself references* (bound by content hash,
`operator_ref`). That count has no channel through which a producer's private
"this beta came from sector A" reasoning could enter; it is purely: how many
eigenvalues of *this actual matrix* lie below *this actual beta*. If a
sector-local beta doesn't separate lambda_1 from lambda_2 of the true, full
operator, the count comes out `!= 1` and the rule abstains before Temple's
arithmetic (`_temple`) is even reached. Temple's own inequality is then
applied only when that premise has been re-established against the true
operator — regardless of what subspace produced the witness vector or the
beta value in the first place.

This means the "sector scope" confusion can only ever cost **coverage**
(more ABSTAINs from a lazier/sector-restricted producer), never **soundness**.
That is exactly the asymmetry the whole repo is built on (README's guarantee
section), just not previously demonstrated with a constructed counterexample
for this specific translation.

## What I touched, and the derivation for each

No bound, tolerance, guard, or threshold was touched anywhere in this
session — nothing needed changing.

- `certkit/checker.py`, `_temple()` docstring: added an explanatory paragraph
  stating explicitly that "the gap" means lambda_2 of the whole operator, not
  of whatever subspace produced `x`/`beta`, and pointing at the new test.
  Documentation only, no logic change.
- `README.md`, "The guarantee" item 3: added a paragraph making the same
  point in the public-facing guarantee section, since this is exactly the
  kind of claim a reader needs when deciding whether to trust the checker
  against an external, symmetry-sector-restricted solver.
- `README.md`, "Known limits": added a bullet stating plainly that a
  sector-restricted producer pays a *coverage* cost (more abstentions), not a
  soundness one — phrased as a limit on the producer, not a relaxation of
  anything the checker guarantees. I did not upgrade any existing
  "Known limits" bullet's conclusion; this is a new, additive bullet.

## Acceptance criteria: which branch, and why

The bead offered two options: "(a) a sector-restricted claim kind that
carries its subspace as part of the claim, or (b) a documented producer rule
that beta must separate the full spectrum and a full-space route for
obtaining it."

I went with **(b)**, because it was already true of the code as it stood —
`_rule_temple_inertia`/`_rule_temple_ref` already require beta to separate
the *full* spectrum (mechanically, via inertia counting against the actual
operator, not by trusting the producer), and `certkit.producer._ground_state`
already only ever solves the whole operator, never a sector. What was
missing was (1) a constructed demonstration that this holds even in the
adversarial "lower sector exists" case, and (2) explicit documentation of the
invariant. Both are now in place.

I deliberately did **not** implement (a), a new sector-restricted claim kind.
Nothing in this repo (or its external bridge, which isn't in this repo)
currently produces or consumes such a claim, so adding one would be
speculative surface — a new claim kind, a new rule, new schema fields — for a
producer contract that doesn't exist here. If a future producer genuinely
needs to certify "the ground state of *this subspace* is bounded", that's a
new bead with its own design, not a retrofit onto this one.

## Documented limits/hedges I was tempted to touch, and what I did instead

I was tempted to soften the "Known limits" framing to something like "sector
scoping is a solved problem" — that would misstate what was shown. What I
wrote instead is narrower and accurate: a sector-restricted producer costs
coverage, not soundness. I did not touch `DENSE_LIMIT`, the Gershgorin
characterization, or any of the other existing "Known limits" bullets; none
of them are affected by this investigation.

## Final test-run line (verbatim)

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

============================= 110 passed in 5.19s ===============================
```
106 baseline + 4 new (`tests/test_sector_scope.py`), 0 failures, 0 skips.

No-dependency checker run — this container has no system `python3`, so I ran
uv's bare managed interpreter directly, with its site-packages excluded from
`sys.path` (`-S` flag), and confirmed numpy is genuinely unimportable there
before running the checker:

```
$ /tmp/uv-python/cpython-3.14.7-linux-aarch64-gnu/bin/python3.14 -c \
    "import sys; sys.path = [p for p in sys.path if 'site-packages' not in p]; import numpy"
Traceback (most recent call last):
  ...
ModuleNotFoundError: No module named 'numpy'

$ /tmp/uv-python/cpython-3.14.7-linux-aarch64-gnu/bin/python3.14 -S -m certkit.cli check \
    examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

(Note on environment: this sandbox came up without `python3` on `PATH` at
all, and without a pre-chowned `uv` cache — I hit the "Permission denied"
cache issue from the prompt's Environment section and used the documented
`/tmp` fallback, `UV_CACHE_DIR=/tmp/uv-cache UV_PYTHON_INSTALL_DIR=/tmp/uv-python`.
That's a container quirk, not a repo problem, but flagging it since the
`python3 -m certkit.cli` command in the prompt's Environment section
doesn't work verbatim here — there's no bare system Python; I had to reach
into uv's managed interpreter directory instead.)

## What I decided not to do, and why

- Did not implement a sector-restricted claim kind (acceptance criterion
  (a)) — covered above, would be speculative surface with no current
  producer.
- Did not touch `certkit/producer.py` at all. The producer already only
  solves full operators; there was nothing sector-scoped to fix there, and
  the bug this bead is about lives in a hypothetical *external* bridge
  (`chem/certkit_bridge.py`), which is not part of this repo.
- Did not try to reconstruct or guess at the real chemistry bridge's code —
  it isn't present in this repo (`chem/`, `temple_bounds.py` don't exist
  here), so I built a synthetic but structurally faithful stand-in (a
  block-diagonal operator with a reachable and an unreachable sector) rather
  than fabricate an external file that isn't mine to invent.
- Did not add a test using the `pauli_sum_real` / matrix-free backend for
  this scenario. The sector-scope question is about checker semantics
  (inertia counting against the true operator vs. a subspace), which is
  backend-independent; the dense backend gives exact, reproducible numbers
  and is what the existing adversarial tests (`test_tamper.py`) already use
  for this kind of case.
- Did not touch `certkit-jcb` (independent review) or any other bead. Left
  `certkit-ph1` and the `8y2.*` Lean beads untouched, per the standing
  instructions for this session.

## What I could not verify

- I could not verify this against a real quantum-chemistry Hamiltonian
  (H2/sto-3g, H4) as the original bead's notes did, because `chem/`,
  `temple_bounds.py`, and the QKSD Krylov solver referenced in the bead are
  not present in this repository — they belong to an external project this
  repo's producer/checker format serves. The synthetic block-diagonal
  operator in `tests/test_sector_scope.py` is a faithful structural analogue
  (a reachable sector with its own local gap, and an unreachable lower
  sector), but it is not the literal molecular case. I'm flagging this
  explicitly rather than implying the chemistry case itself was re-run.
- I did not attempt to prove the Lean-side obligations related to Temple's
  inequality (`lean/Certkit/Soundness.lean` is still all `sorry`, unchanged
  by this session) — the argument above is a Python-level/mathematical
  argument about `checker.py`'s control flow, not a machine-checked proof.

## Handoff commands

```bash
git status
git diff --stat
# modified: README.md, certkit/checker.py
# untracked: tests/test_sector_scope.py, issues.jsonl (re-exported), uv.lock (was already untracked pre-session)

# Suggested commit (not run — git policy for this session is report-only):
git add README.md certkit/checker.py tests/test_sector_scope.py issues.jsonl
git commit -m "certkit-487: document and regression-test that sector-scoped witnesses can only abstain, never falsely verify"
```

`bd close certkit-487` has been run, with the reasoning above as the close
`--reason` and full derivation in the issue's `--notes`. `issues.jsonl` has
been re-exported and is staged as an untracked-but-modified file above (part
of the suggested commit, not committed by me).
