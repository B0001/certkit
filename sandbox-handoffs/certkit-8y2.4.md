# certkit-8y2.4 — Fix pre-existing type-class errors in Soundness.lean

Status: **closed**, evidence below. Both type-class errors reproduced and
fixed by minimally strengthening the two theorems' hypotheses/scope — no
`sorry` count changed, no statement weakened.

## Environment note (not part of the bead, but load-bearing for the evidence)

No Lean toolchain was present in this container at session start (`lake`,
`lean`, `elan` all absent; `/tmp/certkit-lean/.lake` — a symlink target left
by a prior session — had also been wiped since /tmp is not persisted). I
installed elan from `https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh`,
let it fetch the toolchain pinned by `lean/lean-toolchain`
(`leanprover/lean4:v4.34.0-rc2`), and ran `lake exe cache get` to pull
mathlib's prebuilt `.olean` cache (pinned rev
`67f608e6163ac30cf48c9c4b8f3e060a5588117e`, matching `lake-manifest.json`) —
without that, a from-scratch mathlib build would dominate the session.
`~/.cache/mathlib`'s parent is root-owned in this container (same class of
issue as the documented `uv` cache problem), so I pointed
`XDG_CACHE_HOME=/tmp/lean-cache` at scratch space rather than touching the
root-owned directory. This reproduces the same "re-download every worker"
caveat the `uv` fallback note already flags — it is a container property, not
a repo fix, and I did not touch anything under `/home/node/.cache`.

## The two errors, reproduced first

Before making any change, `lake build Certkit` (`Certkit.Soundness` not yet
wired into `Certkit.lean`) succeeds — it doesn't touch `Soundness.lean` at
all. Running the file directly, exactly as the bead's discovery notes
describe:

```
$ lake env lean Certkit/Soundness.lean
...
Certkit/Soundness.lean:80:32: error(lean.synthInstanceFailed): failed to synthesize instance of type class
  LT n
...
Certkit/Soundness.lean:105:44: error(lean.synthInstanceFailed): failed to synthesize instance of type class
  Norm (Matrix n n ℝ)
```

Both match the bead description exactly: `inertia_count_below`'s
`L.BlockTriangular id` (needs `LT` on the type the block function lands in —
here that's `n` itself, since the function is `id`), and `weyl_shift`'s
`‖A - B‖` on `Matrix n n ℝ` (no default `Norm` instance — mathlib
deliberately doesn't pick one globally since a matrix has several natural
norms).

## The fix

**`inertia_count_below`** (`lean/Certkit/Soundness.lean:86`, was line 78
before the doc-comment additions below): added `[LinearOrder n]` to the
theorem's own signature (not to the file-wide `variable` block, so the other
five `sorry` theorems stay maximally generic over any `Fintype`/`DecidableEq`
index type). This is the fix the bead itself suggested. Justification for why
this isn't a smuggled-in weakening of the guarantee: `Matrix.BlockTriangular
M b` requires `[LT α]` where `α` is `b`'s codomain, and this theorem's `b` is
literally `id : n → n`, so triangularity-against-its-own-index-order requires
`n` to carry an order — there's no way to state "L is block triangular
against the identity permutation of its own rows" without one. The Python
checker's actual LDLᵀ sweep already assumes exactly this: it processes row
indices `0, 1, ..., n-1` in order (see `backward_error.sweep`). Adding
`[LinearOrder n]` narrows the theorem from "for any index type" to "for any
*linearly ordered* index type" — a real restriction on generality, but not
one that changes what's being claimed about the matrices the checker actually
handles, all of which are indexed `Fin n` or similar and already linearly
ordered.

**`weyl_shift`** (`lean/Certkit/Soundness.lean:96-113`): added
`open scoped Matrix.Norms.L2Operator in` immediately before the theorem
(placed *before* the doc comment — `open ... in` directly before a doc
comment produces a parse error, `unexpected token 'open'; expected 'lemma'`,
since the doc comment must attach straight to the declaration keyword).
`Matrix.Norms.L2Operator` (from
`Mathlib/Analysis/CStarAlgebra/Matrix.lean`) is mathlib's operator norm on
`Matrix n n 𝕜` for `RCLike 𝕜` — the norm obtained by identifying a matrix
with the continuous linear map it induces on `EuclideanSpace`. This is the
classical spectral norm Weyl's inequality is stated against
(`|λᵢ(A) - λᵢ(B)| ≤ ‖A - B‖₂`), so it's not an arbitrary pick among mathlib's
several matrix-norm options (elementwise, Frobenius, L∞-operator, L2-operator
all exist as separate scoped namespaces specifically so no single one is a
silent default) — it's the one the statement is actually about. I added a doc
note on the theorem making explicit that this is *not* the same norm
`sturm_be` bounds at runtime (that's an entrywise/row-sum bound, effectively
L∞-flavored) — relating the two remains part of what `weyl_shift`'s `sorry`
stands for, and I did not try to paper over that gap.

I did not touch the statement of either theorem's conclusion, weaken any
hypothesis, or remove any obligation — both are still `sorry`.

## Verdict change

| | before | after |
|---|---|---|
| `lake env lean Certkit/Soundness.lean` | 2 `synthInstanceFailed` errors, exit 1 | exit 0, 6 `sorry` warnings, 0 errors |
| `lake build Certkit` (Soundness wired into `Certkit.lean`) | not attempted (file excluded on purpose, see old comment in `Certkit.lean`) | `Build completed successfully (8770 jobs)` |

Wired `Certkit.Soundness` into `lean/Certkit.lean`'s import list (removing
the comment explaining why it used to be excluded — that reason no longer
applies), per the acceptance criterion "`lake build Certkit` succeeds with
Certkit.Soundness imported from Certkit.lean". Full log of the final build:

```
$ lake build Certkit
⚠ [8768/8770] Built Certkit.Soundness (7.5s)
warning: Certkit/Soundness.lean:51:8: declaration uses `sorry`
warning: Certkit/Soundness.lean:59:8: declaration uses `sorry`
warning: Certkit/Soundness.lean:66:8: declaration uses `sorry`
warning: Certkit/Soundness.lean:86:8: declaration uses `sorry`
warning: Certkit/Soundness.lean:99:8: declaration uses `sorry`
warning: Certkit/Soundness.lean:121:8: declaration uses `sorry`
✔ [8769/8770] Built Certkit (6.6s)
Build completed successfully (8770 jobs).
```

Six `sorry` warnings — exactly `rayleigh_ritz_min`,
`residual_encloses_some_eigenvalue`, `temple_lower`, `inertia_count_below`,
`gershgorin_lower`, `weyl_shift`. `sweep_backward_bound` (certkit-8y2.2's
theorem, already in the tree when this session started, not touched by this
bead) contributes no `sorry` warning, as expected. This is exactly "no new
`sorry` introduced beyond the 6 that already exist" from the acceptance
criteria — same six, same theorems, nothing added or removed.

## Bounds, tolerances, guards, or thresholds touched

None. `[LinearOrder n]` and `open scoped Matrix.Norms.L2Operator` are
type-class/scope fixes, not numeric constants — there is no derivation to
write down because there is no number being introduced. I did not touch
`sweep_backward_bound`, `eta_of`/`gamma_of`, or anything in
`BackwardError.lean` (certkit-8y2.2's scope, already closed).

## Documented limits or hedges

None applicable — this bead is pure Lean type-class plumbing, no Python
coverage claim, tolerance, or documented limit is implicated. I updated the
file's own header doc comment to note that `sweep_backward_bound` is now real
(that was already true before this session, from certkit-8y2.2; I left it
alone) — I did not soften or strengthen the "six of seven still `sorry`,
this file has never been compiled" framing beyond what's now literally true
(it compiles as of this bead; it is still six `sorry`s away from a soundness
proof, and I said so in the doc comments I touched).

## What I decided not to do, and why

- **Did not attempt to discharge any of the six `sorry`s.** Out of scope —
  this bead is `certkit-8y2.4`, not `certkit-8y2.3` (which is the "prove the
  theorems" bead, still open, still blocked by nothing but effort).
- **Did not weaken `inertia_count_below` to avoid `[LinearOrder n]`**, e.g. by
  restating `hldl` with an explicit order-encoding function instead of
  reusing `id`. That would be a bigger, less faithful rewrite of the
  bead-author's original statement for no soundness benefit — `[LinearOrder
  n]` is the direct, minimal fix, and it costs nothing the checker's actual
  usage doesn't already assume.
- **Did not pick a different norm for `weyl_shift`** (e.g. the L∞-operator
  norm `Matrix.Norms.Operator`, which is closer to what `sturm_be` bounds at
  runtime) even though it might look more convenient for a future proof that
  connects this theorem to `sweep_backward_bound`. Weyl's inequality is a
  classical fact about the *spectral* (L2-operator) norm; restating it against
  a different norm would either be false in general or require its own
  separate derivation, and picking convenience over the theorem actually
  being true is exactly the kind of trade this repo forbids. The doc comment
  I added flags the norm mismatch with `sturm_be` explicitly so a future
  session proving `weyl_shift` (or bridging it to `sweep_backward_bound`)
  isn't surprised by it.
- **Did not run `bd export -o issues.jsonl`** beyond what closing the bead
  triggers automatically, since I made no other bead-database edits this
  session besides claiming and closing this one bead.
- **Did not commit or push.** Per repo git policy, tree is left ready for a
  human to review and commit.

## What I could not verify

- **`#print axioms` on the two touched theorems was not run.** Both are
  still `sorry`, so `#print axioms` would just report `sorryAx` — not
  informative for a type-class-only fix. I did not check whether
  `[LinearOrder n]` on `inertia_count_below` is *discoverable* automatically
  for every concrete `n` the Python checker's examples would correspond to
  (e.g. `Fin k`) — I only confirmed the statement type-checks generically,
  since the theorem itself is still unproved and not yet instantiated
  anywhere.
- **Did not verify this against a from-scratch (non-cached) mathlib build.**
  I relied on `lake exe cache get`'s prebuilt `.olean`s for the pinned
  mathlib revision; I did not independently rebuild mathlib from source to
  confirm the cache itself is sound (that's mathlib's own CI's job, not
  this bead's).

## Final commands and output

```
$ uv sync --extra dev
... Installed 7 packages ...

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

============================= 110 passed in 5.83s ==============================
```

110, not 106 — `tests/test_sector_scope.py` (4 tests) is new, untracked work
already present in the working tree from a session before mine (predates my
claim of this bead; unrelated to it — I did not add or modify any Python
test). No failures either way. This session touched only `lean/Certkit.lean`
and `lean/Certkit/Soundness.lean`; it made no Python changes.

No-dependency checker run (via the bare uv-managed CPython interpreter, not
the project venv, since the container has no system `python3`):

```
$ /home/node/.local/share/uv/python/cpython-3.12-linux-aarch64-gnu/bin/python3.12 -c "import numpy"
ModuleNotFoundError: No module named 'numpy'

$ /home/node/.local/share/uv/python/cpython-3.12-linux-aarch64-gnu/bin/python3.12 -m certkit.cli check examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

## Files changed by this session

- `lean/Certkit/Soundness.lean` — `[LinearOrder n]` added to
  `inertia_count_below`; `open scoped Matrix.Norms.L2Operator in` added
  before `weyl_shift`; doc comments on both explaining the addition; header
  comment left as-is except for the pre-existing (not mine)
  `sweep_backward_bound`/`Interval.lean` status update from certkit-8y2.2.
- `lean/Certkit.lean` — added `import Certkit.Soundness`, removed the
  now-stale comment explaining its exclusion.

Everything else in `git status` (`README.md`, `certkit/checker.py`,
`issues.jsonl`, `lean/Certkit/BackwardError.lean`, `lean/Certkit/Interval.lean`,
`tests/test_sector_scope.py`, `lean/lake-manifest.json`, `lean/lakefile.toml`,
`lean/lean-toolchain`, `lean/.gitignore`, `uv.lock`) predates this session and
was not touched by it.

## Suggested next commands (not run — git policy)

```
git add lean/Certkit.lean lean/Certkit/Soundness.lean
git commit -m "Fix Soundness.lean type-class errors (inertia_count_below, weyl_shift)"
```

(plus whatever the reviewer decides about the other pending uncommitted files
from earlier sessions, which are outside this bead's scope.)
