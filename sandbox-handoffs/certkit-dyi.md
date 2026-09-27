# Handoff: certkit-dyi — Independent soundness review of banded `sturm_be`

## Verdict

**Not closeable by this session, and not closed.** The bead's own text, and
`certkit-jcb`'s precedent, say a worker session may not close this — a human
must sign off. `bd show certkit-dyi` was already `IN_PROGRESS` when this
session started, with a full first-pass AI review (`REVIEW-dyi.md`) already
written by a prior session. Per this session's instructions ("do not assume
its partial work is correct"), I did not just re-read that review and trust
it — I independently re-derived the argument and re-ran fresh numerical
verification with my own from-scratch implementation, different from the
prior session's (uncommitted, no-longer-extant) script. Left `IN_PROGRESS`.

No code changed. No bound, tolerance, guard, or threshold was touched.

## What was already there (prior session, not mine)

`REVIEW-dyi.md` (repo root, untracked) — a reviewer brief for the banded
(`b>1`) backward-error route (`certkit/backward_error.py`'s
`banded_arrays`/`sweep_banded`, `checker.py`'s `_rule_sturm_be` fallback),
parallel to `REVIEW-jcb.md`. Covers the `LDL^T` reconstruction formula
derivation, eviction-safety hand-proof plus a 5000-trial empirical check, a
3550-trial empirical check of `delta >= ||A-Mtilde||_2` against numpy, and
overflow/abstain path tracing. Concluded no defect found. Full details in
that file and in this bead's history (`bd show certkit-dyi`).

## What I did this session (independent, not a re-read)

1. **Re-derived the formula from scratch and traced it against the code
   myself.** Read `certkit/backward_error.py` lines 240-436 and
   `certkit/checker.py` lines 637-662 directly (not via the review). Derived
   `M_jj = D_j + sum_{k=max(0,j-b)}^{j-1} L_jk^2 D_k` and
   `M_ij = L_ij D_j + sum_{k=max(0,i-b)}^{j-1} L_ik L_jk D_k` (`i>j`)
   independently, then checked `sweep_banded`'s `recon`/`recon_ij`
   accumulation (lines 374-393, 397-421) term by term against it, including
   that the `k=j` term (`Iv.exact(d[j])` / `Iv.exact(lij)*Iv.exact(d[j])`) is
   present in both. Matches what `REVIEW-dyi.md` §3 claims.
2. **Re-derived the `L`-eviction safety argument independently.** `L[i,k]`
   (`i-k<=b`) is last needed at outer step `j=i` (as `ljk` in column `i`'s own
   diagonal loop, lines 375-376). Eviction of column `k`'s entries happens at
   the end of outer step `j=k+b` (lines 427-430), and since `i<=k+b`, the last
   use at outer `j=i` happens no later than the eviction step, and strictly
   before it within that same iteration (diagonal loop runs before the
   eviction block). No case where eviction fires early. Matches `REVIEW-dyi.md`
   §4's conclusion.
3. **Confirmed `sweep_banded` has exactly one call site** outside tests:
   `backward_error.py:450` (`count_eigenvalues_below_backward_banded`), which
   is reached only from `checker.py`'s `_rule_sturm_be` `NotTridiagonal`
   fallback (`grep -rn "sweep_banded\b"` across the repo). Closes checklist
   item 6 ("no other caller of `sweep_banded`") in `REVIEW-dyi.md` §7.
4. **Fresh, from-scratch numerical verification** — a new numpy
   reimplementation of the banded `LDL^T` elimination (`/tmp/verify_dyi.py`,
   `/tmp/verify_dyi_adv.py`, not committed — same reasoning as the prior
   session: these answer a review question, they're not fixtures for
   `tests/test_backward.py`), run against the actual production
   `banded_arrays`/`sweep_banded`, with a different RNG seed and a different
   test-matrix generator than the prior session used:
   - 4000 random banded trials (`n` 2-30, `b` 0-6, `DenseSymmetric` operator
     built directly, not via JSON decode): **0 delta violations**
     (`sweep_banded`'s claimed `delta` was never `< true ||E||_2`, `E`
     computed at full numpy double precision from an independently-tracked
     `L`,`D`); tightest observed `delta/true_norm` ratio **2.4477**.
   - 2000 adversarial ill-conditioned trials (diagonal entries forced to
     `1e-7`/`1e7`, off-diagonals to `1e3`, `n` up to 60, `b` up to 8):
     **0 violations**; tightest ratio **1.6716**.
   - 2000 trials cross-checking `sweep_banded`'s returned `count` against the
     sign-count of my independently-tracked `D` pivots: **0 mismatches**
     (confirms Sylvester's-law step, not just the `delta` bound).
   This is independent corroborating evidence — a different implementation,
   different sampling, same production code under test — not a repeat of the
   prior session's numbers.
5. Re-ran the full test suite and the trust-boundary check fresh (below).

No defect found. Two independent AI passes now agree, plus independent
numerical evidence from a from-scratch reimplementation. This raises
confidence but is explicitly **not** a substitute for human sign-off — see
"What I could not verify."

## What I decided not to do, and why

- **Did not touch the Lean side.** Same reasoning as the prior session:
  out of this bead's scope, `sweep_backward_bound` is specific to the
  tridiagonal `ETA`/`GAMMA` derivation.
- **Did not commit the verification scripts.** Same reasoning as the prior
  session — they're a review artifact answering "does the claimed bound
  actually hold against ground truth," not a regression fixture. If a human
  reviewer wants this kind of property-check made permanent
  (`tests/test_backward.py` currently checks count-vs-LAPOCK agreement, not
  `delta` vs. a numpy-computed true operator norm), that's a good follow-up
  bead — flagging it, not filing it, to avoid unilaterally expanding scope.
- **Did not rewrite or expand `REVIEW-dyi.md`.** It already exists, is
  structurally sound, and duplicating it would just create two documents for
  a human reviewer to reconcile. Recorded this session's independent
  corroboration in the bead's notes (`bd show certkit-dyi`) instead, where a
  reviewer will see both passes in one place.
- **Did not attempt to close `certkit-dyi`.** Explicit in the bead, in
  `CLAUDE.md`'s `certkit-jcb` precedent, and in this session's own
  instructions.
- **Did not re-review `interval.py`'s own overflow/arithmetic contract** —
  `certkit-jcb`'s already-closed scope; relied on it as the prior review did.

## What I could not verify

- **Same blind-spot risk the bead exists to catch, now doubled.** Two model
  sessions independently deriving the same formula and agreeing is stronger
  evidence than one, but if both sessions share a systematic blind spot (the
  same class of algebra mistake, or the same thing neither of us thought to
  adversarially construct), agreement between us proves nothing. A human's
  independent derivation is still the only thing that closes this.
- **I did not construct a matrix specifically designed to break the bound**
  (as opposed to "randomly adversarial" via ill-conditioning). `REVIEW-dyi.md`
  §7's checklist explicitly asks the human reviewer to attempt this; I have
  not substituted for it.
- **Platform-dependence** — ran only on this session's container, same
  caveat the prior session noted (no cross-arch re-check analogous to
  `certkit-8hn`'s tridiagonal one).

## Test suite and no-dependency check (re-run fresh this session)

```
uv run --extra dev pytest tests -q
........................................................................ [ 36%]
........................................................................ [ 72%]
.......................................................                  [100%]
199 passed in 47.49s
```

No bare `python3` in this container (matches the prior session's note).
Ran the trust-boundary suite instead, which mechanically covers the same
property (`test_checker_runs_in_a_process_where_numpy_is_unimportable`):

```
uv run --extra dev pytest tests/test_trust_boundary.py -v
tests/test_trust_boundary.py::test_trusted_modules_do_not_import_the_producer PASSED
tests/test_trust_boundary.py::test_trusted_modules_import_only_stdlib_and_each_other PASSED
tests/test_trust_boundary.py::test_checker_runs_in_a_process_where_numpy_is_unimportable PASSED
tests/test_trust_boundary.py::test_witness_carries_no_producer_computed_bound PASSED
4 passed in 0.20s
```

## Handoff

- `certkit-dyi`: left `IN_PROGRESS`, notes appended documenting this
  session's independent re-derivation and numerical verification (separate
  from, and corroborating, the prior session's `REVIEW-dyi.md`).
- `REVIEW-dyi.md` (repo root): unchanged, still the document for a human
  reviewer to walk through (its §7 checklist is the sign-off gate).
- `issues.jsonl` re-exported (`bd export -o issues.jsonl`) so this session's
  notes survive in git.
- Pre-existing untracked file `lean/Certkit/Scratch2.lean` (dated Sep 2, well
  before this session) present at session start, not mine, not touched.
- Suggested next commands (not run — git policy is report-only):
  ```
  git add issues.jsonl sandbox-handoffs/certkit-dyi.md
  git commit -m "certkit-dyi: second independent AI pass corroborates banded sturm_be review"
  ```
  (`REVIEW-dyi.md` is already untracked from the prior session and was not
  modified here; add it in the same commit if it wasn't already committed.)
