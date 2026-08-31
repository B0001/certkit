/-
  certkit -- soundness obligations, stated in Lean 4 / mathlib4.

  STATUS: compiles clean against the pinned mathlib (see lake-manifest.json).
  Five of the seven theorems below are real, zero-`sorry` proofs:
  `rayleigh_ritz_min`, `inertia_count_below`, `gershgorin_lower`,
  `temple_lower`, and `sweep_backward_bound` (that last one has its own doc
  comment on exactly what it does and does not cover). The other two --
  `residual_encloses_some_eigenvalue` and `weyl_shift` -- are still `sorry`:
  a specification of intent, not a verified artifact. Do not read this file
  as "soundness-complete."

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
    (`Real.sqrt (r ⬝ᵥ r)`), which made the statement true again, and it is
    now a real, zero-`sorry` proof.

    Derivation: `posSemidef_shift_mul_shift` gives
    `0 ≤ x ⬝ᵥ (((A - β•1)*(A - c•1)) *ᵥ x)` with `c := ⨅ j, eigenvalues j`
    (its `hcase` holds: `λ_i ≥ c` always, and either `λ_i ≥ β` or, by `hgap`,
    `λ_i = c`). Expanding that product (`hexpand`, the same shape as
    `rayleigh_ritz_min`'s `hexpand` but for a product of two shifts, using
    `A` symmetric to fold `x ⬝ᵥ (A *ᵥ (A *ᵥ x))` into `(A*ᵥx) ⬝ᵥ (A*ᵥx)`) and
    separately expanding `(residualNorm A x)^2 = (r ⬝ᵥ r)/s` (`hrr`, with
    `s := x ⬝ᵥ x > 0` and `r := A*ᵥx - μ•x`, `μ := rayleigh A x`) both reduce
    to the same quantity `(A*ᵥx)⬝ᵥ(A*ᵥx) - μ^2*s`, which lets the PSD
    inequality be rewritten as `s*(μ-c)*(β-μ) ≤ r ⬝ᵥ r`. Dividing by `s > 0`
    and then by `β - μ > 0` (from `hμβ`) gives `μ - c ≤ (residualNorm A x)^2 /
    (β - μ)`, which rearranges to the goal. -/
theorem temple_lower
    (x : n → ℝ) (hx : x ≠ 0) (β : ℝ)
    (hμβ : rayleigh A x < β)
    (hgap : ∀ i, hA.eigenvalues i < β → hA.eigenvalues i = ⨅ j, hA.eigenvalues j) :
    rayleigh A x - (residualNorm A x) ^ 2 / (β - rayleigh A x)
      ≤ ⨅ i, hA.eigenvalues i := by
  have hxx_pos : 0 < x ⬝ᵥ x := by
    simpa [star_trivial] using (Matrix.dotProduct_self_star_pos_iff (v := x)).mpr hx
  have hcase : ∀ i, 0 ≤ (hA.eigenvalues i - β) * (hA.eigenvalues i - ⨅ j, hA.eigenvalues j) := by
    intro i
    rcases lt_or_ge (hA.eigenvalues i) β with hlt | hge
    · rw [hgap i hlt]; simp
    · have hcle : (⨅ j, hA.eigenvalues j) ≤ hA.eigenvalues i :=
        ciInf_le (Set.Finite.bddBelow (Set.finite_range hA.eigenvalues)) i
      exact mul_nonneg (by linarith) (by linarith)
  have hpsd := posSemidef_shift_mul_shift hA β (⨅ j, hA.eigenvalues j) hcase
  have hnn : 0 ≤ x ⬝ᵥ
      (((A - β • (1 : Matrix n n ℝ)) * (A - (⨅ j, hA.eigenvalues j) • (1 : Matrix n n ℝ)))
        *ᵥ x) := by
    simpa [star_trivial] using hpsd.dotProduct_mulVec_nonneg x
  have hAsymm : Aᵀ = A := by
    rw [← Matrix.conjTranspose_eq_transpose_of_trivial]
    exact hA
  have hq : x ⬝ᵥ (A *ᵥ (A *ᵥ x)) = (A *ᵥ x) ⬝ᵥ (A *ᵥ x) := by
    have h := dotProduct_transpose_mulVec A x (A *ᵥ x)
    rwa [hAsymm] at h
  have hxAx : x ⬝ᵥ (A *ᵥ x) = rayleigh A x * (x ⬝ᵥ x) := by
    rw [rayleigh, div_mul_cancel₀ _ (ne_of_gt hxx_pos)]
  have hexpand :
      x ⬝ᵥ (((A - β • (1 : Matrix n n ℝ)) * (A - (⨅ j, hA.eigenvalues j) • (1 : Matrix n n ℝ)))
          *ᵥ x)
        = (A *ᵥ x) ⬝ᵥ (A *ᵥ x)
          - ((⨅ j, hA.eigenvalues j) + β) * (rayleigh A x * (x ⬝ᵥ x))
          + β * (⨅ j, hA.eigenvalues j) * (x ⬝ᵥ x) := by
    simp only [← Matrix.mulVec_mulVec, Matrix.sub_mulVec, Matrix.smul_mulVec, Matrix.one_mulVec,
      Matrix.mulVec_sub, Matrix.mulVec_smul, dotProduct_sub, dotProduct_smul, smul_eq_mul]
    rw [hq, hxAx]
    ring
  rw [hexpand] at hnn
  have hrr : (A *ᵥ x - rayleigh A x • x) ⬝ᵥ (A *ᵥ x - rayleigh A x • x)
      = (A *ᵥ x) ⬝ᵥ (A *ᵥ x) - (rayleigh A x) ^ 2 * (x ⬝ᵥ x) := by
    simp only [sub_dotProduct, dotProduct_sub, dotProduct_smul, smul_dotProduct, smul_eq_mul]
    rw [dotProduct_comm (A *ᵥ x) x, hxAx]
    ring
  have hrr_nonneg : 0 ≤ (A *ᵥ x - rayleigh A x • x) ⬝ᵥ (A *ᵥ x - rayleigh A x • x) := by
    simpa [star_trivial] using dotProduct_self_star_nonneg (A *ᵥ x - rayleigh A x • x)
  have hresidualNorm_sq : (residualNorm A x) ^ 2
      = ((A *ᵥ x) ⬝ᵥ (A *ᵥ x) - (rayleigh A x) ^ 2 * (x ⬝ᵥ x)) / (x ⬝ᵥ x) := by
    unfold residualNorm
    rw [div_pow, Real.sq_sqrt hrr_nonneg, Real.sq_sqrt hxx_pos.le, hrr]
  have hkey : (rayleigh A x - ⨅ j, hA.eigenvalues j) * (β - rayleigh A x)
      ≤ (residualNorm A x) ^ 2 := by
    rw [hresidualNorm_sq, le_div_iff₀ hxx_pos]
    nlinarith [hnn]
  have hβμ_pos : 0 < β - rayleigh A x := by linarith
  have hstep : rayleigh A x - (⨅ j, hA.eigenvalues j)
      ≤ (residualNorm A x) ^ 2 / (β - rayleigh A x) := by
    rw [le_div_iff₀ hβμ_pos]
    exact hkey
  linarith

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

    Checked across four independent sessions now: mathlib has no Weyl
    eigenvalue-perturbation inequality, Courant-Fischer min-max
    characterisation, or comparable variational eigenvalue result under any
    name (`grep -rl weyl|courant|minimax` across `Mathlib/` turns up nothing
    on point, confirmed again this session against mathlib commit
    `5ba95124681110751345e9bd360994de8541027c`, 2026-08-28).
    `Mathlib.Analysis.InnerProductSpace.Spectrum` (where
    `LinearMap.IsSymmetric.eigenvalues`, the thing `eigenvalues₀` above is
    literally built from) has only the *extreme*-eigenvalue variational facts
    -- `hasEigenvalue_iSup_of_finiteDimensional`,
    `hasEigenvalue_iInf_of_finiteDimensional` -- and no indexed
    Courant-Fischer statement; `Mathlib.Analysis.InnerProductSpace.Rayleigh`
    likewise gives only `norm_eq_iSup_rayleighQuotient` (operator norm as a
    sup over *all* vectors) and nothing about a single indexed eigenvalue.
    An equivalent-difficulty route -- prove Loewner-order monotonicity
    (`A ⪯ B → ∀ k, eigenvalues₀ A k ≤ eigenvalues₀ B k`, which composed with
    `‖A-B‖•1 - (A-B)` being `PosSemidef` would give this theorem in a few
    lines) -- needs exactly the same missing content: that monotonicity
    claim *is* Weyl's monotonicity theorem, itself normally proved via
    Courant-Fischer or Cauchy interlacing.

    This session (2026-08-31, split into its own bead certkit-8y2.6) built
    and *verified compiling* (zero `sorry`, `lake env lean` clean) the "hard
    direction" of Courant-Fischer at the abstract `LinearMap.IsSymmetric` /
    `InnerProductSpace ℝ E` level, in a scratch file (not integrated here --
    see below for why). Reproduce by pasting into a throwaway
    `Certkit/Scratch.lean` and running `lake env lean Certkit/Scratch.lean`:

    ```
    import Mathlib.Analysis.InnerProductSpace.Spectrum
    import Mathlib.Analysis.InnerProductSpace.PiL2

    open scoped Matrix RealInnerProductSpace

    variable {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E] [FiniteDimensional ℝ E]
    variable {n : ℕ} {T : E →ₗ[ℝ] E}

    private lemma inf_ne_bot_of_finrank_lt (s t : Submodule ℝ E)
        (h : Module.finrank ℝ E < Module.finrank ℝ ↥s + Module.finrank ℝ ↥t) :
        s ⊓ t ≠ ⊥ := by
      intro hbot
      have h1 : Module.finrank ℝ ↥(s ⊔ t) + Module.finrank ℝ ↥(s ⊓ t)
          = Module.finrank ℝ ↥s + Module.finrank ℝ ↥t := Submodule.finrank_sup_add_finrank_inf_eq s t
      rw [hbot] at h1
      simp at h1
      have h2 : Module.finrank ℝ ↥(s ⊔ t) ≤ Module.finrank ℝ E := Submodule.finrank_le _
      omega

    private lemma finrank_span_Iio_image [DecidableEq E] {b : Fin n → E} (hb : Orthonormal ℝ b)
        (i₀ : Fin n) :
        Module.finrank ℝ (Submodule.span ℝ ((Finset.Iio i₀).image b : Set E)) = i₀.val := by
      rw [Module.finrank_eq_card_basis (OrthonormalBasis.span hb (Finset.Iio i₀)).toBasis]
      rw [Fintype.card_coe, Fin.card_Iio]

    /-- Hard direction of Courant-Fischer: any subspace of dimension `i₀.val + 1`
    contains a nonzero vector whose Rayleigh quotient is at most `eigenvalues i₀`. -/
    theorem courant_fischer_le (hT : T.IsSymmetric) (hn : Module.finrank ℝ E = n)
        (V : Submodule ℝ E) (i₀ : Fin n) (hV : Module.finrank ℝ V = i₀.val + 1) :
        ∃ x ∈ V, x ≠ 0 ∧ ⟪x, T x⟫ ≤ hT.eigenvalues hn i₀ * ⟪x, x⟫ := by
      classical
      set b := hT.eigenvectorBasis hn with hb_def
      have hb_orth : Orthonormal ℝ b := b.orthonormal
      set U : Submodule ℝ E := Submodule.span ℝ ((Finset.Iio i₀).image b : Set E) with hU_def
      have hUfin : Module.finrank ℝ U = i₀.val := finrank_span_Iio_image hb_orth i₀
      have hWfin : Module.finrank ℝ Uᗮ = n - i₀.val := by
        have hadd := U.finrank_add_finrank_orthogonal
        rw [hn, hUfin] at hadd
        omega
      have hpigeon : V ⊓ Uᗮ ≠ ⊥ := by
        apply inf_ne_bot_of_finrank_lt
        rw [hV, hWfin, hn]
        have : i₀.val < n := i₀.isLt
        omega
      obtain ⟨x, hxmem, hxne⟩ := Submodule.ne_bot_iff _ |>.mp hpigeon
      obtain ⟨hxV, hxW⟩ := Submodule.mem_inf.mp hxmem
      refine ⟨x, hxV, hxne, ?_⟩
      have hbTb : ∀ j, T (b j) = hT.eigenvalues hn j • b j := hT.apply_eigenvectorBasis hn
      have hzero : ∀ j, j < i₀ → ⟪b j, x⟫ = 0 := by
        intro j hj
        have hbjU : b j ∈ U :=
          Submodule.subset_span (Finset.mem_coe.mpr (Finset.mem_image_of_mem b (Finset.mem_Iio.mpr hj)))
        exact Submodule.inner_right_of_mem_orthogonal hbjU hxW
      have hxx : ⟪x, x⟫ = ∑ j, ⟪b j, x⟫ ^ 2 := by
        rw [← b.sum_inner_mul_inner x x]
        congr 1
        funext j
        rw [real_inner_comm x (b j), sq]
      have hxTx : ⟪x, T x⟫ = ∑ j, hT.eigenvalues hn j * ⟪b j, x⟫ ^ 2 := by
        rw [← b.sum_inner_mul_inner x (T x)]
        congr 1
        funext j
        have hsymm : ⟪b j, T x⟫ = ⟪T (b j), x⟫ := (hT (b j) x).symm
        rw [real_inner_comm (b j) x, hsymm, hbTb j, real_inner_smul_left, sq]
        ring
      rw [hxTx, hxx, Finset.mul_sum]
      apply Finset.sum_le_sum
      intro j _
      rcases lt_or_ge j i₀ with hlt | hge
      · rw [hzero j hlt]; simp
      · have hantitone : hT.eigenvalues hn j ≤ hT.eigenvalues hn i₀ :=
          hT.eigenvalues_antitone hn hge
        nlinarith [sq_nonneg (⟪b j, x⟫)]
    ```

    Not integrated into this file because it does not by itself discharge
    `weyl_shift`: three more pieces stand between it and the theorem below,
    none attempted yet, roughly increasing in expected difficulty.

    1. **Easy direction** (companion lemma, expected tractable): for `x` in
       the span of the *top* `i₀.val + 1` eigenvectors `b 0 .. b i₀`,
       `eigenvalues i₀ * ⟪x,x⟫ ≤ ⟪x,T x⟫`. Same Parseval expansion as
       `courant_fischer_le`'s proof above, but needs "`x ∈ span (b '' s)` ⟹
       `⟪b k, x⟫ = 0` for `k ∉ s`" as a side fact -- not found ready-made in
       `Mathlib.Analysis.InnerProductSpace.{PiL2,Orthogonal}` (searched this
       session); doable directly from `Submodule.mem_span_finset` plus
       `Orthonormal`'s pairwise-orthogonality, not yet written.

    2. **Loewner monotonicity**: combine both directions to get, for
       symmetric `T_A, T_B` on the same `E` with `T_A - T_B` positive
       semidefinite, `eigenvalues_B i₀ ≤ eigenvalues_A i₀` for every `i₀`.
       Sketch (standard): apply `courant_fischer_le` to `T_A` at
       `V = span (B's top i₀+1 eigenvectors)` to get `x* ∈ V`,
       `⟪x*,T_A x*⟫ ≤ eigenvalues_A i₀ * ⟪x*,x*⟫`; combine with
       `⟪x*,T_B x*⟫ ≤ ⟪x*,T_A x*⟫` (positive semidefiniteness of
       `T_A - T_B`) and the easy direction applied to `T_B` at the same `x*`
       (`eigenvalues_B i₀ * ⟪x*,x*⟫ ≤ ⟪x*,T_B x*⟫`) to chain the inequality
       through. Not yet written; depends on (1).

    3. **Bridge to `Matrix.IsHermitian`**: `weyl_shift` is stated over
       `Matrix n n ℝ` / `hA.eigenvalues : n → ℝ`, not the abstract
       `LinearMap.IsSymmetric.eigenvalues` used above. Whether these two
       eigenvalue functions provably agree under `Matrix.toEuclideanLin` (or
       the `PiLp`/`EuclideanSpace n ℝ` identification `Mathlib.Analysis.
       Matrix.Spectrum` actually uses to define `Matrix.IsHermitian.
       eigenvalues` in the first place) was **not checked this session** --
       genuinely unknown difficulty, could be a short `simp`-able
       coincidence-of-definitions lemma or its own multi-step project.

    4. **Operator-norm sandwich**: even granting 1-3, `weyl_shift`'s stated
       form is the *shift* inequality (`|λ_i(A) - λ_i(B)| ≤ ‖A-B‖`), not raw
       Loewner monotonicity. Getting from one to the other needs
       `B - t•1 ⪯ A ⪯ B + t•1` for `t = ‖A-B‖`, i.e. that the `L²` operator
       norm of a Hermitian matrix bounds every eigenvalue in absolute value
       -- another fact not located in mathlib this session (only
       `norm_eq_iSup_rayleighQuotient`, an unindexed sup-over-all-vectors
       statement, was found; connecting it to a single indexed eigenvalue's
       absolute value is itself unproven work).

    Given three prior sessions' conclusion that this is a self-contained
    formalisation project and this session's own experience -- a genuinely
    new, verified result on step 0, with three more steps of unassessed
    (2-3) to unknown (3-4, possibly the largest) size still ahead -- this
    remains correctly scoped as its own bead rather than a session-sized
    lemma. Left `sorry`. -/
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
