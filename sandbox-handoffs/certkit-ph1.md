# Handoff: certkit-ph1 (coverage cliff past DENSE_LIMIT)

## Outcome

**Bead left OPEN, claimed.** No code changed in `certkit/`, `tests/`, or
`examples/`. This is the second session on this bead. The first session
(notes preserved in bd history) found the obvious approach unsound (with an
explicit counterexample) and the "safe" fallback sound-but-useless, and
flagged two specific open questions for whoever picked this back up. This
session picked it up, tested both, and both came back negative — which
narrows the search space for the next session rather than leaving it where
session 1 did. Writing this up in full because, per this repo's own rule,
the negative result is the artifact.

## What the acceptance criterion requires

> A counting rule that discharges the gap hypothesis without an O(n^3) dense
> factorisation, giving a Temple-quality width on a Pauli-sum operator of at
> least 256 dimensions.

Concretely: prove "exactly one eigenvalue of A lies below beta" for a
256-16384-dimensional Pauli-sum Hamiltonian using only `op.apply`/`op.row`,
cheaply enough to be worth having. `temple_inertia` already does this exactly
via O(n^3) interval LDL^T, gated at `DENSE_LIMIT = 160`. Not met this
session either.

## Step 0 — reconfirmed the cliff and the current baseline

Same shape as before (`sandbox-handoffs/certkit-ph1-reconfirm.py`,
unchanged from session 1, rerun): `temple_inertia` dies exactly at
`n > DENSE_LIMIT=160`; `gershgorin_rayleigh` width stays O(1)-O(10)
regardless of n, useless against a sub-Hartree target.

Housekeeping note for whoever reads this next: the working tree currently
carries substantial uncommitted changes from *other*, unrelated beads
(certkit-kj6, and in-progress work on certkit-jn1.2 and others) — per this
repo's git policy, nothing gets committed automatically, so multiple
sessions' diffs accumulate in the tree between human commits. Because of
that, `uv run pytest tests` reports **121 passed**, not the "106 passed"
baseline the standing instructions describe — that's other beads' landed
work, not a regression. I diffed the tree before and after this session and
confirmed I added zero lines to any file outside the gitignored
`sandbox-handoffs/` directory. Whoever closes those other beads' commits
should re-baseline the number in the standing instructions.

## Step 1 — open question 1 from session 1: does a genuine physical gap help Variant A?

Session 1's Variant A (Lanczos subspace + global block-residual Weyl
counting) was sound but useless on critical TFIM (`field=1.0`): the block
residual `eps = ||AQ - QT||_2` stayed O(1)-O(10) regardless of Krylov
dimension `k`, because it's a *global* operator-norm bound over the whole
untouched complement, and it only shrinks to zero once k=n (the existing
dense route, restated). Session 1 flagged as unresolved: does a Hamiltonian
with a genuine physical gap and low ground-state entanglement (as opposed to
critical TFIM's near-gapless, near-maximally-entangled point) do any
better?

Tested in `sandbox-handoffs/certkit-ph1-gapped-experiment.py`, sweeping TFIM
field/coupling ratio at fixed q=10 (n=1024) through ferromagnetic
(`field=0.3`, near-degenerate doublet, gap≈0), critical (`field=1.0`,
gap=0.30), paramagnetic (`field=3.0`, gap=4.11), and deep paramagnetic
(`field=8.0`, gap=14.09, close to a product-state ground state):

```
field=1.0 (critical):          k=80  eps_spec=4.706e+00  eps/gap=1.574e+01
field=3.0 (paramagnetic):      k=80  eps_spec=1.121e+01  eps/gap=2.726e+00
field=8.0 (deep paramagnetic): k=80  eps_spec=2.985e+01  eps/gap=2.119e+00
```

**Answer: no.** The ratio `eps/gap` does improve somewhat as the field grows
(15.7 → 2.1), but the raw residual `eps` gets *larger* (4.7 → 30), not
smaller, because `||A||` itself scales with the field strength that's also
creating the gap. `eps` never gets under `gap/2` (the threshold needed to
even attempt disjointness), and there's no sign it's heading there as `k`
grows — it plateaus at the same O(1)-O(10) scale session 1 found for
critical TFIM. Low entanglement / a large physical gap does not make the
*global* block-residual small; that residual measures how much of `A`'s
total norm lives outside the k-dimensional subspace, which is a different
quantity from how isolated the ground state is.

## Step 2 — open question 2 from session 1: shift-invert Lanczos (previously untried)

Session 1 explicitly did not try this and named it as the next thing to
check: build the Krylov subspace from `(A - sigma I)^-1` instead of `A`,
using a matrix-free CG solve, so the subspace should converge to the bottom
of the spectrum far faster than plain Lanczos. The obvious choice for
`sigma` that keeps `A - sigma I` positive semi-definite (so CG is safe)
*without knowing `lam1` in advance* is the existing, sound, matrix-free
Gershgorin floor — already computed by `certify_lambda_min_matrixfree` in
`certkit/producer.py`, no new trusted-side code needed to get `sigma`.

Tested in `sandbox-handoffs/certkit-ph1-shiftinvert-experiment.py` (numpy
prototype; dense CG standing in for a matrix-free CG matvec, since the point
here was to test the *arithmetic*, same discipline as session 1's Variant
A/B prototypes) against TFIM q=6/8/10:

```
q=10 n=1024 lam1=-12.3815 gap=0.2989 gershgorin_sigma=-19.0000 (<=lam1: True)
  k= 5  theta1=-12.255919  eps_spec=5.945e+00  eps/gap=1.989e+01
  k=10  theta1=-12.379434  eps_spec=6.812e+00  eps/gap=2.279e+01
  k=20  theta1=-12.381490  eps_spec=5.844e+00  eps/gap=1.955e+01
  k=40  theta1=-17.611949  eps_spec=1.148e+01  eps/gap=3.841e+01
```

**Answer: no.** `theta1` converges to `lam1` well through k=20 (confirms the
*per-Ritz* residual — the ingredient Variant B uses — is fine; shift-invert
is doing its normal job of accelerating convergence to the targeted
eigenvector). But the *block* residual `eps_spec` that Variant A's Weyl
argument needs stays the same O(1)-O(10) order as plain Lanczos, and gets
worse at k=40 for q=10 (the Gershgorin floor is loose — session 1's own
number, 100-1600x too wide — so `A - sigma I` is poorly conditioned and CG
degrades at higher k; this is a real numerical issue, not just cosmetic).

## What this establishes

Both explicitly-flagged open questions from session 1 are now closed
negative. Put together, they point at the same conclusion from two
different angles: **the obstruction is structural, not a subspace-choice
problem.** `||AQ - QT||_2` small requires `Q` to capture essentially all of
`A`'s significant-norm directions, not merely an accurate estimate of the
ground state. Neither "pick a Krylov subspace that's a better basis for the
targeted eigenvector" (shift-invert) nor "pick an operator where the
targeted eigenvector is genuinely isolated and unentangled" (deep
paramagnetic TFIM) changes that — because in both cases the *rest* of the
spectrum, which the complement's norm depends on, is untouched. For an
extensive many-body Hamiltonian (term count scaling with system size, so the
full spectral width doesn't shrink), no `k << n` subspace of either flavor
tested satisfies the condition Variant A needs.

I'm reporting this as a strengthened negative result, not a proof of
impossibility — I did not attempt polynomial/Chebyshev-filtered subspaces or
contour-integral (FEAST-style) counting, and I have not shown those fail
too. But two independent natural refinements of the same idea both failing
for the same underlying reason is worth a future session not re-deriving.

One more thing worth naming so it isn't mistaken for a finding: the
classical *decision* problem "does this local Hamiltonian family have a
spectral gap" is known to be undecidable in general (Cubitt, Pérez-García,
Wolf, *Nature* 2015). That is a different problem — it concerns a family
parameterized by system size in the thermodynamic limit, not counting
eigenvalues of one fixed finite matrix, which is always decidable in
principle. It doesn't settle this bead's question either way. I mention it
only as context for why "a cheap general certificate for this class of
operator" may be fighting a real structural headwind, not as a reason to
stop looking.

## What I did not do, and why

- **Did not implement anything in `certkit/`.** Nothing sound-and-useful was
  found. Per the standing rule, an undischargeable derivation means not
  touching the trusted code, not padding a threshold and hoping.
- **Did not retest Variant B (the unsound disjoint-balls shortcut).** Session
  1's explicit counterexample stands unchanged; no new information this
  session bears on it.
- **Did not try polynomial/Chebyshev-filtered subspaces or FEAST-style
  contour-integral counting.** Both remain open avenues, genuinely untried by
  either session. Chebyshev filtering in particular changes *which* subspace
  gets built in a way structurally different from both Lanczos and
  shift-invert Lanczos, so it isn't automatically ruled out by this
  session's finding — worth trying before concluding this bead is
  unsolvable.
- **Did not build a molecular-Hamiltonian fixture.** Still out of scope for
  a bead about the counting rule; TFIM remains the stand-in, as in session
  1.
- **Did not touch `DENSE_LIMIT`, any tolerance, or any existing rule.**

## What I could not verify

- Whether Chebyshev-filtered or contour-integral counting methods avoid the
  structural obstruction identified here, or run into the same one for a
  different reason. Not attempted.
- Whether real molecular Hamiltonians (as opposed to TFIM at any field
  strength) have some other structural property — beyond "gapped" and
  "low-entanglement," both now tested and ruled insufficient — that would
  make a small-k subspace's complement genuinely low-norm. I don't have a
  candidate property to test.

## Test suite / trust boundary

```
$ uv sync --extra dev
$ uv run pytest tests
============================= 121 passed in 12.76s =============================
```

(121, not 106 — see the housekeeping note in Step 0. Confirmed unchanged by
this session; the delta is other beads' uncommitted work already in the
tree before I started.)

No-dependency checker run (base interpreter, no venv, numpy unimportable):

```
$ /home/node/.local/share/uv/python/cpython-3.12.13-linux-aarch64-gnu/bin/python3.12 \
    -m certkit.cli check examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

## Working tree

```
$ git status --short
 M README.md
 M certkit/checker.py
 M certkit/interval.py
 M certkit/producer.py
 M examples/banded_demo.py
 M issues.jsonl
 M pyproject.toml
 M tests/test_backward.py
 M tests/test_banded.py
 M uv.lock
?? tests/test_generalized.py
```

**None of the above is from this session** — all pre-existed when I started
(confirmed by diffing before/after), and belongs to other, unrelated beads
(certkit-kj6 closed, certkit-jn1.2 and others in progress). Not mine to
touch or explain further; out of this bead's scope.

This session added two new scratch files under the gitignored
`sandbox-handoffs/` directory (invisible to `git status` by design, listed
here for the record): `certkit-ph1-gapped-experiment.py`,
`certkit-ph1-shiftinvert-experiment.py`. Both are throwaway numpy
prototypes, same discipline as session 1's — not part of the trusted or
test tree, not wired into pytest, rerunnable directly for verification.

## Suggested next commands (none run — git policy)

```
git status   # to see the other beads' pending work, unrelated to this one
```

Nothing from this bead needs a commit — no files under `certkit/`, `tests/`,
or `examples/` changed.

## bd state

`certkit-ph1` is claimed and left **open**, with `--notes` summarizing both
follow-up experiments and the structural conclusion. Recommended next step
for whoever picks this up: try polynomial/Chebyshev-filtered subspaces
before further Lanczos variants (two independent variants now refuted for
the same underlying reason), or accept that this bead's acceptance bar may
not be achievable for generic extensive local Hamiltonians and reframe it
(e.g., restrict to a promise class with bounded treewidth/interaction graph,
if one exists among the Krylov solver's real workloads).
