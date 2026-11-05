# Changelog

## Unreleased

### A VERIFIED names its claim kind, operator and pencil, and callers can require them

`check()` and `certkit check` verified any true claim, and nothing bound the
verdict to the question the caller meant (`certkit-1vm`):

- On an operator whose smallest eigenvalue is 1, three claims printed VERIFIED
  and exited 0: a `residual` claim that some eigenvalue lies in [49.5, 50.5], a
  `rayleigh` upper bound of 1e300 and a `gershgorin` lower bound of -1e300.
- A `gen_gershgorin_rayleigh` claim with `metric_ref` equal to `operator_ref`
  printed `VERIFIED lambda_min_enclosure ... [0.4, 1.1]` for an A whose
  smallest eigenvalue is 100. With S = A every eigenvalue of the pencil is 1,
  so the claim is true of the pencil and false as read.
- `bundle_verdict` returned the tightest VERIFIED of the requested kind about
  any operator or pencil in the bundle. A pencil caller who passed [A, S] got
  λ_min(S) = 1.990, while λ_min(A, S) = 49.84.

What changed:

- `Verdict` has two new fields, `operator_ref` and `metric_ref`, filled from
  the claim. `metric_ref` is None unless the verdict is about the pencil
  A x = λ S x. Only `gen_gershgorin_rayleigh` sets it, because it is the only
  rule that reads S. A claim under any other rule that names a `metric_ref` is
  still a claim about A alone. A pencil verdict prints
  `of the pencil (A, S), metric_ref ...`.
- `bundle_verdict(results, kind, *, operator_ref, metric_ref=None)` returns
  only a verdict about that operator. It treats the operator as a standard
  eigenproblem unless `metric_ref` names the pencil's S.
- `certkit check --require-kind KIND --operator-ref REF` turns a VERIFIED of
  another kind, or about another operator, into ABSTAIN with exit 1. For one
  certificate the reason starts `scope:`.
- `certkit check` no longer answers with a pencil verdict. With one operator
  file the pencil can only be S = A.
- The README guarantee is now stated per claim kind and for pencils.
  INTEGRATION.md and TCB.md say what exit 0 does and does not mean.

**What callers must change:**

- **`bundle_verdict(results)` now raises TypeError.** Pass the operator you
  mean: `bundle_verdict(results, operator_ref=operator_ref(a_enc))`. For a
  pencil, also pass `metric_ref=operator_ref(s_enc)`.
- **Callers of `check()` that read `verdict.enclosure` as the smallest
  eigenvalue** must also check `verdict.claim_kind == "lambda_min_enclosure"`
  and `verdict.metric_ref is None`.
- **Consumers of `certkit check`** should pass
  `--require-kind lambda_min_enclosure`, or whatever kind they act on. Without
  it, exit 0 for one certificate still means "a true claim of the printed
  kind".
- **Pencil certificates checked through the CLI** now exit 1 where they used
  to exit 0. Such a certificate can only have verified with S = A.
- **Code that compares or serialises `Verdict`** sees the two new fields. They
  are the only reason `tests/platform_digest.txt` was regenerated: no verdict,
  and no CLI output, changed on the conformance cases.

The certificate schema is unchanged. A distinct claim kind for pencils would
let `--require-kind` alone tell λ_min(A, S) from λ_min(A). That is a schema
change and needs a coordinated release, so it is left as a follow-up.

### Hostile JSON abstains instead of crashing; CLI exit 2 means no verdict

`check()`, `check_bundle()` and `certkit check` used to raise on JSON that no
producer would emit:

- a lone UTF-16 surrogate (UnicodeEncodeError while sealing);
- a list or object where a rule name, `operator_ref` or operator `kind`
  belongs (TypeError);
- a hex float of 2^1024 or more (OverflowError);
- nesting too deep for `json` (RecursionError);
- a complex Hermitian metric operator for `gen_gershgorin_rayleigh`
  (AttributeError);
- a bundle that is not a list.

All of them now abstain. `digest()` raises `SchemaError` for input with no
canonical form, and `h2f()` raises it on overflow. `gen_gershgorin_rayleigh`
now checks the kind of S. `_verify_uncached` turns any exception it did not
anticipate into ABSTAIN, naming the exception type.

The CLI now exits 2 for a usage, IO or internal error, so a crash no longer
looks like ABSTAIN (exit 1). Unparseable input is still a malformed
certificate and gets ABSTAIN. `conformance/run.py` now fails any case whose
exit status is neither 0 nor 1. Every ABSTAIN case now pins a
`reason_contains`, matched against stdout only, so a traceback cannot satisfy
it. Checker output on the fourteen conformance cases is unchanged, and so is
`tests/platform_digest.txt` (`certkit-3zr`).

### A tight (Temple/inertia) route for complex Hermitian operators

`hermitian_temple_inertia`: the complex analogue of `temple_inertia`, closing
the gap `certkit-3ta` left open. An interval LDL^H factorization of
`A - beta*I` over `CIv` (`checker.count_eigenvalues_below_hermitian`) counts
sign-determined pivots via Sylvester's law of inertia for Hermitian
congruence, discharging the Temple gap parameter inline exactly like the
real route does, rather than trusting it from the witness. Needed one new
primitive in the trusted `interval.py`, `CIv.scale` (multiplication by a real
interval scalar — the real-scalar sibling `CIv.__truediv__`'s real-divisor
restriction already had). Tested in `tests/test_complex_temple_inertia.py`
against `numpy.linalg.eigvalsh`, against the real route on real-embedded
matrices, and for the usual abstain-not-degrade cases (gap too tight, lying
`beta`, tampered witness, cross-kind dispatch) (`certkit-1y7`).

### Conformance suite now covers the banded `sturm_be` route

`conformance/` grows from twelve cases to fourteen: `verified_banded_sturm_be`
(a correct `eigenvalue_count_below` claim on a genuinely banded, bandwidth-3
operator, verified through `_rule_sturm_be`'s `NotTridiagonal` fallback to
`count_eigenvalues_below_backward_banded`) and
`abstain_banded_sturm_be_tampered` (the same route, a lying count claim, must
abstain). Previously every frozen case was tridiagonal or dense, so a
regression specific to the banded backward-error path had no conformance
coverage at all — `tests/` covered it in-process, but a consumer running only
`conformance/run.py` against a pinned release did not (`certkit-2sc`).

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
