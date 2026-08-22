import Mathlib

namespace Certkit

/-! ### Real-number corner extremization for multiplication

Pure real-analysis fact, no floating point involved: for `a` ranging over
`[alo, ahi]` and `b` over `[blo, bhi]`, the product `a * b` is bracketed by
the min/max of the four corner products. This is what lets `Iv.__mul__`
evaluate only the four corners instead of searching the whole box. -/

theorem corner_mul_le_upper (alo ahi blo bhi a b : ℝ)
    (ha1 : alo ≤ a) (ha2 : a ≤ ahi) (hb1 : blo ≤ b) (hb2 : b ≤ bhi) :
    a * b ≤ max (max (alo * blo) (alo * bhi)) (max (ahi * blo) (ahi * bhi)) := by
  rcases le_total 0 a with ha | ha <;> rcases le_total 0 b with hb | hb <;>
    rcases le_total 0 alo with hal | hal <;> rcases le_total 0 ahi with hah | hah <;>
    rcases le_total 0 blo with hbl | hbl <;> rcases le_total 0 bhi with hbh | hbh <;>
  first
  | (have h : a * b ≤ ahi * bhi := by nlinarith
     calc a * b ≤ ahi * bhi := h
       _ ≤ _ := le_max_of_le_right (le_max_right _ _))
  | (have h : a * b ≤ ahi * blo := by nlinarith
     calc a * b ≤ ahi * blo := h
       _ ≤ _ := le_max_of_le_right (le_max_left _ _))
  | (have h : a * b ≤ alo * bhi := by nlinarith
     calc a * b ≤ alo * bhi := h
       _ ≤ _ := le_max_of_le_left (le_max_right _ _))
  | (have h : a * b ≤ alo * blo := by nlinarith
     calc a * b ≤ alo * blo := h
       _ ≤ _ := le_max_of_le_left (le_max_left _ _))

theorem corner_mul_le_lower (alo ahi blo bhi a b : ℝ)
    (ha1 : alo ≤ a) (ha2 : a ≤ ahi) (hb1 : blo ≤ b) (hb2 : b ≤ bhi) :
    min (min (alo * blo) (alo * bhi)) (min (ahi * blo) (ahi * bhi)) ≤ a * b := by
  rcases le_total 0 a with ha | ha <;> rcases le_total 0 b with hb | hb <;>
    rcases le_total 0 alo with hal | hal <;> rcases le_total 0 ahi with hah | hah <;>
    rcases le_total 0 blo with hbl | hbl <;> rcases le_total 0 bhi with hbh | hbh <;>
  first
  | (have h : alo * blo ≤ a * b := by nlinarith
     calc _ ≤ alo * blo := min_le_of_left_le (min_le_left _ _)
       _ ≤ a * b := h)
  | (have h : alo * bhi ≤ a * b := by nlinarith
     calc _ ≤ alo * bhi := min_le_of_left_le (min_le_right _ _)
       _ ≤ a * b := h)
  | (have h : ahi * blo ≤ a * b := by nlinarith
     calc _ ≤ ahi * blo := min_le_of_right_le (min_le_left _ _)
       _ ≤ a * b := h)
  | (have h : ahi * bhi ≤ a * b := by nlinarith
     calc _ ≤ ahi * bhi := min_le_of_right_le (min_le_right _ _)
       _ ≤ a * b := h)

/-! ### Reciprocal monotonicity, for division

`1/x` reverses order on either side of `0`; this plus `corner_mul_le_*`
reduces division to the same four-corner argument as multiplication, which
is exactly what `Iv.__truediv__` computes. -/

theorem inv_mem_of_pos (blo bhi b : ℝ) (hb1 : blo ≤ b) (hb2 : b ≤ bhi) (hpos : 0 < blo) :
    1 / bhi ≤ 1 / b ∧ 1 / b ≤ 1 / blo := by
  have hb : 0 < b := lt_of_lt_of_le hpos hb1
  have hbhi : 0 < bhi := lt_of_lt_of_le hb hb2
  exact ⟨by
      apply one_div_le_one_div_of_le hb hb2
    , by
      apply one_div_le_one_div_of_le hpos hb1⟩

theorem inv_mem_of_neg (blo bhi b : ℝ) (hb1 : blo ≤ b) (hb2 : b ≤ bhi) (hneg : bhi < 0) :
    1 / bhi ≤ 1 / b ∧ 1 / b ≤ 1 / blo := by
  have hb : b < 0 := lt_of_le_of_lt hb2 hneg
  constructor
  · have h := one_div_le_one_div_of_le (neg_pos.mpr hneg) (by linarith : -bhi ≤ -b)
    rw [div_neg, div_neg] at h
    linarith
  · have h := one_div_le_one_div_of_le (neg_pos.mpr hb) (by linarith : -b ≤ -blo)
    rw [div_neg, div_neg] at h
    linarith

/-! ### The rounding contract

This is the `nextafter` widening argument from the `interval.py` docstring,
stated as a hypothesis rather than derived from Lean's `Float` type: mathlib
has no formal IEEE-754 semantics to derive it from (no `nextafter`, no `ulp`,
nothing under those names as of this mathlib checkout), and Python's own
`math.nextafter`/float arithmetic are opaque to Lean regardless. What is
formalized and PROVED below is the mathematical content of the argument: if
- `fl` rounds every real to the nearest representable value, with error at
  most half the local step size (`ulp`) of the *result* -- the standard
  correctly-rounded contract IEEE-754 makes for `+ - * / sqrt`, and
- `down`/`up` move outward by at least one full step (`ulp`) -- what
  `nextafter` does, since the adjacent representable value is one step away,
- and `down`/`up` are order-preserving -- true of the representable grid,

then one step of outward widening always absorbs the rounding error, with
room to spare. That "room to spare" is `roundOutDown_le` / `le_roundOutUp`
below, and it is the fact the rest of `interval.py` is built on. -/

structure RoundingModel where
  fl : ℝ → ℝ
  down : ℝ → ℝ
  up : ℝ → ℝ
  ulp : ℝ → ℝ
  ulp_nonneg : ∀ y, 0 ≤ ulp y
  correctly_rounded : ∀ x, |fl x - x| ≤ ulp (fl x) / 2
  widens_down : ∀ y, down y ≤ y - ulp y
  widens_up : ∀ y, y + ulp y ≤ up y
  mono_down : Monotone down
  mono_up : Monotone up

namespace RoundingModel

variable (R : RoundingModel)

/-- The crux lemma: rounding `x` to the nearest float and then widening
    outward by one step never loses `x` off the low end. -/
theorem roundOutDown_le (x : ℝ) : R.down (R.fl x) ≤ x := by
  have h1 := R.widens_down (R.fl x)
  have h2 := (abs_le.mp (R.correctly_rounded x)).2
  have h3 := R.ulp_nonneg (R.fl x)
  linarith

/-- Mirror image on the high end. -/
theorem le_roundOutUp (x : ℝ) : x ≤ R.up (R.fl x) := by
  have h1 := R.widens_up (R.fl x)
  have h2 := (abs_le.mp (R.correctly_rounded x)).1
  have h3 := R.ulp_nonneg (R.fl x)
  linarith

end RoundingModel

/-! ### `Iv` operation enclosures

Each theorem mirrors one method of `interval.py`'s `Iv` class: given floats
`alo ≤ ahi` and `blo ≤ bhi` (both embedded in `ℝ`, since a double *is* a
real), and reals `a ∈ [alo, ahi]`, `b ∈ [blo, bhi]`, the float value the
Python method computes encloses every possible exact result `a ⊕ b`. -/

open RoundingModel

variable (R : RoundingModel)

/-- `Iv.__add__`. -/
theorem add_enclosure {alo ahi blo bhi a b : ℝ}
    (ha1 : alo ≤ a) (ha2 : a ≤ ahi) (hb1 : blo ≤ b) (hb2 : b ≤ bhi) :
    R.down (R.fl (alo + blo)) ≤ a + b ∧ a + b ≤ R.up (R.fl (ahi + bhi)) := by
  constructor
  · exact le_trans (R.roundOutDown_le (alo + blo)) (by linarith)
  · exact le_trans (by linarith) (R.le_roundOutUp (ahi + bhi))

/-- `Iv.__sub__`. -/
theorem sub_enclosure {alo ahi blo bhi a b : ℝ}
    (ha1 : alo ≤ a) (ha2 : a ≤ ahi) (hb1 : blo ≤ b) (hb2 : b ≤ bhi) :
    R.down (R.fl (alo - bhi)) ≤ a - b ∧ a - b ≤ R.up (R.fl (ahi - blo)) := by
  constructor
  · exact le_trans (R.roundOutDown_le (alo - bhi)) (by linarith)
  · exact le_trans (by linarith) (R.le_roundOutUp (ahi - blo))

/-- `Iv.__mul__`: the four corners are each individually correctly-rounded
    floats (`c1..c4`); the widening is applied to their min/max, exactly as
    `Iv._widen(min(corners), max(corners))` does. -/
theorem mul_enclosure {alo ahi blo bhi a b : ℝ}
    (ha1 : alo ≤ a) (ha2 : a ≤ ahi) (hb1 : blo ≤ b) (hb2 : b ≤ bhi) :
    let c1 := R.fl (alo * blo); let c2 := R.fl (alo * bhi)
    let c3 := R.fl (ahi * blo); let c4 := R.fl (ahi * bhi)
    R.down (min (min c1 c2) (min c3 c4)) ≤ a * b ∧
      a * b ≤ R.up (max (max c1 c2) (max c3 c4)) := by
  intro c1 c2 c3 c4
  have hupper := corner_mul_le_upper alo ahi blo bhi a b ha1 ha2 hb1 hb2
  have hlower := corner_mul_le_lower alo ahi blo bhi a b ha1 ha2 hb1 hb2
  constructor
  · have e1 : R.down (min (min c1 c2) (min c3 c4)) ≤ R.down c1 :=
      R.mono_down (min_le_of_left_le (min_le_left _ _))
    have e2 : R.down (min (min c1 c2) (min c3 c4)) ≤ R.down c2 :=
      R.mono_down (min_le_of_left_le (min_le_right _ _))
    have e3 : R.down (min (min c1 c2) (min c3 c4)) ≤ R.down c3 :=
      R.mono_down (min_le_of_right_le (min_le_left _ _))
    have e4 : R.down (min (min c1 c2) (min c3 c4)) ≤ R.down c4 :=
      R.mono_down (min_le_of_right_le (min_le_right _ _))
    have r1 : R.down c1 ≤ alo * blo := R.roundOutDown_le _
    have r2 : R.down c2 ≤ alo * bhi := R.roundOutDown_le _
    have r3 : R.down c3 ≤ ahi * blo := R.roundOutDown_le _
    have r4 : R.down c4 ≤ ahi * bhi := R.roundOutDown_le _
    rcases min_cases (min (alo * blo) (alo * bhi)) (min (ahi * blo) (ahi * bhi)) with ⟨heq, _⟩ | ⟨heq, _⟩ <;>
      rw [heq] at hlower <;>
      rcases min_cases (alo * blo) (alo * bhi) with ⟨heq2, _⟩ | ⟨heq2, _⟩ <;>
      rcases min_cases (ahi * blo) (ahi * bhi) with ⟨heq3, _⟩ | ⟨heq3, _⟩ <;>
      simp only [heq2, heq3] at hlower <;> linarith
  · have e1 : R.up c1 ≤ R.up (max (max c1 c2) (max c3 c4)) :=
      R.mono_up (le_max_of_le_left (le_max_left _ _))
    have e2 : R.up c2 ≤ R.up (max (max c1 c2) (max c3 c4)) :=
      R.mono_up (le_max_of_le_left (le_max_right _ _))
    have e3 : R.up c3 ≤ R.up (max (max c1 c2) (max c3 c4)) :=
      R.mono_up (le_max_of_le_right (le_max_left _ _))
    have e4 : R.up c4 ≤ R.up (max (max c1 c2) (max c3 c4)) :=
      R.mono_up (le_max_of_le_right (le_max_right _ _))
    have r1 : alo * blo ≤ R.up c1 := R.le_roundOutUp _
    have r2 : alo * bhi ≤ R.up c2 := R.le_roundOutUp _
    have r3 : ahi * blo ≤ R.up c3 := R.le_roundOutUp _
    have r4 : ahi * bhi ≤ R.up c4 := R.le_roundOutUp _
    rcases max_cases (max (alo * blo) (alo * bhi)) (max (ahi * blo) (ahi * bhi)) with ⟨heq, _⟩ | ⟨heq, _⟩ <;>
      rw [heq] at hupper <;>
      rcases max_cases (alo * blo) (alo * bhi) with ⟨heq2, _⟩ | ⟨heq2, _⟩ <;>
      rcases max_cases (ahi * blo) (ahi * bhi) with ⟨heq3, _⟩ | ⟨heq3, _⟩ <;>
      simp only [heq2, heq3] at hupper <;> linarith

/-- `Iv.__truediv__`, restricted to the case the checker requires: the
    divisor interval does not contain zero. Division is multiplication by
    `1/b`, and `1/b` stays inside `[1/bhi, 1/blo]` by `inv_mem_of_pos` /
    `inv_mem_of_neg`; from there it is the same corner argument as `mul`. -/
theorem div_enclosure {alo ahi blo bhi a b : ℝ}
    (ha1 : alo ≤ a) (ha2 : a ≤ ahi) (hb1 : blo ≤ b) (hb2 : b ≤ bhi)
    (hnz : 0 < blo ∨ bhi < 0) :
    let c1 := R.fl (alo / bhi); let c2 := R.fl (alo / blo)
    let c3 := R.fl (ahi / bhi); let c4 := R.fl (ahi / blo)
    R.down (min (min c1 c2) (min c3 c4)) ≤ a / b ∧
      a / b ≤ R.up (max (max c1 c2) (max c3 c4)) := by
  intro c1 c2 c3 c4
  have hinv : 1 / bhi ≤ 1 / b ∧ 1 / b ≤ 1 / blo := by
    rcases hnz with hpos | hneg
    · exact inv_mem_of_pos blo bhi b hb1 hb2 hpos
    · exact inv_mem_of_neg blo bhi b hb1 hb2 hneg
  have key := mul_enclosure R (alo := alo) (ahi := ahi) (blo := 1 / bhi) (bhi := 1 / blo)
    ha1 ha2 hinv.1 hinv.2
  have e1 : alo * (1 / bhi) = alo / bhi := by ring
  have e2 : alo * (1 / blo) = alo / blo := by ring
  have e3 : ahi * (1 / bhi) = ahi / bhi := by ring
  have e4 : ahi * (1 / blo) = ahi / blo := by ring
  have eb : a * (1 / b) = a / b := by ring
  rw [e1, e2, e3, e4, eb] at key
  exact key

/-- `Iv.sqrt`. The exact real `a` enclosed must itself be non-negative for
    `Real.sqrt a` to be the actual square root rather than the junk value
    `Real.sqrt` returns on negatives; this mirrors the caller obligation
    `interval.py` documents on `meet_nonneg` ("only sound where the enclosed
    quantity is provably non-negative — call sites must justify it"). Note
    the interval's own low endpoint need not be non-negative: `Iv.sqrt`
    clamps it to `0` first, matching `max alo 0` here. -/
theorem sqrt_enclosure {alo ahi a : ℝ}
    (ha1 : alo ≤ a) (ha2 : a ≤ ahi) (ha0 : 0 ≤ a) :
    R.down (R.fl (Real.sqrt (max alo 0))) ≤ Real.sqrt a ∧
      Real.sqrt a ≤ R.up (R.fl (Real.sqrt ahi)) := by
  have hlo : max alo 0 ≤ a := max_le ha1 ha0
  have hhi : a ≤ ahi := ha2
  constructor
  · exact le_trans (R.roundOutDown_le _) (Real.sqrt_le_sqrt hlo)
  · exact le_trans (Real.sqrt_le_sqrt hhi) (R.le_roundOutUp _)

end Certkit
