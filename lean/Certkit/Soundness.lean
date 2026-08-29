/-
  certkit -- soundness obligations, stated in Lean 4 / mathlib4.

  STATUS: compiles clean against the pinned mathlib (see lake-manifest.json).
  Four of the seven theorems below are real, zero-`sorry` proofs:
  `rayleigh_ritz_min`, `inertia_count_below`, `gershgorin_lower`, and
  `sweep_backward_bound` (that last one has its own doc comment on exactly
  what it does and does not cover). The other three --
  `residual_encloses_some_eigenvalue`, `temple_lower`, and `weyl_shift` --
  are still `sorry`: a specification of intent, not a verified artifact. Do
  not read this file as "soundness-complete."

  The point of the file is the correspondence. The Python checker performs
  exactly two mathematical steps, and each is one theorem here:

    checker._rule_temple_inertia       upper bound  <->  rayleigh_ritz_min
                                       lower bound  <->  temple_lower
    checker.count_eigenvalues_below                 <->  inertia_count_below
    banded.count_eigenvalues_below_banded           <->  inertia_count_below
    backward_error.count_eigenvalues_below_backward <->  inertia_count_below
                                                     +   weyl_shift
    checker._rule_gershgorin_rayleigh  lower bound  <->  gershgorin_lower

  A third obligation -- that interval arithmetic on doubles encloses the
  real result -- is the floating-point layer; it is formalised and proved,
  zero `sorry`, in `Interval.lean`.
-/

import Mathlib.Analysis.InnerProductSpace.Spectrum
import Mathlib.LinearAlgebra.Matrix.Hermitian
import Mathlib.Analysis.Matrix.Spectrum
import Mathlib.Analysis.Matrix.PosDef
import Mathlib.Algebra.Order.Star.Real
import Certkit.BackwardError

namespace Certkit

open scoped Matrix
open Matrix Unitary

variable {n : Type*} [Fintype n] [DecidableEq n]
variable {A : Matrix n n ℝ} (hA : A.IsHermitian)

/-- The Rayleigh quotient of a nonzero vector. -/
noncomputable def rayleigh (A : Matrix n n ℝ) (x : n → ℝ) : ℝ :=
  (x ⬝ᵥ A.mulVec x) / (x ⬝ᵥ x)

/-- The residual norm, measured relative to the vector's own norm. Both norms
    are Euclidean (ℓ²), written explicitly as `Real.sqrt (· ⬝ᵥ ·)` rather than
    via the ambient `Norm (n → ℝ)` instance -- that instance is the sup norm
    (`Pi.norm_def`), under which Temple's inequality (`temple_lower`) is false.
    `rayleigh` above is already norm-agnostic (it only uses `⬝ᵥ`). -/
noncomputable def residualNorm (A : Matrix n n ℝ) (x : n → ℝ) : ℝ :=
  let r := A.mulVec x - (rayleigh A x) • x
  Real.sqrt (r ⬝ᵥ r) / Real.sqrt (x ⬝ᵥ x)

/-- A Hermitian matrix shifted by `c • 1` is positive semidefinite iff `c` sits
    below every eigenvalue -- the standard "shift trick", proved by unitarily
    diagonalising `A` and reducing to `posSemidef_diagonal_iff`. Used only to
    derive `rayleigh_ritz_min`. -/
private lemma posSemidef_sub_smul_one_iff (c : ℝ) :
    (A - c • (1 : Matrix n n ℝ)).PosSemidef ↔ ∀ i, c ≤ hA.eigenvalues i := by
  have hUU : (hA.eigenvectorUnitary : Matrix n n ℝ) *
      star (hA.eigenvectorUnitary : Matrix n n ℝ) = 1 :=
    Unitary.coe_mul_star_self hA.eigenvectorUnitary
  have hdiagc : (Matrix.diagonal (fun _ : n => c) : Matrix n n ℝ) = c • (1 : Matrix n n ℝ) := by
    rw [← Matrix.diagonal_one, ← Matrix.diagonal_smul]
    congr 1
    funext i
    simp
  have hofReal : (RCLike.ofReal ∘ hA.eigenvalues : n → ℝ) = hA.eigenvalues := by
    funext i; simp
  have hshift : A - c • (1 : Matrix n n ℝ) =
      (hA.eigenvectorUnitary : Matrix n n ℝ) * Matrix.diagonal (fun i => hA.eigenvalues i - c) *
        star (hA.eigenvectorUnitary : Matrix n n ℝ) := by
    conv_lhs => rw [hA.spectral_theorem, conjStarAlgAut_apply, hofReal]
    rw [← Matrix.diagonal_sub, mul_sub, sub_mul, hdiagc, mul_smul_comm, mul_one,
      smul_mul_assoc, hUU]
  rw [hshift, isUnit_coe.posSemidef_star_right_conjugate_iff, posSemidef_diagonal_iff]
  simp only [sub_nonneg]

/-- The eigendecomposition shift identity in transpose (rather than `star`) form --
    same content as `posSemidef_sub_smul_one_iff`'s internal `hshift`, but exposed
    standalone since `inertia_count_below` needs the transpose form to match the
    LDLᵀ hypothesis's shape. Used only to derive `inertia_count_below`. -/
private lemma sub_smul_one_eq_mul_diagonal_mul_transpose (c : ℝ) :
    A - c • (1 : Matrix n n ℝ) =
      (hA.eigenvectorUnitary : Matrix n n ℝ) * Matrix.diagonal (fun i => hA.eigenvalues i - c) *
        ((hA.eigenvectorUnitary : Matrix n n ℝ))ᵀ := by
  have hUU : (hA.eigenvectorUnitary : Matrix n n ℝ) *
      star (hA.eigenvectorUnitary : Matrix n n ℝ) = 1 :=
    Unitary.coe_mul_star_self hA.eigenvectorUnitary
  have hdiagc : (Matrix.diagonal (fun _ : n => c) : Matrix n n ℝ) = c • (1 : Matrix n n ℝ) := by
    rw [← Matrix.diagonal_one, ← Matrix.diagonal_smul]
    congr 1
    funext i
    simp
  have hofReal : (RCLike.ofReal ∘ hA.eigenvalues : n → ℝ) = hA.eigenvalues := by
    funext i; simp
  have hshift : A - c • (1 : Matrix n n ℝ) =
      (hA.eigenvectorUnitary : Matrix n n ℝ) * Matrix.diagonal (fun i => hA.eigenvalues i - c) *
        star (hA.eigenvectorUnitary : Matrix n n ℝ) := by
    conv_lhs => rw [hA.spectral_theorem, conjStarAlgAut_apply, hofReal]
    rw [← Matrix.diagonal_sub, mul_sub, sub_mul, hdiagc, mul_smul_comm, mul_one,
      smul_mul_assoc, hUU]
  rw [hshift, Matrix.star_eq_conjTranspose, Matrix.conjTranspose_eq_transpose_of_trivial]

/-- If `M = L * diagonal d * Lᵀ` with `L` invertible, then the quadratic form of `M`
    is isometrically equivalent to the weighted sum of squares with weights `d`.
    The congruence that underlies Sylvester's law of inertia. Used only to derive
    `inertia_count_below`. -/
private lemma equivalent_weightedSumSquares_of_eq_mul_diagonal_mul_transpose
    {M L : Matrix n n ℝ} {d : n → ℝ} (hL : IsUnit L)
    (hM : M = L * Matrix.diagonal d * Lᵀ) :
    QuadraticMap.Equivalent (Matrix.toQuadraticForm' M) (QuadraticMap.weightedSumSquares ℝ d) := by
  have hdet : IsUnit L.det := (Matrix.isUnit_iff_isUnit_det L).mp hL
  have h1 : L * L⁻¹ = 1 := Matrix.mul_nonsing_inv L hdet
  have h2 : L⁻¹ * L = 1 := Matrix.nonsing_inv_mul L hdet
  have hf1 : (Matrix.toLin' Lᵀ).comp (Matrix.toLin' (L⁻¹)ᵀ) = LinearMap.id := by
    rw [← Matrix.toLin'_mul, ← Matrix.transpose_mul, h2, Matrix.transpose_one, Matrix.toLin'_one]
  have hf2 : (Matrix.toLin' (L⁻¹)ᵀ).comp (Matrix.toLin' Lᵀ) = LinearMap.id := by
    rw [← Matrix.toLin'_mul, ← Matrix.transpose_mul, h1, Matrix.transpose_one, Matrix.toLin'_one]
  have htoQF : ∀ x : n → ℝ, Matrix.toQuadraticForm' M x = x ⬝ᵥ (M *ᵥ x) := fun x =>
    (LinearMap.BilinMap.toQuadraticMap_apply _ x).trans (Matrix.toLinearMap₂'_apply' M x x)
  have hxx : ∀ x : n → ℝ, x ⬝ᵥ (M *ᵥ x) = (Lᵀ *ᵥ x) ⬝ᵥ (Matrix.diagonal d *ᵥ (Lᵀ *ᵥ x)) := by
    intro x
    rw [hM, Matrix.mul_assoc, ← Matrix.mulVec_mulVec, ← Matrix.mulVec_mulVec,
      Matrix.dotProduct_mulVec, ← Matrix.mulVec_transpose]
  set e : (n → ℝ) ≃ₗ[ℝ] (n → ℝ) :=
    LinearEquiv.ofLinearMap (Matrix.toLin' Lᵀ) (Matrix.toLin' (L⁻¹)ᵀ) hf1 hf2 with he_def
  refine ⟨{ e with map_app' := fun x => ?_ }⟩
  show QuadraticMap.weightedSumSquares ℝ d (e x) = Matrix.toQuadraticForm' M x
  rw [he_def, LinearEquiv.coe_ofLinearMap, Matrix.toLin'_apply, htoQF, hxx,
    QuadraticMap.weightedSumSquares_apply, dotProduct]
  refine Finset.sum_congr rfl fun i _ => ?_
  rw [Matrix.mulVec_diagonal, smul_eq_mul]
  ring

/-- If two shifts `β, c` are such that `(λ_i - β)(λ_i - c) ≥ 0` for every
    eigenvalue `λ_i` of `A`, then the product `(A - β•1)(A - c•1)` -- which is
    again Hermitian, since the two factors commute -- is positive
    semidefinite.

    This is the PSD half of the classical proof of Temple's inequality
    (`x ⬝ᵥ ((A-β•1)*(A-c•1)) *ᵥ x ≥ 0`, expanded and rearranged, is exactly
    `‖Ax-μx‖² + ‖x‖²(μ-β)(μ-c) ≥ 0`, with `‖·‖` Euclidean). Still unused: it
    supplies the PSD fact `temple_lower` needs, but the dot-product algebra
    step that turns it into the stated scalar bound is not yet written. -/
private lemma posSemidef_shift_mul_shift (β c : ℝ)
    (hcase : ∀ i, 0 ≤ (hA.eigenvalues i - β) * (hA.eigenvalues i - c)) :
    ((A - β • (1 : Matrix n n ℝ)) * (A - c • (1 : Matrix n n ℝ))).PosSemidef := by
  set U : Matrix n n ℝ := (hA.eigenvectorUnitary : Matrix n n ℝ) with hU_def
  have hUU' : star U * U = 1 := Unitary.coe_star_mul_self hA.eigenvectorUnitary
  have hβ : A - β • (1 : Matrix n n ℝ) =
      U * Matrix.diagonal (fun i => hA.eigenvalues i - β) * star U := by
    rw [Matrix.star_eq_conjTranspose, Matrix.conjTranspose_eq_transpose_of_trivial]
    exact sub_smul_one_eq_mul_diagonal_mul_transpose hA β
  have hc : A - c • (1 : Matrix n n ℝ) =
      U * Matrix.diagonal (fun i => hA.eigenvalues i - c) * star U := by
    rw [Matrix.star_eq_conjTranspose, Matrix.conjTranspose_eq_transpose_of_trivial]
    exact sub_smul_one_eq_mul_diagonal_mul_transpose hA c
  have hprod : (A - β • (1 : Matrix n n ℝ)) * (A - c • (1 : Matrix n n ℝ)) =
      U * Matrix.diagonal (fun i => (hA.eigenvalues i - β) * (hA.eigenvalues i - c)) *
        star U := by
    rw [hβ, hc, Matrix.mul_assoc, Matrix.mul_assoc,
      ← Matrix.mul_assoc (star U) (U * Matrix.diagonal (fun i => hA.eigenvalues i - c)) (star U),
      ← Matrix.mul_assoc (star U) U (Matrix.diagonal (fun i => hA.eigenvalues i - c)),
      hUU', one_mul,
      ← Matrix.mul_assoc (Matrix.diagonal (fun i => hA.eigenvalues i - β))
        (Matrix.diagonal (fun i => hA.eigenvalues i - c)) (star U),
      Matrix.diagonal_mul_diagonal, ← Matrix.mul_assoc]
  rw [hprod, isUnit_coe.posSemidef_star_right_conjugate_iff, posSemidef_diagonal_iff]
  exact hcase

/-- **Rayleigh-Ritz.** The Rayleigh quotient of any nonzero vector is an
    upper bound for the least eigenvalue. This is the checker's upper bound,
    and it is unconditional -- no gap, no witness beyond `x` itself.
    Corresponds to the upper bound in `checker._rule_temple_inertia`. -/
theorem rayleigh_ritz_min (x : n → ℝ) (hx : x ≠ 0) :
    ⨅ i, hA.eigenvalues i ≤ rayleigh A x := by
  set c := ⨅ i, hA.eigenvalues i with hc_def
  have hle : ∀ i, c ≤ hA.eigenvalues i :=
    fun i => ciInf_le (Set.Finite.bddBelow (Set.finite_range hA.eigenvalues)) i
  have hpsd : (A - c • (1 : Matrix n n ℝ)).PosSemidef := (posSemidef_sub_smul_one_iff hA c).mpr hle
  have hxx_pos : 0 < x ⬝ᵥ x := by
    simpa [star_trivial] using (Matrix.dotProduct_self_star_pos_iff (v := x)).mpr hx
  have hnn : 0 ≤ x ⬝ᵥ ((A - c • (1 : Matrix n n ℝ)) *ᵥ x) := by
    simpa [star_trivial] using hpsd.dotProduct_mulVec_nonneg x
  have hexpand : x ⬝ᵥ ((A - c • (1 : Matrix n n ℝ)) *ᵥ x) = x ⬝ᵥ (A *ᵥ x) - c * (x ⬝ᵥ x) := by
    rw [Matrix.sub_mulVec, dotProduct_sub, Matrix.smul_mulVec, Matrix.one_mulVec, dotProduct_smul]
    ring
  rw [hexpand] at hnn
  show c ≤ rayleigh A x
  rw [rayleigh, le_div_iff₀ hxx_pos]
  linarith

/-- **Residual bound.** Some eigenvalue lies within the residual norm of the
    Rayleigh quotient. Note what this does *not* say: the nearby eigenvalue
    need not be the least one. The Python side keeps this as a separate
    claim kind (`spectrum_contains`) precisely to stop that conflation. -/
theorem residual_encloses_some_eigenvalue (x : n → ℝ) (hx : x ≠ 0) :
    ∃ i, |hA.eigenvalues i - rayleigh A x| ≤ residualNorm A x := by
  sorry

/-- **Temple's inequality.** Given a separator `β` that sits strictly above
    the Rayleigh quotient and weakly below the second eigenvalue, the
    residual gives a *lower* bound on the least eigenvalue.

    History: this was `sorry` and *false as previously stated*, because
    `residualNorm` resolved `‖·‖` to the sup norm (`Pi.norm_def`) rather than
    the Euclidean norm Temple's Pythagorean argument requires -- a random
    search found the bound violated in 9362 of 200000 trials (worst margin
    ≈ 1.83 at `n = 3`; full data in `sandbox-handoffs/certkit-8y2.3.md`).
    `residualNorm` is now defined with an explicit Euclidean norm
    (`Real.sqrt (r ⬝ᵥ r)`), so the statement is true again; still `sorry`.

    Remaining obligation: `posSemidef_shift_mul_shift` gives
    `0 ≤ x ⬝ᵥ (((A - β•1)*(A - c•1)) *ᵥ x)` with `c := ⨅ j, eigenvalues j`
    (its `hcase` holds: `λ_i ≥ c` always, and either `λ_i ≥ β` or, by `hgap`,
    `λ_i = c`). Dividing by `s := x ⬝ᵥ x > 0` and writing
    `(residualNorm A x)^2 = (r ⬝ᵥ r)/s = q/s - μ^2` with `μ := rayleigh A x`,
    `q := (A *ᵥ x) ⬝ᵥ (A *ᵥ x)`, the expansion collapses to
    `(residualNorm A x)^2 ≥ (β - μ)(μ - c)`, which rearranges to the goal.
    Same shape as `rayleigh_ritz_min`'s `hexpand`, but for a product of two
    shifts. -/
theorem temple_lower
    (x : n → ℝ) (hx : x ≠ 0) (β : ℝ)
    (hμβ : rayleigh A x < β)
    (hgap : ∀ i, hA.eigenvalues i < β → hA.eigenvalues i = ⨅ j, hA.eigenvalues j) :
    rayleigh A x - (residualNorm A x) ^ 2 / (β - rayleigh A x)
      ≤ ⨅ i, hA.eigenvalues i := by
  sorry

/-- **Sylvester inertia count.** The number of negative pivots in an LDLᵀ
    factorisation of `A - β • 1` equals the number of eigenvalues below `β`.
    This is what discharges `hgap` above: the Python checker computes the
    count in interval arithmetic and requires it to be exactly one.

    `[LinearOrder n]` is required because `L.BlockTriangular id` states
    triangularity of `L` against the order of its own index type `n`
    (`Matrix.BlockTriangular` needs `LT` on whatever type the block function
    lands in, and here that function is `id : n → n`) -- the same requirement
    the checker's own row-major sweep already assumes by processing indices
    `0, 1, ..., n-1` in order. It narrows the statement from "some `n`" to
    "some linearly ordered `n`", not from the guarantee. -/
theorem inertia_count_below [LinearOrder n] (β : ℝ) (d : n → ℝ)
    (hd : ∀ i, d i ≠ 0)
    (hldl : ∃ L : Matrix n n ℝ, L.BlockTriangular id ∧
      (∀ i, L i i = 1) ∧ A - β • (1 : Matrix n n ℝ) = L * (Matrix.diagonal d) * Lᵀ) :
    (Finset.univ.filter fun i => d i < 0).card
      = (Finset.univ.filter fun i => hA.eigenvalues i < β).card := by
  obtain ⟨L, hLtri, hLdiag, hLeq⟩ := hldl
  have hLdet : L.det = 1 := by
    rw [Matrix.det_of_isUpperTriangular hLtri]
    simp [hLdiag]
  have hLunit : IsUnit L := by
    rw [Matrix.isUnit_iff_isUnit_det, hLdet]
    exact isUnit_one
  have hUunit : IsUnit (hA.eigenvectorUnitary : Matrix n n ℝ) :=
    Unitary.isUnit_coe (U := hA.eigenvectorUnitary)
  have hUeq : A - β • (1 : Matrix n n ℝ) =
      (hA.eigenvectorUnitary : Matrix n n ℝ) * Matrix.diagonal (fun i => hA.eigenvalues i - β) *
        ((hA.eigenvectorUnitary : Matrix n n ℝ))ᵀ :=
    sub_smul_one_eq_mul_diagonal_mul_transpose hA β
  have hEquivD :
      QuadraticMap.Equivalent (Matrix.toQuadraticForm' (A - β • (1 : Matrix n n ℝ)))
        (QuadraticMap.weightedSumSquares ℝ d) :=
    equivalent_weightedSumSquares_of_eq_mul_diagonal_mul_transpose hLunit hLeq
  have hEquivEig :
      QuadraticMap.Equivalent (Matrix.toQuadraticForm' (A - β • (1 : Matrix n n ℝ)))
        (QuadraticMap.weightedSumSquares ℝ (fun i => hA.eigenvalues i - β)) :=
    equivalent_weightedSumSquares_of_eq_mul_diagonal_mul_transpose hUunit hUeq
  have hcard1 := QuadraticForm.sigNeg_of_equiv_weightedSumSquares hEquivD
  have hcard2 := QuadraticForm.sigNeg_of_equiv_weightedSumSquares hEquivEig
  have hncard : {i | d i < 0}.ncard = {i | hA.eigenvalues i - β < 0}.ncard :=
    hcard1.symm.trans hcard2
  have h1 : {i | d i < 0}.ncard = (Finset.univ.filter fun i => d i < 0).card := by
    rw [Set.ncard_eq_toFinset_card']
    congr 1
    ext i
    simp
  have h2 : {i | hA.eigenvalues i - β < 0}.ncard
      = (Finset.univ.filter fun i => hA.eigenvalues i < β).card := by
    rw [Set.ncard_eq_toFinset_card']
    congr 1
    ext i
    simp [sub_neg]
  rw [h1, h2] at hncard
  exact hncard

/-- **Gershgorin.** Every eigenvalue is at least the smallest value of
    `a i i - (off-diagonal absolute row sum)`. This is the matrix-free lower
    bound: it needs only row access, no gap and no factorisation, and it is
    what lets the checker say something sound about an operator it can never
    build. -/
theorem gershgorin_lower :
    (⨅ i, hA.eigenvalues i)
      ≥ ⨅ i, (A i i - ∑ j ∈ Finset.univ.erase i, |A i j|) := by
  rcases isEmpty_or_nonempty n with hn | hn
  · simp
  · rw [ge_iff_le]
    apply le_ciInf
    intro i
    have heig : Module.End.HasEigenvalue (Matrix.toLin' A) (hA.eigenvalues i) := by
      rw [Module.End.hasEigenvalue_iff_mem_spectrum, Matrix.spectrum_toLin']
      exact hA.eigenvalues_mem_spectrum_real i
    obtain ⟨k, hk⟩ := eigenvalue_mem_ball heig
    rw [Metric.mem_closedBall, Real.dist_eq] at hk
    simp only [Real.norm_eq_abs] at hk
    have hk' : A k k - ∑ j ∈ Finset.univ.erase k, |A k j| ≤ hA.eigenvalues i := by
      have h1 := (abs_le.mp hk).1
      linarith
    calc (⨅ i', A i' i' - ∑ j ∈ Finset.univ.erase i', |A i' j|)
        ≤ A k k - ∑ j ∈ Finset.univ.erase k, |A k j| :=
          ciInf_le (Set.Finite.bddBelow (Set.finite_range _)) k
      _ ≤ hA.eigenvalues i := hk'

open scoped Matrix.Norms.L2Operator in
/-- **Weyl.** Perturbing a symmetric operator moves each eigenvalue by at most
    the norm of the perturbation. This is what carries the backward-error
    counting rule's conclusion back from the nearby matrix the float sweep
    actually factorises to the operator the certificate is about.

    The `sturm_be` rule bounds `‖A - Atilde‖` at runtime from the entries, then
    brackets: sweeping at `beta - delta` and `beta + delta` and requiring the
    two counts to agree pins the count for `A` itself.

    `‖·‖` here is the `L²` operator norm (`Matrix.Norms.L2Operator`, the norm
    induced by identifying a matrix with the continuous linear map it gives on
    `EuclideanSpace` -- the classical spectral norm Weyl's inequality is stated
    against), opened locally so this file does not choose a global `Norm`
    instance for `Matrix n n ℝ`. It is *not* the entrywise/row-sum bound
    `sturm_be` actually computes at runtime; relating the two remains part of
    the open obligation this theorem's `sorry` stands for.

    Checked this session: mathlib has no Weyl eigenvalue-perturbation
    inequality, Courant-Fischer min-max characterisation, or comparable
    variational eigenvalue result under any name (`grep -rl weyl|courant|
    minimax` across `Mathlib/` turns up nothing on point). Proving this from
    what mathlib does have (`Matrix.IsHermitian.eigenvalues`, the spectral
    theorem, `Analysis.Matrix.PosDef`) means formalising a Courant-Fischer-style
    min-max argument first -- a substantial, self-contained project, not a
    short lemma. Left `sorry` rather than attempted partially. -/
theorem weyl_shift {B : Matrix n n ℝ} (hB : B.IsHermitian) (i : n) :
    |hA.eigenvalues i - hB.eigenvalues i| ≤ ‖A - B‖ := by
  sorry

/-- **The per-step rounding collection**, formalised and proved in
    `Certkit.BackwardError` (`sweep_step_backward_bound`): given the
    one-rounding-per-operation model (each of a sweep step's four operations
    commits at most one relative rounding error of size `u`), the computed
    pivot `d` is exactly what the recurrence would give for a diagonal
    perturbed by a factor `eta` and a squared off-diagonal perturbed by a
    factor `gamma`, with `|eta| ≤ 2.1 * u` and `|gamma| ≤ 3.1 * u` -- the
    exact `ETA`/`GAMMA` constants `backward_error.py` uses.

    This discharges the part of the obligation the bead's acceptance
    criterion asks for: the one-rounding model, formalised, and the per-step
    collection of factors into `eta` and `gamma`, proved rather than
    transcribed. It does **not** discharge the rest of the obligation's
    original framing -- that the row-sums `sweep` accumulates from these
    factors actually dominate `‖A - Atilde‖_∞` (an `Iv`-arithmetic
    bookkeeping fact about `backward_error.sweep`'s Python loop, not part of
    the one-rounding algebra) and that `‖·‖_∞` dominates the operator norm
    `‖·‖_2` used by `weyl_shift` above (a general Hermitian-matrix norm
    inequality, unrelated to rounding). Those remain open, covered by
    `weyl_shift`'s own `sorry` and by the Python test suite, not by this
    theorem. -/
theorem sweep_backward_bound {u e0 e1 e2 e3 a beta bprev dprev : ℝ}
    (hu : 0 ≤ u) (hu1 : u ≤ 1 / 32)
    (h0 : |e0| ≤ u) (h1 : |e1| ≤ u) (h2 : |e2| ≤ u) (h3 : |e3| ≤ u) :
    (((a - beta) * (1 + e2) - (bprev ^ 2 * (1 + e0) / dprev) * (1 + e1)) * (1 + e3)
        = (a - beta) * (1 + eta_of e2 e3) - bprev ^ 2 * (1 + gamma_of e0 e1 e3) / dprev)
      ∧ |eta_of e2 e3| ≤ 2.1 * u ∧ |gamma_of e0 e1 e3| ≤ 3.1 * u :=
  sweep_step_backward_bound hu hu1 h0 h1 h2 h3

end Certkit
