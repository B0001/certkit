# Trusted computing base

What the checker assumes but does not verify. A VERIFIED verdict is only as
good as this list, and an unstated assumption is indistinguishable from a bug.

Written 2026-09-05 against `certkit/1`. Anything added to the checker that
introduces a new assumption belongs here in the same commit.

## 1. Floating-point substrate

| Assumption | Where it bites |
|---|---|
| Python `float` is IEEE-754 binary64. | Every interval endpoint. |
| `+ - * /` are correctly rounded, so each errs by at most half an ulp. | `interval.py` widens by one ulp per operation via `math.nextafter`; a platform erring by more than half an ulp makes every enclosure unsound. |
| `math.nextafter` is correct, including at the boundaries. | The widening itself. Overflow is handled deliberately: `nextafter(inf, -inf)` is the largest finite double, so an overflowed quantity degrades to a wide but sound interval rather than nonsense. |
| No extended-precision or FMA contraction changes a rounded result behind CPython's back. | Any build where a double operation is silently computed at higher precision and rounded once breaks the half-ulp premise. |

certkit does **not** set the FPU rounding mode — Python exposes no way to.
Soundness comes from outward `nextafter` widening instead, which is why every
bound is at least one ulp looser than the exact-float answer. This is the
reason producers must pad; see `pad_claim`.

## 2. Interpreter and standard library

The checker imports **no third-party code**. Verified 2026-09-05: `checker`,
`interval`, `schema`, `operators`, `banded` and `backward_error` contain zero
`import numpy`. A certificate re-checks on a bare interpreter, which is what
makes "different machine, pinned release" cheap to actually do.

What remains trusted: CPython itself, and `math`, `hashlib`, `json` from the
standard library. That is the floor — it cannot be reduced further without
reimplementing the checker in something else, which is a real option for a
second implementation but not a bug in this one.

## 3. Certificate integrity

| Assumption | Note |
|---|---|
| BLAKE2b with `digest_size=16` is collision-resistant enough. | **128-bit digest, so a ~2^64 birthday bound.** Adequate against accident and corruption; thin against a motivated adversary who gets to choose certificate contents. If certificates ever become adversarial inputs rather than pipeline artifacts, this is the first thing to widen. |
| `canonical()` — `json.dumps(sort_keys=True, separators=(",",":"))` — is injective over the certificates actually produced. | Two distinct certificates that canonicalise identically would share a seal. Key order and whitespace are normalised; nothing else is. |
| Floats survive the round trip exactly. | They do, and by construction: `f2h`/`h2f` store every float as `float.hex()`, not decimal, and reject non-finite values outright. This assumption is discharged, not merely hoped for. |

The seal covers the certificate body. It does **not** bind the operator file:
`check()` computes `operator_ref(operator)` from whatever operator it is
handed and resolves the claim's `operator_ref` against it. A mismatched
operator fails to resolve rather than verifying against the wrong matrix — but
the pairing of certificate to operator is the caller's responsibility, not the
seal's.

## 4. The Lean proofs prove the mathematics, not this Python

`lean/` compiles zero-`sorry` against a pinned mathlib, and that is a real
result — but it is a fact about the Lean file, not about the checker.

Two gaps sit between the two, and both are trusted:

1. **The correspondence is by hand.** `Soundness.lean` carries a table mapping
   each theorem to the Python function it is meant to justify
   (`_rule_temple_inertia` ↔ `rayleigh_ritz_min` + `temple_lower`,
   `count_eigenvalues_below` ↔ `inertia_count_below`, and so on). Nothing
   mechanically enforces that the Python still does what the theorem says.
   Change either side and the correspondence can rot silently.
2. **One named, still-uncovered obligation.** `sweep_backward_bound`'s own doc
   comment flags it: that the row-sums `backward_error.sweep` accumulates at
   runtime actually dominate `‖A − Ã‖_∞` is an `Iv`-bookkeeping fact about a
   Python loop, and is not a Lean obligation. The norm-inequality half is
   closed by `l2_opNorm_le_rowSum_of_isHermitian`; this half is not. It is
   tracked as its own piece of work and is the single largest hole in the
   chain.

## 5. Scope limits that are not assumptions

Stated so they are not mistaken for gaps:

- `MAX_DEPTH = 8` bounds dependency-chain recursion; deeper chains abstain.
- `DENSE_LIMIT = 256` bounds the dense inertia route; larger operators take
  the matrix-free path and get no gap discharge.
- A pivot that straddles zero raises `IntervalError` and becomes ABSTAIN. This
  is the honest outcome for a near-degenerate gap, not a failure.

In every case the checker declines to answer. None of them can turn a false
claim into VERIFIED.

## 6. What a VERIFIED verdict therefore means

That the claim was re-derived from the witness and the operator, in outward-
rounded interval arithmetic, by code that shares nothing with the producer —
**given** the substrate in §1, the interpreter in §2, the integrity
assumptions in §3, and the hand-maintained correspondence in §4.

It does not mean the operator is the one you meant to certify, that the
producer's model is physically right, or that anything outside the claim's own
enclosure holds.
