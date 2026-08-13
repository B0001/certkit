# certkit

A certificate format and an independent checker for numerical claims.

A solver emits `(claim, witness)`. The checker re-derives the claim from the
witness in rigorous interval arithmetic and returns **VERIFIED** or
**ABSTAIN**. It never reads the solver's own bound, never imports the solver,
and has no third-party dependencies. Solver quality becomes a coverage
question — *how often do we get an answer?* — instead of a soundness question
— *is the answer we got real?*

The first instantiation is a two-sided enclosure of the smallest eigenvalue of
a real symmetric operator, across dense, sparse, and matrix-free backends.

## The guarantee

> If `check()` returns VERIFIED with enclosure `[lo, hi]`, then the true
> smallest eigenvalue of the operator lies in `[lo, hi]`.

This holds regardless of what the producer did — even if the producer is buggy,
non-deterministic, or adversarial. It rests on four things:

1. **Interval arithmetic with outward rounding.** Python cannot set the FPU
   rounding mode, so each endpoint is widened by one ulp via `math.nextafter`
   after every operation. An IEEE op errs by at most half an ulp, so the
   enclosure is valid. Overflow degrades to a wide interval, not to nonsense.
   Fuzzed against exact `Fraction` arithmetic in `tests/test_interval.py`.
2. **A minimal witness.** The certificate carries the eigenvector estimate and
   the gap parameter and *nothing else*. It does not carry the producer's
   Rayleigh quotient or residual norm, so there is no untrusted number the
   checker could accidentally lean on.
3. **The gap parameter is discharged, not assumed.** Temple's inequality needs
   a separator `β` between λ₁ and λ₂. Asserting one you do not have is the
   classic way to publish a bound that is much too tight. The checker
   establishes it by interval LDLᵀ plus Sylvester's law of inertia: if exactly
   one eigenvalue lies below `β`, then `β ≤ λ₂`. If any pivot interval
   straddles zero, the inertia is undetermined and the checker abstains.
4. **Content addressing.** The certificate is sealed with a BLAKE2b digest and
   references the operator by hash. Mutating either is detected. Floats are
   stored as C99 hex literals so nothing round-trips through decimal.

## Verdicts are two-valued

```
VERIFIED  the claim follows from the witness, under no assumptions
ABSTAIN   anything else, with a reason
```

There is no "probably fine" and no confidence score. ABSTAIN is not an error
condition — it is the correct output whenever a proof was not produced, and
callers are expected to treat it as *no answer*.

## Operators, not matrices

The checker never sees a matrix. It sees something it can apply to an interval
vector and read rows from:

| backend | encoding | notes |
| --- | --- | --- |
| dense | `dense_symmetric_real` | explicit rows, exact symmetry check |
| sparse | `sparse_csr_symmetric_real` | CSR; structure and symmetry validated |
| matrix-free | `pauli_sum_real` | qubit Hamiltonian of dimension 2^q, never built |

A Pauli string acts on a basis state as a bit flip plus a phase, so `apply`
costs O(terms · 2^q) with no matrix anywhere. Strings are required to carry an
even number of `Y` factors — exactly the condition for the operator to be real,
and therefore symmetric.

Rows are handed to the checker as *intervals*, not floats. A Pauli-sum diagonal
entry is a sum of many coefficients and is not exactly representable, so a float
row would describe a slightly different operator than the certificate is about,
and an inertia count on the wrong matrix is the silent substitution this whole
design exists to prevent.

## Composition

A witness may discharge a hypothesis by referencing another certificate by
content hash, and `check_bundle` resolves those references.

```
$ certkit produce --n 8 --seed 5 --rule temple_ref --out b1
$ certkit check b1/certificate.json b1/operator.json
  blake2b16:bf513971a5   VERIFIED  eigenvalue_count_below via inertia
  blake2b16:bfb5d501a7   VERIFIED  lambda_min_enclosure via temple_ref  [...]  <- 1 dep(s)
```

Two things this buys.

**A rule stops caring how its hypothesis was established.** `temple_ref` needs
an eigenvalue count, not a particular way of counting. A future Sturm-sequence
counter for banded operators becomes a new certificate, not an edit to the
Temple code.

**Derivation nodes carry no arithmetic.** The `combine` rule sandwiches a
`spectrum_lower_bound` and a `lambda_min_upper_bound` into an enclosure and does
nothing else. Its two halves are separately reusable — the Gershgorin floor does
not depend on the trial vector at all.

A dependency that abstains makes every dependent abstain; there is no partial
credit. `examples/composition_demo.py` corrupts a count certificate and shows
the Temple node, whose own arithmetic is untouched and still correct, stop
answering:

```
ABSTAIN   claimed 2 eigenvalues below beta, re-derived 1
ABSTAIN   dependency: ... did not verify: claimed 2 eigenvalues below beta, re-derived 1
```

Cycles get a check in the traversal, but the real defence is structural: a
certificate's hash covers the references inside it, so building a cycle would
require finding a hash fixed point. References also carry no authority of their
own — a dependency must prove the right claim kind, about the same operator, at
the same `beta`, or it is refused before it is even re-derived.

## Two sound routes, one tradeoff

```
temple_inertia       tight; needs a spectral gap and an O(n^3) factorisation
temple_ref           the same, with the gap discharged by a referenced certificate
sturm                exactly `count` eigenvalues below `beta`, via banded LDL^T
sturm_be             the same claim, via backward error with a runtime bound
gershgorin_rayleigh  loose; needs no gap at all, and is fully matrix-free
combine              a derivation node: two one-sided bounds, no arithmetic
gershgorin           every eigenvalue is at least `bound`; witness-free
rayleigh             lambda_min is at most `bound`, from a trial vector
inertia              exactly `count` eigenvalues below `beta`; witness-free
residual             unconditional, but claims only that *some* eigenvalue is here
```

`python examples/matrixfree_demo.py`, transverse-field Ising at h = J = 1:

```
 qubits    dim                 route       width   sound
      4     16        temple_inertia    4.17e-14     yes
      4     16   gershgorin_rayleigh    2.24e+00     yes
      6     64        temple_inertia    1.83e-13     yes
      6     64   gershgorin_rayleigh    3.70e+00     yes
      8    256        temple_inertia  no gap route      --
      8    256   gershgorin_rayleigh    5.16e+00     yes
     11   2048        temple_inertia  no gap route      --
     11   2048   gershgorin_rayleigh    7.35e+00     yes
```

At 2048 dimensions the Hamiltonian is never built; the checker only applies it
and reads its rows, straight from the Pauli terms. Where the tight route stops
applying it *says so* rather than degrading, and the loose route reports its
width rather than hiding it in a confidence score.

## Counting without a dense factorisation

`temple_ref` needs an eigenvalue count, and there are now three rules that prove
one:

```
inertia    full interval LDL^T                       O(n^3), dense only
sturm      interval LDL^T that stays inside the band O(n b^2)
sturm_be   float sweep + a runtime backward bound    O(n), tridiagonal
```

The first two track a forward enclosure of every pivot. The Sturm recurrence
divides by the previous pivot, so that enclosure is amplified at each step, and
a 1D Laplacian — whose ground-state gap shrinks like 1/n² — defeats both by
n ≈ 40.

`sturm_be` stops tracking the pivots. It runs the recurrence in plain floating
point, which makes the computed sequence the *exact* pivot sequence of a nearby
tridiagonal matrix; Sylvester's law then applies to that matrix with no error
term, and Weyl's inequality carries the conclusion back. Two bracketing sweeps
at β ± δ pin the count for the operator itself, or the rule abstains because an
eigenvalue sits too close to β to separate.

**No constant is transcribed.** The classical form of this argument (Kahan 1966;
Demmel, Dhillon and Ren for the IEEE correctness proof) ends in a symbolic bound
with a small constant — and a constant copied out of a paper is exactly the kind
of trust the rest of this kit refuses, because getting it slightly wrong yields a
confident wrong answer rather than an abstention. So δ is bounded from the
entries of the matrix in front of the checker, in outward-rounded interval
arithmetic. Weaker than the sharp constant, and answerable without believing
anyone. `test_delta_is_measured_not_assumed` scales the operator by 10⁶ and
checks that δ scales with it.

```
      n         gap    sturm (interval)    sturm_be (backward)
     30    3.07e-02             count=1                count=1
     40    1.76e-02             abstain                count=1
    200    7.33e-04             abstain                count=1
   2000    7.39e-06             abstain                count=1
  20000    7.40e-08             abstain                count=1
```

`python examples/banded_demo.py`, discrete 1D Schrödinger operator with a
harmonic well:

```
      n     dense (inertia)   certified bound       width      s
    100            verified          verified    3.45e-15    0.0
    400         n too large          verified    7.78e-15    0.1
   1000         n too large          verified    1.79e-08    0.3
   4000         n too large          verified    1.01e-01    0.8
  10000         n too large          verified    1.63e+00    1.8
```

`test_one_temple_certificate_three_counting_rules` is the composition bet cashed
in: one Temple certificate, identical in every field but `gap_ref`, verified
against all three counting rules. They share no code path beyond the interval
primitives, and the Temple rule has never been edited to accommodate any of them.

### Checked against an oracle with no rounding

At n = 400 the certified enclosure is narrower than LAPACK's own backward error,
so `numpy.linalg.eigvalsh` lands *outside* it. Bisecting on an exact rational
Sturm count — the diagonal entries are doubles and hence exact rationals, so
`Fraction` has no error term at all — settles who is right:

```
  exact lambda_1        0.04459600719794282
  certified enclosure   [0.044596007197938485, 0.044596007197946264]
  numpy.linalg.eigvalsh 0.04459600719795035
  exact value inside the certified enclosure: True
  LAPACK inside the certified enclosure:      False
```

That is the case for having a checker, in one table.

## Quickstart

```bash
python -m certkit.cli produce --n 10 --seed 3 --out out         # dense, tight route
python -m certkit.cli produce --tfim 11 --rule gershgorin_rayleigh --out ham
python -m certkit.cli check out/certificate.json out/operator.json -v
```

```
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

The re-derived interval is *tighter* than the claim — the producer padded, and
the checker accepted a claim its own reasoning implies. A claim tighter than the
re-derivation is rejected.

```python
from certkit.checker import check
from certkit.producer import certify_lambda_min, tfim_hamiltonian

verdict = check(*certify_lambda_min(tfim_hamiltonian(6)))
if verdict.ok:
    lo, hi = verdict.enclosure
```

## What the coverage sweep shows

`python examples/coverage_sweep.py`, n = 12, 40 matrices per gap:

```
       gap   verified    median width   unsound
     1e+00      40/40       1.887e-14         0
     1e-04      40/40       2.243e-14         0
     1e-08      40/40       2.187e-14         0
     1e-10      36/40       2.376e-14         0
     1e-12      17/40       2.220e-14         0
     1e-14       0/40              --         0
```

Coverage falls to zero as the spectral gap closes; the unsound column stays at
zero throughout. The kit stops answering before it starts lying. That shape —
graceful loss of coverage, never loss of soundness — is the property the whole
design exists to produce.

## Layout

```
certkit/interval.py   rigorous interval arithmetic          TRUSTED
certkit/schema.py     exact encoding, content addressing    TRUSTED
certkit/operators.py  dense / sparse / matrix-free backends TRUSTED
certkit/banded.py     banded LDL^T / Sturm counting          TRUSTED
certkit/backward_error.py  float sweep + runtime delta       TRUSTED
certkit/checker.py    re-derivation and verdicts            TRUSTED
certkit/producer.py   numpy + Lanczos, emits witnesses      untrusted
lean/Certkit/         soundness obligations in Lean 4       statements only
tests/                106 tests: fuzz, backends, composition, counting, adversarial, boundary
```

The trust boundary is enforced mechanically, not by comment.
`tests/test_trust_boundary.py` parses the trusted modules' imports, rejects any
third-party or producer import, and runs the checker in a subprocess where numpy
is unimportable. If someone later reuses a producer-computed Rayleigh quotient
to "save a matvec", the suite fails.

## Adversarial coverage

`tests/test_tamper.py` encodes lies a producer could tell, each of which must
abstain: a shrunk enclosure, a shifted enclosure, an unsealed mutation, a
perturbed witness vector, a substituted operator, a tampered matrix entry, a
non-symmetric operator, a rule/claim mismatch, and — the interesting one — an
inflated `β` that claims a spectral gap the matrix does not have.

Note that the operator reference binds the *encoding*, not the abstract
operator: a CSR and a dense encoding of the same matrix have different refs and
do not interchange. Deliberate. A value-based reference would require
canonicalising every backend into one representation, which is exactly the sort
of trusted preprocessing this design refuses.

## The Lean side

`lean/Certkit/Soundness.lean` states the four obligations (Rayleigh–Ritz,
Temple, Sylvester inertia, Gershgorin) against mathlib4. **Every proof is
`sorry` and the file has not been compiled here.** It is a specification of
intent that pins the Python checker to named theorems; discharging them is a
milestone in itself, and the interval-arithmetic layer is the one after that.

## Known limits

- **Counting is no longer the binding constraint; the producer's eigenvector is.**
  Past n ≈ 10⁴ a Lanczos vector that has not converged yields a large residual,
  and Temple turns that into a wide enclosure — a useless answer rather than a
  wrong one. Better eigensolvers are pure coverage work on the untrusted side.
- `sturm_be` is tridiagonal-only, and needs exactly represented entries. A Pauli
  sum's diagonal is a sum of coefficients, so there is no single matrix the float
  recurrence would be running on; the rule refuses rather than picking one.
- The forward-enclosure routes still grow, and still abstain rather than rounding
  a pivot to a sign. They remain the only option above bandwidth 1.
- `DENSE_LIMIT = 160` — interval LDLᵀ is cubic in pure Python, so above that the
  tight route declines rather than running for an hour.
- Gershgorin is weak on operators with large off-diagonal mass. It is a floor,
  not a good bound.

## Where this connects

- **Krylov solver.** Its two-sided energy bounds are currently trusted because
  the code says so — the same posture that let it return physically impossible
  energies. Emitting a certificate makes them externally auditable, and the
  matrix-free path is the one that matters there.
- **Robot abstention layer.** M0–M3 build an interval substrate, IBP/CROWN
  bounds, and a branch-and-bound discrepancy certifier. Those produce a trusted
  ε; routing them through this format produces a *checkable* ε, and the
  branch-and-bound search becomes a witness generator, and each subproblem bound
  becomes a referenced certificate rather than an internal number.
- **Math knowledge graph.** Shares the Lean 4 / mathlib toolchain, and gets the
  same decision rule: no certificate, no answer.

## Not done yet

- Complex Hermitian operators.
- A banded (b > 1) version of the backward-error analysis.
- Proofs on the Lean side.
- A count rule that works matrix-free, which is what would let a large Pauli
  Hamiltonian use `temple_ref` instead of falling back to Gershgorin.
