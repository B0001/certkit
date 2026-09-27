# certkit-85m — conformance abstain reasons don't name the actual defect

## What was wrong

Two conformance cases were fail-closed (correct ABSTAIN verdict) but the
`Verdict.reason` string misdescribed *why*:

1. `abstain_garbage_input` (`{"not": "a certificate"}`) abstained with
   `schema: content hash mismatch: certificate was modified` — byte-identical
   to `abstain_unsealed_mutation`'s output. Root cause: `_verify_uncached` in
   `certkit/checker.py` called `verify_seal(cert)` as its very first check.
   For a dict that lacks `content_hash` entirely, `verify_seal` still computes
   an expected hash from the body and compares it to `None`, which always
   mismatches — so *any* malformed dict, no matter how far from
   certificate-shaped, got the "was modified" wording, which specifically
   implies tampering of a once-valid certificate. Shape validation (schema
   version, claim/witness presence, rule known, kind match) all ran *after*
   the seal check and never got a chance to fire first.

2. `abstain_enclosure_shifted` (claim ~+7.53, true value ~-2.469 — no
   overlap at all) abstained with `claimed interval is tighter than the
   re-derived enclosure`. `_implies()` (`certkit/checker.py`) used one
   boolean, `not (claim_lo <= lo and hi <= claim_hi)`, to guard both "claim
   overlaps the true enclosure but doesn't fully cover it" (genuinely
   *tighter*) and "claim and true enclosure share no point at all"
   (*disjoint* — a different location, not a narrower one). Both produced
   the same "tighter" message.

## What changed

`certkit/checker.py`:

- `_verify_uncached`: moved `verify_seal(cert)` to run *after* the shape
  checks (`isinstance(cert, dict)`, schema version, claim/witness are dicts,
  rule is known, claim kind matches the rule), instead of before them. Added
  an explicit `require(isinstance(cert, dict), "certificate is not an
  object")` as the very first check, since the shape checks below it call
  `.get()` and previously relied on `verify_seal`'s own isinstance guard to
  protect against `None`/`int`/`str` inputs crashing on `.get`.

  This does not change any verdict: every one of these checks already raised
  `SchemaError` on failure, which is caught by the same `except SchemaError`
  handler regardless of order, and the handler (the code that trusts witness
  numbers) is only reached once *all* the checks, seal included, have
  passed. Reordering two ABSTAIN-triggering guards relative to each other has
  no soundness effect — it only changes which guard fires first, and hence
  which message is reported.

- `_implies`: when the claim doesn't imply the re-derived enclosure, checks
  whether the two intervals are disjoint (`claim_hi < lo or hi < claim_lo`)
  before falling back to the "tighter" wording. Disjoint gets a new message:
  `"claimed interval is disjoint from the re-derived enclosure"`. Overlapping
  but insufficient keeps the existing `"claimed interval is tighter than the
  re-derived enclosure"`. No numeric threshold, tolerance, or bound was
  touched — this is a pure classification of an already-computed boolean
  failure into two named sub-cases using the same `lo`/`hi`/`claim_lo`/
  `claim_hi` the code already had.

## Verdict changes (both still ABSTAIN — only the reason text differs)

```
$ uv run python -m certkit.cli check conformance/cases/abstain_garbage_input/{certificate,operator}.json -v
before: ABSTAIN   schema: content hash mismatch: certificate was modified
after:  ABSTAIN   schema: unknown schema version

$ uv run python -m certkit.cli check conformance/cases/abstain_enclosure_shifted/{certificate,operator}.json -v
before: ABSTAIN   claimed interval is tighter than the re-derived enclosure
after:  ABSTAIN   claimed interval is disjoint from the re-derived enclosure
  re-derived: [-2.469258990315315, -2.469258990315304]   (claim was ~[7.5307, 7.5307])
```

`abstain_unsealed_mutation` is unaffected (still `content hash mismatch:
certificate was modified` — that cert *is* shaped like a certificate, just
tampered after sealing, so this message is now exclusive to genuine tamper
cases). `abstain_enclosure_shrunk` is unaffected (claim point -2.469258990315309
sits strictly inside the true enclosure [-2.469258990315315,
-2.469258990315304], so it's overlapping-but-insufficient, not disjoint —
still reports "tighter").

Fixing `_implies` globally (not just for the one conformance case) changed
one more test's expected string:
`tests/test_complex_witness_transcription.py::test_transcribed_bracket_does_not_verify`
asserted the literal old message for a transcription-mismatch case whose own
docstring already says the claimed bracket is "nowhere near" the true value
(~-1.735 vs -2.0, gap 0.265) — a genuinely disjoint case. Updated the
assertion to the new `"disjoint from"` message and updated the module
docstring's quoted wording to match, noting the certkit-85m split. This is
the *correct* consequence of the fix — I checked the actual numbers (see
`v.rederived` printed in that test) before changing the assertion, not just
made the test pass.

## Bounds/tolerances touched

None. No derivation was needed because no numeric threshold changed — the
change is entirely about *which of two already-true things* (disjoint vs.
merely-not-contained; malformed-shape vs. wrong-hash) is reported, using
comparisons (`claim_hi < lo`, `hi < claim_lo`, `isinstance`, dict key
presence) that were already available to the code.

## Documented limits

None touched, none tempted. This bead is purely about diagnostic wording on
an already-correct fail-closed verdict.

## tests/platform_digest.txt

Regenerated in this commit, since both changed reason strings are exercised
by conformance cases and their exact text is hashed byte-for-byte into this
golden file (`tests/digest_outputs.py`), which CI diffs bit-for-bit
(`.github/workflows/ci.yml`, "Checker output bit-identical to the arm64
golden digest").

```
$ uv run python tests/digest_outputs.py . 
abstain_enclosure_shifted 4328c69d... -> 51da1613...   (reason text changed)
abstain_garbage_input     c45d26e3... -> 03ede25f...   (reason text changed;
                                                          was byte-identical
                                                          to abstain_unsealed_mutation,
                                                          now distinct)
OVERALL                   be1b4272... -> be198a20...
(all other 10 case digests unchanged, confirmed by diff)
```

Verified `uv run python tests/digest_outputs.py | diff tests/platform_digest.txt -`
reports no diff after regeneration.

## Final test-run line (verbatim)

```
$ uv run --extra dev pytest tests
============================= 199 passed in 57.51s =============================
```

## No-dependency checker run (verbatim)

Ran on a bare CPython interpreter with zero third-party packages installed
(`/home/node/.local/share/uv/python/cpython-3.12.13-linux-aarch64-gnu/bin/python3.12`,
confirmed `import numpy` raises `ModuleNotFoundError` on this interpreter;
`python3`/`python` are not on `PATH` in this sandbox at all, so `uv`'s own
managed base interpreter stood in for the "no uv, no venv" run the standing
instructions ask for):

```
$ /home/node/.local/share/uv/python/cpython-3.12.13-linux-aarch64-gnu/bin/python3.12 \
    -m certkit.cli check examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
exit=0
```

## Conformance suite (verbatim)

```
$ uv run python conformance/run.py
12/12 cases passed against schema certkit/1
```

## What I decided not to do

- Did not touch `abstain_unsealed_mutation`'s or `abstain_enclosure_shrunk`'s
  reason strings — both were already accurate for what they describe (real
  tamper-after-seal; real overlapping-but-too-tight claim) and the bead only
  flagged the two mismatched cases.
- Did not add a `reason_contains` pin to `conformance/manifest.json` for the
  two fixed cases. The bead didn't ask for it and `abstain_enclosure_shifted`
  had none before; adding new pinned-reason assertions is a policy question
  (how specific should conformance pins be) outside this bug's scope. Filed
  nothing new here since it's a minor style question, not a defect — happy
  to add if a maintainer wants it.
- Did not generalize `_implies`'s disjoint/tighter split into a third
  category (e.g. "claim fully contains true enclosure but is wider on one
  side") — the bead only asked to stop conflating two specific, distinct,
  already-observed failure shapes, not to enumerate every possible interval
  relationship. Adding more categories with no driving test case would be
  speculative.
- Did not modify `certkit/schema.py`'s `verify_seal`/`SchemaError` messages
  themselves — the fix is entirely about call order in `checker.py`, so
  `schema.py` is untouched.

## What I could not verify

- I could not run the exact CI matrix (ubuntu-latest x86_64, py3.9 and
  py3.13) from this sandbox; I verified the digest is architecture-agnostic
  by re-deriving it here (aarch64 host, Rosetta-emulated x86_64 CPython
  unusable here — `rosetta error: failed to open elf`) and confirming it
  matches what `digest_outputs.py` produces bit-for-bit locally after
  regeneration. The premise that this digest is platform-independent is
  certkit-8hn's own finding (checker output on all 12 conformance cases is
  bit-identical across arm64/x86_64 because it depends only on IEEE binary64
  arithmetic, which both platforms give identically) — I did not re-derive
  that premise myself, only relied on it holding for this session's change,
  which only affects string literals and comparison direction, not floating
  point computation.

## Pre-existing unrelated state in the working tree

At the start of this session `git status` was clean, but by the time I
finished there were unrelated uncommitted modifications already present in
the tree that I did not make and did not touch: `AGENTS.md`, `CLAUDE.md`,
`README.md`, `REVIEW-jcb.md`, `certkit/__init__.py`,
`certkit/backward_error.py`, `issues.jsonl`, `tests/test_backward.py`, plus
untracked `lean/Certkit/Scratch.lean`, `lean/Certkit/Scratch2.lean`,
`sandbox-handoffs/certkit-4ue.md`. These look like another
session/bead's in-progress work (banded backward-error counting, per the
`certkit-4ue` handoff filename) landing in the same checkout while this
session ran. My diff is isolated to `certkit/checker.py`,
`tests/platform_digest.txt`, and `tests/test_complex_witness_transcription.py`
— confirmed via `git diff -- <those three files>` before writing this
handoff. I left everything else exactly as I found it.

## Commands for a human to run

```
git add certkit/checker.py tests/platform_digest.txt tests/test_complex_witness_transcription.py
git commit -m "certkit-85m: name the actual defect in two conformance abstain reasons"
```

(Left the unrelated pre-existing modifications in the tree untouched and
unstaged — a human should review those separately under whatever bead they
belong to.)

## Bead status

Closing `certkit-85m` — acceptance evidence (distinct reason strings, full
test suite green, conformance suite green, digest regenerated and verified
against CI's diff check, no-dependency checker run confirmed) all exists.
