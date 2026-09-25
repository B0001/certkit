# Reviewer brief: soundness sign-off for `certkit-jcb`

**What's being asked.** A second *person* checks one derivation against the published literature
and signs off, or files a defect. Three AI reviews and a citation check against the paper have
already been done (summarised below). They agree the derivation is sound, but the bead's
acceptance criteria require a human, because every review so far could share a blind spot with the
author. Expect **about 30 minutes**.

**What you need:**
- The paper: J. W. Demmel, I. Dhillon, H. Ren, *On the correctness of some bisection-like parallel
  eigenvalue algorithms in floating point arithmetic*, ETNA **3** (1995) 116–149.
  Open access: <https://etna.ricam.oeaw.ac.at/vol.3.1995/pp116-149.dir/pp116-149.pdf>
- `certkit/backward_error.py`: constants at lines 74–81, `sweep` at 141–188, and
  `count_eigenvalues_below_backward` at 191–227.

---

## 1. The claim under review

For a real symmetric tridiagonal $T$ (diagonal $a_j$, off-diagonal $b_j$) and a shift
$\beta$, `count_eigenvalues_below_backward` returns $N(T,\beta)$, the exact number of
eigenvalues of $T$ strictly below $\beta$, or abstains. It never returns a wrong count.

The argument has three steps:

1. **Backward error.** One float Sturm sweep at shift $\sigma$ yields exactly the inertia of a
   nearby symmetric $\tilde T$. Its count of negative pivots equals the number of eigenvalues of
   $\tilde T$ below $\sigma$ (Sylvester).
2. **Perturbation bound.** The sweep also returns $\delta$ with $\|T-\tilde T\|_2 \le \delta$.
3. **Bracketing.** Sweeps at $\beta-\delta_L$ and $\beta+\delta_H$ (Weyl) pin $N(T,\beta)$
   when the two counts agree.

**The risk the bead exists for.** If the rounding budgets in step 2 are too small, interval
arithmetic *faithfully* computes a $\delta$ that is too small, no check fails, and the checker
returns a **false VERIFIED**. Steps 2–3 are implemented with outward rounding, which doesn't help
if the constants are wrong. So the constants must be checked against the literature, not against
their own docstring.

---

## 2. What the code does (`sweep`, lines 141–188)

Unit roundoff $u = 2^{-53}$. Every operation below is one IEEE binary64 operation,
$\mathrm{fl}(x \circ y) = (x\circ y)(1+e)$ with $|e|\le u$:

$$
\begin{aligned}
p_j &= \mathrm{fl}(a_j-\beta) = (a_j-\beta)(1+e_{2})\\
s_j &= \mathrm{fl}(b_{j-1}^2) = b_{j-1}^2(1+e_{0})\\
t_j &= \mathrm{fl}(s_j/d_{j-1}) = \frac{s_j}{d_{j-1}}(1+e_{1})\\
d_j &= \mathrm{fl}(p_j-t_j) = (p_j-t_j)(1+e_{3})
\end{aligned}
$$

Here $d_{j-1}$ is the **computed** float from the previous step. Expanding gives an *exact*
identity:

$$
d_j \;=\; (a_j-\beta)\underbrace{(1+e_2)(1+e_3)}_{1+\eta_j} \;-\; \frac{b_{j-1}^2\,\overbrace{(1+e_0)(1+e_1)(1+e_3)}^{1+\gamma_j}}{d_{j-1}} .
$$

So the computed $d_j$ are exactly the $LDL^\top$ pivots of $\tilde T - \beta I$, where

$$
\tilde a_j - \beta = (a_j-\beta)(1+\eta_j), \qquad \tilde b_{j-1}^{\,2} = b_{j-1}^2 (1+\gamma_j).
$$

**Budgets (lines 79–80):**

$$
|\eta_j| \le 2u+u^2 \le \texttt{ETA} = 2.1u, \qquad |\gamma_j| \le 3u+3u^2+u^3 \le \texttt{GAMMA} = 3.1u .
$$

**Off-diagonal coefficient (`two_u`, line 154).** The largest value of $|\sqrt{1+\gamma}-1|$ over
$|\gamma|\le\Gamma=3.1u$ is at $\gamma=-\Gamma$:

$$
1-\sqrt{1-\Gamma} \;=\; \frac{\Gamma}{1+\sqrt{1-\Gamma}} \;\le\; \frac{\Gamma}{2-\Gamma} \;\approx\; 1.55u \;\le\; 2u .
$$

**Row sums (lines 182–186).** Row $j$ of $E = T-\tilde T$ has three entries, and the code
bounds its 1-norm by

$$
\texttt{ETA}\cdot|p_j| \;+\; 2u\,|b_{j-1}| \;+\; 2u\,|b_j| ,
$$

outward-rounded. Then $\delta = \max_j$ of that, which bounds $\|E\|_\infty$, and
$\|E\|_2 \le \|E\|_\infty$ for symmetric $E$. That last inequality is proved in Lean:
`l2_opNorm_le_rowSum_of_isHermitian`, `lean/Certkit/Soundness.lean:717`. The algebra of the
identity above is `sweep_backward_bound`, `Soundness.lean:811` (zero `sorry`).

**Guards (lines 150–177).** $p_j, s_j, t_j, d_j$ must each be a normal float or an exact zero,
and $t_j$ may not underflow to $0$ from a nonzero $s_j$. A zero or subnormal pivot raises
`IntervalError`, which means abstain. This is what makes the one-rounding model above valid:
there is no gradual-underflow term to account for.

---

## 3. The external check: why 2.0u and not the paper's 2.5u

The paper's headline off-diagonal bound for IEEE arithmetic (their **Model 2**) is
$f(2.5,\varepsilon) \approx 2.5\varepsilon$ (**Table 5.1, p. 137**), which is *larger* than
certkit's $2u$. This is the point to confirm.

**Paper, Eq. (5.6), bottom of p. 132.** DDR keep the diagonal *unperturbed*, so that $T'$ doesn't
depend on the shift. They rescale $\tilde d_i = d_i/(1+\varepsilon_c)^2$, which pushes the
diagonal roundings onto the off-diagonal term:

$$
\tilde d_i \;=\; T_{ii} + (2C+1)\,\eta_i - x \;-\; \sum_{j\ \text{child of}\ i} \frac{T_{ij}^2}{\tilde d_j}\,(1+\varepsilon_{ij})^{C+4} .
$$

For a tridiagonal matrix $C=1$ (§5.2, p. 133), so the off-diagonal term carries
$(1+\varepsilon)^5$. Taking the square root gives the relative perturbation of $b$ as
$\approx 2.5\varepsilon$.

**certkit instead keeps the diagonal perturbation,** relative to the shift:
$|\tilde a_j - a_j| = |a_j-\beta|\,|\eta_j|$, charged in the row sum. Because the identity in §2
uses the computed $d_{j-1}$ as given, with no rescaling carried between steps, only **three**
factors reach $b^2$. That gives $1.55u \le 2u$.

Both are valid backward-error models, with different placement of the same roundings. DDR's
diagonal term is independent of the shift; certkit's isn't, and doesn't need to be, because each
sweep's $\delta$ is computed at its own shift and the bracketing checks it (lines 214–216).

**Also note:**
- Underflow: DDR carry $\eta_i$/$\omega$ underflow terms. certkit abstains instead (the §2 guards).
- DDR's **Lemma 5.1 (p. 136)** is the Weyl step from backward error to eigenvalue error, the same
  role Weyl plays in §4 below, not the backward-error bound itself.

---

## 4. Bracketing (`count_eigenvalues_below_backward`, lines 191–227)

Let $L = \beta-g$ and $H = \beta+g$, outward-rounded, with sweeps returning
$(C_L,\delta_L)$ and $(C_H,\delta_H)$. The code **checks** that
$\beta - L \ge \delta_L$ and $H-\beta \ge \delta_H$ (lines 214–216), and refines $g$ otherwise.
Then, by Weyl, $|\lambda_k(T)-\lambda_k(\tilde T)|\le\delta$:

$$
k \le C_L:\ \ \lambda_k(T) \le \lambda_k(\tilde T_L)+\delta_L < L+\delta_L \le \beta \;\;\Rightarrow\;\; N(T,\beta)\ge C_L ,
$$

$$
k \ge C_H+1:\ \ \lambda_k(T) \ge \lambda_k(\tilde T_H)-\delta_H \ge H-\delta_H \ge \beta \;\;\Rightarrow\;\; N(T,\beta)\le C_H .
$$

If $C_L = C_H$, the count is exact. Otherwise it abstains.

---

## 5. Checklist

Tick each item or file a defect. Anything not ticked means no sign-off.

- [ ] **§2 identity.** `sweep` performs exactly the four operations shown, in that order, on the
      computed $d_{j-1}$ (lines 162–175), and the expansion into $\eta_j,\gamma_j$ is right.
- [ ] **Budgets.** $2u+u^2 \le 2.1u$ and $3u+3u^2+u^3 \le 3.1u$ at $u=2^{-53}$, and the
      $\sqrt{\cdot}$ bound $\le 2u$.
- [ ] **$|p_j|$ vs $|a_j-\beta|$.** The row sum charges $\texttt{ETA}\cdot|p_j|$, the computed
      value, while the perturbation is $|a_j-\beta|\,|\eta_j|$. Confirm the slack covers it:
      $$
      |a_j-\beta|\,|\eta_j| \le \frac{|p_j|}{1-u}\,(2u+u^2) \approx (2u+3u^2)\,|p_j| \le 2.1u\,|p_j| .
      $$
- [ ] **Row structure.** Row $j$'s off-diagonal entries are $b_{j-1}-\tilde b_{j-1}$ (set by
      $\gamma_j$) and $b_j-\tilde b_j$ (set by $\gamma_{j+1}$), so $E$ is symmetric, as
      $\|E\|_2\le\|E\|_\infty$ requires.
- [ ] **Against the paper.** Read DDR pp. 131–133 (the derivation of (5.6) and §5.2 for tridiagonal
      matrices) and Table 5.1 on p. 137. Confirm the 2.5ε-vs-certkit difference is *only* the
      placement of roundings described in §3.
- [ ] **Guards.** Every intermediate is normal or exactly zero (lines 150–177), so no
      gradual-underflow term is missing.
- [ ] **Bracketing.** The margin check at lines 214–216 happens *before* the counts are compared.
- [ ] **Platform assumptions** (TCB.md §1: binary64, no FMA contraction, correctly rounded
      `sqrt`/`nextafter`). These are probed on every CI run on x86_64 and match macOS arm64 bit
      for bit (`tests/probe_platform.py`, `tests/platform_digest.txt`; certkit-8hn). Decide whether
      that's enough or whether a runtime guard is wanted.
- [ ] **certkit-330 fix** (`checker.py:724–745`). `_verify` authenticates the seal (`_sealed`)
      *before* reading or writing the memo, and `check_bundle` indexes only sealed certificates.
      Tests: `tests/test_composition.py` (all permutations of a forged duplicate hash). Its known
      residual: with a forged duplicate present, the *report* entry under that hash shows whichever
      copy came last. Verdicts and dependents aren't affected.

---

## 6. What's already been checked (so you don't redo it)

| Date | By | Covered | Found |
|---|---|---|---|
| 2026-09-01 | AI review | `interval.py`, `backward_error.py` | certkit-279, certkit-186 |
| 2026-09-02 | AI review | `operators.py`, `banded.py` | certkit-gh2 (CSR duplicates, soundness), certkit-be4 |
| 2026-09-02 | exact-rational fuzz | `interval.py` enclosure, 240k ops | none |
| 2026-09-23 | AI review | composition | **certkit-330: false VERIFIED** (fixed in 5597008) |
| 2026-09-24 | CI, x86_64 | platform probes and cross-arch digest | none |
| 2026-09-25 | AI review (Gemini) | derivation vs DDR | one false safety claim (retracted) |
| 2026-09-25 | citation check (Claude) | DDR Eq. 5.6, §5.2, Table 5.1, Lemma 5.1 against the PDF | page and attribution slips only |

The full notes are in the beads tracker: `bd show certkit-jcb`.

## 7. Signing off

Add a note to `certkit-jcb` with your name, the date, the checklist result, and anything you'd
file. If every item is ticked, close `certkit-jcb` and `certkit-330`. Otherwise file the defect and
leave both open.
