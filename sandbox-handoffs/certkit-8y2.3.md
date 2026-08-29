# certkit-8y2.3 — Prove the spectral theorems: Rayleigh-Ritz, Temple, Sylvester, Gershgorin, Weyl

Status: **left open**. 3 of the 5 named theorems are proved (zero `sorry`);
2 are not, and the acceptance criteria ("all five proved") is not met. Not
closing — see "Why this bead stays open" below for why that is the honest
outcome rather than a failure to finish.

## Verdict changes

None. This bead is pure Lean formalization work against
`lean/Certkit/Soundness.lean`; it does not touch `certkit/checker.py` or any
other file the Python `check()` result depends on. No VERIFIED/ABSTAIN
decision the checker makes changes as a result of this session.

## What's proved now (zero `sorry`, confirmed by both `lake env lean` on the
file alone and a full `lake build Certkit`)

- **`rayleigh_ritz_min`** — already proved before this session, reconfirmed
  with no regression.
- **`gershgorin_lower`** — already proved before this session, reconfirmed
  with no regression.
- **`inertia_count_below`** (Sylvester's law of inertia count) — proved this
  session. Derivation: an LDLᵀ factorization of `A - β•1` and the
  eigendecomposition of `A - β•1` are two different congruences of the same
  quadratic form, so by Sylvester's law they have the same negative-index
  count. Formalized via mathlib's `QuadraticMap.Equivalent` /
  `QuadraticForm.sigNeg_of_equiv_weightedSumSquares` machinery. Two new
  `private` helper lemmas carry the weight:
  - `sub_smul_one_eq_mul_diagonal_mul_transpose` — the spectral shift
    identity `A - c•1 = U * diag(λ - c) * Uᵀ` (transpose form, to match the
    LDLᵀ hypothesis's shape; the file already had this identity in `star`
    form inside `posSemidef_sub_smul_one_iff`, needed here as its own
    standalone `transpose`-form lemma).
  - `equivalent_weightedSumSquares_of_eq_mul_diagonal_mul_transpose` — the
    general congruence fact: if `M = L * diag(d) * Lᵀ` with `L` invertible,
    the quadratic form of `M` is isometrically equivalent to the weighted
    sum of squares with weights `d`. Applied once to the LDLᵀ side (weights
    `d`) and once to the eigendecomposition side (weights `λ - β`); both
    equivalences point at the same quadratic form, so `sigNeg` (the negative
    count) agrees between them, which is exactly the theorem's conclusion
    after converting `Set.ncard` to `Finset.card`.

## What's still `sorry`, and why — the substantive finding this session

### `temple_lower` — **the statement is false as written, not merely unproved**

`residualNorm` is defined in `Soundness.lean` as:

```lean
noncomputable def residualNorm (A : Matrix n n ℝ) (x : n → ℝ) : ℝ :=
  ‖A.mulVec x - (rayleigh A x) • x‖ / ‖x‖
```

The `‖·‖` resolves to whatever `Norm` instance Lean finds for `x : n → ℝ`.
Since `n → ℝ` is a plain Pi type (not `EuclideanSpace ℝ n`), that instance is
`Pi.normedAddCommGroup`, i.e. the **sup norm** (`Pi.norm_def : ‖f‖ =
↑(Finset.univ.sup fun b => ‖f b‖₊)`), not the Euclidean norm. Confirmed by a
standalone lemma that compiles clean against this file's own imports:

```lean
example : ‖(![3, -4] : Fin 2 → ℝ)‖ = 4 := by
  apply le_antisymm
  · rw [pi_norm_le_iff_of_nonneg (by norm_num)]; intro i; fin_cases i <;> norm_num
  · have := norm_le_pi_norm (![3, -4] : Fin 2 → ℝ) 1; simpa using this
```

(the Euclidean norm of `(3, -4)` is `5`; this proves it's `4`.)

Temple's inequality is classically a Euclidean/Pythagorean-orthogonality
argument (expand `x` in `A`'s eigenbasis, use that eigenvectors are
orthonormal). It does not transfer to the sup norm — and it is not merely
harder to prove there, it is **numerically false**. I ran a random search
(200000 trials, `n` uniform in `{2,...,5}`, random symmetric `A` via
`M + Mᵀ`, eigenvalues via a from-scratch Jacobi solver, `β` set to the
second-smallest eigenvalue — the widest valid separator, chosen to make a
violation as easy as possible to find if one exists) and found violations in
**9362 of 200000 trials (4.68%)**. Worst recorded instance:

```
n = 3
A = [[-0.9648769165219759, -1.402188087930802,  1.5206317025965617],
     [-1.402188087930802,   1.3768143870166014, 0.709725052905338 ],
     [ 1.5206317025965617,  0.709725052905338,  1.304325756655576 ]]
x = [0.9971309379732416, -0.5632638677598112, 0.39510881419682375]
eigenvalues ≈ {-2.384230194603246, 2.0326690656276565, 2.0678243561257905}
β = 2.0326690656276565     (satisfies hμβ and hgap: only eigenvalue < β is
                            the smallest one, so the gap hypothesis holds)
rayleigh A x ≈ 1.4570550056625322
residualNorm A x ≈ 1.075635924249074       (sup-norm based, as the file defines it)
LHS = rayleigh - residualNorm² / (β - rayleigh) ≈ -0.5529595544496035
⨅ i, eigenvalues i ≈ -2.384230194603246
```

`LHS ≈ -0.553` is **greater than** the claimed upper bound `⨅ eigenvalues ≈
-2.384` by about `1.83` — a large, unambiguous violation, not a
floating-point-precision artifact.

This is not something I can or should paper over by proving a weaker or
different statement under this bead — it's a defect in a shared definition
(`residualNorm` is also used by `residual_encloses_some_eigenvalue`, which
this bead's own notes already scope out). I filed **`certkit-8y2.5`** to fix
it (redefine `residualNorm` with an explicit Euclidean norm, e.g.
`Real.sqrt (r ⬝ᵥ r)`, instead of the ambient `Norm (n → ℝ)` instance) and left
`temple_lower` as `sorry`, with the full derivation above written directly
into its doc comment in `Soundness.lean` so nobody re-attempts the proof
without first reading why it can't work.

What *is* done toward it: the classical proof of Temple's inequality has two
halves — a positive-semidefiniteness fact about `(A-β•1)(A-c•1)` that does
not depend on which vector norm `residualNorm` uses, and a dot-product
algebra step that turns that PSD fact into the stated scalar bound (which
does depend on it, since it needs `‖x‖` and `‖r‖` to mean `√(x⬝ᵥx)` and
`√(r⬝ᵥr)` for the Pythagorean step to go through). I proved the first half,
zero-`sorry`, as a new private lemma:

```lean
private lemma posSemidef_shift_mul_shift (β c : ℝ)
    (hcase : ∀ i, 0 ≤ (hA.eigenvalues i - β) * (hA.eigenvalues i - c)) :
    ((A - β • (1 : Matrix n n ℝ)) * (A - c • (1 : Matrix n n ℝ))).PosSemidef
```

It's currently unused (nothing calls it, since `temple_lower` is still
`sorry`) — kept in the file, documented as such, for whoever picks up
`certkit-8y2.5` and returns to finish `temple_lower`.

### `weyl_shift` — no path forward without formalizing new spectral theory

Already flagged in the file's own doc comment (predating this session) as
the theorem with "the open obligation" undischarged. Checked this session
whether mathlib had since grown a Weyl eigenvalue-perturbation inequality,
Courant-Fischer min-max characterization, or anything on point:

```
$ grep -rln "Weyl\|weyl" .lake/packages/mathlib/Mathlib/    # no eigenvalue-perturbation hit
$ grep -rn "courant\|minimax\|min_max\|CourantFischer" .lake/packages/mathlib/Mathlib/ -i   # nothing on point
```

It has not. Proving `weyl_shift` from what mathlib does have
(`Matrix.IsHermitian.eigenvalues`, the spectral theorem,
`Analysis.Matrix.PosDef`) means formalizing a Courant-Fischer-style min-max
argument first — a substantial, self-contained project on its own, not a
short lemma reachable in this session. Left `sorry`; added a note to the
theorem's doc comment recording that this was checked and came up empty, so
the next session doesn't re-run the same search.

### `residual_encloses_some_eigenvalue` — out of scope, unchanged

Per this bead's own notes: not one of the five named theorems, correctly
left untouched.

## Why this bead stays open

Acceptance criteria is "all five proved." Three are. `weyl_shift` needs
genuinely new spectral theory. `temple_lower` needs `certkit-8y2.5` (a
different bead, a shared-definition fix) landed first, and even then still
needs its own dot-product algebra step written. Closing this bead now would
misrepresent both as done. Left `in_progress` with notes recording exactly
this split.

## What I decided not to do, and why

- **Did not attempt to "fix" `residualNorm` myself under this bead.** It's a
  shared definition (`residual_encloses_some_eigenvalue` also depends on
  it), changing it is a scope decision with consequences beyond this bead's
  five named theorems, and the task instructions for this session are
  explicit that work discovered outside a bead's scope becomes a new bead,
  not something done in place. Filed `certkit-8y2.5` instead.
- **Did not weaken `temple_lower`'s statement** (e.g. add a hypothesis
  forcing `x` to already be an eigenvector, or restrict to some norm-agnostic
  corollary) to get something "provable." The bead asks for Temple's
  inequality; a weakened restatement wouldn't be that, and doing so silently
  would misrepresent what's proved.
- **Did not attempt `weyl_shift` partially** (e.g. prove it for the special
  case of rank-one perturbations, or some other restricted version) since
  the bead names the theorem as stated and a partial version isn't it either.
- **Kept `posSemidef_shift_mul_shift` in the file even though it's currently
  unused.** It's a complete, sorry-free, non-trivial piece of the blocked
  proof (getting the matrix associativity right to expose `Uᵀ * U = 1` took
  several iterations); removing it would just mean re-deriving it later.
  Documented clearly as unused-pending-`certkit-8y2.5` so it doesn't read as
  live infrastructure.

## What I could not verify

- Whether the sup-norm version of `residual_encloses_some_eigenvalue` (also
  built on `residualNorm`) is true or false — did not check independently,
  since it's out of this bead's scope. Flagged in `certkit-8y2.5`'s
  description as something the fix should account for, not resolved here.
- Whether `certkit-8y2.5`'s suggested fix (`Real.sqrt (r ⬝ᵥ r)`) is exactly
  the right final form, versus e.g. switching `residualNorm`'s argument
  types to `EuclideanSpace ℝ n` throughout — I did not attempt the fix
  itself, only diagnosed and scoped it.

## Final test-run line, verbatim

```
$ uv sync --extra dev
...
$ uv run pytest tests
============================= test session starts ==============================
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

============================= 165 passed in 24.28s =============================
```

## No-dependency checker

`sandbox-prompt.md`'s Environment section names `python3 -m certkit.cli
check ...` as the cheap standalone check. This container has no bare
`python3`/`python` binary (same as `certkit-gvg`'s prior session found), and
`uv run python3` reuses the `--extra dev` venv (numpy importable in it — I
checked: `uv run python3 -c "import numpy"` exits 0), so it is *not* a valid
substitute. Falling back to the in-repo equivalent, which is exactly what it
tests for and is part of the 165-passed run above:

```
tests/test_trust_boundary.py::test_checker_runs_in_a_process_where_numpy_is_unimportable PASSED
```

This blocks the checker's own import machinery from finding `numpy`/`scipy`
in a subprocess and runs a real check through it; it passed as part of the
suite.

## Lean build, verbatim

```
$ lake build Certkit
⚠ [8802/8804] Built Certkit.Soundness (35s)
warning: Certkit/Soundness.lean:199:8: declaration uses `sorry`   (residual_encloses_some_eigenvalue)
warning: Certkit/Soundness.lean:249:8: declaration uses `sorry`   (temple_lower)
warning: Certkit/Soundness.lean:270:5: Variable name `hd` is not explicitly referenced.
warning: Certkit/Soundness.lean:367:8: declaration uses `sorry`   (weyl_shift)
✔ [8803/8804] Built Certkit (33s)
Build completed successfully (8804 jobs).
```

The `hd` warning is benign and pre-existing to this session's
`inertia_count_below` proof: `hd : ∀ i, d i ≠ 0` turned out to be unused once
the equivalence/signature argument was used directly. Left as-is rather than
removed, since removing it would change the theorem's public signature away
from what the bead's acceptance criteria / Python-correspondence comment
describes.

## Files changed

- `lean/Certkit/Soundness.lean` — added `sub_smul_one_eq_mul_diagonal_mul_transpose`,
  `equivalent_weightedSumSquares_of_eq_mul_diagonal_mul_transpose`,
  `posSemidef_shift_mul_shift` (all `private`, all sorry-free); filled in
  `inertia_count_below`'s proof (was `sorry`, now proved); rewrote
  `temple_lower`'s and `weyl_shift`'s doc comments with the findings above.
  `rayleigh_ritz_min` and `gershgorin_lower` untouched.
- `lean/Certkit/Scratch.lean` — deleted (debris from earlier debugging in a
  prior, now-summarized segment of this session; was never committed, not
  referenced by `Certkit.lean` or any build target).
- `issues.jsonl` — re-exported via `bd export -o issues.jsonl` to capture
  this session's bead updates (`certkit-8y2.3` notes, new `certkit-8y2.5`).

Other untracked/modified files visible in `git status` (`fetch-mathlib.sh`,
various `sandbox-handoffs/certkit-{ph1,gvg,j82,sqr}*`, `tests/test_exact_oracle.py`,
`pyproject.toml`, `README.md`) are **not from this session** — they predate
it (other beads' work in this same sandbox) and were left untouched.

## Suggested commands for a human to run

```bash
cd /workspace
git status
git add lean/Certkit/Soundness.lean issues.jsonl
git status   # confirm lean/Certkit/Scratch.lean's deletion and the untouched
             # other-bead files are handled as intended before committing
git commit -m "certkit-8y2.3: prove inertia_count_below; diagnose temple_lower/residualNorm as false-as-stated, file certkit-8y2.5"
```

I did not run any of the above — no commit, push, or `bd dolt push` this
session, per the conservative git policy.
