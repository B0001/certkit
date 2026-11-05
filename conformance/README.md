# certkit conformance suite

Frozen certificates with expected verdicts. Consumers run this against the
certkit release they pin, in their own CI, to detect drift in the checker they
depend on.

```sh
python conformance/run.py                      # this interpreter's certkit.cli
python conformance/run.py --checker certkit    # an installed release
```

Exit status is 0 only if every case matches. A checker exit status other than
0 (VERIFIED) or 1 (ABSTAIN) fails the case outright: certkit exits 2 when it
has no verdict at all (a usage, IO or internal error). Beyond that there are
two failure directions, and they mean opposite things:

- **A `verified_*` case that abstains** — the pinned checker got stricter, or
  broke. Claims you were relying on no longer verify.
- **An `abstain_*` case that verifies** — the pinned checker lost a safety
  property. This is the serious direction.

Both are release-blocking.

## Why this is separate from `tests/`

`tests/` is certkit's own test suite: it imports the checker in-process,
generates cases at runtime, and needs numpy. A consumer cannot run it against
a pinned release without reproducing this repo's environment.

This suite is the opposite by design. The cases are **frozen artifacts**, not
generated, and `run.py` imports nothing from certkit — it invokes the checker
as a subprocess over files, which is how the integration contract says a
consumer checks anything. Stdlib only, no numpy.

## The cases

| Case | Expect | What it pins |
|---|---|---|
| `verified_dense_lambda_min` | VERIFIED | Baseline: a correct enclosure on a 6×6 dense symmetric operator. |
| `verified_composed_bundle` | VERIFIED | A temple certificate discharging its gap hypothesis through a referenced count certificate. |
| `verified_banded_sturm_be` | VERIFIED | A correct count claim on a genuinely banded (bandwidth 3) operator, verified through `sturm_be`'s `NotTridiagonal` fallback to the banded backward-error route. |
| `abstain_enclosure_shrunk` | ABSTAIN `tighter` | The witness does not support the claim — the headline failure class. |
| `abstain_enclosure_shifted` | ABSTAIN `disjoint` | Enclosure moved off the true eigenvalue. |
| `abstain_unsealed_mutation` | ABSTAIN `content hash mismatch` | Body altered without re-sealing; the hash must catch it before any mathematics runs. |
| `abstain_witness_tampered` | ABSTAIN `tighter` | Perturbed witness vector has a larger residual than claimed. |
| `abstain_operator_substituted` | ABSTAIN `operator` | A valid certificate against the wrong operator. |
| `abstain_unknown_rule` | ABSTAIN `unknown witness rule` | Unknown rule names are refused, never ignored. |
| `abstain_garbage_input` | ABSTAIN `unknown schema version` | Malformed input abstains rather than crashing. |
| `abstain_dependency_missing` | ABSTAIN `not in the bundle` | Broken dependency: the referenced count certificate is absent. |
| `abstain_banded_sturm_be_tampered` | ABSTAIN `re-derived` | A lying count claim on the same banded `sturm_be` route, not just its tridiagonal fast path. |
| `abstain_forged_cycle` | ABSTAIN `content hash mismatch` | A cycle, buildable only by lying about content hashes. |
| `abstain_self_reference` | ABSTAIN `content hash mismatch` | A cycle of length one. |

Every ABSTAIN case carries a `reason_contains` in `manifest.json` and must
abstain *for that reason*, matched against the checker's stdout. A checker that
refuses everything indiscriminately, or crashes with a traceback on stderr,
therefore fails them all: a stub that always exits 1 passes none of the 14.
`tests/test_hostile_json.py` runs the suite against such stubs (`certkit-3zr`).

## Regenerating

The cases are frozen deliberately: a suite that regenerates its own inputs
cannot detect a change in what the producer emits. Regenerate only when the
certificate format itself changes, and expect the diff to be reviewed.
