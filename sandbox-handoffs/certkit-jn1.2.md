# certkit-jn1.2 — Support the generalized eigenproblem Ax = lambda S x

## Verdict

Closed. The implementation was already complete and sound on arrival, sitting
uncommitted in the working tree since a previous session claimed the bead on
2026-08-22 and never closed it. I reviewed it, ran independent adversarial
verification, added the missing documentation, confirmed the full suite is
green, and closed the bead.

## What's new (from the previous session, verified by me)

- `certkit/checker.py`: `_gershgorin_upper` (mirror of `_gershgorin_lower`,
  gives a sound matrix-free ceiling on a symmetric operator's spectrum) and
  `_rule_gen_gershgorin_rayleigh`, registered as rule name
  `gen_gershgorin_rayleigh` under claim kind `lambda_min_enclosure`.
- `certkit/producer.py`: `certify_lambda_min_generalized(A, S, *, slack=1e-9)`,
  an untrusted producer that reduces the pencil via numpy Cholesky to find a
  trial vector, then emits a certificate with a second reference field,
  `metric_ref`, alongside the usual `operator_ref`.
- `tests/test_generalized.py` (untracked, now reviewed and left as-is): exact
  oracle test on a diagonal pencil via `Fraction` (zero rounding error in the
  ground truth — required by the bead's acceptance criteria), a randomized
  dense-pencil test checked against an independently-computed numpy/Cholesky
  reduction (not `certify_lambda_min_generalized`'s own reduction — the thing
  under test, `gen_gershgorin_rayleigh` in checker.py, does no such
  reduction itself), the abstain-when-S-not-provably-PD case, the
  abstain-when-metric-operator-missing case, and the tampered-`metric_ref`
  case.

No verdict changed from ABSTAIN to VERIFIED on any *existing* input — this is
new surface area (a new claim kind's rule), not a change to an existing rule's
behavior. Command showing it working:

```
uv run pytest tests/test_generalized.py -v
```

## The derivation (why I believe this is sound, not just tested)

Full derivation is in the docstring of `_rule_gen_gershgorin_rayleigh` in
`certkit/checker.py`. Summary, since this is the load-bearing part of the
bead:

- **Upper bound.** For S symmetric, `T := S^-1 A` is self-adjoint with
  respect to the S-inner product `<u,v>_S = u^T S v`, and `Tv = lambda v` iff
  `A v = lambda S v`, so the ordinary Rayleigh-Ritz theorem applied in that
  inner product space gives, for any nonzero witness x:
  `lambda_min(A,S) <= (x'Ax)/(x'Sx)`. This is recomputed from the witness by
  the checker in outward-rounded interval arithmetic (`mu` in the code) —
  never taken from the producer.
- **Lower bound.** For any nonzero x, `x'Ax = a*||x||^2` and
  `x'Sx = s*||x||^2` for real numbers a, s each lying in their own operator's
  true spectrum range (the ordinary, un-generalized Rayleigh quotient
  theorem, which holds for *any* symmetric matrix, not just this pencil).
  `(x'Ax)/(x'Sx) = a/s` exactly — the `||x||^2` cancels — so this holds *for
  every nonzero x*, including the one that minimizes the generalized
  Rayleigh quotient, whose value is `lambda_min(A,S)` itself. a and s are
  each bounded matrix-free by the (already-proven-sound) Gershgorin discs on
  A and S respectively, so the *interval quotient* of the two
  Gershgorin-enclosed spectra is a sound, witness-free floor. Interval
  division here is standard interval arithmetic (four corners, min/max) —
  sound regardless of the sign of the numerator interval, as long as the
  denominator interval excludes zero, which is exactly what the
  positive-definiteness check below buys.
- **S positive-definiteness is proved, not assumed.** The rule only proceeds
  once `_gershgorin_lower(S).is_positive` — i.e. Gershgorin itself proves
  every eigenvalue of S is strictly positive. If S is positive definite but
  not diagonally dominant enough for Gershgorin to see it (the checked-in
  test uses a 1D-Laplacian-like tridiagonal `[[2,-1,0],[-1,2,-1],[0,-1,2]]`,
  whose true eigenvalues are all positive but whose Gershgorin lower bound is
  exactly 0), the rule abstains. This is correct abstain-not-degrade
  behavior, not a bug: I did not touch it.
- **S = I collapses this exactly to `gershgorin_rayleigh`**, since dividing
  by the degenerate interval `[1,1]` is a no-op — a sanity check I did by
  inspection, not a new test (the existing `gershgorin_rayleigh` tests
  already exercise `_gershgorin_lower`/`_gershgorin_upper`'s ungeneralized
  behavior; adding a redundant S=I test for the generalized rule seemed like
  test-count padding rather than new coverage, so I didn't add one).

No transcribed constants anywhere in this rule — every bound is Gershgorin
discs computed from the matrix in front of the checker, or the Rayleigh
quotient recomputed from the witness. `metric_ref` tampering is caught the
same mechanical way `operator_ref` tampering already was: it's a content
hash, and `ctx.operators.get(metric_ref)` returns `None` for any S that
doesn't hash-match.

## My own verification beyond what's checked in

I don't trust "the tests pass" alone for a soundness-critical rule, so I ran
two throwaway (uncommitted, not part of the test suite) adversarial fuzz
sweeps directly against `certkit.checker.check_bundle`, comparing every
VERIFIED enclosure against `scipy.linalg.eigh(a, s, eigvals_only=True)` as an
independent ground truth:

- 2000 random dense pencils, S built diagonally dominant (so Gershgorin
  *can* usually prove PD): 1836 verified, 164 abstained, **0 soundness
  violations**, worst-case margin between the true eigenvalue and the
  nearer enclosure endpoint was 1.2e-17.
- 2000 random dense pencils with S drawn unconstrained (symmetric,
  sometimes indefinite, sometimes near-singular — deliberately adversarial
  to the positive-definiteness gate): 51 verified, 1949 abstained, **0
  soundness violations**, and I additionally checked that every VERIFIED
  case in this sweep really did have a positive-definite S (`np.linalg.eigvalsh(s)`
  all > 1e-12) — i.e. the gate never let a non-PD S through.

I did not commit these scripts; they were sanity checks, not new tests. If a
reviewer wants them re-run, the commands are in my session log; I can
reproduce on request but didn't think a repo already at 121 tests needed two
more randomized ones layered on top of the six `seed in range(6)` cases
already in `test_verified_and_sound_against_numpy_reduction`.

## What I touched

Only `README.md`: added a "## The generalized eigenproblem" section (after
"## Two sound routes, one tradeoff") explaining the rule, the `metric_ref`
mechanism, and the derivation summary above, plus one line in that section's
rule table (`gen_gershgorin_rayleigh  the pencil A x = lambda S x; needs S
provably PD`). The feature had zero documentation before this. Nothing else.

## What I did not touch (found already in the shared working tree, out of
## scope for this bead)

The working tree had substantial uncommitted work from *other* in-progress
beads mixed into the same checkout when I started (this appears to be a
shared tree across concurrent fleet workers, not something this session
created):

- `certkit-8q0` (better producer-side eigensolver): `_tridiagonal_ground_state`
  in `producer.py`, the `_pad` → `pad_claim` rename/export, the README
  "Writing a producer" section and "Known limits" rewrite, `banded_demo.py`'s
  n=100000 row, and `test_ground_state_eigenvector_is_no_longer_the_binding_constraint`
  in `test_backward.py`.
- Complex interval arithmetic (`CIv`, `cdot`, `csqnorm`) added to
  `interval.py` — unused by `gen_gershgorin_rayleigh`, presumably staged for
  `certkit-3ta` (complex Hermitian operators) or `certkit-bz5` (real-time
  Krylov witness is complex).
- A `test_banded.py` change switching a ground-truth comparison from
  `numpy.linalg.eigvalsh` to an exact rational Sturm oracle
  (`exact_lambda_min`) — looks related to `certkit-8q0`'s width improvements
  making the certified interval competitive with LAPACK's own error.

I left all of this exactly as I found it. I did not verify its soundness,
did not run it down further, and am not reporting on its correctness one way
or the other — it belongs to whichever bead(s) it's for for someone else, or
a future me, to review and close on their own terms.

## What I could not verify

- I did not verify that the other in-progress work described above is itself
  sound or that it doesn't interact badly with something once committed —
  out of scope, not my call to make.
- I did not add a dedicated `metric_ref`-tamper-detection stress test beyond
  the one already in `test_generalized.py`
  (`test_tampered_metric_ref_is_caught`) — one case, exercising the same
  hash-lookup mechanism `operator_ref` already relies on, seemed sufficient;
  I did not invent a second variant.
- The two ad hoc fuzz sweeps above are real runs from this session (numbers
  are exact transcriptions of what printed), but they are not reproducible
  from a committed script — an honest limitation of "trust me" verification
  versus a checked-in test. Re-running them is cheap if a reviewer wants to.

## Final test-run line (verbatim)

```
$ uv run pytest tests -q
........................................................................ [ 59%]
.................................................                        [100%]
121 passed in 12.82s
```

No-dependency checker run (interpreter with numpy unimportable, no `uv`, no
venv):

```
$ /home/node/.local/share/uv/python/cpython-3.12-linux-aarch64-gnu/bin/python3.12 -m certkit.cli check examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

(That sample certificate exercises `temple_inertia`, not the new
`gen_gershgorin_rayleigh` rule specifically, but it proves the same
interpreter — with the new `_gershgorin_upper`/`_rule_gen_gershgorin_rayleigh`
code now present in `checker.py` — still imports and runs with zero
third-party dependencies, which is the property this check exists to catch a
regression in.)

## Git state at handoff

Not committed, per this repo's git policy — the tree is ready to commit but
contains other beads' uncommitted work alongside mine (see above). Suggested
commands, for whoever reviews and decides how to split this:

```
git status
git diff README.md                 # my change: this bead's documentation
git diff certkit/checker.py        # certkit-jn1.2: gen_gershgorin_rayleigh
git diff certkit/producer.py       # mixed: certify_lambda_min_generalized (jn1.2)
                                    #   + _tridiagonal_ground_state/pad_claim (certkit-8q0)
git add tests/test_generalized.py  # untracked, certkit-jn1.2's exact-oracle test
bd export -o issues.jsonl          # already run this session; re-run if beads change again before commit
```

I did not run `git add`, `git commit`, or `git push` — beyond scope and
against this repo's git policy without explicit instruction to commit
someone else's in-progress work bundled with mine.
