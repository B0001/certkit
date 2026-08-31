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

/-- Easy direction of Courant-Fischer: any vector in the span of the top
`i₀.val + 1` eigenvectors has Rayleigh quotient at least `eigenvalues i₀`. -/
theorem courant_fischer_ge (hT : T.IsSymmetric) (hn : Module.finrank ℝ E = n)
    (i₀ : Fin n) (x : E)
    (hx : x ∈ Submodule.span ℝ (hT.eigenvectorBasis hn '' (↑(Finset.Iic i₀) : Set (Fin n)))) :
    hT.eigenvalues hn i₀ * ⟪x, x⟫ ≤ ⟪x, T x⟫ := by
  set b := hT.eigenvectorBasis hn with hb_def
  have hbTb : ∀ j, T (b j) = hT.eigenvalues hn j • b j := hT.apply_eigenvectorBasis hn
  have hxmem : x ∈ Submodule.span ℝ (b.toBasis '' (↑(Finset.Iic i₀) : Set (Fin n))) := by
    rwa [OrthonormalBasis.coe_toBasis]
  have hsupp : ↑(b.toBasis.repr x).support ⊆ (↑(Finset.Iic i₀) : Set (Fin n)) :=
    b.toBasis.mem_span_image.mp hxmem
  have hzero : ∀ k, i₀ < k → ⟪b k, x⟫ = 0 := by
    intro k hk
    have hknotin : k ∉ Finset.Iic i₀ := by simp [Finset.mem_Iic, not_le.mpr hk]
    have : (b.toBasis.repr x) k = 0 := by
      by_contra hne
      exact hknotin (hsupp (Finsupp.mem_support_iff.mpr hne))
    rw [OrthonormalBasis.coe_toBasis_repr_apply] at this
    rw [← b.repr_apply_apply x k]
    exact this
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
  rcases lt_or_ge i₀ j with hlt | hge
  · rw [hzero j hlt]; simp
  · have hantitone : hT.eigenvalues hn i₀ ≤ hT.eigenvalues hn j :=
      hT.eigenvalues_antitone hn hge
    nlinarith [sq_nonneg (⟪b j, x⟫)]

variable {TB : E →ₗ[ℝ] E}

private lemma finrank_span_Iic_image [DecidableEq E] {b : Fin n → E} (hb : Orthonormal ℝ b)
    (i₀ : Fin n) :
    Module.finrank ℝ (Submodule.span ℝ ((Finset.Iic i₀).image b : Set E)) = i₀.val + 1 := by
  rw [Module.finrank_eq_card_basis (OrthonormalBasis.span hb (Finset.Iic i₀)).toBasis]
  rw [Fintype.card_coe, Fin.card_Iic]

/-- Loewner monotonicity: if `T - TB` is positive semidefinite (in Rayleigh-quotient
form), every `TB`-eigenvalue is at most the corresponding `T`-eigenvalue at the same
index. -/
theorem loewner_le (hA : T.IsSymmetric) (hB : TB.IsSymmetric) (hn : Module.finrank ℝ E = n)
    (hPSD : ∀ x, 0 ≤ ⟪x, (T - TB) x⟫) (i₀ : Fin n) :
    hB.eigenvalues hn i₀ ≤ hA.eigenvalues hn i₀ := by
  classical
  set bB := hB.eigenvectorBasis hn with hbB_def
  set V : Submodule ℝ E := Submodule.span ℝ ((Finset.Iic i₀).image bB : Set E) with hV_def
  have hVfin : Module.finrank ℝ V = i₀.val + 1 := finrank_span_Iic_image bB.orthonormal i₀
  obtain ⟨x, hxV, hxne, hxleA⟩ := courant_fischer_le hA hn V i₀ hVfin
  have hxV' : x ∈ Submodule.span ℝ (bB '' (↑(Finset.Iic i₀) : Set (Fin n))) := by
    rw [hV_def, Finset.coe_image] at hxV; exact hxV
  have hxgeB : hB.eigenvalues hn i₀ * ⟪x, x⟫ ≤ ⟪x, TB x⟫ := courant_fischer_ge hB hn i₀ x hxV'
  have hxx_pos : 0 < ⟪x, x⟫ := real_inner_self_pos.mpr hxne
  have hpsd_x : ⟪x, TB x⟫ ≤ ⟪x, T x⟫ := by
    have h := hPSD x
    rw [LinearMap.sub_apply, inner_sub_right] at h
    linarith
  have hchain : hB.eigenvalues hn i₀ * ⟪x, x⟫ ≤ hA.eigenvalues hn i₀ * ⟪x, x⟫ :=
    le_trans hxgeB (le_trans hpsd_x hxleA)
  exact le_of_mul_le_mul_right hchain hxx_pos

/-- Shifted one-sided Loewner comparison: if `T - TB` is bounded above by `c • 1` (in
Rayleigh-quotient form), then every `T`-eigenvalue is at most the corresponding
`TB`-eigenvalue plus `c`, at the same index. Setting `c = 0` recovers `loewner_le`
(with `T`/`TB` swapped). -/
theorem eigenvalues_sub_le (hT : T.IsSymmetric) (hTB : TB.IsSymmetric)
    (hn : Module.finrank ℝ E = n) (c : ℝ)
    (hbound : ∀ x, ⟪x, (T - TB) x⟫ ≤ c * ⟪x, x⟫) (i₀ : Fin n) :
    hT.eigenvalues hn i₀ ≤ hTB.eigenvalues hn i₀ + c := by
  classical
  set bT := hT.eigenvectorBasis hn with hbT_def
  set V : Submodule ℝ E := Submodule.span ℝ ((Finset.Iic i₀).image bT : Set E) with hV_def
  have hVfin : Module.finrank ℝ V = i₀.val + 1 := finrank_span_Iic_image bT.orthonormal i₀
  obtain ⟨x, hxV, hxne, hxleTB⟩ := courant_fischer_le hTB hn V i₀ hVfin
  have hxV' : x ∈ Submodule.span ℝ (bT '' (↑(Finset.Iic i₀) : Set (Fin n))) := by
    rw [hV_def, Finset.coe_image] at hxV; exact hxV
  have hxgeT : hT.eigenvalues hn i₀ * ⟪x, x⟫ ≤ ⟪x, T x⟫ := courant_fischer_ge hT hn i₀ x hxV'
  have hxx_pos : 0 < ⟪x, x⟫ := real_inner_self_pos.mpr hxne
  have hbound_x : ⟪x, T x⟫ ≤ ⟪x, TB x⟫ + c * ⟪x, x⟫ := by
    have h := hbound x
    rw [LinearMap.sub_apply, inner_sub_right] at h
    linarith
  have hchain : hT.eigenvalues hn i₀ * ⟪x, x⟫ ≤ (hTB.eigenvalues hn i₀ + c) * ⟪x, x⟫ := by
    rw [add_mul]
    linarith [hxgeT, hxleTB, hbound_x]
  exact le_of_mul_le_mul_right hchain hxx_pos

/-- Abstract Weyl shift: if `T - TB` is bounded in Rayleigh-quotient form by `c` on both
sides (i.e. `-c•1 ⪯ T - TB ⪯ c•1`), every pair of same-index eigenvalues differs by at
most `c`. -/
theorem weyl_shift_abstract (hT : T.IsSymmetric) (hTB : TB.IsSymmetric)
    (hn : Module.finrank ℝ E = n) (c : ℝ)
    (hbound : ∀ x, |⟪x, (T - TB) x⟫| ≤ c * ⟪x, x⟫) (i₀ : Fin n) :
    |hT.eigenvalues hn i₀ - hTB.eigenvalues hn i₀| ≤ c := by
  rw [abs_le]
  refine ⟨?_, ?_⟩
  · have h := eigenvalues_sub_le hTB hT hn c (fun x => by
      have h1 := (abs_le.mp (hbound x)).1
      have h2 : ⟪x, (TB - T) x⟫ = -⟪x, (T - TB) x⟫ := by
        rw [LinearMap.sub_apply, LinearMap.sub_apply, inner_sub_right, inner_sub_right]; ring
      rw [h2]; linarith)
    linarith [h i₀]
  · have h := eigenvalues_sub_le hT hTB hn c (fun x => (abs_le.mp (hbound x)).2)
    linarith [h i₀]
