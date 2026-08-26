# Handoff: certkit-0vd — Emit certificates from the robot abstention layer

## Verdict

**Closed as not executable from this repository, and not executable as
specified by any future certkit-only session either.** This is a stronger
finding than "the file isn't here" (the situation `certkit-bz5` and
`certkit-487` hit for the chem bridge): even granting that the robot-side
code existed and were handed to a session here, the acceptance criteria as
written — "verified by an **unmodified** certkit checker" — cannot be
satisfied for what IBP/CROWN branch-and-bound certifiers actually produce,
because that class of bound is not the kind of claim this checker's rule set
understands. No code was changed. No certificate was fabricated. The 127-test
suite is exactly as I found it.

## What I checked before concluding this

1. **The external system is absent, not just uncommitted.** Unlike the
   working tree's other in-progress beads (which leave real diffs sitting
   uncommitted), there is no trace anywhere of "M0-M3," an "interval
   substrate," "IBP," "CROWN," "branch-and-bound," "discrepancy," or "robot"
   as a codebase:
   - `git log --all --oneline -- '**/M0*' '**/M1*' '**/M2*' '**/M3*' '**/ibp*' '**/crown*' '**/robot*' '**/abstention*'` → empty.
   - `find / -iname "*robot*" -o -iname "*abstention*" -o -iname "*ibp*" -o -iname "*crown*"` (excluding `/proc`, `/usr`, venvs) → nothing.
   - `bd search robot` / `bd search abstention` / `bd search IBP` / `bd search CROWN` / `bd search discrepancy` / `bd search cross-project` → only `certkit-0vd` itself matches, on the first two; the rest return nothing.
   - `bd memories robot` / `bd memories abstention` → nothing recorded from any
     prior session either.
   - The only text describing this system anywhere in the repo is
     `README.md`'s "Where this connects" section (one paragraph, added in the
     very first commit `ade3c5c` alongside the checker itself, sitting next
     to an equally aspirational "Math knowledge graph" bullet that has never
     spawned a bead). It is vision text about future integrations, not a
     pointer to a pre-existing artifact.

2. **Compared this to how `certkit-jn1.1` (this bead's one dependency) was
   actually closed.** That bead's close reason describes a real, self-
   contained numerical instance — an H2/sto-3g Hamiltonian, a Krylov energy
   bound, a bracket recomputed by an unmodified checker via `temple_inertia`
   — which is why it could succeed even though `chem/certkit_bridge.py`
   itself never persisted in this repo (`certkit-bz5`'s independent
   investigation confirmed that file was never committed here). Quantum
   chemistry's H2/sto-3g Hamiltonian is a small, standard, fully-specified
   numerical object; a session can honestly reconstruct it from public data
   and route a real Rayleigh-quotient bound through `lambda_min_enclosure`.

   I looked for an equivalent path here and could not find one. The
   checker's entire rule table (`RULES` in `checker.py`) is:
   `residual → spectrum_contains`, `temple_inertia`/`temple_ref`/
   `gershgorin_rayleigh`/`gen_gershgorin_rayleigh` → `lambda_min_enclosure`,
   `gershgorin` → `spectrum_lower_bound`, `rayleigh` → `lambda_min_upper_bound`,
   `inertia`/`sturm`/`sturm_be` → `eigenvalue_count_below`, `combine` →
   `lambda_min_enclosure`. Every single one requires an `operator_ref` to a
   linear operator and produces a claim about *that operator's spectrum*.
   There is no claim kind for "the range of a (possibly nonlinear) function
   over a box," which is what IBP (Interval Bound Propagation) and CROWN
   (linear/quadratic relaxation bounds for neural networks) actually certify,
   and what a branch-and-bound *discrepancy* (output-margin violation)
   certifier's per-subproblem ε would be.

3. **Considered, and rejected, forcing a fit.** There is a real, different
   line of certified-robustness work (Raghunathan, Steinhardt & Liang,
   "Certified Defenses against Adversarial Examples," ICLR 2018) that *does*
   reduce a robustness margin to the smallest eigenvalue of a matrix built
   from the network's weights and a perturbation budget — i.e. something
   `lambda_min_enclosure` could genuinely host. But that is an SDP-relaxation
   technique, not IBP/CROWN (which the bead names explicitly), and it isn't
   what a branch-and-bound-over-linear-relaxations verifier computes.
   Substituting it and calling the result "a certified epsilon from the
   robot abstention layer" would misdescribe what was actually tested —
   structurally the same move as widening a bound to make a case verify,
   just applied to the connector story instead of to arithmetic, and this
   repo's standard treats that as the one unacceptable move. I did not do
   it. I also did not invent M0-M3's semantics from nothing and build a
   "representative" IBP/CROWN implementation myself, the way I might have
   reconstructed H2/sto-3g: unlike a Hamiltonian, IBP/CROWN branch-and-bound
   has no single standard numeric instance whose ε is a known, citable
   ground truth I could hold the checker's answer against, and no existing
   claim kind to route it through even if I had one.

4. **Checked `certkit-jcb`'s framing for the analogous "cannot be done by
   you" pattern** named explicitly in this repo's standing context (a
   session cannot manufacture the second human reviewer `certkit-jcb` asks
   for). `certkit-0vd` is not identical to that shape, but it rhymes: the
   thing the bead needs (real M0-M3 code, or at minimum a written spec of
   what mathematical object ε is) is not something a certkit-only session
   can manufacture without guessing, and guessing here is exactly the
   failure mode the repo is built to refuse.

## What I did not touch

Nothing. `certkit/checker.py`, `certkit/schema.py`, `certkit/interval.py`,
`certkit/producer.py`, `README.md`, and every test file are unmodified by
this session. The working tree still carries the same uncommitted work from
other in-progress beads (`certkit-8q0`, `certkit-3ta`) that `certkit-jn1.2`'s
and `certkit-bz5`'s handoffs already catalogued — I did not review, verify,
or touch any of it; it is not this bead's concern.

## Bounds, tolerances, guards, or thresholds touched

None. I made zero code changes this session.

## Documented limits I was tempted to soften

None apply — this bead is about a claim-format connector, not about any of
the README's numeric limits (`DENSE_LIMIT`, the Gershgorin characterization,
the coverage-cliff numbers). I was tempted to write the close reason as "not
yet possible" (implying a future session could just try harder); I wrote it
instead as "not possible for an unmodified checker against IBP/CROWN-style
bounds specifically," because that is the actual mathematical shape of the
obstruction, not a matter of effort.

## What I decided not to do, and why

- Did not fabricate a synthetic "robot abstention layer" producer the way
  `certkit-bz5` fabricated a synthetic complex-witness case. `bz5`'s synthetic
  case was faithful because the bead text gave an exact, checkable bug (a
  specific Hamiltonian shape, a specific 53%-imaginary-weight number, a
  specific wrong witness field). `certkit-0vd`'s bead text gives no
  mathematical specifics at all — no operator, no claim kind, no numeric
  example — so anything I built would be my own invention presented as if it
  represented the named external system, which I'm not willing to do.
- Did not add a new claim kind to `checker.py` to accept a generic interval
  bound on an arbitrary function. That would violate the bead's own
  acceptance criteria ("unmodified certkit checker") and would be exactly
  the kind of speculative surface `certkit-487`'s handoff already declined
  to add for a better-specified case ("adding a claim kind nothing in this
  repo produces would be speculative surface, not a fix").
- Did not attempt the SDP-eigenvalue substitution described above, for the
  misdescription reason given in point 3.
- Did not touch `certkit-3ta` (complex Hermitian support) or `certkit-8q0`
  (producer eigensolver improvements) — their uncommitted work sits in the
  tree from earlier sessions, unrelated to this bead, not mine to review.

## What I could not verify

- I could not verify that "M0-M3," "IBP/CROWN bounds," or a "branch-and-bound
  discrepancy certifier" mean anything more specific than the one README
  paragraph describing them, because no other artifact describing them
  exists anywhere I have access to (this container, this repo, this repo's
  full git history, or the beads database).
- I could not verify whether a real robot-side ε, if it were ever handed to
  a certkit session, would in fact reduce to one of the checker's existing
  eigenvalue claim kinds — that depends on facts about the external system I
  don't have.

## Final test-run line (verbatim)

```
$ uv sync --extra dev
Resolved 20 packages ... Installed 8 packages in 237ms

$ uv run pytest tests -q
........................................................................ [ 56%]
.......................................................                  [100%]
127 passed in 10.45s
```

(Same 127 as `certkit-bz5`'s handoff reported at the start of this session —
121 from before that bead plus its 6 new tests. I added zero.)

No-dependency checker run (uv-managed interpreter, `sys.path` stripped of
site-packages, numpy confirmed unimportable first):

```
$ /home/node/.local/share/uv/python/cpython-3.12.13-linux-aarch64-gnu/bin/python3.12 -S -c \
    "import sys; sys.path=[p for p in sys.path if 'site-packages' not in p]; import numpy"
ModuleNotFoundError: No module named 'numpy'

$ /home/node/.local/share/uv/python/cpython-3.12.13-linux-aarch64-gnu/bin/python3.12 -S -m certkit.cli check \
    examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

## Git state at handoff

No changes. `git status` is identical to what this session found at start:
the same other-beads' uncommitted work (`certkit/checker.py`,
`certkit/interval.py`, `certkit/producer.py`, `examples/banded_demo.py`,
`pyproject.toml`, `tests/test_backward.py`, `tests/test_banded.py`,
`uv.lock`, untracked `tests/test_complex_witness_transcription.py` and
`tests/test_generalized.py`), plus `README.md`/`issues.jsonl` from
`certkit-bz5`'s just-completed session. I did not run `git add`, `git
commit`, or `git push`, and there is nothing of mine to stage.

```bash
git status   # unchanged from session start; nothing from this bead to add
```

`bd export -o issues.jsonl` was run after closing this bead (see below) so
the close reason survives in the git-tracked export.
