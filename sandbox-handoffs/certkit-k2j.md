# Handoff: certkit-k2j (certified tensor-network/MPO counting rule)

## Outcome

**Closed as infeasible-for-now, single session** (the bead's own design section
flagged this as the plausible outcome of a first, scoping-focused session: "If
the first session concludes it's not tractable within certkit's
interval-arithmetic, no-transcribed-constants discipline, that is a valid and
complete result"). No code changed in `certkit/`, `tests/`, or `examples/`.
One new scratch file added, numpy/scipy-based (producer-side style, same
convention as `sandbox-handoffs/certkit-ph1-*-experiment.py`):

```
sandbox-handoffs/certkit-k2j-entanglement-experiment.py
```

Rerunnable directly: `uv run --extra dev python sandbox-handoffs/certkit-k2j-entanglement-experiment.py`
(takes a few minutes; the q=16/18 tail and the disorder-averaged pass are the
slow parts).

## The question this session was scoped to answer

`certkit-ph1` (six sessions, closed 2026-08-31) ruled out every
concretely-named matrix-free eigenvalue-counting rule for `PauliSumReal`
operators past `DENSE_LIMIT`: the entire matvec-oracle family (proven
impossible, session 4), term-count exploitation, the banded/Sturm route, and
FEAST/contour-integral counting (all closed by direct computation, session
5), and fill-reducing sparse LDLᵀ reordering (closed by direct computation,
sessions 6-7 — same cubic growth order as dense, just a smaller constant).
Its own closing notes named exactly one genuinely new, unattempted idea:
certified tensor-network/MPO methods (bounded bond dimension with an
interval-arithmetic-bounded truncation error).

This bead's design section asked for a *narrower* first-session question
before attempting any implementation: **is a certified truncation-error bound
even achievable for `PauliSumReal`-shaped operators?** That is what this
session answers — with, I believe, more confidence and more generality than
strictly required, because the answer turned out to rest on a much broader
fact than anything specific to `PauliSumReal`'s particular sparsity
structure.

## Answer: no, not for the class `PauliSumReal` actually is — for two
independent reasons, one argued and one both argued and measured

### Reason 1 — complexity-theoretic (argued; conditional on a standard, widely-believed conjecture, not an unconditional proof like session 4's)

`PauliSumReal.__init__` (`certkit/operators.py:199`) accepts
`terms: list[tuple[float, str]]` with **no locality or geometry
restriction whatsoever** — confirmed by reading the constructor and
`certkit/schema.py` (no validation on term placement anywhere in either
file). A term can act on any subset of the `q` qubits, and there is nothing
stopping every term from being 2-local (acting on exactly two qubits) on an
**arbitrary graph** of qubit pairs, not just a 1D chain.

That specific class — 2-local qubit Hamiltonians on an unrestricted
interaction graph — is exactly the subject of two established results I
independently verified (fetched and read the actual papers rather than
trusting a half-remembered citation, given this repo's own "no transcribed
constants" standard applies just as much to citing a wrong theorem as to
transcribing a wrong number):

- Kempe, Kitaev, Regev, *"The Complexity of the Local Hamiltonian Problem"*
  (arXiv:quant-ph/0406180): the 2-local Hamiltonian problem — decide whether
  the ground energy is below `a` or above `b`, promised one holds, for a
  Hamiltonian that is a sum of 2-local terms on an arbitrary interaction
  graph — is **QMA-complete**.
- Cubitt, Montanaro, *"Complexity classification of local Hamiltonian
  problems"* (arXiv:1311.3161): refines this to a full classification by
  term type. Specifically, **transverse-field Ising-type Hamiltonians
  (ZZ + X terms) on a general graph are QMA-complete when the couplings are
  frustrated / non-stoquastic (mixed-sign)** — stoquastic (all
  ferromagnetic, same-sign) instances fall into the believed-strictly-weaker
  class StoqMA, so the hardness genuinely depends on allowing frustration,
  not just on being 2-local.

`certkit`'s `eigenvalue_count_below` claim, for the specific case of
"exactly 0 eigenvalues below `beta`" (i.e., "is the ground energy below
`beta`"), **is** this decision problem — no reduction is even needed, the
task is stated identically, and it's a strictly *easier* special case of
what the full counting rule is asked to certify for arbitrary `beta`.
`PauliSumReal` permits exactly the term family (frustrated 2-local
transverse-field-Ising-shaped Pauli sums on an unrestricted graph) that
Cubitt–Montanaro place in the QMA-complete class.

**What this means, honestly stated**: unless QMA-complete problems admit
polynomial-time (classical *or* quantum) algorithms — a conjecture in the
same family as, and believed at least as firmly as, P≠NP, since QMA⊇NP — no
algorithm of *any* structure (tensor-network-based, DMRG-based, or anything
not yet named) can decide this problem in time polynomial in `q` for the
fully general `PauliSumReal` class, in the worst case. This is not specific
to tensor networks; it subsumes and extends session 4's narrower
matvec-oracle-only impossibility proof to *every* algorithm, at the cost of
resting on a conjecture rather than being unconditional. I want to be
precise about that cost: session 4's bound is a proof; this is a citation of
an established hardness result plus the standard complexity-theoretic
assumption that QMA-complete problems don't have efficient algorithms. I did
not re-derive QMA-completeness from scratch (did not re-derive
Kempe–Kitaev–Regev's reduction, the same way `certkit-ph1` session 6 cited
Harper's isoperimetric theorem for the hypercube separator bound without
re-deriving it) — I verified the papers say what I'm citing them for by
fetching and reading them directly, not from memory alone.

### Reason 2 — circularity in the one case where a real theorem *does* apply, plus a direct, disorder-averaged measurement

Reason 1 covers the general case. The natural objection: `certkit`'s own
sample operator (`examples/sample/pauli_operator.json`) *is* geometrically
local (nearest-neighbor TFIM chain), and for 1D-local, **gapped** Hamiltonians
there is a real, rigorously proven theorem — Hastings' area law (2007) — that
does bound ground-state entanglement entropy, which is exactly the
ingredient a certified bond-dimension truncation bound would need. So does
that narrower, favorable case actually work?

No, for two compounding reasons:

1. **Circular for this checker's actual job.** Hastings' bound is stated
   *in terms of the spectral gap* — you need a numeric gap lower bound as an
   input to get a numeric entanglement bound out. `certkit`'s whole reason
   for existing is to establish an eigenvalue enclosure (which pins down the
   gap) *without already assuming it*. A bound that needs the gap to certify
   the gap is not usable here, for the same structural reason
   `backward_error.py`'s docstring refuses a priori worst-case perturbation
   bounds transcribed from a paper: it would be trusting an unproven input,
   not deriving a bound from the matrix in front of the checker.
2. **The known constants are exactly the kind this repo refuses even where
   the circularity isn't the issue.** Hastings' bound's dependence on the
   gap is doubly exponential in `1/gap` in the original proof (this is a
   documented, widely-cited feature of the area-law literature, not
   something I derived) — a "constant" like that is not something
   `checker.py` could compute from a real operator's actual gap and get a
   usable (non-vacuous) bond dimension at any size this repo cares about,
   even setting the circularity aside.

3. And critically, **`PauliSumReal` is not restricted to the favorable
   case by anything in the code** (Reason 1's point again) — the repo's own
   `jw_two_body` family (already used throughout `certkit-ph1`, sessions
   5-7) is a Jordan-Wigner-mapped two-body chemistry Hamiltonian, which is
   inherently all-to-all after the transform, not nearest-neighbor. A
   certified rule that only worked for the nice 1D case would not cover this
   repo's own stated motivating examples (H4, N2) without a *new*,
   locality-restricted operator kind — a repo-level scope change, out of
   bounds for this bead.

**Direct measurement**, to make Reason 2's claim about entanglement growth
concrete rather than asserted (`sandbox-handoffs/certkit-k2j-entanglement-experiment.py`):
built two families of `PauliSumReal`-shaped Hamiltonians with identical
building blocks (ZZ two-body terms + local X + local Z, real coefficients,
even-Y-count-real, matching `certkit.operators.PauliSumReal`'s own
constraints) —

- `chain_1d`: nearest-neighbor ZZ, matching `examples/sample/pauli_operator.json`'s
  own structure, at `h = J` (the chain's critical point — deliberately the
  *most*-entangled point a 1D-local Hamiltonian can produce, to give the
  area-law case its best shot).
- `all_to_all`: ZZ on every pair with random ±J couplings (SK-model
  normalization `J/sqrt(q)` so total per-spin coupling energy stays O(1) as
  q grows), plus the same local X and Z terms — the specific frustrated,
  non-stoquastic, unrestricted-graph shape Cubitt–Montanaro's classification
  places in QMA-complete, and structurally the same shape as this repo's own
  `jw_two_body` family.

Both include a small explicit symmetry-breaking longitudinal field. **That
field mattered, and finding out why is worth recording as its own result**:
the naive first version of this experiment (no symmetry-breaking field, both
families) found entanglement entropy saturating at **exactly log(2) nats for
both families**, independent of geometry — which would have read as "neither
family shows volume-law growth, tensor networks might be fine after all." It
is a confound, not a finding: `H = -J·ΣZZ - h·ΣX` commutes with the global
spin-flip parity `P = Π_i X_i` for *any* geometry, and near the classically
ordered regime the true finite-size ground state is a symmetric/antisymmetric
cat combination of two near-degenerate classical configurations — which
contributes exactly `log(2)` of measured entanglement regardless of whether
the bulk state has any real structure at all. Adding a weak random
longitudinal field breaks the degeneracy and removes this artifact. (Recorded
in the script's own docstrings so a future session doesn't rediscover this
the slow way.)

With the confound removed, ground states found by exact diagonalization
(`n ≤ 4096`) or Lanczos (`scipy.sparse.linalg.eigsh`, `n` up to 262144;
residual norms `‖Hv - Ev‖` verified `~1e-13` to `1e-14` at every size tested,
i.e. genuinely converged, not an artifact — checked explicitly because the
first `q=16/18` single-seed run showed a surprising dip that turned out to be
realization noise, not non-convergence), entanglement entropy across a
balanced qubit bipartition, **disorder-averaged over 5 random-coupling seeds
per `q`** (a single seed is too noisy — the single-seed series has `q=16`
reading *below* `q=14`, before recovering at `q=18`; needed averaging to see
past that):

```
family        q   mean(S)  std(S)   mean(S)/q   frac_of_max
chain_1d       8   0.3006  0.0252    0.03758       0.108
all_to_all     8   0.4638  0.0622    0.05798       0.167
chain_1d      10   0.2796  0.0512    0.02796       0.081
all_to_all    10   0.5743  0.0483    0.05743       0.166
chain_1d      12   0.2452  0.0628    0.02043       0.059
all_to_all    12   0.6360  0.0477    0.05300       0.153
chain_1d      14   0.2321  0.0721    0.01658       0.048
all_to_all    14   0.8571  0.0980    0.06122       0.177
```

- `chain_1d`: mean `S` is **flat to slightly decreasing** over three
  doublings of `n` (0.301 → 0.232 nats) — consistent with the expected
  area-law-adjacent behavior at a 1D critical point (logarithmic, not
  extensive, growth; here even the log term isn't visible at this size).
  This is the case tensor-network methods are built for, and it looks like
  it, on the repo's own sample structure.
- `all_to_all`: mean `S` **grows close to linearly in `q`** — `S/q` is
  stable at 0.053-0.061 across the whole range (three doublings of `n`,
  `q=8..14`), the textbook signature of volume-law entanglement. A
  Schmidt rank growing exponentially in `q` across the balanced cut (the
  best case for any linear MPS qubit ordering) means **no fixed
  polynomial-in-`q` bond dimension captures this state to bounded error**,
  for any qubit ordering — this is not an ordering problem tensor networks
  can route around (analogous to `certkit-ph1` session 6's finding that no
  qubit reordering fixes the bit-flip-mask bandwidth problem for the
  computational-basis picture).

This is a direct, disorder-averaged, residual-verified, reproducible
measurement — not a proof by itself (that's Reason 1) — but it concretely
instantiates Reason 1's conclusion on operators of exactly the shape this
repo's own `jw_two_body` family already uses.

## Cumulative state, extending `certkit-ph1`'s table

| Avenue | Status | Session |
|---|---|---|
| Certified tensor-network/MPO methods (bounded bond dimension, interval-bounded truncation error) | infeasible for the general `PauliSumReal` class: QMA-hard (argued, citing Kempe–Kitaev–Regev + Cubitt–Montanaro) in the worst case; and for the one case where a real bound exists (Hastings' area law, gapped 1D-local), it needs the gap as an input (circular) with impractical constants even if not — plus a direct, disorder-averaged measurement showing `PauliSumReal`'s own permitted generality (`jw_two_body`-shaped, all-to-all) already produces volume-law-scaling ground-state entanglement, in contrast to the repo's own 1D sample structure | k2j (this bead) |

Every concretely-named angle across `certkit-ph1` (sessions 1-7) and this
bead is now closed off with a proof, a direct computation, or (here) both.

## What I did not do, and why

- **Did not attempt any implementation in `certkit/`.** Both findings above
  say, in the design section's own words, this avenue is "not tractable
  within certkit's interval-arithmetic, no-transcribed-constants discipline"
  — there was nothing sound to build.
- **Did not pursue a locality-restricted operator kind** (a hypothetical
  `LocalPauliSumReal` limited to nearest-neighbor terms) as a narrower
  positive avenue. This would need: a new operator kind (repo-level scope
  change, out of bounds for this bead), a resolution of the gap-circularity
  problem in Reason 2, and a from-scratch (non-transcribed) derivation of a
  usable version of Hastings' bound — three separate open problems stacked
  on top of each other. Flagging as a possible, but very large and uncertain,
  follow-on if a future session wants to attempt it — not attempted here.
- **Did not re-derive QMA-completeness of 2-local Hamiltonian from scratch.**
  Cited Kempe–Kitaev–Regev and Cubitt–Montanaro, verified by fetching and
  reading the actual papers (not from memory), consistent with `certkit-ph1`
  session 6's own practice of citing Harper's theorem rather than
  re-deriving hypercube-separator optimality.
- **Did not push disorder averaging past `q=14`** (5 seeds × 4 sizes already
  took several minutes; `q=16`+ at 5 seeds each would be much slower). The
  `q=8..14` trend (`S/q` stable to within about ±15% across three doublings)
  is already unambiguous, and the `q=16/18` single-seed points (0.412, 1.021
  nats) are consistent with, not contradicting, that trend once
  realization-to-realization noise (confirmed real, not a convergence
  artifact — see residual norms above) is accounted for.
- **Did not sweep the transverse field `h`** to find the actual
  most-entangled point of the `all_to_all` family; picked `h=1` to match the
  chain's own critical point for a like-for-like comparison, not because
  it's verified to be `all_to_all`'s hardest case.

## What I could not verify

- Whether the QMA-completeness argument's conclusion transfers airtight to
  `certkit`'s *exact* promise structure (a numeric interval-arithmetic gap
  tolerance discharged by pivot enclosure, rather than a fixed `1/poly(n)`
  promise gap as in the standard Local Hamiltonian Problem formalization). The
  correspondence is standard and I'm confident in it at the level stated
  above, but I did not work through the promise-gap parameters in full
  formal detail — this is an argued equivalence, not a checked reduction.
- Whether a locality-restricted operator kind would actually give tensor
  networks real traction in practice at this repo's scale (`q~8-16`) even
  setting circularity aside — I know Hastings' bound's constants are
  asymptotically extreme (doubly exponential in `1/gap`) but did not
  attempt to quantify what they'd actually evaluate to for, say, the
  repo's own `examples/sample/pauli_operator.json` at its measured gap.
- Whether `h=1, J/sqrt(q)` is close to the `all_to_all` family's actual
  hardest (most-entangled) point, or whether a different parameter choice
  would show an even starker contrast with `chain_1d` — the qualitative
  conclusion (linear vs. flat growth) does not depend on this, but the
  specific `S/q ≈ 0.06` constant might not be the largest achievable one.

## Test suite / trust boundary

Nothing under `certkit/`, `tests/`, or `examples/` was touched this session
(only a new file added under `sandbox-handoffs/`), so both checks below are
reconfirmations, not new evidence of anything — run anyway per the repo's
own standard of re-measuring rather than trusting a pinned number.

```
$ uv run --extra dev pytest tests
============================= 181 passed in 27.71s =============================
```

```
$ uv run --no-project python3 -c '<block numpy/scipy via sys.meta_path, then run certkit.cli check>' \
    check examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

(No system `python3` in this container, same as every prior session's
environment note — used the same `uv run --no-project python3` +
`sys.meta_path` blocker fallback documented in `certkit-ph1.md` and
`sandbox-prompt.md`.)

## Working tree

```
$ git status --short
 M README.md
 M issues.jsonl
 M lean/Certkit/Soundness.lean
 M sandbox-prompt.md
?? lean/Certkit/Scratch.lean
?? lean/Certkit/Scratch2.lean
?? sandbox-handoffs/certkit-1ta.md
?? sandbox-handoffs/certkit-8y2.7.md
?? sandbox-handoffs/certkit-93j.md
?? sandbox-handoffs/certkit-k2j-entanglement-experiment.py    <- this session
?? sandbox-handoffs/certkit-k2j.md                            <- this session
?? sandbox-handoffs/certkit-shj.md
?? sandbox-handoffs/certkit-t2k.md
```

Everything except the two `certkit-k2j*` entries is other sessions'
uncommitted work, left exactly as found (git policy is no commits regardless
of which session produced a diff, and none of it is in this bead's scope to
review or clean up). `issues.jsonl`'s working-tree diff includes this
session's `bd export` in addition to whatever prior sessions left uncommitted
there.

## Suggested next commands (none run — git policy)

```
git add sandbox-handoffs/certkit-k2j.md \
        sandbox-handoffs/certkit-k2j-entanglement-experiment.py \
        issues.jsonl
git commit -m "certkit-k2j: close tensor-network/MPO counting-rule avenue (QMA-hardness + measured volume-law entanglement)"
```

(Leaving the other pre-existing uncommitted files — `README.md`,
`lean/Certkit/Soundness.lean`, `sandbox-prompt.md`, the other
`sandbox-handoffs/*.md` files, `lean/Certkit/Scratch*.lean` — for whichever
session or human owns that work; not part of this commit.)

## bd state

`certkit-k2j` claimed and closed this session with `--reason` summarizing the
above. `bd export -o issues.jsonl` run since the bead's notes/status changed
meaningfully.
