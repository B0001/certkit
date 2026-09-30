# certkit-2sc — conformance/ suite gets banded (bandwidth>1) sturm_be coverage

## Verdict

Done. Added one `verified_*` and one `abstain_*` conformance case, both
genuinely exercising `_rule_sturm_be`'s `NotTridiagonal` fallback to
`count_eigenvalues_below_backward_banded` — confirmed by probe (below), not
assumed from the bandwidth number alone. No checker/trusted-module code was
touched; this is purely conformance-suite content plus docs.

## What was missing (confirmed at session start)

```
$ grep -rn "banded\|sturm_be" conformance/manifest.json conformance/cases/
(no matches)
$ ls conformance/cases/
abstain_dependency_missing  abstain_operator_substituted  abstain_witness_tampered
abstain_enclosure_shifted   abstain_self_reference        verified_composed_bundle
abstain_enclosure_shrunk    abstain_unknown_rule          verified_dense_lambda_min
abstain_forged_cycle        abstain_unsealed_mutation
abstain_garbage_input
```

12 cases, all tridiagonal/dense, matching the bead's description exactly.

## What I added

Two new cases, generated with a throwaway script (not committed) that calls
`certkit.producer.certify_count_below_backward` — the same producer function
`tests/test_backward.py::test_sturm_be_falls_back_to_banded_for_bandwidth_greater_than_one`
and `test_sturm_be_catches_a_lying_banded_certificate` already use in-process
— and writes the resulting sealed certificate + operator encoding straight to
`conformance/cases/<name>/{certificate.json,operator.json}`, formatted
`json.dumps(..., indent=2, sort_keys=True)` to match the existing files'
style (alphabetical keys, no trailing newline).

- **`conformance/cases/verified_banded_sturm_be/`** — a bandwidth-3, n=24
  symmetric banded operator (`random_banded(24, 3, seed=41)`, same fixture
  shape as the in-process test), a correct `eigenvalue_count_below` claim
  (`count=8` below `beta` at the midpoint between eigenvalues 7 and 8), rule
  `sturm_be`. Verifies.
- **`conformance/cases/abstain_banded_sturm_be_tampered/`** — a bandwidth-2,
  n=20 banded operator (`random_banded(20, 2, seed=43)`), a lying claim
  (`count=3` at `beta=-100.0`, where the true count is 0), rule `sturm_be`.
  Abstains with reason `"claimed 3 eigenvalues below beta, re-derived 0"`.

Both added to `conformance/manifest.json` (the abstain case pins
`"reason_contains": "re-derived"`, so a checker that abstained for the wrong
reason — or that stopped abstaining at all — would fail it), and to
`conformance/README.md`'s case table.

### Confirmation the banded path (not the tridiagonal fast path) is actually exercised

The acceptance criteria explicitly ask for this, since a bandwidth>1 operator
that happened to have all its bandwidth-2/3 entries be zero would silently
fall through to the tridiagonal route and this bead's coverage gap would
still exist under a different name. Checked directly:

```python
from certkit.operators import decode_operator
from certkit.backward_error import count_eigenvalues_below_backward, NotTridiagonal

for name in ("verified_banded_sturm_be", "abstain_banded_sturm_be_tampered"):
    op = decode_operator(json.load(open(f"conformance/cases/{name}/operator.json")))
    try:
        count_eigenvalues_below_backward(op, 0.0)
        print(name, "tridiagonal path succeeded (BAD)")
    except NotTridiagonal as e:
        print(name, "-> NotTridiagonal raised as expected:", e)
```

Output:
```
verified_banded_sturm_be -> NotTridiagonal raised as expected: operator is not tridiagonal (entry at 0,2)
abstain_banded_sturm_be_tampered -> NotTridiagonal raised as expected: operator is not tridiagonal (entry at 0,2)
```

So `_rule_sturm_be` genuinely takes the `except NotTridiagonal:` branch into
`count_eigenvalues_below_backward_banded` for both cases, not the tridiagonal
`sweep`/`tridiagonal_arrays` path. Also confirmed the abstain case isn't a
schema-level rejection: its reason string is exactly the re-derivation
mismatch message from `_rule_sturm_be` (`"claimed 3 eigenvalues below beta,
re-derived 0"`), which only fires after the banded count completes
successfully.

## Verdict changes

Nothing that existed before changed verdict — these are two brand-new cases,
not a change to any of the original twelve. Before this session: 12/12 cases,
zero banded coverage. After:

```
$ uv run python conformance/run.py
  pass  verified_dense_lambda_min        VERIFIED
  pass  verified_composed_bundle         VERIFIED
  pass  verified_banded_sturm_be         VERIFIED
  pass  abstain_enclosure_shrunk         ABSTAIN
  pass  abstain_enclosure_shifted        ABSTAIN
  pass  abstain_unsealed_mutation        ABSTAIN
  pass  abstain_witness_tampered         ABSTAIN
  pass  abstain_operator_substituted     ABSTAIN
  pass  abstain_unknown_rule             ABSTAIN
  pass  abstain_garbage_input            ABSTAIN
  pass  abstain_dependency_missing       ABSTAIN
  pass  abstain_banded_sturm_be_tampered ABSTAIN
  pass  abstain_forged_cycle             ABSTAIN
  pass  abstain_self_reference           ABSTAIN

14/14 cases passed against schema certkit/1
```

## Bounds/tolerances/thresholds touched

None. No changes to `interval.py`, `backward_error.py`, `banded.py`,
`checker.py`, or any numeric constant anywhere. This bead is conformance-data
plus docs only.

## Documented limits touched, or tempted to soften

None touched, but one number in `conformance/README.md` was stale by
construction as soon as I added cases, and needed a genuine re-measurement
rather than an assumption:

> "A checker that refuses everything indiscriminately still fails them —
> verified by running the suite against a stub that always exits 1, which
> passes only 7 of 12."

With 14 cases now (3 `verified_*` + 4 `reason_contains` abstains = 7 that an
always-abstain stub fails), re-ran the stub check rather than just doing the
arithmetic by hand:

```
$ uv run python conformance/run.py --checker /tmp/stub_fail.sh   # stub: #!/bin/sh; exit 1
7/14 cases passed against schema certkit/1
failed: verified_dense_lambda_min, verified_composed_bundle, verified_banded_sturm_be,
        abstain_enclosure_shrunk, abstain_operator_substituted, abstain_dependency_missing,
        abstain_banded_sturm_be_tampered
```

Updated `"only 7 of 12"` to `"only 7 of 14"` — the ratio-preserving update the
CLAUDE.md instructions call for (re-measure, don't just bump the denominator
by assumption).

## CHANGELOG

Did **not** edit the existing `0.2.0` entry (which states "twelve frozen
certificates"), per the bead's explicit instruction. Added a new `## Unreleased`
section above it describing the two new cases and citing `certkit-2sc`.

## Final test-run line (verbatim)

```
$ uv run --extra dev pytest tests -q
........................................................................ [ 36%]
........................................................................ [ 72%]
.......................................................                  [100%]
199 passed in 27.87s
```

(Re-ran after the formatting/newline fixup on the new case files: still
`199 passed in 27.53s`, unaffected — these are new conformance fixtures, not
`tests/` fixtures.) `tests/test_trust_boundary.py` specifically: `4 passed in
0.10s`.

## No-dependency checker run

Found a genuinely third-party-free interpreter this session — the raw
uv-managed CPython under
`/home/node/.local/share/uv/python/cpython-3.12.13-linux-aarch64-gnu/bin/python3.12`
(the aarch64 build; there's also an x86_64 build at
`.../cpython-3.12.14-linux-x86_64-gnu/...` but it fails under this
container's rosetta layer with `rosetta error: failed to open elf` — a
container/arch quirk, not a certkit issue). Confirmed numpy is genuinely
absent on it first, then ran both new cases through `certkit.cli check`:

```
$ RAWPY=/home/node/.local/share/uv/python/cpython-3.12.13-linux-aarch64-gnu/bin/python3.12
$ $RAWPY -c "import numpy"
ModuleNotFoundError: No module named 'numpy'

$ $RAWPY -m certkit.cli check conformance/cases/verified_banded_sturm_be/certificate.json \
                              conformance/cases/verified_banded_sturm_be/operator.json -v
VERIFIED  eigenvalue_count_below via sturm_be
(exit 0)

$ $RAWPY -m certkit.cli check conformance/cases/abstain_banded_sturm_be_tampered/certificate.json \
                              conformance/cases/abstain_banded_sturm_be_tampered/operator.json -v
ABSTAIN   claimed 3 eigenvalues below beta, re-derived 0
(exit 1)
```

This is a stronger check than prior sessions' handoffs managed (no system
`python3` was available to them at all) — it directly demonstrates the new
banded cases check clean on an interpreter where importing numpy fails, which
is the property the trust boundary and this conformance suite both exist to
let a consumer rely on.

The documented example command
(`python3 -m certkit.cli check examples/sample/certificate.json
examples/sample/operator.json -v`) also passes on this interpreter, for
completeness:

```
$ $RAWPY -m certkit.cli check examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [...]
```

## What I decided not to do, and why

- Did not touch `examples/sample/banded_bundle.json` or `examples/banded_demo.py`
  (the "existing artifacts that could seed this" the bead mentions) — the
  sample bundle uses rule `sturm` (the interval-LDL^T banded route), not
  `sturm_be` (the backward-error route this bead is specifically about), so
  it wouldn't have exercised the right code path. Building fresh fixtures with
  `certify_count_below_backward` directly was more precise for the bead's
  named target than adapting an artifact built for a different rule.
- Did not use `certify_lambda_min_backward` (the full temple+count bundle) for
  the conformance cases — a standalone `eigenvalue_count_below` certificate
  checked with `check()` (not `check_bundle()`) is simpler, is exactly the
  shape `test_sturm_be_falls_back_to_banded_for_bandwidth_greater_than_one`
  uses to test this same code path in-process, and avoids pulling in
  `temple_ref`/gap-hypothesis machinery that isn't what this bead is pinning.
- Did not add a third case for the `max_bandwidth` exceeded / non-symmetric /
  inexact-entry refusal paths inside `banded_arrays` — the bead's acceptance
  criteria ask for "at least one verified_* and one abstain_*", both delivered
  and both aimed at the specific gap named (a *lying claim* on the banded
  route, not a malformed-operator refusal, which is arguably a different
  conformance concern already partially covered by `abstain_garbage_input`).
  If broader banded-refusal conformance coverage is wanted, that's cleaner as
  its own bead than folding into this one.
- Did not commit, push, or run `bd dolt push` — git policy is report-only.

## What I could not verify

- Whether a future certkit release's CI (mentioned in `CHANGELOG.md`'s 0.2.0
  entry: "one job installs the checker with no extras and runs the
  conformance suite against it") will actually pick up these two new cases —
  I did not find or run that CI job definition in this session; I verified
  the equivalent property manually via the numpy-free raw interpreter above,
  which is the same guarantee that job is presumably built to check.

## Files changed

- `conformance/cases/verified_banded_sturm_be/{certificate.json,operator.json}` — new.
- `conformance/cases/abstain_banded_sturm_be_tampered/{certificate.json,operator.json}` — new.
- `conformance/manifest.json` — two new entries.
- `conformance/README.md` — case table rows added; stub-checker ratio
  re-measured (`7 of 12` → `7 of 14`).
- `CHANGELOG.md` — new `## Unreleased` section added above the existing
  `0.2.0` entry (which was not modified).
- `issues.jsonl` — re-exported via `bd export -o issues.jsonl` after
  claiming/closing `certkit-2sc` (bead-state change only).

## Suggested next commands (not run — git policy is report-only)

```
git add conformance/cases/verified_banded_sturm_be conformance/cases/abstain_banded_sturm_be_tampered \
        conformance/manifest.json conformance/README.md CHANGELOG.md issues.jsonl
git commit -m "conformance: add banded sturm_be verified/abstain cases (certkit-2sc)"
```
