# Handoff: certkit-bz5 — Real-time Krylov witness is complex; the format is real-only

## Verdict

**Not fixed in the place the bead's acceptance criteria names** —
`chem/certkit_bridge.py` is not part of this repository and never has been
(`git log --all -- '**/certkit_bridge.py' 'chem/**'` returns nothing; the
directory doesn't exist in the working tree either). `certkit-487`'s handoff
independently confirmed the same thing for a different bead. I cannot edit a
file that isn't here.

What *is* actionable in this repo, and what I did:

1. Constructed the exact adversarial case the bead describes and confirmed
   the checker refuses it — it cannot be made to falsely VERIFY.
2. Closed the coverage gap that made the external bug possible in the first
   place: `certkit.producer` had no supported entry point for a certificate
   built around a witness vector the *caller* supplies (as opposed to one
   `producer.py` finds itself via `_ground_state`). Every `certify_*`
   function computes its own witness internally, so an external bridge with
   its own solver (a QKSD Krylov solver, in this case) had nothing to call
   except hand-assembling a certificate directly against the schema — which
   is exactly how a bracket computed on one vector (`psi0`) ends up shipped
   next to a different one (`Re(psi0)`) in the witness field.
3. Documented the pitfall and the fix in the README's "Writing a producer"
   section, pointing at the new function.

No verdict for any *existing* input changed — this is new coverage
(`certify_lambda_min_from_witness`) plus a new regression test, not a change
to any existing rule's behaviour.

## The bug, reproduced

`tests/test_complex_witness_transcription.py`:

- `H = diag(-2.0, -1.5, 5.0)` (real symmetric, three well-separated levels;
  `e0`, `e1`, `e2` are its exact eigenvectors).
- `psi0 = a*e0 + i*b*e1`, normalised, with `a**2 = 0.47`, `b**2 = 0.53` —
  53% of the weight in the imaginary part, matching the bead's own H2/sto-3g
  number exactly.
- The naive bridge computes `mu_complex = <psi0|H|psi0>` honestly (`sum
  |c_i|^2 * lambda_i`, using the actual complex amplitudes) — that's a real
  number a real solver's own diagnostics would report, ≈ -1.735. It then
  submits a certificate whose **witness field carries `Re(psi0)`** (which
  here is exactly `e0`'s direction — the true ground eigenvector, own
  Rayleigh quotient exactly -2.0) with the bracket built around `mu_complex`.
- `check()` on that certificate: **ABSTAIN**,
  `"claimed interval is tighter than the re-derived enclosure"` — the exact
  message quoted in the bead. The re-derivation the checker actually used
  (recomputed from the real vector that's actually in the witness field) is
  centred on -2.0, not -1.735; the claimed bracket doesn't contain it.
- A second test confirms this isn't checker overcaution: taken at face
  value, `[mu_complex - pad, mu_complex + pad]` does **not** contain the
  true lambda_min (-2.0) either. The claim really was false.

Command:
```
uv run pytest tests/test_complex_witness_transcription.py -v
# 6 passed
```

## Why the checker cannot be fooled by this bug class, structurally

`_temple()` in `checker.py` computes `mu, rho2 = _rayleigh_and_residual(op, x)`
from `x` — the vector *actually in the witness field* — against the operator
the certificate references by content hash. It has no channel for a
producer's separately-computed `mu` to enter; `_implies()` then requires the
*claimed* interval to contain the *re-derived* one or refuses. A bracket
computed on `psi0` and a witness vector of `Re(psi0)` are, from the checker's
point of view, simply "a claimed interval" and "a re-derived interval from
a specific vector" — if they were computed from different vectors, they
generally won't match, and the claim gets refused. This is the same
"structurally impossible to break" argument `certkit-487`'s handoff made for
sector-scoped witnesses, applied to a different producer bug.

This means the whole bug class the bead is about — real Krylov witness
carrying a bracket derived from a complex state — can only ever cost
**coverage** (an ABSTAIN where the honest bridge fix would have gotten a
VERIFIED), never soundness. That distinction is worth stating plainly since
it's easy to read "produces a wrong ABSTAIN message" as a checker bug; it
isn't one.

## The fix: what a bridge should call instead

`certkit/producer.py` had no function that takes an externally-supplied
witness vector — every `certify_*` function finds its own via
`_ground_state`, which solves the *whole* operator itself. That's fine for
`certkit.producer`'s own use, and it's *also* exactly why an external bridge
with a vector from a different solver had nothing correct to call: it had to
either not use `producer.py` at all (assembling a certificate by hand, where
the transcription bug happens easily) or find some other way in.

Added `certify_lambda_min_from_witness(operator, x, *, slack=1e-9)`:
recomputes mu, the residual, and the lower bound from `x` and `operator`
alone, via the same code path (`_temple_inertia_bracket`, extracted from
`certify_lambda_min` — same operations, same order, no numeric change) that
`certify_lambda_min` already uses for its own internally-found vector. There
is no parameter or code path through which a number computed against a
different vector could enter the emitted certificate. Called on `Re(psi0)`
in the same H2-shaped test, it produces a certificate that **VERIFIES**,
correctly, around `Re(psi0)`'s own Rayleigh quotient — demonstrating the
"bridge recomputes mean/variance on the emitted real witness" branch of the
bead's acceptance criteria actually works when there's a real function to
call for it. Called on `Im(psi0)` (which here happens to be `e1`'s
direction, the second level, not the ground state) it correctly **ABSTAINs**
("Rayleigh quotient is not provably below beta") — the honest outcome for a
vector that genuinely isn't a valid lambda_min witness, not something to be
massaged into verifying.

`certify_lambda_min`'s own output is unchanged: the refactor only moved the
existing five lines (`ax = apply(x); nx2 = ...; mu = ...; r = ...; rho2 =
...` plus the gap/pad logic) into a shared helper in the same order; the
full suite (including every test that pins `certify_lambda_min`'s exact
numeric output) still passes.

## Bounds, tolerances, guards, or thresholds touched

None. `pad_claim`, the Temple inequality, the inertia discharge, and every
existing tolerance are untouched. The only numeric code added
(`_temple_inertia_bracket`) is a byte-for-byte extraction of code that
already existed in `certify_lambda_min`, reused by the new function; no new
constant, magic number, or relaxed guard was introduced anywhere.

## Documented limits I was tempted to touch, and what I did instead

None directly apply to this bead (`DENSE_LIMIT`, the Gershgorin
characterization, and the coverage-cliff numbers are all untouched and
unaffected by this change). I was tempted to phrase the README addition as
"this is now fixed" — it isn't; the bug lived in an external bridge this
repo can't edit, and what's fixed here is that the bridge now has a correct,
supported function to call instead of a coverage gap that made hand-rolling
the bug easy. I wrote the README section to say exactly that (a pitfall +
a fix to call, not a claim that the external bug is resolved).

## What I decided not to do, and why

- Did not touch `certkit-3ta` (complex Hermitian support), the acceptance
  criteria's other branch. It's a separate bead, already `in_progress` under
  a different claim, with its own uncommitted work already in the tree
  (`certkit/interval.py`'s `CIv`/`cdot`/`csqnorm` additions). Out of scope
  for this bead and not mine to claim.
- Did not attempt to reconstruct or guess at the real chemistry bridge's
  code — `chem/`, `certkit_bridge.py`, and the `QuantumKrylovSolver` class
  referenced in the bead are not present in this repository. Built a
  structurally faithful synthetic case instead (real symmetric H, complex
  psi0 with the bead's own 53%-imaginary-weight number), same approach
  `certkit-487`'s handoff used for the same reason.
- Did not add a `certify_*_from_witness` variant for the matrix-free
  (Gershgorin) or generalized-eigenproblem routes. The bead is specifically
  about the Temple+inertia route (`certify_lambda_min`, the one `jn1.1`'s
  bridge actually used per its close reason: "VERIFIED via temple_inertia").
  Extending the same pattern to the other routes would be speculative
  surface for a use case that hasn't been asked for yet — a new bead if a
  producer actually needs it.
- Did not change `certify_lambda_min`'s public behaviour or signature. The
  refactor is purely internal code sharing; I verified no numeric output
  changed by running the full suite (all of which passed, including tests
  that pin `certify_lambda_min`'s exact enclosure).

## What I could not verify

- I could not verify this against the real `QuantumKrylovSolver` output or
  the actual H2/sto-3g Hamiltonian from `certkit-jn1.1`, because none of
  that (the solver, the bridge, the molecular Hamiltonian) is present in
  this repository. The synthetic case matches the bead's own stated numbers
  (53% imaginary weight) and structure (real symmetric H, complex ground
  estimate, real/imaginary parts as distinct valid witnesses with distinct
  Rayleigh quotients) but is not the literal molecular case.
- I did not verify that `certify_lambda_min_from_witness` is the API shape
  an actual external bridge maintainer would want (e.g. whether it should
  also accept a caller-supplied `beta` instead of always re-deriving one via
  a full internal solve). I chose the minimal shape that solves the bug
  described and matches the existing `certify_*` calling convention; a real
  integration might reveal a better shape, which would be a bridge-side
  finding, not something I can discover from this repo alone.
- I did not attempt any Lean-side verification;
  `lean/Certkit/Soundness.lean` is unrelated to this bead and untouched.

## Final test-run line (verbatim)

```
$ uv run pytest tests -q
........................................................................ [ 56%]
.......................................................                  [100%]
127 passed in 10.35s
```

(121 pre-existing in this tree at session start — other beads' uncommitted
work, not mine — + 6 new in `tests/test_complex_witness_transcription.py`.
0 failures, 0 skips.)

No-dependency checker run (interpreter with numpy unimportable, confirmed
before running the checker; no system `python3` in this container, no `uv`,
no venv — used uv's already-downloaded managed interpreter directly with
site-packages stripped from `sys.path`, matching the pattern documented in
`certkit-487`'s handoff for the same container quirk):

```
$ /home/node/.local/share/uv/python/cpython-3.12.13-linux-aarch64-gnu/bin/python3.12 -S -c \
    "import sys; sys.path=[p for p in sys.path if 'site-packages' not in p]; import numpy"
Traceback (most recent call last):
  ...
ModuleNotFoundError: No module named 'numpy'

$ /home/node/.local/share/uv/python/cpython-3.12.13-linux-aarch64-gnu/bin/python3.12 -S -m certkit.cli check \
    examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

## Git state at handoff

Only `README.md` and `certkit/producer.py` (my changes) plus the new,
untracked `tests/test_complex_witness_transcription.py` are this bead's
work. `issues.jsonl` was re-exported (`bd export -o issues.jsonl`) and is
also modified. Everything else modified in the working tree
(`certkit/checker.py`, `certkit/interval.py`, `examples/banded_demo.py`,
`pyproject.toml`, `tests/test_backward.py`, `tests/test_banded.py`,
`uv.lock`, `tests/test_generalized.py`) is other beads' uncommitted work
(certkit-3ta, certkit-jn1.2, and others per their own handoffs) that
predates this session and that I did not touch.

Not committed, per this repo's git policy. Suggested commands, for whoever
reviews and decides how to split this from the other uncommitted work:

```bash
git status
git diff README.md              # this bead: "Writing a producer" addition
git diff certkit/producer.py    # this bead: certify_lambda_min_from_witness
                                 #   + _temple_inertia_bracket extraction
git add README.md certkit/producer.py \
        tests/test_complex_witness_transcription.py issues.jsonl
git commit -m "certkit-bz5: certify_lambda_min_from_witness for externally-supplied witnesses"
```

I did not run `git add`, `git commit`, or `git push`.

`bd close certkit-bz5` will be run after this file is written, with a
`--reason` summarizing the above (bug reproduced and confirmed
unexploitable; coverage gap that enabled it closed with a new producer
function; the acceptance criteria's `chem/certkit_bridge.py` branch remains
the responsibility of that external repo).
