# Changelog

## 0.2.0 — 2026-09-05

The first pinnable release. Consumers should pin this rather than a git ref.

**Why 0.2.0 and not 0.1.0.** `0.1.0` was never tagged or published, and over
the repo's history it denoted several mutually incompatible trees — a producer
built against one `0.1.0` failed to import against another (see the `pad_claim`
note below). A version that has already meant more than one thing cannot be
made to mean one thing retroactively, so the first release consumers can
actually pin takes a new number.

### The integration contract is now decided and documented

`INTEGRATION.md`. certkit is consumed as a **protocol over files, not an
imported checker**: a producer emits a certificate and an operator, and the
checker runs out of process over those files, from a pinned release. A checker
running inside the producer's process shares its dependencies and conventions,
so a bug present on both sides cancels out precisely where the certificate is
supposed to catch it.

The rule for producers: **import what computes, never what judges.**
`certkit.interval`, `certkit.operators`, `certkit.schema` and
`certkit.producer.pad_claim` are fair game; `certkit.checker`, the `certify_*`
functions, and any private name are not.

### The trusted computing base is written down

`TCB.md` enumerates what a VERIFIED verdict actually rests on: IEEE-754 with
correctly-rounded operations, `math.nextafter` widening (Python cannot set the
FPU rounding mode), CPython plus three stdlib modules, and the
certificate-integrity primitives.

Two items in it are worth a consumer's attention. The content hash is BLAKE2b
at `digest_size=16` — a ~2⁶⁴ birthday bound, fine against corruption but thin
against an adversary who chooses certificate contents. And the Lean proofs,
while zero-`sorry`, prove the mathematics rather than this Python: the
theorem-to-function correspondence is hand-maintained, and
`sweep_backward_bound`'s runtime row-sum bookkeeping remains uncovered.

### A conformance suite consumers can run

`conformance/` ships twelve frozen certificates with expected verdicts — two
that must verify, ten that must abstain — covering a broken dependency, a
cycle, and a claim whose witness does not support it. `conformance/run.py`
imports nothing from certkit and invokes the checker as a subprocess, so it
runs against whatever release you pin without reproducing this repo's
environment:

```sh
python conformance/run.py --checker certkit
```

Run it in your CI. A `verified_*` case that abstains means the checker got
stricter or broke; an `abstain_*` case that verifies means it lost a safety
property.

### CI

The repo now has CI, which it did not before. Alongside the tests, one job
installs the checker with **no extras** and runs the conformance suite against
it, so `dependencies = []` — a load-bearing claim, since it is what lets a
consumer check a certificate on a bare interpreter — is enforced rather than
merely asserted. The matrix covers Python 3.9 and 3.13, the floor and ceiling
of `requires-python`; 3.9 was previously an untested claim.

### Breaking

- **`certkit.producer._pad` is now `pad_claim`** and is public. External
  producers must pad their claims: the checker re-derives in outward-rounded
  interval arithmetic, so its enclosure is strictly wider than an exact-float
  bound, and an unpadded claim is always refused as "tighter than the
  re-derived enclosure". This is calibration, not a soundness bug — see the
  README's "Writing a producer".

### Certificate format

`schema` is `certkit/1`. The compatibility policy is **strict refusal**: a
certificate whose schema is not exactly `certkit/1` is refused outright, with
no partial-coverage path in either direction. Partial verification of a
certificate the checker only half understands is a verdict nobody can act on.
The cost is that a schema bump is a coordinated release across every consumer.

### Checker routes available

Dense symmetric, banded, tridiagonal, generalized (`A`, `S`), complex
Hermitian, matrix-free Pauli-sum, and backward-error. `DENSE_LIMIT` is 256,
which reaches H4 scale; above it the matrix-free path applies and no gap
discharge is available. `MAX_DEPTH` bounds dependency chains at 8. In every
case the checker abstains rather than guessing.
