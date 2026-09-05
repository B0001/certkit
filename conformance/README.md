# certkit conformance suite

Frozen certificates with expected verdicts. Consumers run this against the
certkit release they pin, in their own CI, to detect drift in the checker they
depend on.

```sh
python conformance/run.py                      # this interpreter's certkit.cli
python conformance/run.py --checker certkit    # an installed release
```

Exit status is 0 only if every case matches. There are two failure directions
and they mean opposite things:

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
| `abstain_enclosure_shrunk` | ABSTAIN `tighter` | The witness does not support the claim — the headline failure class. |
| `abstain_enclosure_shifted` | ABSTAIN | Enclosure moved off the true eigenvalue. |
| `abstain_unsealed_mutation` | ABSTAIN | Body altered without re-sealing; the hash must catch it before any mathematics runs. |
| `abstain_witness_tampered` | ABSTAIN | Perturbed witness vector has a larger residual than claimed. |
| `abstain_operator_substituted` | ABSTAIN `operator` | A valid certificate against the wrong operator. |
| `abstain_unknown_rule` | ABSTAIN | Unknown rule names are refused, never ignored. |
| `abstain_garbage_input` | ABSTAIN | Malformed input abstains rather than crashing. |
| `abstain_dependency_missing` | ABSTAIN `not in the bundle` | Broken dependency: the referenced count certificate is absent. |
| `abstain_forged_cycle` | ABSTAIN | A cycle, buildable only by lying about content hashes. |
| `abstain_self_reference` | ABSTAIN | A cycle of length one. |

Cases carrying a `reason_contains` in `manifest.json` must abstain *for that
reason*. A checker that refuses everything indiscriminately still fails them —
verified by running the suite against a stub that always exits 1, which passes
only 7 of 12.

## Regenerating

The cases are frozen deliberately: a suite that regenerates its own inputs
cannot detect a change in what the producer emits. Regenerate only when the
certificate format itself changes, and expect the diff to be reviewed.
