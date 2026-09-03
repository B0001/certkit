/-
  certkit -- soundness obligations, stated in Lean 4 / mathlib4.

  STATUS: compiles clean against the pinned mathlib (see lake-manifest.json).
  All eight theorems below are real, zero-`sorry` proofs: `rayleigh_ritz_min`,
  `inertia_count_below`, `gershgorin_lower`, `temple_lower`, `weyl_shift`,
  `residual_encloses_some_eigenvalue`, `l2_opNorm_le_rowSum_of_isHermitian`,
  and `sweep_backward_bound`. The last two each have their own doc comment on
  exactly what they do and do not cover -- in particular `sweep_backward_bound`'s
  doc comment flags a specific, still-uncovered gap: that the row-sums
  `backward_error.sweep` accumulates at runtime actually dominate
  `‖A - Atilde‖_∞`, an `Iv`-arithmetic bookkeeping fact about that Python
  loop rather than a Lean obligation. (The norm-inequality half of that
  gap -- `‖·‖_∞` dominating the `‖·‖_2` `weyl_shift` is stated against --
  is closed by `l2_opNorm_le_rowSum_of_isHermitian`.) Every theorem
  compiling with no `sorry` is a fact about this file;
  it is not the same claim as "the checker is proved sound end-to-end" --
  that also requires the Python side to actually implement what each theorem
  states (see the correspondence table below) and requires `lake build
  Certkit` to succeed for the project as a whole, which is checked
  separately from any one theorem. Do not read this file as
  "soundness-complete" without checking both.

  The point of the file is the correspondence. The Python checker performs
  exactly two mathematical steps, and each is one theorem here:

    checker._rule_temple_inertia       upper bound  <->  rayleigh_ritz_min
                                       lower bound  <->  temple_lower
    checker.count_eigenvalues_below                 <->  inertia_count_below
    banded.count_eigenvalues_below_banded           <->  inertia_count_below
    backward_error.count_eigenvalues_below_backward <->  inertia_count_below
                                                     +   weyl_shift
                                                     +   l2_opNorm_le_rowSum_of_isHermitian
    checker._rule_gershgorin_rayleigh  lower bound  <->  gershgorin_lower

  A third obligation -- that interval arithmetic on doubles encloses the
  real result -- is the floating-point layer; it is formalised and proved,
  zero `sorry`, in `Interval.lean`.
-/

import Mathlib.Analysis.InnerProductSpace.Spectrum
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.LinearAlgebra.Matrix.Hermitian
import Mathlib.Analysis.Matrix.Spectrum
import Mathlib.Analysis.Matrix.PosDef
import Mathlib.Analysis.CStarAlgebra.Matrix
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
  obtain ⟨i₁, -⟩ := Function.ne_iff.mp hx
  set μ := rayleigh A x with hμ
  set U : Matrix n n ℝ := (hA.eigenvectorUnitary : Matrix n n ℝ) with hU
  have hUUt : U * Uᵀ = 1 := by
    rw [hU, ← Matrix.conjTranspose_eq_transpose_of_trivial, ← Matrix.star_eq_conjTranspose]
    exact Unitary.coe_mul_star_self hA.eigenvectorUnitary
  have hUtU : Uᵀ * U = 1 := by
    rw [hU, ← Matrix.conjTranspose_eq_transpose_of_trivial, ← Matrix.star_eq_conjTranspose]
    exact Unitary.coe_star_mul_self hA.eigenvectorUnitary
  set y : n → ℝ := Uᵀ *ᵥ x with hy
  have hxy : U *ᵥ y = x := by
    rw [hy, Matrix.mulVec_mulVec, hUUt, Matrix.one_mulVec]
  have horth : ∀ v : n → ℝ, (U *ᵥ v) ⬝ᵥ (U *ᵥ v) = v ⬝ᵥ v := by
    intro v
    rw [dotProduct_mulVec, ← Matrix.mulVec_transpose, Matrix.mulVec_mulVec, hUtU,
      Matrix.one_mulVec]
  have hxx : x ⬝ᵥ x = ∑ i, (y i) ^ 2 := by
    rw [← hxy, horth, dotProduct]
    exact Finset.sum_congr rfl fun i _ => (sq (y i)).symm
  have hr : A *ᵥ x - μ • x = U *ᵥ (Matrix.diagonal (fun i => hA.eigenvalues i - μ) *ᵥ y) := by
    have h1 : A *ᵥ x - μ • x = (A - μ • (1 : Matrix n n ℝ)) *ᵥ x := by
      rw [Matrix.sub_mulVec, Matrix.smul_mulVec, Matrix.one_mulVec]
    rw [h1, sub_smul_one_eq_mul_diagonal_mul_transpose hA μ, ← Matrix.mulVec_mulVec,
      ← Matrix.mulVec_mulVec, ← hy, ← hU]
  have hrr : (A *ᵥ x - μ • x) ⬝ᵥ (A *ᵥ x - μ • x)
      = ∑ i, (hA.eigenvalues i - μ) ^ 2 * (y i) ^ 2 := by
    rw [hr, horth, dotProduct]
    refine Finset.sum_congr rfl fun i _ => ?_
    rw [Matrix.mulVec_diagonal]
    ring
  obtain ⟨i₀, -, hmin⟩ :=
    Finset.exists_min_image Finset.univ (fun i => |hA.eigenvalues i - μ|) ⟨i₁, Finset.mem_univ i₁⟩
  refine ⟨i₀, ?_⟩
  set d := |hA.eigenvalues i₀ - μ| with hd
  have hbound : d ^ 2 * (x ⬝ᵥ x) ≤ (A *ᵥ x - μ • x) ⬝ᵥ (A *ᵥ x - μ • x) := by
    rw [hrr, hxx, Finset.mul_sum]
    refine Finset.sum_le_sum fun i _ => ?_
    have h1 : d ^ 2 ≤ (hA.eigenvalues i - μ) ^ 2 := by
      rw [hd, ← sq_abs (hA.eigenvalues i - μ)]
      exact pow_le_pow_left₀ (abs_nonneg _) (hmin i (Finset.mem_univ i)) 2
    nlinarith [sq_nonneg (y i)]
  have hxx_pos : 0 < x ⬝ᵥ x := by
    simpa [star_trivial] using (Matrix.dotProduct_self_star_pos_iff (v := x)).mpr hx
  show d ≤ residualNorm A x
  unfold residualNorm
  rw [← hμ, le_div_iff₀ (Real.sqrt_pos.mpr hxx_pos)]
  have hdsqrt : d * Real.sqrt (x ⬝ᵥ x) = Real.sqrt (d ^ 2 * (x ⬝ᵥ x)) := by
    rw [Real.sqrt_mul (sq_nonneg d), Real.sqrt_sq (by rw [hd]; exact abs_nonneg _)]
  rw [hdsqrt]
  exact Real.sqrt_le_sqrt hbound

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

open scoped RealInnerProductSpace

section CourantFischer

/-!
Self-contained Courant-Fischer / Loewner-monotonicity development used to
prove `weyl_shift` below. Worked out and verified in mathlib commit
`5ba95124681110751345e9bd360994de8541027c` (2026-08-28) under bead
certkit-8y2.6, after four sessions confirming mathlib has no Weyl
eigenvalue-perturbation inequality, Courant-Fischer min-max
characterisation, or comparable variational eigenvalue result under any
name (`Mathlib.Analysis.InnerProductSpace.Spectrum` has only the
*extreme*-eigenvalue facts `hasEigenvalue_iSup_of_finiteDimensional` /
`hasEigenvalue_iInf_of_finiteDimensional`, no indexed statement;
`Mathlib.Analysis.InnerProductSpace.Rayleigh` has only the unindexed
`norm_eq_iSup_rayleighQuotient`). Everything from here to `weyl_shift`
is derived from mathlib primitives -- no numeric constant is transcribed
and no step is asserted without proof.
-/

variable {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E] [FiniteDimensional ℝ E]
variable {k : ℕ} {T TWeyl : E →ₗ[ℝ] E}

private lemma weyl_inf_ne_bot_of_finrank_lt (s t : Submodule ℝ E)
    (h : Module.finrank ℝ E < Module.finrank ℝ ↥s + Module.finrank ℝ ↥t) :
    s ⊓ t ≠ ⊥ := by
  intro hbot
  have h1 : Module.finrank ℝ ↥(s ⊔ t) + Module.finrank ℝ ↥(s ⊓ t)
      = Module.finrank ℝ ↥s + Module.finrank ℝ ↥t := Submodule.finrank_sup_add_finrank_inf_eq s t
  rw [hbot] at h1
  simp at h1
  have h2 : Module.finrank ℝ ↥(s ⊔ t) ≤ Module.finrank ℝ E := Submodule.finrank_le _
  omega

private lemma weyl_finrank_span_Iio_image [DecidableEq E] {b : Fin k → E} (hb : Orthonormal ℝ b)
    (i₀ : Fin k) :
    Module.finrank ℝ (Submodule.span ℝ ((Finset.Iio i₀).image b : Set E)) = i₀.val := by
  rw [Module.finrank_eq_card_basis (OrthonormalBasis.span hb (Finset.Iio i₀)).toBasis]
  rw [Fintype.card_coe, Fin.card_Iio]

private lemma weyl_finrank_span_Iic_image [DecidableEq E] {b : Fin k → E} (hb : Orthonormal ℝ b)
    (i₀ : Fin k) :
    Module.finrank ℝ (Submodule.span ℝ ((Finset.Iic i₀).image b : Set E)) = i₀.val + 1 := by
  rw [Module.finrank_eq_card_basis (OrthonormalBasis.span hb (Finset.Iic i₀)).toBasis]
  rw [Fintype.card_coe, Fin.card_Iic]

/-- Hard direction of Courant-Fischer: any subspace of dimension `i₀.val + 1`
contains a nonzero vector whose Rayleigh quotient is at most `eigenvalues i₀`. -/
private theorem weyl_courant_fischer_le (hT : T.IsSymmetric) (hk : Module.finrank ℝ E = k)
    (V : Submodule ℝ E) (i₀ : Fin k) (hV : Module.finrank ℝ V = i₀.val + 1) :
    ∃ x ∈ V, x ≠ 0 ∧ ⟪x, T x⟫ ≤ hT.eigenvalues hk i₀ * ⟪x, x⟫ := by
  classical
  set b := hT.eigenvectorBasis hk with hb_def
  have hb_orth : Orthonormal ℝ b := b.orthonormal
  set U : Submodule ℝ E := Submodule.span ℝ ((Finset.Iio i₀).image b : Set E) with hU_def
  have hUfin : Module.finrank ℝ U = i₀.val := weyl_finrank_span_Iio_image hb_orth i₀
  have hWfin : Module.finrank ℝ Uᗮ = k - i₀.val := by
    have hadd := U.finrank_add_finrank_orthogonal
    rw [hk, hUfin] at hadd
    omega
  have hpigeon : V ⊓ Uᗮ ≠ ⊥ := by
    apply weyl_inf_ne_bot_of_finrank_lt
    rw [hV, hWfin, hk]
    have : i₀.val < k := i₀.isLt
    omega
  obtain ⟨x, hxmem, hxne⟩ := Submodule.ne_bot_iff _ |>.mp hpigeon
  obtain ⟨hxV, hxW⟩ := Submodule.mem_inf.mp hxmem
  refine ⟨x, hxV, hxne, ?_⟩
  have hbTb : ∀ j, T (b j) = hT.eigenvalues hk j • b j := hT.apply_eigenvectorBasis hk
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
  have hxTx : ⟪x, T x⟫ = ∑ j, hT.eigenvalues hk j * ⟪b j, x⟫ ^ 2 := by
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
  · have hantitone : hT.eigenvalues hk j ≤ hT.eigenvalues hk i₀ :=
      hT.eigenvalues_antitone hk hge
    nlinarith [sq_nonneg (⟪b j, x⟫)]

/-- Easy direction of Courant-Fischer: any vector in the span of the top
`i₀.val + 1` eigenvectors has Rayleigh quotient at least `eigenvalues i₀`. -/
private theorem weyl_courant_fischer_ge (hT : T.IsSymmetric) (hk : Module.finrank ℝ E = k)
    (i₀ : Fin k) (x : E)
    (hx : x ∈ Submodule.span ℝ (hT.eigenvectorBasis hk '' (↑(Finset.Iic i₀) : Set (Fin k)))) :
    hT.eigenvalues hk i₀ * ⟪x, x⟫ ≤ ⟪x, T x⟫ := by
  set b := hT.eigenvectorBasis hk with hb_def
  have hbTb : ∀ j, T (b j) = hT.eigenvalues hk j • b j := hT.apply_eigenvectorBasis hk
  have hxmem : x ∈ Submodule.span ℝ (b.toBasis '' (↑(Finset.Iic i₀) : Set (Fin k))) := by
    rwa [OrthonormalBasis.coe_toBasis]
  have hsupp : ↑(b.toBasis.repr x).support ⊆ (↑(Finset.Iic i₀) : Set (Fin k)) :=
    b.toBasis.mem_span_image.mp hxmem
  have hzero : ∀ j, i₀ < j → ⟪b j, x⟫ = 0 := by
    intro j hj
    have hjnotin : j ∉ Finset.Iic i₀ := by simp [Finset.mem_Iic, not_le.mpr hj]
    have : (b.toBasis.repr x) j = 0 := by
      by_contra hne
      exact hjnotin (hsupp (Finsupp.mem_support_iff.mpr hne))
    rw [OrthonormalBasis.coe_toBasis_repr_apply] at this
    rw [← b.repr_apply_apply x j]
    exact this
  have hxx : ⟪x, x⟫ = ∑ j, ⟪b j, x⟫ ^ 2 := by
    rw [← b.sum_inner_mul_inner x x]
    congr 1
    funext j
    rw [real_inner_comm x (b j), sq]
  have hxTx : ⟪x, T x⟫ = ∑ j, hT.eigenvalues hk j * ⟪b j, x⟫ ^ 2 := by
    rw [← b.sum_inner_mul_inner x (T x)]
    congr 1
    funext j
    have hsymm : ⟪b j, T x⟫ = ⟪T (b j), x⟫ := (hT (b j) x).symm
    rw [real_inner_comm (b j) x, hsymm, hbTb j, real_inner_smul_left, sq]
    ring
  rw [hxTx, hxx, Finset.mul_sum]
  apply Finset.sum_le_sum
  intro j _
  rcases lt_or_ge i₀ j with hlt | hge
  · rw [hzero j hlt]; simp
  · have hantitone : hT.eigenvalues hk i₀ ≤ hT.eigenvalues hk j :=
      hT.eigenvalues_antitone hk hge
    nlinarith [sq_nonneg (⟪b j, x⟫)]

/-- Shifted one-sided Loewner comparison: if `T - TWeyl` is bounded above by
`c • 1` (in Rayleigh-quotient form), every `T`-eigenvalue is at most the
corresponding `TWeyl`-eigenvalue plus `c`, at the same index. -/
private theorem weyl_eigenvalues_sub_le (hT : T.IsSymmetric) (hTW : TWeyl.IsSymmetric)
    (hk : Module.finrank ℝ E = k) (c : ℝ)
    (hbound : ∀ x, ⟪x, (T - TWeyl) x⟫ ≤ c * ⟪x, x⟫) (i₀ : Fin k) :
    hT.eigenvalues hk i₀ ≤ hTW.eigenvalues hk i₀ + c := by
  classical
  set bT := hT.eigenvectorBasis hk with hbT_def
  set V : Submodule ℝ E := Submodule.span ℝ ((Finset.Iic i₀).image bT : Set E) with hV_def
  have hVfin : Module.finrank ℝ V = i₀.val + 1 := weyl_finrank_span_Iic_image bT.orthonormal i₀
  obtain ⟨x, hxV, hxne, hxleTW⟩ := weyl_courant_fischer_le hTW hk V i₀ hVfin
  have hxV' : x ∈ Submodule.span ℝ (bT '' (↑(Finset.Iic i₀) : Set (Fin k))) := by
    rw [hV_def, Finset.coe_image] at hxV; exact hxV
  have hxgeT : hT.eigenvalues hk i₀ * ⟪x, x⟫ ≤ ⟪x, T x⟫ := weyl_courant_fischer_ge hT hk i₀ x hxV'
  have hxx_pos : 0 < ⟪x, x⟫ := real_inner_self_pos.mpr hxne
  have hbound_x : ⟪x, T x⟫ ≤ ⟪x, TWeyl x⟫ + c * ⟪x, x⟫ := by
    have h := hbound x
    rw [LinearMap.sub_apply, inner_sub_right] at h
    linarith
  have hchain : hT.eigenvalues hk i₀ * ⟪x, x⟫ ≤ (hTW.eigenvalues hk i₀ + c) * ⟪x, x⟫ := by
    rw [add_mul]
    linarith [hxgeT, hxleTW, hbound_x]
  exact le_of_mul_le_mul_right hchain hxx_pos

/-- Abstract Weyl shift: if `T - TWeyl`'s Rayleigh quotient is bounded in
absolute value by `c * ⟪x,x⟫`, every eigenvalue moves by at most `c`. -/
private theorem weyl_shift_abstract (hT : T.IsSymmetric) (hTW : TWeyl.IsSymmetric)
    (hk : Module.finrank ℝ E = k) (c : ℝ)
    (hbound : ∀ x, |⟪x, (T - TWeyl) x⟫| ≤ c * ⟪x, x⟫) (i₀ : Fin k) :
    |hT.eigenvalues hk i₀ - hTW.eigenvalues hk i₀| ≤ c := by
  rw [abs_le]
  refine ⟨?_, ?_⟩
  · have h := weyl_eigenvalues_sub_le hTW hT hk c (fun x => by
      have h1 := (abs_le.mp (hbound x)).1
      have h2 : ⟪x, (TWeyl - T) x⟫ = -⟪x, (T - TWeyl) x⟫ := by
        rw [LinearMap.sub_apply, LinearMap.sub_apply, inner_sub_right, inner_sub_right]; ring
      rw [h2]; linarith)
    linarith [h i₀]
  · have h := weyl_eigenvalues_sub_le hT hTW hk c (fun x => (abs_le.mp (hbound x)).2)
    linarith [h i₀]

end CourantFischer

open scoped Matrix.Norms.L2Operator

/-- Cauchy-Schwarz + operator-norm sandwich: the Rayleigh quotient of a real
matrix `M` (via `toEuclideanLin`) is bounded in absolute value by
`‖M‖ * ⟪x,x⟫`, where `‖M‖` is the `L²` operator norm. -/
private lemma weyl_abs_inner_toEuclideanLin_le (M : Matrix n n ℝ) (x : EuclideanSpace ℝ n) :
    |⟪x, Matrix.toEuclideanLin M x⟫| ≤ ‖M‖ * ⟪x, x⟫ := by
  have h1 : |⟪x, Matrix.toEuclideanLin M x⟫| ≤ ‖x‖ * ‖Matrix.toEuclideanLin M x‖ :=
    abs_real_inner_le_norm x (Matrix.toEuclideanLin M x)
  have h2 : ‖Matrix.toEuclideanLin M x‖ ≤ ‖M‖ * ‖x‖ := by
    rw [← Matrix.l2_opNorm_toEuclideanCLM M]
    exact (Matrix.toEuclideanCLM (n := n) (𝕜 := ℝ) M).le_opNorm x
  have h3 : ⟪x, x⟫ = ‖x‖ * ‖x‖ := real_inner_self_eq_norm_mul_norm x
  calc |⟪x, Matrix.toEuclideanLin M x⟫| ≤ ‖x‖ * ‖Matrix.toEuclideanLin M x‖ := h1
    _ ≤ ‖x‖ * (‖M‖ * ‖x‖) := by gcongr
    _ = ‖M‖ * (‖x‖ * ‖x‖) := by ring
    _ = ‖M‖ * ⟪x, x⟫ := by rw [h3]

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
    against). It is *not* the entrywise/row-sum bound `sturm_be` actually
    computes at runtime; relating the two is a separate obligation, proved
    below as `l2_opNorm_le_rowSum_of_isHermitian` (for Hermitian matrices,
    the L² operator norm is bounded by the row-sum norm), not by this
    theorem.

    Proved from mathlib primitives via the `CourantFischer` section above:
    Courant-Fischer min-max (both directions) at the abstract
    `LinearMap.IsSymmetric` level, specialised to `T := A.toEuclideanLin` /
    `TWeyl := B.toEuclideanLin` (the bridge from `Matrix.IsHermitian.
    eigenvalues` to the abstract `LinearMap.IsSymmetric.eigenvalues` is
    definitional -- `rfl` -- via `Matrix.isSymmetric_toEuclideanLin_iff` and
    `finrank_euclideanSpace`, exactly how `Matrix.IsHermitian.eigenvalues₀`
    itself is defined in `Mathlib.Analysis.Matrix.Spectrum`), combined with
    the Cauchy-Schwarz/operator-norm sandwich
    `weyl_abs_inner_toEuclideanLin_le` above. No numeric constant is
    transcribed; every step is a mathlib lemma application. -/
theorem weyl_shift {B : Matrix n n ℝ} (hB : B.IsHermitian) (i : n) :
    |hA.eigenvalues i - hB.eigenvalues i| ≤ ‖A - B‖ := by
  have hTA : (Matrix.toEuclideanLin A).IsSymmetric := Matrix.isSymmetric_toEuclideanLin_iff.mpr hA
  have hTB : (Matrix.toEuclideanLin B).IsSymmetric := Matrix.isSymmetric_toEuclideanLin_iff.mpr hB
  have hbound : ∀ x : EuclideanSpace ℝ n,
      |⟪x, (Matrix.toEuclideanLin A - Matrix.toEuclideanLin B) x⟫| ≤ ‖A - B‖ * ⟪x, x⟫ := by
    intro x
    have hsub : Matrix.toEuclideanLin A - Matrix.toEuclideanLin B
        = Matrix.toEuclideanLin (A - B) := (map_sub Matrix.toEuclideanLin A B).symm
    rw [hsub]
    exact weyl_abs_inner_toEuclideanLin_le (A - B) x
  have hw := weyl_shift_abstract hTA hTB finrank_euclideanSpace ‖A - B‖ hbound
      ((Fintype.equivOfCardEq (Fintype.card_fin (Fintype.card n))).symm i)
  have heqA : hTA.eigenvalues finrank_euclideanSpace
      ((Fintype.equivOfCardEq (Fintype.card_fin (Fintype.card n))).symm i) = hA.eigenvalues i := rfl
  have heqB : hTB.eigenvalues finrank_euclideanSpace
      ((Fintype.equivOfCardEq (Fintype.card_fin (Fintype.card n))).symm i) = hB.eigenvalues i := rfl
  rwa [heqA, heqB] at hw

/-- **Row-sum dominates the L² operator norm, for symmetric matrices.** This
    is the gap `weyl_shift`'s doc comment above and `sweep_backward_bound`'s
    doc comment below both flag as open: `sturm_be` bounds the perturbation
    `E := A - Atilde` from the entries via a row sum `∑ j, |E i j|` (the
    operator norm mathlib calls `Matrix.linfty_opNNNorm_def`; spelled out
    here directly rather than opened as its own scoped norm instance, since
    that scope's `‖·‖` notation would clash with `Matrix.Norms.L2Operator`,
    already open in this section), while `weyl_shift` needs that bound
    against the L² operator norm. `backward_error.py`'s module docstring
    asserts the link in one line -- `delta >= ‖A - Atilde‖_2 (via ‖E‖_2 ≤
    ‖E‖_inf for symmetric E)` -- and this theorem is that assertion, proved.

    Assumes `[Nonempty n]` only so the row-sum bound `M` can be taken as a
    `Finset.sup'` (which needs a witness element) instead of detouring
    through `ℝ≥0`; every real use of this theorem is a tridiagonal sweep
    with `n ≥ 1`, so nothing is lost.

    **Proof (Schur test).** Let `M` bound every row sum. For any `x`,
    Cauchy-Schwarz on row `i` (weighted by `|E i j|`) gives
    `(∑ j, |E i j| * |x j|) ^ 2 ≤ (∑ j, |E i j|) * ∑ j, |E i j| * x j ^ 2
                                 ≤ M * ∑ j, |E i j| * x j ^ 2`,
    and the triangle inequality bounds `|(E x) i|` by that same LHS. Summing
    over `i` and swapping the order of summation turns the inner sum into a
    sum over columns weighted by `∑ i, |E i j|`, which by symmetry
    (`E i j = E j i`, from `hE`) is itself a row sum and so also `≤ M`. This
    gives `‖E x‖ ^ 2 ≤ M ^ 2 * ‖x‖ ^ 2`, i.e. `‖E x‖ ≤ M * ‖x‖` for every `x`
    -- exactly the defining bound on the operator norm. No numeric constant
    is transcribed: the classical fact used is `‖E‖_1 = ‖E‖_∞` for symmetric
    `E` (row sums equal column sums) combined with the interpolation bound
    `‖E‖_2 ≤ sqrt (‖E‖_1 * ‖E‖_∞)`, done directly via Cauchy-Schwarz rather
    than via a named interpolation theorem, since mathlib does not carry one
    for finite matrices. -/
theorem l2_opNorm_le_rowSum_of_isHermitian [Nonempty n] {E : Matrix n n ℝ}
    (hE : E.IsHermitian) :
    ‖E‖ ≤ (Finset.univ : Finset n).sup' Finset.univ_nonempty (fun i => ∑ j, |E i j|) := by
  set M : ℝ := (Finset.univ : Finset n).sup' Finset.univ_nonempty (fun i => ∑ j, |E i j|)
    with hM_def
  have hMi : ∀ i, ∑ j, |E i j| ≤ M := fun i => by
    rw [hM_def]; exact Finset.le_sup' (f := fun i => ∑ j, |E i j|) (Finset.mem_univ i)
  have hM0 : 0 ≤ M :=
    le_trans (Finset.sum_nonneg fun j _ => abs_nonneg _) (hMi (Classical.arbitrary n))
  have hsymm : ∀ i j, E i j = E j i := fun i j => by
    have h := hE.apply i j; simp only [star_trivial] at h; exact h.symm
  have hcol : ∀ j, ∑ i, |E i j| ≤ M := fun j => by
    have heq : (∑ i, |E i j|) = ∑ i, |E j i| :=
      Finset.sum_congr rfl fun i _ => by rw [hsymm i j]
    rw [heq]; exact hMi j
  rw [← Matrix.l2_opNorm_toEuclideanCLM]
  refine ContinuousLinearMap.opNorm_le_bound _ hM0 fun x => ?_
  set y : EuclideanSpace ℝ n → n → ℝ := fun z i => (toEuclideanCLM (n := n) (𝕜 := ℝ) E z) i
    with hy_def
  have hEx : y x = fun i => ∑ j, E i j * x j := by
    funext i
    show ((toEuclideanCLM (n := n) (𝕜 := ℝ) E) x).ofLp i = ∑ j, E i j * x j
    rw [ofLp_toEuclideanCLM, Matrix.mulVec_apply_eq_sum]
  have hrow : ∀ i, |y x i| ^ 2 ≤ (∑ j, |E i j|) * ∑ j, |E i j| * x j ^ 2 := by
    intro i
    have hxi : y x i = ∑ j, E i j * x j := congrFun hEx i
    rw [hxi]
    calc |∑ j, E i j * x j| ^ 2
        ≤ (∑ j, |E i j * x j|) ^ 2 := by
          gcongr
          exact Finset.abs_sum_le_sum_abs _ _
      _ = (∑ j, |E i j| * |x j|) ^ 2 := by simp [abs_mul]
      _ ≤ (∑ j, |E i j|) * ∑ j, |E i j| * x j ^ 2 := by
          have hcs := Finset.sum_mul_sq_le_sq_mul_sq (Finset.univ : Finset n)
            (fun j => Real.sqrt |E i j|) (fun j => Real.sqrt |E i j| * |x j|)
          have heq1 : ∀ j, Real.sqrt |E i j| * (Real.sqrt |E i j| * |x j|) = |E i j| * |x j| :=
            fun j => by rw [← mul_assoc, Real.mul_self_sqrt (abs_nonneg _)]
          have heq2 : ∀ j, Real.sqrt |E i j| ^ 2 = |E i j| := fun j => Real.sq_sqrt (abs_nonneg _)
          have heq3 : ∀ j, (Real.sqrt |E i j| * |x j|) ^ 2 = |E i j| * x j ^ 2 := fun j => by
            rw [mul_pow, heq2, sq_abs]
          simpa only [heq1, heq2, heq3] using hcs
  have hsum : ∑ i, |y x i| ^ 2 ≤ M * ∑ j, x j ^ 2 * ∑ i, |E i j| :=
    calc ∑ i, |y x i| ^ 2
        ≤ ∑ i, (∑ j, |E i j|) * ∑ j, |E i j| * x j ^ 2 := Finset.sum_le_sum fun i _ => hrow i
      _ ≤ ∑ i, M * ∑ j, |E i j| * x j ^ 2 := by
          refine Finset.sum_le_sum fun i _ => ?_
          gcongr
          exact hMi i
      _ = M * ∑ i, ∑ j, |E i j| * x j ^ 2 := by rw [Finset.mul_sum]
      _ = M * ∑ j, ∑ i, |E i j| * x j ^ 2 := by rw [Finset.sum_comm]
      _ = M * ∑ j, x j ^ 2 * ∑ i, |E i j| := by
          congr 1
          refine Finset.sum_congr rfl fun j _ => ?_
          rw [← Finset.sum_mul, mul_comm]
  have hMx : ∑ j, x j ^ 2 * ∑ i, |E i j| ≤ M * ∑ j, x j ^ 2 := by
    calc ∑ j, x j ^ 2 * ∑ i, |E i j|
        ≤ ∑ j, x j ^ 2 * M :=
          Finset.sum_le_sum fun j _ => mul_le_mul_of_nonneg_left (hcol j) (sq_nonneg _)
      _ = M * ∑ j, x j ^ 2 := by rw [← Finset.sum_mul, mul_comm]
  have goal_sq : ‖toEuclideanCLM (n := n) (𝕜 := ℝ) E x‖ ^ 2 ≤ (M * ‖x‖) ^ 2 := by
    have hxnorm : ‖toEuclideanCLM (n := n) (𝕜 := ℝ) E x‖ ^ 2 = ∑ i, |y x i| ^ 2 := by
      rw [EuclideanSpace.real_norm_sq_eq]
      exact Finset.sum_congr rfl fun i _ => (sq_abs _).symm
    rw [hxnorm, mul_pow, EuclideanSpace.real_norm_sq_eq x]
    calc ∑ i, |y x i| ^ 2 ≤ M * ∑ j, x j ^ 2 * ∑ i, |E i j| := hsum
      _ ≤ M * (M * ∑ j, x j ^ 2) := by gcongr
      _ = M ^ 2 * ∑ i, x i ^ 2 := by ring
  calc ‖toEuclideanCLM (n := n) (𝕜 := ℝ) E x‖
      = Real.sqrt (‖toEuclideanCLM (n := n) (𝕜 := ℝ) E x‖ ^ 2) := (Real.sqrt_sq (norm_nonneg _)).symm
    _ ≤ Real.sqrt ((M * ‖x‖) ^ 2) := Real.sqrt_le_sqrt goal_sq
    _ = M * ‖x‖ := Real.sqrt_sq (mul_nonneg hM0 (norm_nonneg _))

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
    the one-rounding algebra). That the row-sum norm `‖·‖_∞` in turn dominates
    the operator norm `‖·‖_2` used by `weyl_shift` above is a separate,
    general Hermitian-matrix norm inequality, unrelated to rounding -- it is
    proved above as `l2_opNorm_le_rowSum_of_isHermitian`, not by this
    theorem. Only the `Iv`-arithmetic bookkeeping fact remains open here,
    covered by the Python test suite, not by this theorem. -/
theorem sweep_backward_bound {u e0 e1 e2 e3 a beta bprev dprev : ℝ}
    (hu : 0 ≤ u) (hu1 : u ≤ 1 / 32)
    (h0 : |e0| ≤ u) (h1 : |e1| ≤ u) (h2 : |e2| ≤ u) (h3 : |e3| ≤ u) :
    (((a - beta) * (1 + e2) - (bprev ^ 2 * (1 + e0) / dprev) * (1 + e1)) * (1 + e3)
        = (a - beta) * (1 + eta_of e2 e3) - bprev ^ 2 * (1 + gamma_of e0 e1 e3) / dprev)
      ∧ |eta_of e2 e3| ≤ 2.1 * u ∧ |gamma_of e0 e1 e3| ≤ 3.1 * u :=
  sweep_step_backward_bound hu hu1 h0 h1 h2 h3

end Certkit
