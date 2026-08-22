/-
  certkit -- soundness obligations, stated in Lean 4 / mathlib4.

  STATUS: mostly statements, not proofs. Six of the seven theorems below are
  `sorry` and this file has not been compiled in the environment where the
  Python kit was built, so treat those six as a specification of intent, not
  a verified artifact. The seventh, `sweep_backward_bound`, is a real,
  compiled, zero-`sorry` proof (see its own doc comment for exactly what it
  does and does not cover) -- do not read that as license to call the other
  six proved, or this file "soundness-complete."

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
  real result -- is the floating-point layer; it is formalised and proved,
  zero `sorry`, in `Interval.lean`.
-/

import Mathlib.Analysis.InnerProductSpace.Spectrum
import Mathlib.LinearAlgebra.Matrix.Hermitian
import Mathlib.Analysis.Matrix.Spectrum
import Certkit.BackwardError

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
    the open obligation this theorem's `sorry` stands for. -/
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
