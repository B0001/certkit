# certkit-8y2.3 — Prove the spectral theorems: Rayleigh-Ritz, Temple, Sylvester, Gershgorin, Weyl

Status: **left open** (in_progress), same as the prior session left it. This
session did not add a new proof. It independently re-verified the prior
session's `temple_lower` proof from scratch (did not trust the handoff's
description), did additional research on `weyl_shift` beyond re-running the
prior grep, and recorded that research in the theorem's doc comment. The
count stays 4 of 5 named theorems proved (zero `sorry`). Acceptance criteria
("all five proved") is not met, so the bead is not closed.

This is a continuation of a session that started 2026-08-13, has run several
times before (see the bead's own notes history via `bd show certkit-8y2.3`),
and most recently proved `temple_lower` earlier the same day (2026-08-31)
this session ran. That prior work is described in detail further down (kept
for record) — this section covers only what *this* session did on top of it.

## What this session did

1. **Re-verified the tree, not the handoff.** The instructions for this
   session are explicit that a prior worker's notes are not to be trusted at
   face value. Ran `lake build Certkit` (8804 jobs) and
   `lake env lean Certkit/Soundness.lean` from a clean state before touching
   anything. Confirmed independently: builds clean, exactly 2 `sorry`
   warnings (`residual_encloses_some_eigenvalue` at what was line 201,
   out of this bead's 5-theorem scope per long-standing notes on the bead;
   `weyl_shift`, then at line 401). `temple_lower` genuinely has zero
   `sorry` — the prior session's claim holds up.

2. **Did new research on `weyl_shift`**, going past the keyword grep the
   prior two sessions ran (`grep -rl weyl|courant|minimax`, which found
   nothing and is reconfirmed here too). This time: read the actual
   definition site. `Matrix.IsHermitian.eigenvalues₀` (what `eigenvalues`
   is built from) is defined via
   `LinearMap.IsSymmetric.eigenvalues` in
   `Mathlib.Analysis.InnerProductSpace.Spectrum`. That file has only
   *extreme*-eigenvalue variational facts —
   `hasEigenvalue_iSup_of_finiteDimensional`,
   `hasEigenvalue_iInf_of_finiteDimensional` — and no indexed
   Courant-Fischer statement for a general `eigenvalues i`.
   `Mathlib.Analysis.InnerProductSpace.Rayleigh` likewise has only
   `norm_eq_iSup_rayleighQuotient` (operator norm as a sup over *all*
   vectors), nothing about a single indexed eigenvalue.

3. **Checked for a shortcut and ruled it out.** The standard alternate route
   to Weyl's inequality avoids Courant-Fischer directly: prove Loewner-order
   monotonicity (`A ⪯ B → ∀ k, eigenvalues₀ A k ≤ eigenvalues₀ B k`), which
   composed with the easy fact that `‖A-B‖•1 - (A-B)` is `PosSemidef` (an
   elementary Cauchy-Schwarz argument) would give `weyl_shift` in a few
   lines. Checked whether mathlib has *that* instead —
   `Mathlib.Analysis.Matrix.Order` has only generic `PosSemidef`
   order-instance facts (transitivity, closedness, the star-ordered-ring
   instance), nothing that touches an eigenvalue index. The monotonicity
   claim itself *is* Weyl's monotonicity theorem — normally proved via
   Courant-Fischer or Cauchy interlacing — so this route needs exactly the
   same missing content, not less.

4. **Recorded the finding in the theorem's doc comment** (the only code
   change this session made to `Soundness.lean`) so a future session doesn't
   have to re-derive that the shortcut doesn't exist. Rebuilt after the edit
   to confirm it is comment-only: same 2 `sorry` count, all other theorem
   statements and proof terms byte-for-byte unchanged.

No proof code changed. No bound, tolerance, hypothesis, or threshold was
touched anywhere in the file. This session's only diff to `Soundness.lean`
is the `weyl_shift` doc comment.

## Why `weyl_shift` stays `sorry`

Third independent assessment (three separate sessions, now including one
that read the definition site rather than only keyword-searching) reaching
the same conclusion: proving `weyl_shift` requires formalising
Courant-Fischer's min-max characterisation or Cauchy eigenvalue interlacing
from primitives mathlib does not have. That is a genuine, self-contained
research/formalisation project — plausibly the hardest single piece of
Lean work named anywhere in this repo's Lean scope — not a lemma reachable
inside one session's budget. Per this repo's standard (an honest, documented
`sorry` beats a rushed or partial proof), it stays `sorry`.

## Why this bead stays open

Acceptance criteria: "All five proved, with the Python rule that consumes
each named in a comment." Four are proved; `weyl_shift` is not, and closing
this bead would misrepresent that. Left `in_progress`. Given three sessions
have now reached the identical conclusion on `weyl_shift` specifically, a
human may want to consider whether `weyl_shift` deserves its own dedicated,
appropriately-scoped research bead separate from `8y2.3`'s "mathlib
plumbing" framing (its own description says the work is expected to be
"standard mathematics... rather than discovery" — that description does not
hold for this one theorem, as now-triply confirmed). Did not create that
bead myself: it would still be work on the same theorem this bead already
names, not work outside `8y2.3`'s scope, so splitting it is a judgment call
for whoever reads this, not something to do unilaterally mid-session.

## What's proved now (zero `sorry`), unchanged this session

Confirmed by both `lake env lean Certkit/Soundness.lean` (single file,
~22s against the pinned mathlib) and a full `lake build Certkit` (8804
jobs):

- `rayleigh_ritz_min`
- `gershgorin_lower`
- `inertia_count_below` (Sylvester)
- `temple_lower`

## `temple_lower`: how it was proved (prior session, re-verified this one)

The prior session had already: (a) diagnosed and gotten fixed (via
`certkit-8y2.5`, closed) the bug that made the statement false as originally
written — `residualNorm` used to resolve to the sup norm via the ambient
`Norm (n → ℝ)` instance, and now uses an explicit Euclidean norm
(`Real.sqrt (r ⬝ᵥ r)`); and (b) proved the positive-semidefiniteness half of
the classical argument as a standalone lemma, `posSemidef_shift_mul_shift`.
The remaining dot-product algebra step connecting that PSD fact to the
stated scalar bound was completed earlier the same day (2026-08-31), before
this session started.

Derivation (also written into `temple_lower`'s doc comment in the file, so
it doesn't need to be reverse-engineered from the proof term):

Let `c := ⨅ j, eigenvalues j`, `μ := rayleigh A x`, `s := x ⬝ᵥ x > 0`,
`r := A *ᵥ x - μ • x` (the residual vector), `q := (A *ᵥ x) ⬝ᵥ (A *ᵥ x)`.

1. **`hcase`**: for every eigenvalue `λ_i`, `0 ≤ (λ_i - β)(λ_i - c)`. Two
   cases on `λ_i` vs `β`: if `λ_i < β`, `hgap` forces `λ_i = c`, making the
   product `(c - β) * 0 = 0`; otherwise `λ_i ≥ β ≥ c` (the second inequality
   from `c` being the infimum), so both factors are nonnegative.
2. Feed `hcase` to `posSemidef_shift_mul_shift` to get
   `((A - β•1) * (A - c•1)).PosSemidef`, then to `.dotProduct_mulVec_nonneg`
   to get `0 ≤ x ⬝ᵥ (((A - β•1) * (A - c•1)) *ᵥ x)` (`hnn`).
3. **`hexpand`**: expand that bilinear form via `simp only` on standard
   mulVec/dotProduct distributivity lemmas, reducing everything to sums of
   `x ⬝ᵥ (A *ᵥ (A *ᵥ x))`, `x ⬝ᵥ (A *ᵥ x)`, `x ⬝ᵥ x`. The one non-mechanical
   step: folding `x ⬝ᵥ (A *ᵥ (A *ᵥ x))` into `q = (A *ᵥ x) ⬝ᵥ (A *ᵥ x)` needs
   `A` symmetric, via `hAsymm : Aᵀ = A` fed into mathlib's
   `dotProduct_transpose_mulVec`. Result:
   `hexpand : x ⬝ᵥ (((A-β•1)*(A-c•1)) *ᵥ x) = q - (c+β)*(μ*s) + β*c*s`.
4. **`hrr`**: expand `r ⬝ᵥ r` the same way to `q - μ^2 * s`.
5. **`hresidualNorm_sq`**: `(residualNorm A x)^2 = (r ⬝ᵥ r)/s`, via
   `Real.sq_sqrt` on numerator and denominator, then `rw [hrr]`.
6. Combine: `hnn` rewritten via `hexpand` says
   `0 ≤ q - (c+β)*(μ*s) + β*c*s`, algebraically (`nlinarith`) equivalent to
   `s*(μ-c)*(β-μ) ≤ q - μ^2*s = r ⬝ᵥ r`. Dividing by `s > 0` then by
   `β - μ > 0` (from `hμβ`) gives `μ - c ≤ (residualNorm A x)^2 / (β - μ)`,
   which `linarith` rearranges into the goal.

No new axioms. No transcribed constants. Nothing widened or weakened:
`hμβ` and `hgap` are used exactly as the theorem states them, and the goal
inequality is the one originally stated.

## `weyl_shift`: still `sorry` — see "What this session did" above for the
new research this session added on top of the prior finding.

## Verdict changes

None. This bead is pure Lean formalization work against
`lean/Certkit/Soundness.lean`. It does not touch `certkit/checker.py`,
`certkit/backward_error.py`, or any other file the Python `check()` result
depends on. No VERIFIED/ABSTAIN decision the checker makes changes as a
result of this session.

## What I decided not to do, and why

- **Did not attempt `weyl_shift`.** See above. It is real, unbounded
  research work — formalising Courant-Fischer or Cauchy interlacing from
  scratch — not a short lemma, and three independent sessions (including
  this one, which read the definition site rather than trusting a keyword
  grep) now agree on that assessment.
- **Did not touch `residual_encloses_some_eigenvalue`.** Explicitly out of
  scope per this bead's own long-standing notes (not one of the five named
  theorems).
- **Did not re-derive or "clean up" `temple_lower`'s proof, or the private
  helper lemmas.** They compile clean and are load-bearing; re-verifying by
  rebuilding was enough — rewriting working proof code without a reason is
  risk for no benefit.
- **Did not create a separate bead for `weyl_shift`.** It's judgment call
  territory (see "Why this bead stays open" above), not something to do
  unilaterally when the task was "do only this bead."
- **Did not touch the unrelated modified files already sitting in the
  working tree** (`README.md`, `certkit/operators.py`,
  `examples/banded_demo.py`, `sandbox-prompt.md`, `sandbox-handoffs/certkit-l7r*`,
  `sandbox-handoffs/certkit-wew.md`) — these predate this session (other
  beads' in-progress work in this same shared sandbox checkout) and are out
  of this bead's scope.

## What I could not verify

- Whether a shorter or more idiomatic proof of `temple_lower` exists in
  mathlib style. Not needed for soundness; flagged for any later cleanup
  pass.
- Whether `weyl_shift` might be reachable via some indirect mathlib route
  not covered by the two files I read in depth this session plus the
  repo-wide keyword grep — I read the two files closest to the relevant
  definitions, not mathlib's entire analysis library. A specialist in
  mathlib's operator theory might know a name I didn't try.

## Final test-run line, verbatim

```
$ uv sync --extra dev
Installed 8 packages in 218ms
 + certkit==0.1.0 (from file:///workspace)
 + iniconfig==2.3.0
 + numpy==2.5.2
 + packaging==26.3
 + pluggy==1.6.0
 + pygments==2.21.0
 + pytest==9.1.1
 + scipy==1.18.1

$ uv run pytest tests
platform linux -- Python 3.12.13, pytest-9.1.1, pluggy-1.6.0
rootdir: /workspace
configfile: pyproject.toml
collected 165 items

tests/test_backends.py ..............                                    [  8%]
tests/test_backward.py ....................                              [ 20%]
tests/test_banded.py ...............                                     [ 29%]
tests/test_complex_hermitian.py .................                        [ 40%]
tests/test_complex_witness_transcription.py ......                       [ 43%]
tests/test_composition.py ....................                           [ 55%]
tests/test_end_to_end.py ............                                    [ 63%]
tests/test_exact_oracle.py ...........                                   [ 69%]
tests/test_generalized.py ..........                                     [ 75%]
tests/test_interval.py ..................                                [ 86%]
tests/test_sector_scope.py ....                                          [ 89%]
tests/test_tamper.py ..............                                      [ 97%]
tests/test_trust_boundary.py ....                                        [100%]

============================= 165 passed in 22.91s =============================
```

Unchanged from baseline — expected, since this session touched only a doc
comment in `lean/Certkit/Soundness.lean`.

## No-dependency checker

This container has no bare `python3`/`python` binary (confirmed again this
session via `which` and a filesystem search). The uv-managed base
interpreter (not the project venv, which has numpy via `--extra dev`) is
the right stand-in — confirmed `import numpy` fails on it, then ran the
checker:

```
$ /home/node/.local/share/uv/python/cpython-3.12.13-linux-aarch64-gnu/bin/python3.12 -c "import numpy"
ModuleNotFoundError: No module named 'numpy'

$ /home/node/.local/share/uv/python/cpython-3.12.13-linux-aarch64-gnu/bin/python3.12 \
    -m certkit.cli check examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

Same result the trust-boundary test itself exercises
(`tests/test_trust_boundary.py::test_checker_runs_in_a_process_where_numpy_is_unimportable`,
passing as part of the 165 above).

## Lean build, verbatim

```
$ lake build Certkit
⚠ [8802/8804] Replayed Certkit.Soundness
warning: Certkit/Soundness.lean:201:8: declaration uses `sorry`   (residual_encloses_some_eigenvalue)
warning: Certkit/Soundness.lean:304:5: Variable name `hd` is not explicitly referenced.
warning: Certkit/Soundness.lean:414:8: declaration uses `sorry`   (weyl_shift, line moved by this
                                                                    session's doc-comment growth)
Build completed successfully (8804 jobs).
```

Two `sorry` warnings, same as at session start. The `hd` warning is
pre-existing (from an earlier session's `inertia_count_below` proof,
unrelated to any work this session did) and benign — `hd : ∀ i, d i ≠ 0` is
part of the theorem's public signature (matches the Python-correspondence
comment), unused in the proof body. Not touched.

## Files changed

- `lean/Certkit/Soundness.lean`: only `weyl_shift`'s doc comment, expanded
  with this session's research (see "What this session did" above). No
  theorem statement, hypothesis, proof term, or other doc comment touched.
- `issues.jsonl` — re-exported via `bd export -o issues.jsonl` to capture
  this session's bead notes update on `certkit-8y2.3`.

Other modified/untracked files visible in `git status`
(`README.md`, `certkit/operators.py`, `examples/banded_demo.py`,
`sandbox-prompt.md`, `sandbox-handoffs/certkit-l7r*`,
`sandbox-handoffs/certkit-wew.md`) are **not from this session** — they
predate it (other beads' work in this same shared sandbox checkout) and
were left untouched.

## Suggested commands for a human to run

```bash
cd /workspace
git status
git diff lean/Certkit/Soundness.lean   # confirm: doc-comment-only diff
git add lean/Certkit/Soundness.lean issues.jsonl
git status   # confirm only the two files above are staged, and that the
             # other-bead files (README.md, certkit/operators.py,
             # examples/banded_demo.py, sandbox-prompt.md, the l7r/wew
             # handoffs) are NOT included, since they're unrelated
             # in-progress work from other sessions in this sandbox
git commit -m "certkit-8y2.3: record weyl_shift research (doc comment only, no proof progress)"
```

I did not run any of the above — no commit, push, or `bd dolt push` this
session, per the conservative git policy in `CLAUDE.md`.
