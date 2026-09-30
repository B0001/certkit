import Certkit.Soundness
import Mathlib.LinearAlgebra.StdBasis
import Mathlib.LinearAlgebra.FiniteDimensional.Lemmas
import Mathlib.LinearAlgebra.Matrix.NonsingularInverse

/-!
# Complex-Hermitian tight route: LDL^H and Sylvester's law (`certkit-v3e`)

`certkit-1y7`'s `hermitian_temple_inertia` rule is built on
`checker.count_eigenvalues_below_hermitian`, which factors `A - β·I` over
`CIv` (complex interval arithmetic) as `L D Lᴴ` with `L` unit-lower-
triangular complex and `D` real, then reads off the number of eigenvalues of
`A` below `β` as the number of negative entries of `D`. The real-valued
analogue (`count_eigenvalues_below`/LDL^T) is formalized by
`Soundness.inertia_count_below`, whose proof leans on
`QuadraticForm.sigNeg_of_equiv_weightedSumSquares` -- a real-quadratic-form
fact with no complex/Hermitian counterpart anywhere in mathlib (confirmed by
exhaustive search of `Mathlib.LinearAlgebra.QuadraticForm.Signature`, the
only file with any `Signature`/`sigNeg` content, and it is hard-coded to
`[LinearOrder R]`, which `ℂ` does not have and cannot have compatibly with
its field structure).

Rather than transcribing Sylvester's law as an unproven constant, or
declining the obligation as an obstruction, this file rebuilds the classical
*elementary* proof of Sylvester's law of inertia from scratch, using only
mathlib primitives that are already generic in the base ring/field
(`Matrix.PosSemidef`, `Pi.spanSubset`, `Submodule.finrank_add_finrank_le_of_disjoint`,
the spectral theorem for `RCLike`). The argument: if `x` is supported on the
"D-negative" index set and its image under the congruence is supported on
the "Δ-nonnegative" index set, expanding the quadratic identity forces
`x = 0` -- so the image of the D-negative coordinate subspace is disjoint
from the Δ-nonnegative coordinate subspace, and a dimension count over the
ambient `n`-dimensional space bounds one negative-count by the other. Running
the same argument with the congruence inverted gives the reverse inequality,
hence equality. This is the textbook "maximal negative subspace" proof of
Sylvester's law, re-derived here for the concrete diagonal-congruence
instance the checker needs (not a general reusable `Signature` theory).

Two obligations, matching the docstring of
`checker.count_eigenvalues_below_hermitian`:

1. `hermitianRecon`/`hermitianRecon_diag`/`hermitianRecon_offdiag`: the LDL^H
   pivot recurrences reproduce `A` when multiplied back out. Direct complex
   analogue of `BandedBackwardError.bandedRecon` and its `_diag`/`_offdiag`
   lemmas, with a `starRingEnd ℂ` inserted on the second `L` factor.
2. `hermitian_inertia_count_below`: Sylvester's law of inertia for the
   specific Hermitian-congruence instance the checker relies on -- the
   number of negative pivots of `D` equals the number of eigenvalues of `A`
   below `β`.
-/

namespace Certkit

open Matrix Module

/-! ## Obligation 1: LDL^H reconstruction correctness -/

/-- The `(i, j)` entry of `L * diagonal D * Lᴴ`, unfolded as the sum over the
    shared prefix `k ≤ min i j`. Complex analogue of `bandedRecon`, with a
    conjugate inserted on the second `L` factor to match `Lᴴ`. -/
noncomputable def hermitianRecon (L : ℕ → ℕ → ℂ) (D : ℕ → ℝ) (i j : ℕ) : ℂ :=
  ∑ k ∈ Finset.range (min i j + 1), L i k * (starRingEnd ℂ) (L j k) * (D k : ℂ)

/-- `hermitianRecon` is conjugate-symmetric in its two indices, matching
    `A i j = conj (A j i)` for Hermitian `A`. -/
theorem hermitianRecon_conj_symm (L : ℕ → ℕ → ℂ) (D : ℕ → ℝ) (i j : ℕ) :
    (starRingEnd ℂ) (hermitianRecon L D i j) = hermitianRecon L D j i := by
  unfold hermitianRecon
  rw [min_comm i j, map_sum]
  refine Finset.sum_congr rfl fun k _ => ?_
  simp only [map_mul, Complex.conj_conj]
  rw [Complex.conj_ofReal]
  ring

/-- Diagonal pivot recurrence: `D[j] = A[j][j] - Σ_{k<j} |L[j][k]|² D[k]`,
    rearranged as a reconstruction identity. -/
theorem hermitianRecon_diag (L : ℕ → ℕ → ℂ) (D : ℕ → ℝ) (hLdiag : ∀ i, L i i = 1) (j : ℕ) :
    hermitianRecon L D j j =
      (D j : ℂ) + ∑ k ∈ Finset.range j, L j k * (starRingEnd ℂ) (L j k) * (D k : ℂ) := by
  unfold hermitianRecon
  rw [min_self, Finset.sum_range_succ, hLdiag j, map_one]
  ring

/-- Off-diagonal pivot recurrence:
    `L[i][j] = (A[i][j] - Σ_{k<j} L[i][k] D[k] conj(L[j][k])) / D[j]`,
    rearranged as a reconstruction identity, for `j < i`. -/
theorem hermitianRecon_offdiag (L : ℕ → ℕ → ℂ) (D : ℕ → ℝ) (hLdiag : ∀ i, L i i = 1)
    {i j : ℕ} (hij : j < i) :
    hermitianRecon L D i j =
      (∑ k ∈ Finset.range j, L i k * (starRingEnd ℂ) (L j k) * (D k : ℂ)) + L i j * (D j : ℂ) := by
  unfold hermitianRecon
  rw [min_eq_right hij.le, Finset.sum_range_succ, hLdiag j, map_one]
  ring

/-! ## Obligation 2: Sylvester's law of inertia for Hermitian congruence -/

variable {n : Type*} [Fintype n] [DecidableEq n]

/-- Expanding a congruence-transformed quadratic form by substituting
    `y := B *ᵥ x`. The same rewrite mathlib's
    `Matrix.PosSemidef.mul_mul_conjTranspose_same` uses to reduce a
    congruence to `A`'s own quadratic form -- recorded here as an equality
    (mathlib's version only needs the resulting inequality). -/
private lemma quadCongr (A B : Matrix n n ℂ) (x : n → ℂ) :
    star x ⬝ᵥ ((Bᴴ * A * B) *ᵥ x) = star (B *ᵥ x) ⬝ᵥ (A *ᵥ (B *ᵥ x)) := by
  rw [← Matrix.mulVec_mulVec, ← Matrix.mulVec_mulVec, Matrix.dotProduct_mulVec,
    ← Matrix.star_mulVec]

/-- Specializing `quadCongr` to a diagonal middle matrix turns the
    congruence form into the weighted sum of squared norms the checker's
    pivot recurrence is built on. -/
private lemma quadCongr_diagonal (d : n → ℝ) (B : Matrix n n ℂ) (x : n → ℂ) :
    star x ⬝ᵥ ((Bᴴ * Matrix.diagonal (fun i => (d i : ℂ)) * B) *ᵥ x)
      = ((∑ i, d i * Complex.normSq ((B *ᵥ x) i) : ℝ) : ℂ) := by
  rw [quadCongr]
  unfold dotProduct
  push_cast
  refine Finset.sum_congr rfl fun i _ => ?_
  have hz : (B *ᵥ x) i * star ((B *ᵥ x) i) = (Complex.normSq ((B *ᵥ x) i) : ℂ) := by
    rw [← starRingEnd_apply]; exact Complex.mul_conj _
  rw [Matrix.mulVec_diagonal, Pi.star_apply,
    show star ((B *ᵥ x) i) * ((d i : ℂ) * (B *ᵥ x) i)
        = (d i : ℂ) * ((B *ᵥ x) i * star ((B *ᵥ x) i)) from by ring,
    hz]

/-- Pushing a submodule forward along an injective linear map preserves its
    finite rank. The elementary fact underlying "an invertible change of
    variables doesn't change dimension," specialized to `p.map f` for an
    arbitrary submodule `p` (not just `f`'s whole range). -/
private lemma finrank_map_eq_of_injective {f : (n → ℂ) →ₗ[ℂ] (n → ℂ)}
    (hf : Function.Injective f) (p : Submodule ℂ (n → ℂ)) :
    Module.finrank ℂ (p.map f) = Module.finrank ℂ p := by
  have hpinj : Function.Injective (f.domRestrict p) := by
    intro x y h
    refine Subtype.ext (hf ?_)
    simpa only [LinearMap.domRestrict_apply] using h
  rw [← LinearMap.range_domRestrict p f]
  exact LinearMap.finrank_range_of_inj hpinj

/-- If a congruence by an invertible complex matrix `M` carries the weighted
    quadratic form of `D` to that of `Δ`, then `D` has at most as many
    negative entries as `Δ`. Half of the elementary "maximal negative
    subspace" proof of Sylvester's law of inertia. -/
private lemma card_neg_le_of_congr (D Δ : n → ℝ) (M : Matrix n n ℂ) (hM : IsUnit M)
    (hcongr : ∀ x : n → ℂ,
      ∑ i, D i * Complex.normSq (x i) = ∑ i, Δ i * Complex.normSq ((M *ᵥ x) i)) :
    {i | D i < 0}.ncard ≤ {i | Δ i < 0}.ncard := by
  classical
  have hMinj : Function.Injective M.mulVec := Matrix.mulVec_injective_iff_isUnit.2 hM
  have hMLinj : Function.Injective M.mulVecLin := by
    intro a b hab
    exact hMinj (by simpa only [Matrix.mulVecLin_apply] using hab)
  set S : Set n := {i | D i < 0} with hSdef
  set T : Set n := {i | 0 ≤ Δ i} with hTdef
  have hSTdisjoint :
      Disjoint (Submodule.map M.mulVecLin (Pi.spanSubset ℂ S)) (Pi.spanSubset ℂ T) := by
    rw [Submodule.disjoint_def]
    rintro y hy hyT
    obtain ⟨x, hxS, rfl⟩ := Submodule.mem_map.mp hy
    have htermD : ∀ i ∈ (Finset.univ : Finset n), D i * Complex.normSq (x i) ≤ 0 := by
      intro i _
      by_cases hiS : i ∈ S
      · exact mul_nonpos_of_nonpos_of_nonneg hiS.le (Complex.normSq_nonneg _)
      · have hxi0 : x i = 0 := Pi.mem_spanSubset_iff.mp hxS i hiS
        simp [hxi0]
    have htermΔ :
        ∀ i ∈ (Finset.univ : Finset n), 0 ≤ Δ i * Complex.normSq ((M.mulVecLin x) i) := by
      intro i _
      by_cases hiT : i ∈ T
      · exact mul_nonneg hiT (Complex.normSq_nonneg _)
      · have hyi0 : (M.mulVecLin x) i = 0 := Pi.mem_spanSubset_iff.mp hyT i hiT
        simp [hyi0]
    have hle : ∑ i, D i * Complex.normSq (x i) ≤ 0 := Finset.sum_nonpos htermD
    have hge : 0 ≤ ∑ i, Δ i * Complex.normSq ((M.mulVecLin x) i) := Finset.sum_nonneg htermΔ
    have hcongr' : ∑ i, D i * Complex.normSq (x i)
        = ∑ i, Δ i * Complex.normSq ((M.mulVecLin x) i) := by
      simpa only [Matrix.mulVecLin_apply] using hcongr x
    rw [hcongr'] at hle
    have hDsum_zero : ∑ i, Δ i * Complex.normSq ((M.mulVecLin x) i) = 0 := le_antisymm hle hge
    rw [← hcongr'] at hDsum_zero
    have heq0 : ∀ i ∈ (Finset.univ : Finset n), D i * Complex.normSq (x i) = 0 :=
      (Finset.sum_eq_zero_iff_of_nonpos htermD).mp hDsum_zero
    have hx0 : x = 0 := by
      funext i
      by_cases hiS : i ∈ S
      · have hDi : D i ≠ 0 := ne_of_lt hiS
        rcases mul_eq_zero.mp (heq0 i (Finset.mem_univ i)) with h | h
        · exact absurd h hDi
        · exact Complex.normSq_eq_zero.mp h
      · exact Pi.mem_spanSubset_iff.mp hxS i hiS
    simp [hx0]
  have hMapFinrank :
      Module.finrank ℂ (Submodule.map M.mulVecLin (Pi.spanSubset ℂ S))
        = Module.finrank ℂ (Pi.spanSubset ℂ S) :=
    finrank_map_eq_of_injective hMLinj (Pi.spanSubset ℂ S)
  have hbound := Submodule.finrank_add_finrank_le_of_disjoint hSTdisjoint
  rw [hMapFinrank, (Pi.dim_spanSubset (R := ℂ) (s := S)), (Pi.dim_spanSubset (R := ℂ) (s := T)),
    Module.finrank_fintype_fun_eq_card] at hbound
  have hTcompl : T = {i : n | Δ i < 0}ᶜ := by
    ext i; simp [hTdef, not_lt]
  have hpartition : {i : n | Δ i < 0}.ncard + T.ncard = Nat.card n := by
    rw [hTcompl]; exact Set.ncard_add_ncard_compl {i : n | Δ i < 0}
  rw [Nat.card_eq_fintype_card] at hpartition
  omega

/-- Running `card_neg_le_of_congr` with the congruence inverted: if `M`
    carries `D`'s quadratic form to `Δ`'s, then `M⁻¹` carries `Δ`'s back to
    `D`'s. -/
private lemma congr_symm_of_isUnit {D Δ : n → ℝ} {M : Matrix n n ℂ} (hM : IsUnit M)
    (hcongr : ∀ x : n → ℂ,
      ∑ i, D i * Complex.normSq (x i) = ∑ i, Δ i * Complex.normSq ((M *ᵥ x) i)) :
    ∀ y : n → ℂ, ∑ i, Δ i * Complex.normSq (y i) = ∑ i, D i * Complex.normSq ((M⁻¹ *ᵥ y) i) := by
  intro y
  have hy : M *ᵥ (M⁻¹ *ᵥ y) = y := by
    rw [Matrix.mulVec_mulVec, M.mul_nonsing_inv (M.isUnit_iff_isUnit_det.mp hM),
      Matrix.one_mulVec]
  have h := hcongr (M⁻¹ *ᵥ y)
  rw [hy] at h
  exact h.symm

/-- **Sylvester's law of inertia**, for the specific instance the checker's
    Hermitian pivot recurrence needs: an invertible complex congruence
    carrying `D`'s weighted quadratic form to `Δ`'s preserves the count of
    negative entries. Combines both directions of `card_neg_le_of_congr`. -/
private lemma card_neg_eq_of_congr (D Δ : n → ℝ) (M : Matrix n n ℂ) (hM : IsUnit M)
    (hcongr : ∀ x : n → ℂ,
      ∑ i, D i * Complex.normSq (x i) = ∑ i, Δ i * Complex.normSq ((M *ᵥ x) i)) :
    {i | D i < 0}.ncard = {i | Δ i < 0}.ncard :=
  le_antisymm (card_neg_le_of_congr D Δ M hM hcongr)
    (card_neg_le_of_congr Δ D M⁻¹ (Matrix.isUnit_nonsing_inv_iff.2 hM) (congr_symm_of_isUnit hM hcongr))

/-- The complex shift trick: `A - β·I` factors through the spectral theorem
    as a congruence of `diagonal (eigenvalues - β)` by the (unitary, hence
    invertible) eigenvector matrix. Complex analogue of `Soundness`'s
    `sub_smul_one_eq_mul_diagonal_mul_transpose`, simpler since no
    `star`-to-transpose conversion is needed. -/
private lemma sub_smul_one_eq_mul_diagonal_mul_star {A : Matrix n n ℂ} (hA : A.IsHermitian)
    (c : ℝ) :
    A - (c : ℂ) • (1 : Matrix n n ℂ) =
      (hA.eigenvectorUnitary : Matrix n n ℂ) *
        Matrix.diagonal (fun i => ((hA.eigenvalues i - c : ℝ) : ℂ)) *
        star (hA.eigenvectorUnitary : Matrix n n ℂ) := by
  set U : Matrix n n ℂ := (hA.eigenvectorUnitary : Matrix n n ℂ) with hU
  have hUU : U * star U = 1 := Unitary.coe_mul_star_self hA.eigenvectorUnitary
  have hcdiag : (c : ℂ) • (1 : Matrix n n ℂ) = U * Matrix.diagonal (fun _ : n => (c : ℂ)) * star U := by
    have hcd : Matrix.diagonal (fun _ : n => (c : ℂ)) = (c : ℂ) • (1 : Matrix n n ℂ) := by
      ext i j
      by_cases h : i = j <;> simp [h]
    rw [hcd, Matrix.mul_smul, Matrix.mul_one, Matrix.smul_mul, hUU]
  have hdiag_eq :
      Matrix.diagonal (RCLike.ofReal (K := ℂ) ∘ hA.eigenvalues) -
          Matrix.diagonal (fun _ : n => (c : ℂ)) =
        Matrix.diagonal (fun i => ((hA.eigenvalues i - c : ℝ) : ℂ)) := by
    rw [Matrix.diagonal_sub]
    congr 1
    funext i
    simp only [Function.comp_apply, RCLike.ofReal_eq_complex_ofReal]
    push_cast
    ring
  conv_lhs => rw [hA.spectral_theorem, Unitary.conjStarAlgAut_apply]
  rw [hcdiag, ← sub_mul, ← mul_sub, hdiag_eq]

/-- **Formalization of `certkit-1y7`'s complex-Hermitian inertia counting.**
    Given a Hermitian congruence `A - β·I = L D Lᴴ` with `L` unit-lower-
    triangular complex and `D` real (the LDL^H the checker's
    `count_eigenvalues_below_hermitian` computes in interval arithmetic),
    the number of negative entries of `D` equals the number of eigenvalues
    of `A` strictly below `β`. Direct complex analogue of
    `Soundness.inertia_count_below`. -/
theorem hermitian_inertia_count_below [LinearOrder n] {A : Matrix n n ℂ} (hA : A.IsHermitian)
    (β : ℝ) (D : n → ℝ)
    (hldl : ∃ L : Matrix n n ℂ, L.BlockTriangular id ∧ (∀ i, L i i = 1) ∧
      A - (β : ℂ) • (1 : Matrix n n ℂ) = L * Matrix.diagonal (fun i => (D i : ℂ)) * star L) :
    {i | D i < 0}.ncard = {i | hA.eigenvalues i < β}.ncard := by
  obtain ⟨L, hLtri, hLdiag, hLeq⟩ := hldl
  have hLdet : L.det = 1 := by
    rw [Matrix.det_of_isUpperTriangular hLtri]
    exact Finset.prod_eq_one fun i _ => hLdiag i
  have hLunit : IsUnit L := by
    rw [Matrix.isUnit_iff_isUnit_det, hLdet]; exact isUnit_one
  set Λ : n → ℝ := fun i => hA.eigenvalues i - β with hΛdef
  set U : Matrix n n ℂ := (hA.eigenvectorUnitary : Matrix n n ℂ) with hUdef
  have hUunit : IsUnit U := Unitary.isUnit_coe
  have hUeq : A - (β : ℂ) • (1 : Matrix n n ℂ) = U * Matrix.diagonal (fun i => (Λ i : ℂ)) * star U :=
    sub_smul_one_eq_mul_diagonal_mul_star hA β
  have hLUeq : L * Matrix.diagonal (fun i => (D i : ℂ)) * star L
      = U * Matrix.diagonal (fun i => (Λ i : ℂ)) * star U := hLeq ▸ hUeq
  have hLUeq' : L * Matrix.diagonal (fun i => (D i : ℂ)) * Lᴴ
      = U * Matrix.diagonal (fun i => (Λ i : ℂ)) * Uᴴ := by
    rw [Matrix.star_eq_conjTranspose, Matrix.star_eq_conjTranspose] at hLUeq
    exact hLUeq
  have hLHunit : IsUnit (Lᴴ) := (Matrix.isUnit_conjTranspose L).2 hLunit
  have hUHunit : IsUnit (Uᴴ) := (Matrix.isUnit_conjTranspose U).2 hUunit
  have hLHinv : Lᴴ * (Lᴴ)⁻¹ = 1 :=
    Lᴴ.mul_nonsing_inv (Lᴴ.isUnit_iff_isUnit_det.mp hLHunit)
  set M : Matrix n n ℂ := Uᴴ * (Lᴴ)⁻¹ with hMdef
  have hMunit : IsUnit M := hUHunit.mul (Matrix.isUnit_nonsing_inv_iff.2 hLHunit)
  have hcongr : ∀ x : n → ℂ,
      ∑ i, D i * Complex.normSq (x i) = ∑ i, Λ i * Complex.normSq ((M *ᵥ x) i) := by
    intro x
    have hLcancel : Lᴴ *ᵥ ((Lᴴ)⁻¹ *ᵥ x) = x := by
      rw [Matrix.mulVec_mulVec, hLHinv, Matrix.one_mulVec]
    have hMx : Uᴴ *ᵥ ((Lᴴ)⁻¹ *ᵥ x) = M *ᵥ x := by
      rw [hMdef, Matrix.mulVec_mulVec]
    have hleft := quadCongr_diagonal D Lᴴ ((Lᴴ)⁻¹ *ᵥ x)
    have hright := quadCongr_diagonal Λ Uᴴ ((Lᴴ)⁻¹ *ᵥ x)
    rw [Matrix.conjTranspose_conjTranspose, hLcancel] at hleft
    rw [Matrix.conjTranspose_conjTranspose, hMx] at hright
    have heq : star ((Lᴴ)⁻¹ *ᵥ x) ⬝ᵥ
          ((L * Matrix.diagonal (fun i => (D i : ℂ)) * Lᴴ) *ᵥ ((Lᴴ)⁻¹ *ᵥ x))
        = star ((Lᴴ)⁻¹ *ᵥ x) ⬝ᵥ
          ((U * Matrix.diagonal (fun i => (Λ i : ℂ)) * Uᴴ) *ᵥ ((Lᴴ)⁻¹ *ᵥ x)) := by
      rw [hLUeq']
    rw [hleft, hright] at heq
    exact_mod_cast heq
  have hset : {i | Λ i < 0} = {i | hA.eigenvalues i < β} := by
    ext i
    simp only [Set.mem_setOf_eq, hΛdef]
    constructor <;> intro h <;> linarith
  rw [← hset]
  exact card_neg_eq_of_congr D Λ M hMunit hcongr

end Certkit
