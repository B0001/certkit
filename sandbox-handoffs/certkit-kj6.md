# certkit-kj6 handoff

## Bead

"Document that producers must pad claims against the checker's interval
widening." Acceptance criteria: `_pad` or an equivalent is public and
documented in the README's producer-side notes, with the reason spelled out.

## What was wrong

The checker re-derives every claim from scratch in outward-rounded interval
arithmetic, so its enclosure is always at least as wide as (and typically
strictly wider than) an exact-float bound the producer computed. An external
producer that transcribes a correct bound with no calibration margin gets
ABSTAIN, and nothing in the README explained why or what to do about it.
`certkit.producer._pad` already encoded the right convention (relative slack
plus an n-dependent ulp-accumulation term) but was private, undocumented in
the README, and its docstring didn't name the mechanism it was compensating
for.

## What changed

1. **`certkit/producer.py`**: renamed `_pad` → `pad_claim` (public, no leading
   underscore) via a mechanical sed across the file — every one of its 8 call
   sites was updated in the same commit-worth of change, so behavior is
   byte-for-byte identical, only the name changed. Verified this directly: a
   diff of `sed 's/_pad/pad_claim/g'` applied to the pre-session file against
   the post-session file matches everywhere except the docstring itself.
   Expanded the docstring to explain *why* the pad exists (the checker never
   reads the producer's bound; it re-derives from the witness and operator in
   outward-rounded arithmetic, which accumulates ~n ulps across a length-n dot
   product), what each parameter means, and that every `certify_*` function in
   the module already follows this convention.

2. **`README.md`**: added a new "Writing a producer" section (between
   Quickstart and "What the coverage sweep shows") that states the refusal
   mode in plain terms, shows `pad_claim`'s signature and a usage snippet
   lifted from the module's own call sites, and says explicitly that
   over-padding costs coverage but never soundness, so producers should round
   up.

Nothing in `interval.py`, `schema.py`, `operators.py`, `banded.py`,
`backward_error.py`, or `checker.py` was touched. No bound, tolerance, or
threshold value changed — `pad_claim`'s formula (`rel * scale + 16.0 * U * n *
scale + 1e-300`) is exactly what `_pad` computed before; only its name and
docstring changed.

## Note on the working tree at claim time

When I claimed this bead, `certkit/checker.py` and `certkit/producer.py` were
already modified and `tests/test_generalized.py` was already untracked —
uncommitted work from a prior, unrelated, unfinished session (evidently
`certkit-jn1.2`, the generalized eigenproblem `Ax = lambda S x`, which is
still `in_progress` per `bd list`). That work already used `_pad` internally
(now `pad_claim` after my rename, since sed touched every occurrence in the
file including inside `certify_lambda_min_generalized`). I did not review,
endorse, or otherwise touch the substance of that diff — it is out of scope
for this bead and I left it exactly as I found it except for the mechanical
rename that necessarily passed through it. I did not run `bd close` on
`certkit-jn1.2` and did not claim it.

## Verdict change demonstrated

Constructed the failure mode the bead describes and its fix, using the
checker's public API (no internals poked):

```python
from certkit.checker import check
import certkit.producer as producer

# Simulate an external producer that ships an exact-float bound with no
# calibration margin (pad_claim → 0):
producer.pad_claim = lambda *a, **k: 0.0
cert, op = producer.certify_lambda_min(producer.tfim_hamiltonian(6))
check(cert, op).status   # -> ABSTAIN

# Restored / normal producer path (uses pad_claim as shipped):
cert, op = certify_lambda_min(tfim_hamiltonian(6))
check(cert, op).status   # -> VERIFIED
```

Ran both; output was `ABSTAIN` then `VERIFIED` exactly as shown. This is the
same shape the README's Quickstart already demonstrates ("the re-derived
interval is tighter than the claim — the producer padded"), now with an
explicit before/after and a name (`pad_claim`) an external integrator can call.

Also confirmed `pad_claim` is importable and public:
`from certkit.producer import pad_claim` succeeds; `callable(pad_claim)` is
`True`.

## No bounds/tolerances/thresholds touched

None. This bead is documentation-and-naming only. The pad *formula* is
unchanged — I did not adjust `rel`, the `16.0 * U` ulp-accumulation
coefficient, or the `1e-300` floor, and would not have without a derivation
for a new value, which nothing in this bead calls for.

## Documented limits I did not touch

None of the stated limits (DENSE_LIMIT=160, Gershgorin as a floor not a good
bound, coverage falling to zero as the gap closes, n≈10⁴ eigenvector
constraint) are implicated by this change and none were softened.

## Test run (verbatim)

```
$ uv sync --extra dev
...
Installed 7 packages in 108ms
 + certkit==0.1.0 (from file:///workspace)
 + iniconfig==2.3.0
 + numpy==2.5.2
 + packaging==26.3
 + pluggy==1.6.0
 + pygments==2.21.0
 + pytest==9.1.1

$ uv run pytest tests
============================= test session starts ==============================
platform linux -- Python 3.12.13, pytest-9.1.1, pluggy-1.6.0
rootdir: /workspace
configfile: pyproject.toml
collected 120 items

tests/test_backends.py ..............                                    [ 11%]
tests/test_backward.py ...................                               [ 27%]
tests/test_banded.py ...............                                     [ 40%]
tests/test_composition.py ....................                           [ 56%]
tests/test_end_to_end.py ............                                    [ 66%]
tests/test_generalized.py ..........                                     [ 75%]
tests/test_interval.py ........                                          [ 81%]
tests/test_sector_scope.py ....                                          [ 85%]
tests/test_tamper.py ..............                                      [ 96%]
tests/test_trust_boundary.py ....                                        [100%]

============================= 120 passed in 5.95s ==============================
```

**120 passed, 0 failed, 0 new skips.** This is not the "106 passed" baseline
stated in the standing repo instructions — the difference (`tests/test_backends.py`
now 14 vs presumably fewer, plus the whole of `tests/test_generalized.py` and
`tests/test_sector_scope.py`) is entirely accounted for by the pre-existing
uncommitted `jn1.2` work described above, which was already in the tree
before I claimed this bead and which I did not add to or modify beyond the
mechanical rename. I did not subtract from or weaken any test to get to
green; every test that existed before I started still exists and still
passes, plus the ones that were already there from the other in-progress
session.

No-dependency checker run — `python3` is not on `PATH` in this container (only
`uv`'s managed interpreter exists), so I used the same technique
`tests/test_trust_boundary.py::test_checker_runs_in_a_process_where_numpy_is_unimportable`
already uses (a `sys.meta_path` blocker that raises `ImportError` for
`numpy`/`scipy`) against `uv`'s python, then ran the documented CLI command
through it:

```
$ /tmp/venv/bin/python3 -c "
import sys
class Block:
    def find_module(self, name, path=None):
        if name.split('.')[0] in ('numpy', 'scipy'):
            raise ImportError('blocked: ' + name)
sys.meta_path.insert(0, Block())
sys.argv = ['certkit.cli', 'check', 'examples/sample/certificate.json', 'examples/sample/operator.json', '-v']
from certkit.cli import main
main()
"
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

Confirms the checker path still needs no third-party package, unchanged by
this bead's edits (which never touched a trusted module).

## What I decided not to do

- **Did not rename `_pad` in a way that breaks the private/public split
  elsewhere** — e.g. did not add it to `certkit/__init__.py`'s `__all__`.
  Nothing else in `producer.py` is re-exported at the package level either
  (README's own examples do `from certkit.producer import certify_lambda_min`
  directly), so adding `pad_claim` alone to `__init__.py` would be
  inconsistent with the module's existing export convention, not a fix the
  bead asked for. `from certkit.producer import pad_claim` already works,
  which is what "public" means here.
- **Did not touch `certify_lambda_min_generalized` or the rest of the
  pre-existing uncommitted diff** beyond the mechanical rename that had to
  pass through its one `_pad` call site. Reviewing or completing that
  unrelated bead's work is out of scope and would risk conflating two
  sessions' changes in one diff.
- **Did not add a new test asserting the zero-pad/ABSTAIN behavior.** The
  existing test suite (`test_tamper.py`, `test_end_to_end.py`) already
  exercises padded claims verifying and shrunk/tampered claims abstaining;
  this bead is a documentation task, and the acceptance criteria only ask for
  `pad_claim` to be public and documented, not for new test coverage. I
  verified the behavior manually above instead of adding a permanent test for
  a docs-only bead.
- **Did not change the pad formula's constants** (`rel`, `16.0 * U`,
  `1e-300`) — no derivation-worthy reason came up during this work, and the
  bead didn't ask for a formula change.

## What I could not verify

- I could not independently confirm that 120 (vs. the 106 the standing repo
  instructions describe as baseline) is the *correct* expected count for the
  current tree, since that requires judging the completeness/correctness of
  another session's in-progress `jn1.2` work, which is explicitly out of
  scope for me. I can only state that every test present passes and I did not
  reduce or skip any.
- I did not attempt to find or contact the author of the uncommitted
  `certify_lambda_min_generalized` work; I'm relying on `bd list
  --status=in_progress` showing `certkit-jn1.2` still open as the explanation
  for its presence, not on direct confirmation.

## Suggested commands for the human

```
git add README.md certkit/producer.py
git commit   # producer.py's rename touches jn1.2's uncommitted work mechanically;
             # a human should decide whether to commit that generalized-eigenproblem
             # code together with this doc change or split it out first.
```

I did not run `git commit`, `git push`, or `bd dolt push` per the git policy.
`bd close certkit-kj6` will be run after this handoff is written, per the
session prompt's instructions.
