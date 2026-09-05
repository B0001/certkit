# certkit integration contract

Status: decided 2026-09-05. This is the contract three consumers pin against
(Krylov solver, robot abstention layer, math-graph). Changing it is a
breaking change to all of them.

## The decision: protocol, not library

**certkit is consumed as a protocol over files, not as an imported checker.**

certkit's entire value is that the checker is independent of the producer. A
checker that runs inside the producer's process, on the producer's data
structures, sharing the producer's dependencies, is not an independent
checker — it is a subroutine of the thing it is meant to check, and a bug
shared between the two cancels out and is invisible in exactly the cases the
certificate exists to catch.

So:

- Consumers are **producers**. They emit files: a certificate plus the
  operator/witness data needed to re-derive the claim.
- The checker runs **out of process**, on those files, with no access to
  producer internals, from a pinned release. Different interpreter is the
  minimum bar; different machine (CI) is the intended deployment.
- The producer's own verdict is **not** a verification. Only a checker run
  that a consumer did not influence counts.

## The import rule

A producer MAY import, as ordinary library code for its own arithmetic:

| Module | Why it is allowed |
|---|---|
| `certkit.interval` (`Iv`, `IntervalError`) | Rigorous arithmetic is a substrate, not an adjudication. Using it makes the producer's own bounds sound; it does not let the producer grade itself. |
| `certkit.operators` (`encode_*`, `operator_ref`) | Serialisation of the operator into the exchange format. Format code, not verdict code. |
| `certkit.schema` (`SCHEMA_VERSION`, `seal`, `f2h`) | Writing a well-formed, sealed certificate is the producer's job. |

A producer MUST NOT import:

| Module | Why it is forbidden |
|---|---|
| `certkit.checker` — `check`, `check_bundle`, `bundle_verdict`, `count_eigenvalues_below*`, `Verdict` | This is the adjudication path. Importing it collapses the independence the certificate is for. |
| Any private name (leading underscore) from any certkit module | A private symbol is not a contract. If a producer needs it, it is missing from the public format and must be added deliberately. |
| `certkit.producer` internals | Sharing the producer's own conventions with certkit's reference producer means a convention bug is present identically on both sides and cancels. |

The rule in one line: **import what computes, never what judges.**

## The exchange

Producer writes two files:

```
<out>/operator.json      the operator, via certkit.operators.encode_*
<out>/certificate.json   claim + witness + producer identity, via schema.seal()
```

Checker is invoked as a subprocess, never as a call:

```sh
certkit check <certificate.json> <operator.json>     # exit 0 = VERIFIED, 1 = ABSTAIN
```

Exit status is the verdict. Anything a consumer needs from the check must be
on stdout or in the artifact, not returned through a Python object.

## Version compatibility

Certificates carry `schema` (currently `certkit/1`). The checker's policy is
**strict refusal**: `require(cert["schema"] == SCHEMA_VERSION)`. A certificate
from any other version — older or newer — is refused outright; there is no
partial-coverage path and no forward compatibility.

This is a deliberate choice, not an omission. Partial verification of a
certificate the checker only half understands is a verdict nobody can act on.
The cost is that a schema bump is a coordinated release across all three
consumers, which is the honest price of the guarantee.

## Conformance

Each consumer's CI runs the conformance suite against its pinned certkit and
fails the build on any deviation. The suite must include failure cases —
a broken dependency, a cycle, a claim whose witness does not support it —
because a suite of passing certificates only proves the checker says yes.

The suite does not exist yet; it is the blocking item for consumer CI.

## Conformance of the existing consumer

`certkit_bridge.py` on `B0001/krylov-quantum-solver` main is the first real
producer and it does **not** yet meet this contract. Recorded here so the gap
is tracked rather than rediscovered:

1. It imports `certkit.checker.check` and calls it in-process to produce its
   report. The emitted artifacts do re-check standalone out of process — that
   was verified when the bridge was written — so the underlying claims stand;
   what fails the contract is the in-process verdict path, which must become
   a subprocess call.
2. It imports `_pad` from `certkit.producer` — a private symbol — and uses it
   to widen the bracket that it then submits for checking. This is the
   shared-convention failure the contract exists to prevent: if `_pad` is
   wrong, the producer widens by exactly the amount the checker expects and
   the error is invisible. Either `_pad` becomes public and specified as part
   of the format, or the bridge computes its own padding.

Neither is a defect in the certificates already emitted. Both are defects in
the integration path, and both must close before a second consumer copies the
pattern.

## What this contract does not settle

- **The trusted computing base.** The checker assumes IEEE-754 semantics and
  a floating-point Sturm sweep perturbation bound currently justified by
  reading and tests, not machine-checked. Unstated assumptions are
  indistinguishable from bugs; the list must be written down separately.
- **Runtime latency.** A safety layer cannot block on a slow checker.
  Whether the robot layer checks online within budget or emits now and checks
  offline — with a correspondingly weaker runtime guarantee, stated as such —
  is a measurement, not a decision to make here.
- **Rejection semantics.** What a consumer does when the checker rejects is a
  safety question owned by the consumer, not by this contract.
