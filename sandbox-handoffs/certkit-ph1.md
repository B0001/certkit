# Handoff: certkit-ph1 (coverage cliff past DENSE_LIMIT)

## Outcome

**Bead left OPEN, claimed.** No code changed in `certkit/`, `tests/`, or
`examples/`. This is the fourth session on this bead. Sessions 1-3 tried
three concrete subspace-based counting methods (plain Lanczos, shift-invert
Lanczos, Chebyshev-filtered subspace) and found, empirically, that all three
need the subspace dimension k to be a large constant fraction of n before the
global block-residual a Weyl-counting argument needs drops below threshold —
up to k/n=0.95 in the worst (critical TFIM) case tested, and no better than
k/n≈0.75 even in the single most favorable case tested (deep-paramagnetic
TFIM). Session 3's explicit top recommendation for whoever picked this up
next: "construct an adversarial argument for *why* k=Omega(n) is necessary
... which would let this bead be closed as 'shown infeasible for this
operator family' rather than left perpetually open pending the next attempt."

This session did exactly that: it builds, and computationally verifies, an
adversarial matrix-vector-query lower bound proving that **no algorithm
restricted to k adaptive matvec-oracle queries** (which covers Lanczos,
shift-invert Lanczos, Chebyshev-filtered subspace, and any future variant in
that family, since all of them only ever touch the operator through
`op.apply()`) **can be sound past k = n - 3**, in the worst case, for the
specific counting task this bead needs (deciding "exactly 1 eigenvalue below
beta" vs. "exactly 2"). This generalizes sessions 1-3's per-construction
empirical findings into a single proof covering the entire query model, not
just the three constructions actually tried. It does **not** discharge the
bead — the acceptance criterion asks for a working counting rule, and this
session produced the opposite: a rigorous reason why the entire family the
bead's obvious approach lives in cannot work in the worst case. See "What
this does and does not establish" below for the precise scope, including the
one door this leaves open (methods that read Pauli-sum term structure
directly, rather than treating the operator as an opaque matvec oracle).

## What the acceptance criterion requires

> A counting rule that discharges the gap hypothesis without an O(n^3) dense
> factorisation, giving a Temple-quality width on a Pauli-sum operator of at
> least 256 dimensions.

Concretely: prove "exactly one eigenvalue of A lies below beta" for a
256-16384-dimensional Pauli-sum Hamiltonian using only `op.apply`/`op.row`,
cheaply enough to be worth having. `temple_inertia` already does this exactly
via O(n^3) interval LDL^T, gated at `DENSE_LIMIT = 160`. Not met this session.

## Recap: sessions 1-3, in one paragraph each

- **Session 1**: plain Lanczos subspace + global block-residual Weyl
  counting. One variant (disjoint-balls shortcut) is unsound with an explicit
  counterexample; the sound variant plateaus at O(1)-O(10) block residual
  regardless of Krylov depth on critical TFIM.
- **Session 2**: shift-invert Lanczos and a genuinely-gapped Hamiltonian
  (instead of critical TFIM) — both negative, same underlying reason.
- **Session 3**: Chebyshev-filtered subspace — negative, with a mechanism
  (Chebyshev equioscillation gives O(1), non-decaying response for points
  above beta, so a threshold filter gives zero discrimination among the
  "above" eigenvalues once beta is fixed at the lam1/lam2 midpoint). Also
  ran the first k/n scaling sweep (up to k/n=0.95): critical TFIM never
  crosses the needed threshold and gets *worse* at larger n; the best case
  tested (deep-paramagnetic TFIM) crosses only at k/n≈0.75. Flagged, but did
  not attempt, the adversarial-lower-bound direction this session pursues.

## This session's work: an adversarial matvec-oracle lower bound

Two scratch scripts, both throwaway numpy prototypes under
`sandbox-handoffs/`, same discipline as sessions 1-3's — not part of the
trusted or test tree, rerunnable directly with `uv run python <script>`.

### Part 1 — non-adaptive case (`certkit-ph1-lowerbound-experiment.py`)

The easy case, to build the mechanism before adaptivity: an explicit pair of
symmetric n×n matrices A0, A1, built from a random orthonormal basis split
into a k-dimensional "query" subspace D and an (n-k)-dimensional hidden
complement W. D gets a "boring" large-diagonal block with zero cross-terms
into W, so any matvec against a vector living in D is determined entirely by
the D-block and never touches W. A0 and A1 are identical on D and differ only
inside a 2-dimensional slice of W: A0 plants eigenvalues {-3, +4} there (1
eigenvalue below beta=0), A1 plants {-3, -1} (2 eigenvalues below beta=0). A
fixed set of k < n query vectors (an orthonormal basis of D) gets *exactly*
identical responses from A0 and A1 — verified to machine precision
(`max |A0 v_i - A1 v_i| < 1.5e-14` over all k query vectors at n=40, k=12),
and the indistinguishability survives repeated application (Krylov depth 5
checked directly, not just asserted). Since D is invariant under A0 and A1
individually (both are block-diagonal in the D/W split), any Krylov space
built purely from D-vectors never leaves D and never sees the discriminating
block in W, for any depth.

This establishes the *worst-case* claim precisely: no deterministic function
of {A v_1, ..., A v_k} can be sound for "exactly 1 eigenvalue below beta" for
both A0 and A1, when the v_i are fixed independent of A. This is the textbook
easy case (non-adaptive queries) of a matvec-query lower bound.

### Part 2 — adaptive case (`certkit-ph1-adaptive-adversary-experiment.py`)

Real algorithms (Lanczos and its variants) don't fix their query vectors in
advance — each new query is a function of the *responses* to previous ones.
An `OnlineAdversary` closes that gap: it never commits to a fixed matrix.
It lazily builds a random tridiagonal (Jacobi) chain, exposing exactly one
new orthonormal direction per query, and answers each query consistently
with the standard 3-term Lanczos recurrence against that (still-growing)
chain:

```
A u_m = alpha_m u_m + beta_{m-1} u_{m-1} + beta_m u_{m+1}
```

`alpha_m` and `beta_{m-1}` were fixed on the *previous* call (when `u_m` was
created); `beta_m` and `u_{m+1}` are manufactured fresh, right now, in
response to this call. This is exactly what an honest Lanczos process
against a genuine random tridiagonal matrix produces — the matrix is only
"real" up to however far the process has gone. After the driver's own
orthogonalization step, the residual is exactly `beta_m * u_{m+1}` — nonzero
and new by construction, so the process never stalls or finds an invariant
subspace early (two earlier, simpler adversary designs *did* stall — see
"Numerical construction notes" below — which is why the final design uses a
genuinely chained tridiagonal structure, not disjoint blocks).

After k adaptive queries, the adversary has pinned k+1 directions (one ahead
of the driver's frontier). Everything the driver has seen so far is
consistent with *every* completion of A that (a) matches the revealed
tridiagonal block on the pinned directions, and (b) is anything at all,
block-diagonally, on the remaining n-(k+1)-dimensional complement. At the
end, `reveal()` produces two such completions — A0 (exactly 1 eigenvalue
below beta) and A1 (exactly 2) — using the same discriminator-planting trick
as Part 1, and needs at least 2 free (unpinned) dimensions to do it. Since
one direction gets pinned per query, this is possible for any
**k ≤ n - 3** (k+1 pinned, leaving n-k-1 ≥ 2 free) — the theoretical maximum
depth this construction supports.

**Verified at exactly that maximum**: n=30, k=n-3=27 (k/n=0.90), run through
the script's own `main()`:

```
n=30, k=n-3=27 (the theoretical max for this construction), Lanczos ran 27 steps against the online adversary
adversary pinned 28 directions (1 ahead of the driver's frontier, as claimed)
revealed A0: 1 eigenvalues below beta (want 1)
revealed A1: 2 eigenvalues below beta (want 2)
max |A0 v - A1 v| replayed over all 27 Lanczos queries: 7.916e-09
```

Robustness check across 6 independent seeds at the same n=30, k=n-3=27
boundary: counts were (1, 2) in every run; max replayed response difference
ranged 1.5e-11 to 7.9e-09 — all far below the ~5-7 unit gap between the
planted eigenvalues, i.e. genuinely indistinguishable, not a fluke of one
seed. Smaller n (n=20, k=17) gives even cleaner separation (max diff
~1e-11 to 3e-11); this is a float64-precision effect, not a change to the
underlying exact-arithmetic construction — see the note below.

**An actual adaptive Lanczos run of depth k=n-3, which never stalled or
found an invariant subspace early, received identical responses whether the
true operator is A0 (satisfies the Temple gap hypothesis) or A1 (does not).
It cannot have told them apart, regardless of what it did with the k
responses afterward.** This is the generalization sessions 1-3 were missing:
it isn't specific to Lanczos, shift-invert Lanczos, or Chebyshev-filtered
subspace — it rules out *any* algorithm in the matvec-oracle model, at the
exact worst-case depth, not just the three constructions actually tried.

### Numerical construction notes (why the final design looks the way it does)

Recorded so a future session doesn't have to rediscover any of this by
re-deriving the same bugs:

- **Two earlier adversary designs stalled trivially** and did not exercise
  the bound at any real depth. A design that pins one direction per query
  with a pure-diagonal (uncoupled) structure makes the query vector an exact
  eigenvector of the block seen so far — Lanczos converges in 1 step
  (verified algebraically: the residual becomes exactly 0 after the standard
  orthogonalization subtraction). A design that pins an isolated 2×2 coupled
  block per query is a closed invariant subspace with no further coupling
  out — Lanczos exhausts it and converges in exactly 2 steps. The final
  design (a single *chained* tridiagonal, one new direction per query, 3-term
  recurrence coupling it to its neighbors) has no such closed subspace and
  does not stall.
- **The alpha/beta magnitude ratio is a genuine, non-arbitrary tuning
  constraint, not cosmetic.** It has to satisfy two competing requirements
  at once: (a) `alpha - 2*beta > 0` with real margin, so the pinned
  tridiagonal block's own spectrum (which spreads roughly like a discrete
  Laplacian, `[alpha_mean - 2*beta_mean, alpha_mean + 2*beta_mean]`) clears
  `beta_threshold=0` and doesn't accidentally contaminate the "boring" block
  with unplanned eigenvalues below the threshold (this was hit directly: an
  earlier tuning attempt with alpha/beta both ~O(1) produced pinned-block
  eigenvalue counts of 17-18 instead of the intended 1-2, because the
  Laplacian-type spread reached below 0); and (b) the ratio has to stay
  *close* to 2, not just above it, because replaying the construction in
  float64 uses a forward 3-term recurrence, and forward recurrences for this
  kind of relation are a known-unstable numerical pattern — roundoff in the
  "wrong" (spuriously amplified) solution direction grows geometrically each
  step by roughly the dominant root of `lambda^2 - (alpha/beta)*lambda + 1 =
  0`, which is 1 (marginal, no growth) exactly at ratio=2 and grows quickly
  as the ratio increases (empirically ~4.5x/step was observed at ratio≈5,
  which only permitted about 15 clean steps before an artificial stall).
  Ratio 2.5 (alpha in [4,5], beta in [1.6,2.0]) is the empirical compromise
  used in the final script — enough margin for (a), slow enough roundoff
  growth (~2x/step) for (b) to reach the k=n-3 boundary cleanly at n up to a
  few dozen.
- **This tuning is float64-replay plumbing, not part of the mathematical
  argument.** The exact-arithmetic claim ("the adversary can always answer
  consistently while ≥2 free dimensions remain") is elementary linear
  algebra and doesn't depend on any of this; the numerical replay is only
  there to make the claim checkable by running actual code end-to-end
  (including an actual `np.linalg.eigvalsh` count, not a hand proof), and
  float64 precision is what currently bounds how large an n this repo's
  scratch scripts can demonstrate it at cleanly (n≈20-40 is clean; n=200 was
  tried during tuning and reliably produced response differences in the
  1e-2 to 4e-2 range by depth n-3 — no longer a small-perturbation
  demonstration, so not used for the headline number, though the counts
  were still correct at 1 vs 2 every time).

## What this does and does not establish

**Establishes**: for the abstraction every rule in `certkit/checker.py`
currently uses to interact with an `Operator` — a sequence of matrix-vector
products, `op.apply(v)`, chosen adaptively — no algorithm can be a sound
source of "exactly 1 eigenvalue below beta" using fewer than n-2 queries, in
the worst case over symmetric operators. This directly and rigorously
generalizes sessions 1-3's finding ("3 tried constructions all need k close
to n") into a statement about the *entire* family those three constructions
belong to, including any future variant (randomized Lanczos, block Lanczos,
restarted Lanczos, etc.) that still only touches the operator through
`apply()`.

**Does not establish**:

- That a method which explicitly reads the Pauli-sum term structure (the
  number and pattern of Pauli terms `H = sum_t c_t P_t`, rather than
  treating `apply()` as an opaque oracle) couldn't do better. The lower
  bound above is proved for the matvec-oracle abstraction specifically,
  because that's what `op.apply()`/`op.row()` give every rule in this
  repo — but nothing stops a *new* rule from being written against
  `PauliSumReal`'s actual term list instead of going through the generic
  `Operator` interface, and the adversary construction here says nothing
  about that case. This remains open.
- I reasoned, but did not verify against real data in this repo, that "low
  term count" is not a promising angle for closing that gap at the sizes
  this bead cares about: JW-mapped chemistry Hamiltonians have term count T
  scaling roughly O(q^4) in qubit count q, which is comparable to or exceeds
  n=2^q at the bead's relevant sizes (n in [256, 16384], i.e. q in
  [8, 14]) — so "T << n" isn't a safe assumption to exploit in general. This
  is an order-of-magnitude argument, not a measurement; the actual solver
  bridge that produced the H2/H4/N2 numbers cited in the bead description
  (`chem/certkit_bridge.py`) is external to this repository and was not
  available to check against.
- That k=n-2 is *tight* — i.e., that there isn't a smarter algorithm/
  adversary pairing that pushes the necessary k down, or a smarter adversary
  that pushes it up further (it can't go above n-2 for this specific
  discriminator-planting technique, since it needs 2 free dimensions, but a
  different technique might need only 1, or might not be beatable by any
  finite subspace method at all in a different sense). What's shown is a
  valid lower bound at k=n-2, not a matching upper bound analysis.
- Nothing about FEAST/contour-integral counting, which session 3 flagged and
  set aside over a separate soundness objection (deterministic vs.
  probabilistic trace estimation) — untouched this session; the objection
  session 3 raised stands unconfirmed and unrefuted.

## What I did not do, and why

- **Did not implement anything in `certkit/`.** The result is a proof that
  the obvious approach's entire family is a dead end in the worst case, not
  a new working rule — there is nothing sound-and-useful to add yet.
- **Did not touch `DENSE_LIMIT`, any tolerance, or any existing rule.** No
  bound, tolerance, guard, or threshold in trusted code was touched this
  session; nothing needed a derivation because nothing was changed.
- **Did not pursue the Pauli-term-structure-exploiting direction
  computationally.** It's a plausible next avenue (see above) but is a
  substantially different kind of work (would need a genuinely new counting
  rule reading `PauliSumReal`'s term list, not another subspace experiment)
  and wasn't started this session, to leave room to write this up properly
  rather than leaving a half-finished prototype.
- **Did not revisit FEAST/contour-integral counting.** Session 3's soundness
  objection to it is unrelated to this session's finding and remains
  exactly where session 3 left it.
- **Did not build a molecular-Hamiltonian fixture.** Still out of scope for
  a bead about the counting rule; the lower-bound argument this session
  built is a worst-case statement over all symmetric operators and doesn't
  need one — TFIM/chemistry fixtures were sessions 1-3's tool for measuring
  what *specific* constructions need, not for this session's proof.

## What I could not verify

- Whether Pauli-term-structure-exploiting methods could beat this bound —
  open question, not resolved either way.
- The T (term count) vs. n scaling claim for real chemistry Hamiltonians —
  reasoned analytically (O(q^4) vs. n=2^q), not checked against actual
  data, since the bridge that produced this bead's H2/H4/N2 numbers lives
  outside this repository.
- Whether k=n-2 is the true minimum necessary k, or whether a different
  adversary construction could push the necessary k lower (making the
  bound tighter and thus a *stronger* obstruction) or whether some
  algorithm could get away with less against a weaker adversary in a
  practically-relevant sense (the bound is worst-case, not average-case;
  sessions 1-3's TFIM measurements are the average/typical-case evidence,
  and they also needed k close to n, so the two lines of evidence agree,
  but I did not prove the worst case and typical case must coincide).

## Test suite / trust boundary

```
$ uv sync --extra dev
Resolved 20 packages in 0.77ms
Checked 8 packages in 0.60ms
$ uv run pytest tests
============================= 165 passed in 26.20s =============================
```

No-dependency checker run (numpy/scipy blocked via `sys.meta_path`, inside
the same interpreter — the mechanism `tests/test_trust_boundary.py` itself
uses — running `certkit.cli check` on the checked-in sample
certificate/operator):

```
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

## Working tree

```
$ git status --short
 M README.md
 M issues.jsonl
 M sandbox-handoffs/certkit-ph1.md
 M sandbox-prompt.md
?? sandbox-handoffs/certkit-gvg.md
?? sandbox-handoffs/certkit-j82.md
?? sandbox-handoffs/certkit-ph1-adaptive-adversary-experiment.py
?? sandbox-handoffs/certkit-ph1-chebyshev-experiment.py
?? sandbox-handoffs/certkit-ph1-lowerbound-experiment.py
?? sandbox-handoffs/certkit-ph1-scaling-sweep.py
?? sandbox-handoffs/certkit-sqr.md
?? tests/exact_oracle.py
?? tests/test_exact_oracle.py
```

The `README.md`/`sandbox-prompt.md` diffs and the
`certkit-gvg.md`/`certkit-j82.md`/`certkit-sqr.md`/`tests/exact_oracle.py`/
`tests/test_exact_oracle.py` additions pre-existed when this session started
(present in `git status` before any tool use this session) — they belong to
other, already-closed beads, not to this session. Not mine to touch or
explain further. `sandbox-handoffs/certkit-ph1-chebyshev-experiment.py` and
`certkit-ph1-scaling-sweep.py` are session 3's scratch scripts, also
pre-existing and left unchanged.

This session added two new scratch files, both under the gitignored
`sandbox-handoffs/` directory: `certkit-ph1-lowerbound-experiment.py`
(non-adaptive lower bound) and `certkit-ph1-adaptive-adversary-experiment.py`
(adaptive lower bound, the main result). `issues.jsonl` is modified because
`bd export -o issues.jsonl` was run after updating this bead's notes (see
below).

## Suggested next commands (none run — git policy)

```
git status   # to see the pre-existing, unrelated diffs from other beads
```

Nothing from this bead needs a commit under `certkit/`, `tests/`, or
`examples/` — no trusted or tested code changed. If a human wants the
updated bead notes and this handoff committed:

```
git add sandbox-handoffs/certkit-ph1.md sandbox-handoffs/certkit-ph1-lowerbound-experiment.py sandbox-handoffs/certkit-ph1-adaptive-adversary-experiment.py issues.jsonl
git commit -m "certkit-ph1: adversarial matvec-oracle lower bound (session 4)"
```

## bd state

`certkit-ph1` is claimed and left **open**, with `--notes` summarizing this
session's adversarial lower-bound result. `bd export -o issues.jsonl` was
run since the notes changed meaningfully. Recommended next steps, in
priority order:

1. Decide whether this lower bound is enough to close the bead as
   "shown infeasible for the matvec-oracle-based subspace family" (a
   judgment call about whether the acceptance criterion's intent extends to
   "we now know why, and it's provably not this family" or strictly
   requires a working rule to exist) — this session leaves that call to a
   human/future session rather than making it unilaterally, since closing
   without a working counting rule would be a norm change to what "closed"
   means for this bead, not something to decide alone.
2. If continuing to search for a working rule: the one door this session's
   bound leaves open is a rule that reads Pauli-sum term structure directly
   (number/pattern of terms in `H = sum_t c_t P_t`) rather than treating the
   operator as an opaque matvec oracle — untried by any of the four
   sessions so far. Start by checking whether real chemistry term counts
   (from the external `chem/certkit_bridge.py` solver, not in this repo)
   actually satisfy T << n at the bead's relevant sizes; this session's
   O(q^4)-vs-2^q argument suggests they likely don't, which would close off
   this direction too, but that argument was not checked against real data.
3. Separately, session 3's FEAST/contour-integral soundness objection
   (stochastic trace estimation vs. this repo's unconditional-soundness
   requirement) remains unconfirmed and unrefuted — worth resolving with a
   concrete derivation before anyone prototypes it.
4. Unrelated to this bead: the pure-Python interval LDL^T behind
   `DENSE_LIMIT=160` could in principle be sped up to raise that threshold a
   few x (flagged by session 3). Does not satisfy this bead's "without
   O(n^3)" criterion; would need its own bead.
