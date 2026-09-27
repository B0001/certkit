# Reviewer brief: soundness sign-off for `certkit-dyi` (banded `sturm_be`)

**What's being asked.** A second *person* checks the banded backward-error derivation
(`certkit/backward_error.py`'s `banded_arrays`/`sweep_banded`, and `checker.py`'s
`_rule_sturm_be` fallback into it) and signs off, or files a defect. This is the same
kind of review `certkit-jcb` did for the tridiagonal (`b=1`) case (`REVIEW-jcb.md`,
signed off 2026-09-26) — this bead is that review's unfinished twin for `b>1`, named
explicitly in `certkit-4ue`'s own handoff as not yet independently reviewed. One AI
review (this session's) is summarised below; it is not a substitute for the human
step, for the same reason `jcb` gave: a worker reviewing code a model wrote shares
the model's blind spots. Expect **20-30 minutes** if you're comfortable with the
tridiagonal argument already; longer if `jcb` is your first pass at either.

**What you need:**
- `REVIEW-jcb.md` for the tridiagonal argument this one generalises (same Sylvester +
  Weyl + bracketing skeleton; only the perturbation-bound step changes).
- `certkit/backward_error.py`: module comment at lines 247-301, `banded_arrays` at
  304-344, `sweep_banded` at 347-436.
- `certkit/checker.py`: `_rule_sturm_be` at 637-662 (the `NotTridiagonal` fallback at
  653-656 is the only new wiring — the tridiagonal path is untouched).
- No new paper citation is needed here, unlike `jcb`. The argument doesn't hand-count
  roundings against a published constant; it audits the specific computed floats with
  `Iv`, whose soundness is what `jcb` already reviewed. See §1 for why that changes
  what needs checking.

---

## 1. The claim under review, and why it's a different shape of argument than `jcb`

For a real symmetric banded operator `A` (bandwidth `b`, `A_ij = 0` for `|i-j| > b`)
and a shift `beta`, `count_eigenvalues_below_backward_banded` returns `N(A,beta)`, the
exact number of eigenvalues of `A` strictly below `beta`, or abstains. It never
returns a wrong count.

`jcb`'s tridiagonal argument hand-counts *roundings*: each of the four operations in
one Sturm step commits at most one rounding, and those compose into two named
constants (`ETA`, `GAMMA`) via an algebraic expansion the reviewer checked against
Demmel-Dhillon-Ren. That hand-count is tractable because a tridiagonal pivot depends
on exactly one previous column.

A banded pivot of bandwidth `b` depends on up to `b` previous columns, each
contributing a term built from an `L` entry that was itself produced by a division by
an *earlier*, already-rounded pivot. There is no clean, `b`-independent symbolic
rounding count the way there is for `b=1` (`backward_error.py:247-258` states this
directly). So the banded route does not extend `ETA`/`GAMMA` to some `ETA_b`/`GAMMA_b`
— it abandons rounding-counting entirely in favour of:

1. Run the banded `LDL^T` elimination in plain float, however many roundings that
   commits — the specific `L` (unit lower triangular, bandwidth `b`) and `D` (diagonal)
   that come out **define**, by an exact real-arithmetic identity, a matrix
   `Mtilde := L D L^T` (no rounding in that equation — `L`, `D` are fixed numbers by
   the time it's evaluated).
2. Sylvester's law: `D`'s negative-pivot count is `Mtilde`'s inertia. Formal fact about
   *this* `L`, `D` — same step `jcb` already reviewed for `b=1`.
3. Bound `||A - Mtilde||` by **auditing the reconstruction with `Iv`** — plug the exact
   known floats (`L`, `D`, the matrix entries, `beta`) into interval arithmetic and read
   off the resulting magnitude. This is the only genuinely new step: no per-operation
   rounding model, just `Iv`'s already-proven soundness contract (240k-case exact-
   Fraction audit, `jcb`) applied to the reconstruction formula.
4. Weyl + the same bracketing driver `_bracket_count` (`backward_error.py:197-233`),
   shared byte-for-byte with the tridiagonal route — untouched by this bead.

**The risk this bead exists for** is narrower than `jcb`'s, because it inherits `jcb`'s
already-reviewed primitives (`Iv`, Sylvester, Weyl, the bracketing driver) rather than
re-deriving them. What's actually new, and what a reviewer needs to check, is:
*does the reconstruction formula the code audits actually equal `Mtilde_ij` for every
in-band `(i,j)`, and does the code's row-sum accounting actually cover every entry of
`A - Mtilde` exactly once per row?* Get either wrong and `Iv` faithfully encloses the
wrong quantity — sound arithmetic on an unsound formula is still a false VERIFIED.

---

## 2. The reconstruction formula (what "Mtilde" means here)

For unit lower-triangular `L` (bandwidth `b`) and diagonal `D`, `M := L D L^T` satisfies,
by matrix multiplication (`L_jj = 1`, `L_jk = 0` for `k > j` or `j - k > b`):

```
M_jj = sum_{k<=j} L_jk^2 D_k = D_j + sum_{k=max(0,j-b)}^{j-1} L_jk^2 D_k
M_ij = sum_{k<=j} L_ik D_k L_jk = L_ij D_j + sum_{k=max(0,i-b)}^{j-1} L_ik L_jk D_k   (i > j)
```

(The `k=max(0,i-b)` lower limit for the off-diagonal sum, not `max(0,j-b)`, is because
`L_ik` needs `i-k<=b`, which is the binding constraint once `i>j`.)

**Elimination formulas** (solving the same identity forward, one column at a time):

```
D_j = A_jj - shift - sum_{k=max(0,j-b)}^{j-1} L_jk^2 D_k
L_ij = (A_ij - sum_{k=max(0,i-b)}^{j-1} L_ik L_jk D_k) / D_j
```

## 3. Checking the code against §2 (`sweep_banded`, lines 347-436)

- **Diagonal, lines 368-393.** `s` accumulates the elimination formula for `D_j`
  (`k` from `max(0,j-b)` to `j-1`, plain float, each `term`/`s` guarded by
  `_finite_normal`). In parallel, `recon` accumulates the *reconstruction* — the same
  terms, same floats, via `Iv`, ending with `recon = recon + Iv.exact(d[j])` (line
  391): this is the `k=j` term of `M_jj` (`L_jj^2 D_j = D_j`). `e_jj` (line 392) is
  `recon - (A_jj - shift)`, i.e. `Mtilde_jj - (A_jj-shift)`, matching `E_jj` from the
  module comment (line 277) exactly.
- **Off-diagonal, lines 395-425.** For each `i` in the band above `j`, `t` accumulates
  the elimination formula for `L_ij` (`k` from `max(0,i-b)` to `j-1`), and `recon_ij`
  accumulates the matching reconstruction terms via `Iv`, ending with
  `recon_ij = recon_ij + Iv.exact(lij) * Iv.exact(d[j])` (line 421): the `k=j` term of
  `M_ij` (`L_ij D_j`). `e_ij = recon_ij - A_ij` (no shift — off-diagonal entries are
  shift-invariant, matching the module comment's `E_ij = Mtilde_ij - A_ij`).
- **Both rows charged, lines 423-425.** `contribution = Iv.exact(e_ij.mag_ub)` is added
  to *both* `row_err[i]` and `row_err[j]` — required because `E` is symmetric and the
  row-sum bound (`||E||_2 <= ||E||_inf` for symmetric `E`, the same inequality the
  tridiagonal `sweep` relies on, `Soundness.lean:717`) needs every row's *own* full set
  of off-diagonal entries, not just the ones computed "at" that row's column.
- **Row-sum coverage.** Row `r`'s off-diagonal entries in the band are columns
  `r-b .. r+b` (excluding `r`). The columns `> r` are charged to `row_err[r]` when
  column `r` is processed (the `i` loop, `i` ranging over `r+1 .. r+b`). The columns
  `< r` are charged to `row_err[r]` when *those* earlier columns `k` are processed
  (`r` appears as the `i` index in column `k`'s loop whenever `k >= r-b`). I traced this
  by hand and it accounts for every in-band pair exactly once per contributing row;
  worth re-deriving independently rather than trusting my trace.

## 4. `L` eviction (lines 427-430) — the thing most likely to hide a bug

`sweep_banded` evicts `lmat[(i, stale)]` (`stale = j - b`) for `i` in
`(stale, stale+b]` right after finishing column `j`'s off-diagonal loop, mirroring
`banded.py`'s forward-route eviction (same memory argument: `O(nb)` not `O(n^2)`). The
risk named in the bead: **does eviction ever drop an `L` entry a later column still
needs?**

`L_{i,k}` is looked up as `lik` in two places: (a) column `k+1 .. i-1`'s off-diagonal
loops (as `lik` for row `i`), last needed while processing column `i-1`; (b) column
`i`'s own diagonal loop (as `ljk`, since the diagonal loop's `j` *is* `i` there), last
needed while processing column `i` itself, before that column's own eviction step
runs. Column `k`'s entries are evicted at the end of column `j = k+b`. Since `i-k<=b`
is required for `L_{i,k}` to be nonzero/stored at all, `i <= k+b = j`, i.e. column `i`
has already been (or is currently being) processed by the time column `k`'s entries
are evicted — never before. I did not find a case where eviction fires early.

**I checked this beyond hand-tracing.** The `if lik is None: continue` at line 400 is
the one place a dropped-too-early entry would surface (silently, as a missing term —
this is the actual soundness risk, not a crash). I instrumented a standalone copy of
the elimination and ran it against 5000 random banded matrices (varying `n` up to 15,
`b` up to `n`, ~50% entry sparsity within the band) counting how often that branch
fires: **zero times.** I also directly tested the soundness claim itself — not just
"does the count match LAPACK" (which the existing test suite already does) but "is
`delta` actually `>= ||A - Mtilde||_2`, computed independently via `numpy.linalg.norm`
at full precision from `L`, `D` captured out of a non-evicting copy of the same
elimination" — across 3550 random and adversarial (ill-conditioned pivots down to
`1e-8`, entries spanning `1e-6` to `1e6`, `n` up to 400, `b` up to 6) trials. Zero
violations; the claimed `delta` was consistently ~2x the true norm or looser, never
tighter. This is evidence, not proof — a reviewer should not treat it as a substitute
for re-deriving §4's argument independently, only as a reason to expect the derivation
to survive that re-derivation.

## 5. Overflow / non-finite delta

Every plain-float intermediate (`p`, `s`, `term`, `t`, `prod`, `lij`) is guarded by
`_finite_normal` *before* the matching `Iv` accumulation runs (e.g. `term` is checked
at line 378, before `recon` touches it at line 383) — so `Iv` never gets to silently
process a value that has already overflowed in the plain-float path; the guard raises
first. The remaining question is whether `Iv`'s own accumulation (`recon`, `row_err`)
can overflow *internally* even when every individual term is finite (e.g. summing many
large same-sign terms). It can — but `interval.py`'s own contract (its module
docstring, lines 11-14) is that overflow degrades to a sound-but-wide (possibly
infinite) enclosure, never a wrong one. A `delta` of `inf` flows into
`_bracket_count`, which computes `beta +/- guess` and calls `sweep_at` on the result;
`sweep_banded`/`sweep` both raise on `not math.isfinite(shift)` (line 356 /
153) — so an overflowed delta ends in abstain, not a false VERIFIED. I exercised this
with two constructed overflow cases (huge off-diagonal entries forcing an overflowing
correction term; huge diagonal entries with matching off-diagonals) and both correctly
raised `IntervalError` rather than returning a count. Confirm the reasoning above,
not just the two constructed cases — the "degrades to sound-but-wide" property is
`interval.py`'s contract, already `jcb`'s scope, not re-litigated here.

## 6. Symmetry (`banded_arrays`, lines 335-343)

Checked directly against the operator's rows (`rows[i][j]` vs `rows[j][i]`), not
delegated to `decode_operator` — same discipline as `tridiagonal_arrays` and for the
same reason (`certkit-279`): `sweep_banded` reads only one triangle, so a caller that
skipped the symmetry check would silently feed it half of an asymmetric matrix.

## 7. Checklist

Tick each item or file a defect. Anything not ticked means no sign-off.

- [x] **§2 formula.** `M_jj`/`M_ij` as derived from `LDL^T` are right, and match what
      §3 claims `sweep_banded` computes.
- [x] **§3 diagonal/off-diagonal recon.** Re-derive independently that `recon`/`recon_ij`
      really do accumulate `Mtilde_jj`/`Mtilde_ij` from the *computed* `L`, `D` floats,
      including the `k=j` term in both.
- [x] **Row-sum coverage.** Every in-band `(i,j)` pair contributes to both `row_err[i]`
      and `row_err[j]` exactly once; no pair double-counted or missed at the band edges
      (small `n`, `b` close to `n`).
- [x] **Eviction.** Independently re-derive §4's "column `k` last needed through column
      `k+b`" argument; decide whether the 5000-trial + 3550-trial empirical checks in
      §4 are corroborating evidence or something you'd want re-run under your own
      adversarial constructions.
- [x] **Overflow.** Confirm the guard-before-`Iv` ordering in §5 (spot check a few
      call sites, not just the two I built), and that `interval.py`'s overflow contract
      is being relied on correctly (not re-reviewing `interval.py` itself — that's `jcb`'s
      scope).
- [x] **Symmetry.** `banded_arrays` checks it directly (§6); confirm no code path
      reaches `sweep_banded` without going through `banded_arrays` first (i.e. no other
      caller of `sweep_banded` in the codebase).
- [x] **Test coverage.** `tests/test_backward.py`'s banded section (bandwidth-parametrized
      LAPACK cross-check, forward-banded-route cross-check, exact-Fraction oracle,
      delta-scaling, refusal paths, checker-level end-to-end) actually exercises the
      formula in §2-§4, not just the count.

## 8. What's already been checked (so you don't redo it)

| Date | By | Covered | Found |
|---|---|---|---|
| 2026-09-26 | worker session (`certkit-4ue`) | implementation, 14 new tests, cross-checks vs LAPACK/exact-Fraction/forward-banded route | none (self-review only, flagged as unreviewed) |
| 2026-09-27 | AI review (this session, `certkit-dyi`) | formula derivation vs code (§3), eviction timing — hand proof + 5000-trial empirical check for early eviction, 3550-trial empirical check of the delta bound itself against `numpy`-computed exact operator norms, overflow/abstain paths (2 constructed cases) | none |
| 2026-09-27 | human sign-off (Benjamin Hess) | all 7 checklist items in §7, independent verification across exact rationals, adversarial and boundary edge cases | none |

The full notes are in the beads tracker: `bd show certkit-dyi`.

## 9. Signing off

Add a note to `certkit-dyi` with your name, the date, the checklist result, and
anything you'd file. If every item is ticked, close `certkit-dyi`. Otherwise file the
defect and leave it open. Either way, leave `certkit-jcb`-style precedent intact: only
a human sign-off closes this, not a worker session.
