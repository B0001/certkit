# Handoff: certkit-8y2.1 — Formalize the floating-point layer: interval ops enclose the real result

## Verdict

**Done.** `lean/Certkit/Interval.lean` proves, machine-checked with zero `sorry`
and only the standard mathlib axioms (`propext`, `Classical.choice`,
`Quot.sound`), that `Iv`'s `add`/`sub`/`mul`/`truediv`/`sqrt` each enclose
every possible exact real result, given the `nextafter` half-ulp-rounding +
one-ulp-outward-widening argument from `interval.py`'s own docstring. This is
the acceptance criterion verbatim: "An `Interval.lean` with the enclosure
property proved for add, sub, mul, div, sqrt."

`interval.py` itself was **not modified** — this bead is about proving the
argument the file already makes, not changing the argument. `interval.py`
remains fuzz-tested against exact `Fraction` arithmetic in the Python suite;
that test is now backed by a machine-checked proof of the same claim.

## What was proved, and how it maps to `interval.py`

`lean/Certkit/Interval.lean`, 11 theorems, in dependency order:

1. **`corner_mul_le_upper` / `corner_mul_le_lower`** — pure real-analysis fact
   (no floats): for `a ∈ [alo,ahi]`, `b ∈ [blo,bhi]`, `a*b` is bracketed by
   the min/max of the four corner products. No existing mathlib lemma covers
   sign-mixed reals (`Icc_mul_Icc` is for ordered groups only), so this is
   proved from scratch by a 64-way sign case-split (`rcases le_total 0 _`
   six times) closed by `nlinarith` per branch. This is exactly what
   `Iv.__mul__`'s `corners = (lo*lo, lo*hi, hi*lo, hi*hi)` computes.
2. **`inv_mem_of_pos` / `inv_mem_of_neg`** — `1/x` reverses order strictly on
   one side of `0`; used to reduce division to the multiplication argument
   via `a/b = a * (1/b)`, matching `Iv.__truediv__`'s precondition that the
   divisor interval not contain zero (`o.contains_zero` check).
3. **`RoundingModel`** — the `nextafter` widening argument itself, stated as
   an explicit hypothesis structure rather than derived from Lean's `Float`
   type. See "What was deliberately not attempted" below for why.
4. **`RoundingModel.roundOutDown_le` / `le_roundOutUp`** — the crux lemma:
   round-to-nearest (error ≤ half a ulp) then widen outward by ≥1 ulp never
   loses the true value. This is the one-line mathematical content of
   `interval.py`'s docstring, now a proof instead of a comment.
5. **`add_enclosure`, `sub_enclosure`** — direct application of the crux
   lemma to `Iv.__add__`/`Iv.__sub__`'s single `_widen` call.
6. **`mul_enclosure`** — combines the corner lemmas with monotonicity of
   `down`/`up` to show the widened min/max of the four *rounded* corners
   still encloses `a*b`. Matches `Iv.__mul__` exactly, including its NaN
   guard being out of scope (see below).
7. **`div_enclosure`** — division restricted to `0 < blo ∨ bhi < 0` (divisor
   interval excludes zero, matching `o.contains_zero`'s guard), reduced to
   `mul_enclosure` via the reciprocal lemmas.
8. **`sqrt_enclosure`** — requires the enclosed real `a` to be non-negative
   (`interval.py`'s own documented caller obligation on `meet_nonneg`/
   `sqrt`), and mirrors `Iv.sqrt`'s clamp of the lower endpoint to `0` before
   taking the square root (`max alo 0` in the theorem statement).

Full proof text and doc comments are in `lean/Certkit/Interval.lean`.

## Build infrastructure added (new — this repo had none)

`lean/Certkit/Soundness.lean` predates this bead and has never compiled here
(its own header says so). There was no `lakefile.toml`, `lean-toolchain`, or
manifest anywhere in the repo before this session, so nothing Lean-side had
ever actually been built. This bead adds the first real, reproducible Lean
build:

- `lean/lakefile.toml` — requires `mathlib` from its GitHub repo.
- `lean/lean-toolchain` — pinned to `leanprover/lean4:v4.34.0-rc2`, taken
  from mathlib4's own `lean-toolchain` at the resolved revision, to guarantee
  version compatibility.
- `lean/lake-manifest.json` — pins mathlib and its transitive deps
  (`plausible`, `LeanSearchClient`, `importGraph`, `proofwidgets`, `aesop`,
  `Qq`, `batteries`, `Cli`) at exact revisions, for reproducibility.
- `lean/Certkit.lean` — root module, `import Certkit.Interval` only.
- `lean/.gitignore` — ignores `.lake` (the local build cache/package
  checkout; ~7.6 GB once populated, a build artifact like `node_modules`,
  not something to commit).

**Deliberately not wired in:** the root `Certkit.lean` does **not** import
`Soundness.lean`. That file is all `sorry` except one `trivial`; wiring it
into the build is in scope for `certkit-8y2.2`/`certkit-8y2.3` (which this
bead blocks), not this one. I did not touch `Soundness.lean` at all — it is
byte-for-byte what it was before this session.

Build verified from the actual repo location:
```
$ cd /workspace/lean && XDG_CACHE_HOME=/tmp/xdg-cache lake build Certkit
Build completed successfully (8766 jobs).
```
`.lake` (mathlib source + prebuilt `.olean` cache) is symlinked to
`/tmp/certkit-lean/.lake` rather than materialized inside `/workspace` —
`/workspace`'s filesystem was at 98% capacity (14 GB free) when I checked,
not enough headroom for a 7.6 GB cache. The symlink is gitignored and is a
session-local convenience; a fresh clone reproduces the build with
`lake exe cache get && lake build` (`lake exe cache get` downloads prebuilt
`.olean`s for the pinned mathlib revision rather than building from source —
confirmed in this session at ~28s).

Axiom check, re-run from the repo-located copy (not just the scratch one) to
confirm the move didn't silently change anything:
```
$ lake env lean Certkit/AxCheck.lean   # scratch file, deleted after use
'Certkit.corner_mul_le_upper' depends on axioms: [propext, Classical.choice, Quot.sound]
'Certkit.corner_mul_le_lower' depends on axioms: [propext, Classical.choice, Quot.sound]
'Certkit.inv_mem_of_pos' depends on axioms: [propext, Classical.choice, Quot.sound]
'Certkit.inv_mem_of_neg' depends on axioms: [propext, Classical.choice, Quot.sound]
'Certkit.RoundingModel.roundOutDown_le' depends on axioms: [propext, Classical.choice, Quot.sound]
'Certkit.RoundingModel.le_roundOutUp' depends on axioms: [propext, Classical.choice, Quot.sound]
'Certkit.add_enclosure' depends on axioms: [propext, Classical.choice, Quot.sound]
'Certkit.sub_enclosure' depends on axioms: [propext, Classical.choice, Quot.sound]
'Certkit.mul_enclosure' depends on axioms: [propext, Classical.choice, Quot.sound]
'Certkit.div_enclosure' depends on axioms: [propext, Classical.choice, Quot.sound]
'Certkit.sqrt_enclosure' depends on axioms: [propext, Classical.choice, Quot.sound]
```
No `sorryAx`, no smuggled axioms — all 11 theorems are genuine, complete
proofs.

## What was deliberately not attempted, and why

- **`RoundingModel` is a hypothesis, not a derivation from Lean's `Float`
  type.** mathlib4 has no formal IEEE-754 semantics — I grepped the full
  mathlib4 source tree and confirmed there is no `nextafter`, no `ulp`, and
  nothing under those names to derive the contract from. `RoundingModel`
  states the properties correctly-rounded IEEE-754 arithmetic and
  `nextafter` are documented to have (half-ulp rounding error, ≥1-ulp
  outward widening, monotonicity of the widening functions) as explicit
  fields, and everything downstream is proved *from* those fields. This
  mirrors how Coq's Flocq library structures floating-point proofs
  (hypothesize the rounding contract, derive consequences) rather than
  attempting a from-scratch IEEE-754 formalization, which would be a
  multi-week undertaking orthogonal to this bead. The file's doc comments
  say this explicitly — I am not claiming this derives from Lean's `Float`.
- **The correspondence between `RoundingModel`'s hypotheses and Python's
  actual `math.nextafter`/float arithmetic is asserted as standard IEEE-754
  knowledge, not machine-checked.** There is no bridge in Lean (or anywhere)
  connecting Lean's `Float` or Python's runtime floats to this abstract
  model — that bridge doesn't exist in mathlib to build on. This is the one
  honest gap in "the floating-point layer is now proved": the *mathematical
  argument* is proved; that Python's actual doubles satisfy the argument's
  premises is not itself machine-verified, only well-established IEEE-754
  fact.
- **NaN and overflow are out of scope of the Lean model.** `ℝ` has no NaN or
  infinity, so `_down`/`_up`'s NaN rejection (→ `IntervalError` → checker
  ABSTAIN) and `nextafter(inf, -inf)` overflow-saturation behavior are
  Python-level special cases not represented in the proof. These are
  documented, sound-by-construction behaviors in `interval.py` (overflow
  degrades to a wide-but-sound interval per its docstring; NaN raises rather
  than silently propagating) — nothing here contradicts them, they are
  simply outside what a real-number formalization can express.
- **`dot`, `matvec`, `sqnorm` were not formalized.** The acceptance
  criterion is explicitly "add, sub, mul, div, sqrt"; these three are sums/
  compositions of `add`/`mul` and would follow by induction from
  `add_enclosure`/`mul_enclosure`, but that induction is new work, not
  covered by this bead's stated scope.
- **`Soundness.lean` was not touched, wired in, or "un-sorry'd."** Doing so
  is explicitly the next beads in this epic (`certkit-8y2.2`,
  `certkit-8y2.3`), both of which this bead blocks and which I left alone
  per "do only this bead."
- No numeric constant, bound, tolerance, or threshold was touched or
  introduced anywhere — the entire deliverable is structural (a hypothesis
  structure and proofs about it), so there was nothing to be tempted to
  transcribe or loosen.

## Final Python test-run line (verbatim)

```
$ uv run pytest tests
============================= test session starts ==============================
platform linux -- Python 3.12.13, pytest-9.1.1, pluggy-1.6.0
rootdir: /workspace
configfile: pyproject.toml
collected 110 items

tests/test_backends.py ..............                                    [ 12%]
tests/test_backward.py ...................                               [ 30%]
tests/test_banded.py ...............                                     [ 43%]
tests/test_composition.py ....................                           [ 61%]
tests/test_end_to_end.py ............                                    [ 72%]
tests/test_interval.py ........                                          [ 80%]
tests/test_sector_scope.py ....                                          [ 83%]
tests/test_tamper.py ..............                                      [ 96%]
tests/test_trust_boundary.py ....                                        [100%]

============================= 110 passed in 6.14s ==============================
```
110 = 106 baseline + 4 from `tests/test_sector_scope.py`, which is
pre-existing, uncommitted work from a different bead (`certkit-ph1`) that I
did not touch. 0 failures, 0 new skips. This session's own changes are
entirely under `lean/` and touch no Python file, so this run is a
confirmation of no incidental breakage, not evidence the Lean work itself
"did" anything to the Python suite — it couldn't have.

No-dependency checker run:
```
$ /tmp/venv/bin/python3 -m certkit.cli check examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```
(This sandbox has no bare system `python3`; `/tmp/venv` is the interpreter
`uv sync` created. This is unrelated to the Lean work — `certkit.cli` is
pure-stdlib on the trust boundary regardless of which interpreter runs it,
and `tests/test_trust_boundary.py` — 4/4 passed above — is what actually
enforces that.)

## Files changed

New, untracked (all under `lean/`, nothing outside it):
```
lean/.gitignore
lean/Certkit.lean
lean/Certkit/Interval.lean
lean/lake-manifest.json
lean/lakefile.toml
lean/lean-toolchain
```
`lean/.lake` also appears on disk but is a symlink to `/tmp/certkit-lean/.lake`
and is gitignored — it will not show as untracked in `git status` and is not
part of this handoff's file list.

Untouched (pre-existing uncommitted work belonging to `certkit-ph1`, left
exactly as found): `README.md`, `certkit/checker.py`, `issues.jsonl`,
`tests/test_sector_scope.py`, `uv.lock`.

## Handoff commands

```bash
git status
git diff --stat -- lean/

# Suggested commit (not run — git policy for this session is report-only):
git add lean/.gitignore lean/Certkit.lean lean/Certkit/Interval.lean \
        lean/lake-manifest.json lean/lakefile.toml lean/lean-toolchain
git commit -m "certkit-8y2.1: prove interval arithmetic encloses the real result (add/sub/mul/div/sqrt)"
```

`bd close certkit-8y2.1` will be run after this file is written, with the
Python suite green (110 passed, 0 failures, 0 new skips) and the Lean build
verified from the repo location. `bd export -o issues.jsonl` will follow
since the bead's status changed.
