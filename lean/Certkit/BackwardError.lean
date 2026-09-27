import Mathlib

namespace Certkit

/-! ### The one-rounding-per-operation model

`backward_error.py`'s docstring assumes IEEE-754 correct rounding: every
elementary floating-point operation (`+ - * /`) commits at most one relative
rounding error bounded by the unit roundoff `u`. That is standard IEEE-754
fact, not derivable from anything in mathlib (mathlib has no formal IEEE-754
semantics -- confirmed already in `Interval.lean`), so here as there it is
taken as a hypothesis on each of the four operations in one Sturm-sweep step,
each supplying its own error term `e0 e1 e2 e3`. What is proved is the
mathematical content of the docstring's derivation: that these four
per-operation errors collect into exactly two aggregate factors, `eta` on the
diagonal term and `gamma` on the squared off-diagonal term, and that those
factors are bounded by the constants `ETA = 2.1 * U` and `GAMMA = 3.1 * U`
`backward_error.py` actually uses. -/

/-- Product of two roundings, e.g. `(1 + e2) * (1 + e3) - 1`: the aggregate
    relative error `eta` from two operations each individually erring by at
    most `e2` and `e3`. -/
def eta_of (e2 e3 : ℝ) : ℝ := (1 + e2) * (1 + e3) - 1

/-- Product of three roundings: the aggregate relative error `gamma` from
    three operations each erring by at most `e0`, `e1`, `e3`. -/
def gamma_of (e0 e1 e3 : ℝ) : ℝ := (1 + e0) * (1 + e1) * (1 + e3) - 1

/-- `|xy| ≤ u^2` when both factors are bounded by `u` in absolute value. -/
theorem abs_mul_le_sq {x y u : ℝ} (hu : 0 ≤ u) (hx : |x| ≤ u) (hy : |y| ≤ u) :
    |x * y| ≤ u * u := by
  rw [abs_mul]
  exact mul_le_mul hx hy (abs_nonneg _) hu

/-- `|xyz| ≤ u^3` when all three factors are bounded by `u` in absolute value. -/
theorem abs_mul_mul_le_cube {x y z u : ℝ} (hu : 0 ≤ u) (hx : |x| ≤ u) (hy : |y| ≤ u)
    (hz : |z| ≤ u) : |x * y * z| ≤ u * u * u := by
  rw [abs_mul, abs_mul]
  have hxy : |x| * |y| ≤ u * u := mul_le_mul hx hy (abs_nonneg _) hu
  have hxy0 : 0 ≤ |x| * |y| := mul_nonneg (abs_nonneg _) (abs_nonneg _)
  calc |x| * |y| * |z| ≤ (u * u) * |z| := mul_le_mul_of_nonneg_right hxy (abs_nonneg _)
    _ ≤ (u * u) * u := mul_le_mul_of_nonneg_left hz (mul_nonneg hu hu)
    _ = u * u * u := by ring

/-- **Two-rounding bound.** `eta`, the aggregate relative error on the
    diagonal term `(a_j - beta)` from the two roundings `p_j = fl(a_j - beta)`
    and `d_j = fl(p_j - t_j)`, is bounded by `2.1 * u` -- matching `ETA` in
    `backward_error.py` exactly, with the `0.1 * u` of headroom absorbing the
    second-order `e2 * e3` term the docstring writes as `O(u^2)`. -/
theorem eta_bound {u e2 e3 : ℝ} (hu : 0 ≤ u) (hu1 : u ≤ 1 / 10)
    (h2 : |e2| ≤ u) (h3 : |e3| ≤ u) : |eta_of e2 e3| ≤ 2.1 * u := by
  have hexpand : eta_of e2 e3 = e2 + e3 + e2 * e3 := by unfold eta_of; ring
  rw [hexpand]
  have t1 := abs_add_le (e2 + e3) (e2 * e3)
  have t2 := abs_add_le e2 e3
  have t3 : |e2 * e3| ≤ u * u := abs_mul_le_sq hu h2 h3
  have hsum : |e2 + e3 + e2 * e3| ≤ u + u + u * u := by linarith
  nlinarith [hsum, mul_nonneg hu (by linarith : (0:ℝ) ≤ 1 / 10 - u)]

/-- **Three-rounding bound.** `gamma`, the aggregate relative error on the
    squared off-diagonal term `b^2` from the three roundings `s_j = fl(b^2)`,
    `t_j = fl(s_j / d_{j-1})`, and `d_j = fl(p_j - t_j)`, is bounded by
    `3.1 * u` -- matching `GAMMA` in `backward_error.py` exactly. -/
theorem gamma_bound {u e0 e1 e3 : ℝ} (hu : 0 ≤ u) (hu1 : u ≤ 1 / 32)
    (h0 : |e0| ≤ u) (h1 : |e1| ≤ u) (h3 : |e3| ≤ u) :
    |gamma_of e0 e1 e3| ≤ 3.1 * u := by
  have hexpand : gamma_of e0 e1 e3 =
      e0 + e1 + e3 + e0 * e1 + e0 * e3 + e1 * e3 + e0 * e1 * e3 := by
    unfold gamma_of; ring
  rw [hexpand]
  have h01 : |e0 * e1| ≤ u * u := abs_mul_le_sq hu h0 h1
  have h03 : |e0 * e3| ≤ u * u := abs_mul_le_sq hu h0 h3
  have h13 : |e1 * e3| ≤ u * u := abs_mul_le_sq hu h1 h3
  have h013 : |e0 * e1 * e3| ≤ u * u * u := abs_mul_mul_le_cube hu h0 h1 h3
  have g1 := abs_add_le e0 e1
  have g2 := abs_add_le (e0 + e1) e3
  have g3 := abs_add_le (e0 + e1 + e3) (e0 * e1)
  have g4 := abs_add_le (e0 + e1 + e3 + e0 * e1) (e0 * e3)
  have g5 := abs_add_le (e0 + e1 + e3 + e0 * e1 + e0 * e3) (e1 * e3)
  have g6 := abs_add_le (e0 + e1 + e3 + e0 * e1 + e0 * e3 + e1 * e3) (e0 * e1 * e3)
  have hsum : |e0 + e1 + e3 + e0 * e1 + e0 * e3 + e1 * e3 + e0 * e1 * e3|
      ≤ u + u + u + u * u + u * u + u * u + u * u * u := by linarith
  have p1 : u * u ≤ u / 32 := by nlinarith [mul_nonneg hu (by linarith : (0:ℝ) ≤ 1 / 32 - u)]
  have p2 : u * u * u ≤ (u * u) / 32 := by
    nlinarith [mul_nonneg (mul_nonneg hu hu) (by linarith : (0:ℝ) ≤ 1 / 32 - u)]
  nlinarith [hsum, p1, p2]

/-- **The per-step collection.** One Sturm-sweep pivot step, with each of its
    four operations (`s_j = fl(b_{j-1}^2)`, `t_j = fl(s_j / d_{j-1})`,
    `p_j = fl(a_j - beta)`, `d_j = fl(p_j - t_j)`) committing at most one
    rounding of size `u`, computes exactly the pivot the *exact* recurrence
    would give for a perturbed diagonal entry `(a - beta) * (1 + eta)` and a
    perturbed squared off-diagonal `bprev^2 * (1 + gamma)`, with `eta` and
    `gamma` bounded as in `eta_bound` / `gamma_bound` above. This is the
    "collecting the factors" step of the `backward_error.py` docstring, made
    exact: no approximation, no `O(u^2)` hand-waving, just algebra plus the
    two bounds above.

    `dprev = 0` is not excluded: the identity holds unconditionally (both
    sides read `0` for the `t`/final term in that case, via `div_zero`), it
    is `backward_error.sweep`'s caller that guards against it before trusting
    the *count*, not this arithmetic identity. -/
theorem sweep_step_backward_bound {u e0 e1 e2 e3 a beta bprev dprev : ℝ}
    (hu : 0 ≤ u) (hu1 : u ≤ 1 / 32)
    (h0 : |e0| ≤ u) (h1 : |e1| ≤ u) (h2 : |e2| ≤ u) (h3 : |e3| ≤ u) :
    (((a - beta) * (1 + e2) - (bprev ^ 2 * (1 + e0) / dprev) * (1 + e1)) * (1 + e3)
        = (a - beta) * (1 + eta_of e2 e3) - bprev ^ 2 * (1 + gamma_of e0 e1 e3) / dprev)
      ∧ |eta_of e2 e3| ≤ 2.1 * u ∧ |gamma_of e0 e1 e3| ≤ 3.1 * u := by
  refine ⟨?_, eta_bound hu (by linarith) h2 h3, gamma_bound hu hu1 h0 h1 h3⟩
  unfold eta_of gamma_of
  field_simp
  ring

/-! ### The row-sum obligation (`certkit-62j`)

`backward_error.sweep` does not accumulate `ETA * |a_j - beta|` for row `j`'s
diagonal contribution -- it accumulates `ETA * |p|` where `p = fl(a_j -
beta) = (a_j - beta) * (1 + e2)` is the *rounded* value the runtime code
actually holds. `eta_bound` above only bounds `|eta_of e2 e3|` by `2.1 * u`
outright; it says nothing about how that bound relates to `|1 + e2|`, which
is exactly the gap between the exact `a_j - beta` and the rounded `p` the
runtime code scales by. `diag_perturbation_le` below is the sharper claim
that closes it. -/

/-- **Diagonal perturbation, scaled by the rounded pivot rather than the
    exact value.** The true diagonal perturbation on row `j` is
    `(a_j - beta) * eta_of e2 e3` (since `atilde_j - beta =
    (a_j - beta) * (1 + eta_of e2 e3)`, from `sweep_step_backward_bound`
    above), but the runtime code scales `ETA` by `|p| = |(a_j - beta) *
    (1 + e2)|`, not by `|a_j - beta|` itself. Soundness needs
    `|a_j - beta| * |eta_of e2 e3| ≤ (2.1 * u) * |(a_j - beta) * (1 + e2)|`,
    which is strictly stronger than `eta_bound`'s `|eta_of e2 e3| ≤ 2.1 * u`
    whenever `|1 + e2| < 1` (i.e. `e2 < 0`). Proved directly from `|e2| ≤ u`,
    `|e3| ≤ u`, `u ≤ 1/32` by the same case-bound-and-`nlinarith` technique
    as `eta_bound` -- no asymptotic `O(u^2)` hand-waving, and this is the
    step `ETA`'s `0.1 * u` headroom was silently covering (`certkit-62j`). -/
theorem diag_perturbation_le {u e2 e3 a beta : ℝ} (hu : 0 ≤ u) (hu1 : u ≤ 1 / 32)
    (h2 : |e2| ≤ u) (h3 : |e3| ≤ u) :
    |a - beta| * |eta_of e2 e3| ≤ (2.1 * u) * |(a - beta) * (1 + e2)| := by
  have h2' := abs_le.mp h2
  have h3' := abs_le.mp h3
  have hexpand : eta_of e2 e3 = e2 + e3 + e2 * e3 := by unfold eta_of; ring
  have h1pe2 : (0:ℝ) ≤ 1 + e2 := by linarith [h2'.1]
  have habsp : |(a - beta) * (1 + e2)| = |a - beta| * (1 + e2) := by
    rw [abs_mul, abs_of_nonneg h1pe2]
  have hetabound : |eta_of e2 e3| ≤ (2.1 * u) * (1 + e2) := by
    rw [hexpand]
    have t1 := abs_add_le (e2 + e3) (e2 * e3)
    have t2 := abs_add_le e2 e3
    have t3 : |e2 * e3| ≤ u * u := abs_mul_le_sq hu h2 h3
    nlinarith [t1, t2, t3, h2'.1, h2'.2, h3'.1, h3'.2]
  calc |a - beta| * |eta_of e2 e3| ≤ |a - beta| * ((2.1 * u) * (1 + e2)) :=
        mul_le_mul_of_nonneg_left hetabound (abs_nonneg _)
    _ = (2.1 * u) * (|a - beta| * (1 + e2)) := by ring
    _ = (2.1 * u) * |(a - beta) * (1 + e2)| := by rw [habsp]

/-- **Off-diagonal perturbation.** `btilde^2 = b^2 * (1 + gamma)` (from
    `sweep_step_backward_bound`), so up to sign `btilde = b * sqrt(1 +
    gamma)` (`sweep` only ever consumes `b^2`, never `btilde` itself, so the
    sign choice cannot affect the count or the bound), and the entrywise
    perturbation is `b * (sqrt(1 + gamma) - 1)`. `GAMMA = 3.1 * u` and the
    runtime code's `two_u = 2 * u`; `sweep`'s guard `GAMMA / 2 ≤ 2 * u`
    checks exactly the coefficient relationship this lemma needs. Proved by
    monotonicity of `Real.sqrt` from `(1 - 2u)^2 ≤ 1 + gamma ≤ (1 + 2u)^2`,
    not by a transcribed Taylor coefficient -- matches the 60-digit-decimal
    check recorded in `bd recall backward-error-mechanism`
    (`|sqrt(1 ± GAMMA) - 1| = 1.550000u` exactly, against the `2u` budget
    used here, `0.45u` slack). -/
theorem sqrt_one_add_sub_one_abs_le {gamma u : ℝ} (hu : 0 ≤ u) (hu1 : u ≤ 1 / 32)
    (hg : |gamma| ≤ 3.1 * u) : |Real.sqrt (1 + gamma) - 1| ≤ 2 * u := by
  have hg' := abs_le.mp hg
  have h1mu : (0:ℝ) ≤ 1 - 2 * u := by linarith
  have h1pg : (0:ℝ) ≤ 1 + gamma := by nlinarith
  rw [abs_le]
  constructor
  · have hlow : (1 - 2 * u) ≤ Real.sqrt (1 + gamma) := by
      rw [Real.le_sqrt h1mu h1pg]
      nlinarith [hg'.1]
    linarith
  · have hhigh : Real.sqrt (1 + gamma) ≤ 1 + 2 * u := by
      rw [Real.sqrt_le_left (by linarith : (0:ℝ) ≤ 1 + 2 * u)]
      nlinarith [hg'.2]
    linarith

end Certkit
