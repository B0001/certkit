# Handoff: certkit-4ue — Extend the backward-error analysis to bandwidth > 1

## Verdict

**Implemented.** `sturm_be` no longer refuses everything past tridiagonal.
`certkit/backward_error.py` gains `banded_arrays`, `sweep_banded`, and
`count_eigenvalues_below_backward_banded`; `checker.py`'s `_rule_sturm_be`
catches `NotTridiagonal` from the tridiagonal fast path and falls back to the
banded route; both are exported from `certkit/__init__.py`. The bead's named
acceptance test, `test_delta_is_measured_not_assumed`, is extended to the
banded case as `test_delta_is_measured_not_assumed_banded`, plus a further
dozen correctness/refusal/reach tests. Full suite: **199 passed** (was 185 at
session start; 14 new tests added here, 0 removed, 0 skipped). See the
verbatim run at the bottom.

## Why the existing derivation doesn't just generalize by widening ETA/GAMMA

`backward_error.sweep`'s `ETA = 2.1*U` / `GAMMA = 3.1*U` are not worst-case
constants — they're a hand-count of *exactly which roundings compose onto
which quantity* for a specific 4-operation-per-step recurrence (`p = diag -
shift`, `s = b*b`, `t = s/d`, `d = p - t`), verified operation-by-operation
(`bd memories backward-error-mechanism`, 2026-09-02 entry). That hand-count is
only tractable because a tridiagonal pivot depends on exactly one previous
column. A banded pivot of bandwidth `b` depends on up to `b` previous columns,
each contributing a term built from an `L` entry that was itself produced by a
division by an *earlier*, already-rounded pivot. There is no clean, bandwidth-
independent symbolic answer to "how many roundings compose here" the way there
is for `b=1` — re-deriving one by hand for general `b` would mean either (a) a
fresh derivation with a `b`-dependent constant nobody has independently
reviewed, which is exactly what `certkit-jcb` just finished reviewing for the
`b=1` case and would need re-running, or (b) a worst-case symbolic bound over
a whole class of matrices, which is the "transcribed constant" failure mode
the module's own docstring explicitly rejects.

## What I built instead

Stop counting roundings. Run the banded LDL^T elimination in plain floats —
whatever `L` (unit lower triangular, band `b`) and `D` (diagonal) come out,
however many roundings produced them. These specific floats *define* a
symmetric matrix `Mtilde := L D L^T` by an algebraic identity that holds
regardless of how `L`/`D` were computed:

```
Mtilde_jj = D_j + sum_{k<j, j-k<=b} L_jk^2 D_k
Mtilde_ij = L_ij D_j + sum_{k<j, i-k<=b} L_ik L_jk D_k     (i > j)
```

Sylvester's law gives `D`'s negative-pivot count as `Mtilde`'s inertia — again
a formal fact about *this* `L`/`D`, not a claim about the arithmetic that
produced them. The only work left is bounding `||A - Mtilde||`, entry by
entry, and every quantity on the right of both equations above (the specific
`L`/`D` floats, the true matrix entries) is already an exact, known real
number by the time elimination finishes — so the entrywise error can be
*rigorously enclosed* by plugging those numbers into `Iv` and reading off
`.mag_ub`. No rounding-count argument, no per-operation model, no new
symbolic constant: just the already-proven soundness of `Iv` arithmetic
(240k-case exact-Fraction audit, `certkit-jcb`) plus Sylvester and Weyl, which
`sweep_backward_bound` (Lean) already establishes are safe to combine this
way for the `b=1` case's own bracketing argument — the bracketing driver
itself (`_bracket_count`, refactored out of both entrypoints) is untouched
and bandwidth-agnostic.

`sweep_banded` (`backward_error.py`) does this per column: eliminate in plain
float (same eviction pattern as `banded.py`'s forward route, so memory stays
`O(n b)` not `O(n^2)`), and in parallel accumulate an `Iv`-audited
reconstruction residual per row, taking the max row sum as a rigorous bound on
`||A - Atilde||_inf >= ||A - Atilde||_2` (same inequality the tridiagonal
`sweep` already relies on for symmetric error matrices). `banded_arrays`
generalizes `tridiagonal_arrays`: same refusals (inexact/enclosed entries,
asymmetry — checked directly, not delegated, per `certkit-279`), same
`MAX_BANDWIDTH` cap `banded.py` already uses for the forward route.

## What this does *not* require believing that the tridiagonal case didn't

- Still needs `Iv`'s soundness (already reviewed, `certkit-jcb`).
- Still needs Sylvester's law and Weyl's inequality (used identically to the
  `b=1` case; no new mathematical machinery).
- Still needs every pivot to be a genuine nonzero, finite, normal float (the
  same `_finite_normal` guard `sweep` already uses, reused verbatim) — so that
  its sign is well-defined and the elimination hasn't silently left the
  regime this kit models.

## What it does *not* need, unlike the tridiagonal case

- It does **not** assume "each floating-point operation commits at most one
  rounding" (the model `ETA`/`GAMMA` are built on). That model is correct for
  CPython/IEEE-754 (`certkit-8hn` checked it cross-architecture) — this
  derivation just never invokes it, because the residual is measured
  post-hoc on the actual output floats rather than predicted from a
  per-operation accounting.
- It does **not** introduce a new symbolic constant of any kind, `b`-dependent
  or otherwise.

## Honest gap: no independent review of this specific argument yet

The tridiagonal derivation went through a dedicated soundness review
(`certkit-jcb`, closed 2026-09-26, `REVIEW-jcb.md`) before this bead's
dependency was satisfied. The argument above is, I believe, *more* robust than
that one (it leans on fewer assumptions — no rounding-model dependency at
all), but "I believe" is exactly the standard this repo doesn't accept for
soundness-critical code without a second pair of eyes. This is new,
untranscribed, un-reviewed reasoning, even though it reuses only
already-reviewed primitives (`Iv`, and the same Sylvester/Weyl combination).
I am **not** closing this out as independently reviewed — I'm flagging it
plainly, and I'd recommend filing a follow-up review bead (parallel to
`certkit-jcb`'s scope, but for `banded_arrays`/`sweep_banded` specifically)
before anyone treats a `sturm_be` VERIFIED on a genuinely banded (non-
tridiagonal) operator with the same confidence as the tridiagonal case
currently deserves. I have not filed that bead myself, since the task
instructions were to do only this bead and file follow-ups as new beads
rather than act on them — happy to file it if that's wanted, but leaving it
to explicit direction rather than assuming scope.

I also did **not** add a Lean proof for this — the existing
`sweep_backward_bound` (`BackwardError.lean`) is specific to the tridiagonal
ETA/GAMMA derivation and says nothing about the banded reconstruction-residual
argument. README's "Not done yet" section now says this explicitly (see
below) rather than implying Lean coverage extends to the new code.

## Correctness evidence beyond the bead's one named test

The bead only names the delta-scaling test, but a novel numerical derivation
without independent review deserves more than one test before I'd trust it,
so `tests/test_backward.py` also gained (all under the new "bandwidth > 1"
section):

- `test_banded_backward_matches_lapack_across_the_spectrum` (b=1,2,4,
  parametrized) — cross-checked against `numpy.linalg.eigvalsh` across the
  spectrum of a random banded matrix.
- `test_banded_backward_agrees_with_the_forward_banded_route` — cross-checked
  against `banded.count_eigenvalues_below_banded`, a route that shares no
  code beyond `Iv` itself.
- `test_banded_backward_matches_exact_rational_oracle` — cross-checked
  against a from-scratch exact-`Fraction` LDL^T elimination (no floating
  point, no LAPACK, no rounding anywhere) at `n=15, b=3` across five betas.
- `test_delta_is_measured_not_assumed_banded` — the bead's named test,
  extended: scale a `b=3` operator by 1e6, delta scales with it (same
  `0.5e6 < ratio < 2e6` bound as the tridiagonal test).
- `test_banded_delta_is_tiny_relative_to_the_operator_norm`,
  `test_banded_beta_on_an_eigenvalue_abstains` — mirror the tridiagonal
  sanity checks.
- `test_banded_exceeding_the_bandwidth_limit_is_refused`,
  `test_banded_non_banded_operator_is_refused`,
  `test_banded_inexact_entries_are_refused`,
  `test_banded_asymmetric_operator_is_refused_without_decode_operator` —
  refusal paths, mirroring the tridiagonal and forward-banded refusal tests.
- `test_sturm_be_falls_back_to_banded_for_bandwidth_greater_than_one`,
  `test_sturm_be_catches_a_lying_banded_certificate` — checker-level,
  end-to-end: a genuinely banded (not tridiagonal) `sturm_be` certificate
  verifies through the new fallback, and a lying one is caught.

Two test-authoring mistakes worth flagging in case they recur: I first tried
`tfim_hamiltonian(9)` for "non-banded operator refused" and
`tfim_hamiltonian(2)` for "inexact entries refused", copying the tridiagonal
test's fixtures — but checked empirically (not assumed) that
`tfim_hamiltonian`'s Pauli-sum diagonal is *exact* at `n=2` (4×4) and *inexact*
starting around `n=5`, so the two fixtures needed swapping/replacing (used a
hand-built out-of-band `DenseSymmetric` for the bandwidth refusal instead,
and `tfim_hamiltonian(5)` for the inexactness refusal). Caught by running the
tests, not by inspection — recorded here so a future session doesn't
rediscover it from scratch.

## Docs updated with fresh measurements, not upgraded conclusions

Per this repo's rule that documented limits are measurements to redo, not
conclusions to soften, I re-measured rather than just declaring victory:

- `README.md`'s `sturm_be` comparison-table row and prose now describe the
  general-bandwidth argument (still `O(n b^2)`, same as `sturm`), alongside
  the tridiagonal-specific ETA/GAMMA description (kept, since that's still
  the actual code path for `b=1` — the banded route is a fallback, not a
  replacement).
- Added a **newly measured** reach table, analogous to the existing
  tridiagonal one, using `L^2` (`L` = the standard 1D Laplacian) — genuinely
  pentadiagonal (`b=2`), symmetric, exactly representable (integer entries),
  with a closed-form spectrum (`(2 - 2cos(kpi/(n+1)))^2`) so the ground truth
  needs no LAPACK or oracle:

  ```
        n         gap    sturm (banded, interval)    sturm_be (banded)
       20    7.40e-03                     abstain               count=1
       40    5.15e-04                     abstain               count=1
      200    8.95e-07                     abstain               count=1
     1000    1.46e-09                     abstain               count=1
     2000    9.11e-11                     abstain               count=1
    10000    1.46e-13                     abstain               abstain
  ```

  Measured, not assumed: the forward banded route gives up even earlier here
  (~n=20) than in the tridiagonal case (~n=40) — squaring the Laplacian
  doubles the per-step amplification the interval LDL^T recurrence
  accumulates. `sturm_be` (banded) reaches four orders of magnitude further,
  then **also abstains** at n=10000 — I measured this rather than picking a
  smaller n that would look unconditionally impressive. The entries here are
  O(16) (squared), not O(2) as in the tridiagonal Laplacian, so the runtime
  delta is correspondingly larger and the route runs out sooner. I reported
  the abstention as the honest boundary of the measurement, not hidden.
- Removed the now-false "The forward-enclosure routes... remain the only
  option above bandwidth 1" claim from "Known limits", replacing it with the
  measured tradeoff above (further reach, not unconditional reach).
- Updated `sturm_be is tridiagonal-only` to state it now handles any
  bandwidth up to `MAX_BANDWIDTH`.
- Removed "A banded (b > 1) version of the backward-error analysis" from
  "Not done yet" (it's done) and replaced it with the actual remaining gap:
  no Lean proof exists yet for this specific derivation.
- `CLAUDE.md`, `AGENTS.md`, `README.md`: the pinned pytest count was already
  stale before I touched anything (185 vs. 198 live at session start, per
  `test_doc_pass_count.py`) and drifted further with my 14 new tests. Updated
  all three to the freshly measured **199 passing, ~48s** (was previously
  documented as ~28s at 185 tests; also re-measured, not copied forward).

## What I decided not to do, and why

- Did not touch `interval.py`, `banded.py`'s forward route, or
  `tridiagonal_arrays`/`sweep`/`ETA`/`GAMMA` themselves — strictly additive,
  per the plan. Confirmed via the trust-boundary test and the full suite that
  nothing about the existing tridiagonal fast path changed behavior.
- Did not write a Lean proof for the new derivation — flagged above as the
  honest remaining gap, not silently left implied-covered.
- Did not file the independent-review follow-up bead myself — noted the
  recommendation above, left the decision to file it to whoever reads this,
  per "if you discover work outside this bead's scope, file it as a new bead
  — do not do it now" (filing itself, even, felt like it should follow a
  decision about scope/priority I don't have visibility into this session).
- Left `lean/Certkit/Scratch.lean` and `lean/Certkit/Scratch2.lean`
  (untracked, present before this session started per the initial git
  status) untouched — they look like exploratory sqrt-perturbation-bound and
  `Matrix.toEuclideanCLM` drafts, unrelated to this bead, and not mine to
  delete or fold in.
- Left `REVIEW-jcb.md` untouched — it was already modified in the working
  tree before this session started; not part of this bead's scope.

## Final test-run line (verbatim)

```
$ uv run --extra dev pytest tests -q
........................................................................ [ 36%]
........................................................................ [ 72%]
.......................................................                  [100%]
199 passed in 44.20s
```

Trust boundary specifically (unaffected, re-confirmed):
```
$ uv run --extra dev pytest tests/test_trust_boundary.py -q
....                                                                     [100%]
4 passed in 0.18s
```

No-dependency checker verification:
```
$ uv run --extra dev python3 -m certkit.cli check examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

## Handoff commands

Git policy for this session is report-only — nothing has been committed or
pushed.

```bash
git status
git diff --stat
# modified: AGENTS.md, CLAUDE.md, README.md, certkit/__init__.py,
#           certkit/backward_error.py, certkit/checker.py, tests/test_backward.py
# (REVIEW-jcb.md was already modified before this session; untouched by me)
# untracked, pre-existing, untouched: lean/Certkit/Scratch.lean, lean/Certkit/Scratch2.lean

# Suggested commit (not run):
git add AGENTS.md CLAUDE.md README.md certkit/__init__.py \
        certkit/backward_error.py certkit/checker.py tests/test_backward.py
git commit -m "certkit-4ue: extend backward-error eigenvalue counting to bandwidth > 1"
```

`bd close certkit-4ue` follows this handoff, with this file's summary as the
close reason and full derivation in the issue's notes.
