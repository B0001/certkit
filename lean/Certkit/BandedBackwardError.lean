import Certkit.BackwardError

/-!
# The banded row-sum obligation (`certkit-sp1`)

`certkit-4ue`'s banded (bandwidth `> 1`) backward-error route abandons the
tridiagonal route's per-operation rounding model entirely (see the module
comment at `certkit/backward_error.py:240` and `REVIEW-dyi.md` §1-§2): it
forms `Mtilde := L D Lᵀ` from the actual floats `L`, `D` that plain-float
elimination produced, then bounds `‖A - Mtilde‖` by directly auditing the
reconstruction formula against the known exact entries of `A`, using
`Iv`-interval arithmetic whose own soundness is proved elsewhere
(`Interval.lean`). No rounding-error bound is needed for this route at all.

What *is* needed, and is exactly `sweep_row_bound`'s job for the tridiagonal
route, is a real-number inequality showing that the row sums the checker
actually accumulates dominate `‖E‖_∞` where `E := Mtilde - Ã` (`Ã` being `A`
with the runtime shift folded into the diagonal). `REVIEW-dyi.md`'s §7
checklist names three concerns for this: formula correctness, row-sum
coverage (including the `k = j` term), and eviction safety. Eviction safety
is a claim about the Python loop's memory-management faithfulness to the
formula below, not about the formula itself (`certkit-sp1`'s own scoping
language); it is out of scope here and stays covered by `REVIEW-dyi.md`'s
human/empirical review. Formula correctness and row-sum coverage are real-
number claims, formalized below.

Everything here is stated over plain `ℕ`-indexed functions rather than
`Matrix n n ℝ` / `Fintype` / `Hermitian`, matching the precedent that
`sweep_row_bound` itself is not machine-linked to
`l2_opNorm_le_rowSum_of_isHermitian` by an `exact` chain -- only by the
prose correspondence table in `Soundness.lean`'s header. -/

namespace Certkit

/-- The `(i, j)` entry of `L * diagonal D * Lᵀ`, unfolded as the sum over the
    shared prefix `k ≤ min i j` that `REVIEW-dyi.md` §2 writes down for
    `Mtilde`. Plain `ℕ → ℕ → ℝ` / `ℕ → ℝ` functions rather than `Matrix ℝ`,
    since nothing below needs matrix multiplication or inversion -- just
    this one finite sum. -/
noncomputable def bandedRecon (L : ℕ → ℕ → ℝ) (D : ℕ → ℝ) (i j : ℕ) : ℝ :=
  ∑ k ∈ Finset.range (min i j + 1), L i k * L j k * D k

/-- `bandedRecon` is symmetric in its two indices unconditionally: `min i j =
    min j i` and the summand is symmetric in `i`/`j`. Matches `Mtilde` being
    manifestly symmetric by construction. -/
theorem bandedRecon_symm (L : ℕ → ℕ → ℝ) (D : ℕ → ℝ) (i j : ℕ) :
    bandedRecon L D i j = bandedRecon L D j i := by
  unfold bandedRecon
  rw [min_comm]
  exact Finset.sum_congr rfl fun k _ => by ring

/-- **Diagonal reconstruction formula** (`REVIEW-dyi.md` §2's `M_jj`, matching
    `recon`'s accumulation at `backward_error.py:368-391`, including the
    `k = j` term folded in at the end of that loop). Needs only that `L` has
    unit diagonal (`hLdiag`), unconditionally true of every `LDLᵀ`
    elimination, plus `Finset.sum_range_succ` to peel the `k = j` term off. -/
theorem bandedRecon_diag (L : ℕ → ℕ → ℝ) (D : ℕ → ℝ) (hLdiag : ∀ i, L i i = 1) (j : ℕ) :
    bandedRecon L D j j = D j + ∑ k ∈ Finset.range j, L j k * L j k * D k := by
  unfold bandedRecon
  rw [min_self, Finset.sum_range_succ, hLdiag j]
  ring

/-- **Off-diagonal reconstruction formula** (`REVIEW-dyi.md` §2's `M_ij` for
    `i > j`, matching `recon_ij`'s accumulation at
    `backward_error.py:395-421`, including the `k = j` term folded in at the
    end of that loop). Same shape as `bandedRecon_diag`. -/
theorem bandedRecon_offdiag (L : ℕ → ℕ → ℝ) (D : ℕ → ℝ) (hLdiag : ∀ i, L i i = 1)
    {i j : ℕ} (hij : j < i) :
    bandedRecon L D i j = (∑ k ∈ Finset.range j, L i k * L j k * D k) + L i j * D j := by
  unfold bandedRecon
  rw [min_eq_right hij.le, Finset.sum_range_succ, hLdiag j]
  ring

/-- `bandedRecon` vanishes for any pair farther apart than the bandwidth `b`,
    given `L` has that bandwidth (`hLband`). Every summand
    `L i k * L j k * D k` with `k ≤ min i j` has one of `L i k`, `L j k`
    equal to zero: whichever of `i`, `j` is the larger, say `i ≥ j` (so
    `min i j = j`), every `k ≤ j` satisfies `Nat.dist i k = i - k ≥ i - j =
    Nat.dist i j > b`. Matches `REVIEW-dyi.md`'s §1 remark that `Mtilde` has
    bandwidth `≤ b` because `L` does by construction. -/
theorem bandedRecon_eq_zero_of_band_lt {L : ℕ → ℕ → ℝ} {D : ℕ → ℝ} {b i j : ℕ}
    (hLband : ∀ p q, b < Nat.dist p q → L p q = 0) (h : b < Nat.dist i j) :
    bandedRecon L D i j = 0 := by
  unfold bandedRecon
  apply Finset.sum_eq_zero
  intro k hk
  rw [Finset.mem_range, Nat.lt_succ_iff] at hk
  rcases le_total j i with hji | hij
  · rw [min_eq_right hji] at hk
    rw [Nat.dist_eq_sub_of_le_right hji] at h
    have hik : b < Nat.dist i k := by
      rw [Nat.dist_eq_sub_of_le_right (hk.trans hji)]
      omega
    rw [hLband i k hik]; ring
  · rw [min_eq_left hij] at hk
    rw [Nat.dist_eq_sub_of_le hij] at h
    have hjk : b < Nat.dist j k := by
      rw [Nat.dist_eq_sub_of_le_right (hk.trans hij)]
      omega
    rw [hLband j k hjk]; ring

/-- The banded backward-error perturbation entry: `Mtilde - A` off the
    diagonal, `Mtilde - (A - beta)` (equivalently `Mtilde - A + beta`) on it,
    matching `e_jj` / `e_ij` in `sweep_banded`
    (`backward_error.py:392`, `:422`). -/
noncomputable def bandedE (L : ℕ → ℕ → ℝ) (D : ℕ → ℝ) (A : ℕ → ℕ → ℝ) (beta : ℝ)
    (i j : ℕ) : ℝ :=
  bandedRecon L D i j - A i j + (if i = j then beta else 0)

/-- `bandedE` is symmetric given `A` is. -/
theorem bandedE_symm {L : ℕ → ℕ → ℝ} {D : ℕ → ℝ} {A : ℕ → ℕ → ℝ} {beta : ℝ}
    (hAsymm : ∀ i j, A i j = A j i) (i j : ℕ) :
    bandedE L D A beta i j = bandedE L D A beta j i := by
  unfold bandedE
  rw [bandedRecon_symm L D i j, hAsymm i j]
  by_cases h : i = j
  · simp [h]
  · simp [h, Ne.symm h]

/-- `bandedE` vanishes outside the band, given both `A` and `L` do. -/
theorem bandedE_eq_zero_of_band_lt {L : ℕ → ℕ → ℝ} {D : ℕ → ℝ} {A : ℕ → ℕ → ℝ} {beta : ℝ}
    {b i j : ℕ}
    (hAband : ∀ p q, b < Nat.dist p q → A p q = 0)
    (hLband : ∀ p q, b < Nat.dist p q → L p q = 0)
    (h : b < Nat.dist i j) :
    bandedE L D A beta i j = 0 := by
  unfold bandedE
  rw [bandedRecon_eq_zero_of_band_lt hLband h, hAband i j h]
  have hij : i ≠ j := by
    intro heq; rw [heq, Nat.dist_self] at h; omega
  simp [hij]

/-- **Row-sum coverage** (`certkit-sp1`, generalising `sweep_row_bound` from
    bandwidth 1 to general `b`). `sweep_banded`'s runtime code never computes
    a full row sum directly: it credits the diagonal term once, and each
    off-diagonal pair `(i, j)` with `i > j` and `Nat.dist i j ≤ b` to *both*
    `row_err[i]` and `row_err[j]` (`backward_error.py:423-425`), because each
    such pair is visited exactly once (when column `j`'s loop reaches row
    `i`), not twice.

    This theorem is that accounting claim in the abstract: given any
    symmetric `E` vanishing outside the band (the shape `bandedE_symm` /
    `bandedE_eq_zero_of_band_lt` establish for the concrete banded backward-
    error perturbation), crediting `|E r r|` once plus `|E i r|` for each
    band-neighbour `i > r` plus `|E r j|` for each band-neighbour `j < r`
    reconstructs the *full* row sum `∑ c, |E r c|` -- the quantity
    `l2_opNorm_le_rowSum_of_isHermitian` needs. For `b = 1` this reduces to
    `sweep_row_bound`'s three-term shape (`|E r r|` plus one predecessor, one
    successor); the proof never special-cases `b`.

    What this does **not** cover, same scoping as `sweep_row_bound`: whether
    `sweep_banded`'s `Iv`-arithmetic loop, in whatever order it visits
    `(i, j)` pairs, computes an outward-rounded enclosure of this real-number
    sum, and whether `lmat`'s eviction (`backward_error.py:427-430`) has
    already discarded an entry this sum needs before it is read. Both are
    claims about the *Python loop's* faithfulness to the formula below, not
    about the formula itself; they stay Python-test obligations
    (`REVIEW-dyi.md` §4's empirical eviction check and
    `tests/test_backward.py`'s banded section), exactly as `sweep_row_bound`
    excludes the `Iv`-loop-faithfulness question for the tridiagonal
    route. -/
theorem banded_row_err_eq_row_sum {n b : ℕ} {E : ℕ → ℕ → ℝ}
    (hsymm : ∀ i j, E i j = E j i)
    (hband : ∀ i j, b < Nat.dist i j → E i j = 0)
    {r : ℕ} (hr : r < n) :
    |E r r|
      + ∑ i ∈ (Finset.range n).filter (fun i => r < i ∧ Nat.dist i r ≤ b), |E i r|
      + ∑ j ∈ (Finset.range n).filter (fun j => j < r ∧ Nat.dist r j ≤ b), |E r j|
    = ∑ c ∈ Finset.range n, |E r c| := by
  have hflip : ∀ i, |E i r| = |E r i| := fun i => by rw [hsymm i r]
  set S1 := (Finset.range n).filter (fun i => r < i ∧ Nat.dist i r ≤ b) with hS1_def
  set S2 := (Finset.range n).filter (fun j => j < r ∧ Nat.dist r j ≤ b) with hS2_def
  set T1 := (Finset.range n).filter (fun i => r < i) with hT1_def
  set T2 := (Finset.range n).filter (fun j => j < r) with hT2_def
  have hsub1 : S1 ⊆ T1 := by
    intro i hi
    rw [hS1_def, Finset.mem_filter] at hi
    rw [hT1_def, Finset.mem_filter]
    exact ⟨hi.1, hi.2.1⟩
  have hext1 : ∑ i ∈ S1, |E i r| = ∑ i ∈ T1, |E r i| := by
    rw [Finset.sum_congr rfl (fun i (_ : i ∈ S1) => hflip i)]
    apply Finset.sum_subset hsub1
    intro i hiT hiS
    rw [hT1_def, Finset.mem_filter] at hiT
    have hiS' : ¬ (r < i ∧ Nat.dist i r ≤ b) := fun h => hiS (by
      rw [hS1_def, Finset.mem_filter]; exact ⟨hiT.1, h⟩)
    have hd : b < Nat.dist i r := by
      by_contra hc
      push Not at hc
      exact hiS' ⟨hiT.2, hc⟩
    have hz : E r i = 0 := by rw [hsymm r i]; exact hband i r hd
    rw [hz, abs_zero]
  have hsub2 : S2 ⊆ T2 := by
    intro j hj
    rw [hS2_def, Finset.mem_filter] at hj
    rw [hT2_def, Finset.mem_filter]
    exact ⟨hj.1, hj.2.1⟩
  have hext2 : ∑ j ∈ S2, |E r j| = ∑ j ∈ T2, |E r j| := by
    apply Finset.sum_subset hsub2
    intro j hjT hjS
    rw [hT2_def, Finset.mem_filter] at hjT
    have hjS' : ¬ (j < r ∧ Nat.dist r j ≤ b) := fun h => hjS (by
      rw [hS2_def, Finset.mem_filter]; exact ⟨hjT.1, h⟩)
    have hd : b < Nat.dist r j := by
      by_contra hc
      push Not at hc
      exact hjS' ⟨hjT.2, hc⟩
    rw [hband r j hd, abs_zero]
  have hunion : (Finset.range n).erase r = T1 ∪ T2 := by
    ext c
    simp only [Finset.mem_erase, Finset.mem_range, Finset.mem_union, hT1_def, hT2_def,
      Finset.mem_filter]
    omega
  have hdisj : Disjoint T1 T2 := by
    rw [Finset.disjoint_left]
    intro c hc1 hc2
    simp only [hT1_def, hT2_def, Finset.mem_filter] at hc1 hc2
    omega
  have hpeel : |E r r| + ∑ c ∈ (Finset.range n).erase r, |E r c| = ∑ c ∈ Finset.range n, |E r c| :=
    Finset.add_sum_erase (Finset.range n) (fun c => |E r c|) (Finset.mem_range.mpr hr)
  rw [hunion, Finset.sum_union hdisj] at hpeel
  rw [hext1, hext2]
  linarith [hpeel]

end Certkit
