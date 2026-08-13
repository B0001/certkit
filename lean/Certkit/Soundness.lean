/-
  certkit -- soundness obligations, stated in Lean 4 / mathlib4.

  STATUS: statements only. Every proof below is `sorry`. This file has not
  been compiled in the environment where the Python kit was built, so treat
  it as a specification of intent, not as a verified artifact.

  The point of the file is the correspondence. The Python checker performs
  exactly two mathematical steps, and each is one theorem here:

    checker._check_temple_inertia      upper bound  <->  rayleigh_ritz_min
                                       lower bound  <->  temple_lower
    checker.count_eigenvalues_below                 <->  inertia_count_below
    banded.count_eigenvalues_below_banded           <->  inertia_count_below
    backward_error.count_eigenvalues_below_backward <->  inertia_count_below
                                                     +   weyl_shift
    checker._check_gershgorin_rayleigh lower bound  <->  gershgorin_lower

  A third obligation -- that interval arithmetic on doubles encloses the
  real result -- is the floating-point layer, and is the natural next thing
  to formalise (see `Interval.lean`, not yet written).
-/

import Mathlib.Analysis.InnerProductSpace.Spectrum
import Mathlib.LinearAlgebra.Matrix.Hermitian
import Mathlib.LinearAlgebra.Matrix.Spectrum

namespace Certkit

open scoped Matrix

variable {n : Type*} [Fintype n] [DecidableEq n]
variable {A : Matrix n n ℝ} (hA : A.IsHermitian)

/-- The Rayleigh quotient of a nonzero vector. -/
noncomputable def rayleigh (A : Matrix n n ℝ) (x : n → ℝ) : ℝ :=
  (x ⬝ᵥ A.mulVec x) / (x ⬝ᵥ x)

/-- The residual norm, measured relative to the vector's own norm. -/
noncomputable def residualNorm (A : Matrix n n ℝ) (x : n → ℝ) : ℝ :=
  ‖A.mulVec x - (rayleigh A x) • x‖ / ‖x‖

/-- **Rayleigh-Ritz.** The Rayleigh quotient of any nonzero vector is an
    upper bound for the least eigenvalue. This is the checker's upper bound,
    and it is unconditional -- no gap, no witness beyond `x` itself. -/
theorem rayleigh_ritz_min (x : n → ℝ) (hx : x ≠ 0) :
    ⨅ i, hA.eigenvalues i ≤ rayleigh A x := by
  sorry

/-- **Residual bound.** Some eigenvalue lies within the residual norm of the
    Rayleigh quotient. Note what this does *not* say: the nearby eigenvalue
    need not be the least one. The Python side keeps this as a separate
    claim kind (`spectrum_contains`) precisely to stop that conflation. -/
theorem residual_encloses_some_eigenvalue (x : n → ℝ) (hx : x ≠ 0) :
    ∃ i, |hA.eigenvalues i - rayleigh A x| ≤ residualNorm A x := by
  sorry

/-- **Temple's inequality.** Given a separator `β` that sits strictly above
    the Rayleigh quotient and weakly below the second eigenvalue, the
    residual gives a *lower* bound on the least eigenvalue. -/
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
    count in interval arithmetic and requires it to be exactly one. -/
theorem inertia_count_below (β : ℝ) (d : n → ℝ)
    (hd : ∀ i, d i ≠ 0)
    (hldl : ∃ L : Matrix n n ℝ, L.BlockTriangular id ∧
      (∀ i, L i i = 1) ∧ A - β • (1 : Matrix n n ℝ) = L * (Matrix.diagonal d) * Lᵀ) :
    (Finset.univ.filter fun i => d i < 0).card
      = (Finset.univ.filter fun i => hA.eigenvalues i < β).card := by
  sorry

/-- **Gershgorin.** Every eigenvalue is at least the smallest value of
    `a i i - (off-diagonal absolute row sum)`. This is the matrix-free lower
    bound: it needs only row access, no gap and no factorisation, and it is
    what lets the checker say something sound about an operator it can never
    build. -/
theorem gershgorin_lower :
    (⨅ i, hA.eigenvalues i)
      ≥ ⨅ i, (A i i - ∑ j ∈ Finset.univ.erase i, |A i j|) := by
  sorry

/-- **Weyl.** Perturbing a symmetric operator moves each eigenvalue by at most
    the norm of the perturbation. This is what carries the backward-error
    counting rule's conclusion back from the nearby matrix the float sweep
    actually factorises to the operator the certificate is about.

    The `sturm_be` rule bounds `‖A - Atilde‖` at runtime from the entries, then
    brackets: sweeping at `beta - delta` and `beta + delta` and requiring the
    two counts to agree pins the count for `A` itself. -/
theorem weyl_shift {B : Matrix n n ℝ} (hB : B.IsHermitian) (i : n) :
    |hA.eigenvalues i - hB.eigenvalues i| ≤ ‖A - B‖ := by
  sorry

/-- The remaining obligation, and the one that would retire the most hand
    analysis: that a single IEEE operation commits at most one rounding, and
    that the running bound assembled in `backward_error.sweep` really does
    dominate `‖A - Atilde‖`. Until this is formalised, that derivation is
    checked by tests and by reading, not by a machine. -/
theorem sweep_backward_bound : True := by
  trivial

end Certkit
