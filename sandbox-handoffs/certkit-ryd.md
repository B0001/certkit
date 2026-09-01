# certkit-ryd — Performance: the checker is pure Python

## What this bead actually was

The bead had no acceptance criteria, no notes, and no design — just a title
and a description stating a design tradeoff already made ("A Rust or C core
... is the obvious move, but it enlarges the trusted base ... Deliberate
tradeoff, not an oversight"). It was claimed by a prior session on
2026-08-24 and left `in_progress` with zero commits, zero notes, and no
working-tree trace — that session did nothing on it (confirmed: `git log`
around that date and `grep -rn certkit-ryd` over the repo turn up nothing
but the bead record itself).

So there was no partial work to pick up. Given the vague scope, I treated
this as: *is the bead's own performance claim actually true, and is there a
safe, trust-boundary-respecting fix?* — i.e., turn a folklore estimate into
a measurement, per this repo's usual standard, and either fix what's safely
fixable or document precisely what isn't.

## What I measured

Benchmark script: `sandbox-handoffs/certkit-ryd-bench.py` (stdlib-only,
imports only `certkit.interval`/`certkit.operators`/`certkit.banded`, runs
fine under the no-dependency interpreter). Reproduce with:

```
PYTHONPATH=. python3 sandbox-handoffs/certkit-ryd-bench.py            # tridiagonal, seconds
PYTHONPATH=. python3 sandbox-handoffs/certkit-ryd-bench.py --wide-band # b=16/64, tens of seconds
```

All runs pick β below the spectrum of every leading principal submatrix, so
no pivot straddles zero and the run measures pure arithmetic cost rather
than getting cut short by an (expected, correct) abstention.

CPython 3.12.13, this container, `count_eigenvalues_below_banded` (the
`sturm` rule's O(n b²) forward-interval route, the one actually built from
raw `Iv` objects at every pivot):

```
      n   b      seconds
  1,000   1        0.005
  5,000   1        0.022
 20,000   1        0.074
 50,000   1        0.199
100,000   1        0.422
200,000   1        0.851
  2,000  64        6.574
  5,000  64       16.655
 10,000  64       33.814
 20,000  16        4.661
```

Timing is linear in n at fixed b (confirmed: b=16 n=20,000 predicted from
the b=64 n=10,000 point via the O(n b²) model at 4.25s, measured 4.66s).
Extrapolating the b=64 (`MAX_BANDWIDTH`, the module's own cap) line to
n=200,000 gives ≈11 minutes, not 60 seconds. The tridiagonal (b=1) line
reaches n=200,000 in well under a second — nowhere near 60 seconds. Solving
the O(n b²) model for where n=200,000 crosses 60s gives b ≈ 19–20: the
bead's "60 seconds at n=2e5" figure is roughly right for a mid-bandwidth
operator, badly optimistic for `MAX_BANDWIDTH=64`, and badly pessimistic for
plain tridiagonal.

I also checked what actually runs at n=2e5 in practice, since `sturm`
(interval) is not the production route for a large tridiagonal operator —
`sturm_be` is (per README's own "Counting without a dense factorisation"
section: the interval route's pivot enclosure blows up and abstains by
n≈40 on a shrinking-gap operator; `sturm_be` exists precisely to survive
past that). Measured `count_eigenvalues_below_backward` with β genuinely
inside the spectrum (so this is a realistic, non-degenerate case, unlike the
`sturm` runs above which needed β outside the spectrum just to complete):
n=20,000 → 0.21s, n=100,000 → 1.08s, n=200,000 → 2.14s. Also measured
`_gershgorin_lower` (the matrix-free fallback): n=200,000 → 0.54s. Neither
comes close to 60 seconds either.

**Conclusion: the "60 seconds at n=2e5" performance concern is real, but
narrowly localized** — to the `sturm` rule's forward-interval route at
moderate-to-wide bandwidth (roughly b≳20). It is not a property of "the
checker" in general at that scale.

## Where the cost actually is (profiled, not guessed)

`cProfile` on `count_eigenvalues_below_banded(n=2000, b=64)` (21.07s total,
124.7M function calls):

```
ncalls       tottime   cumtime   function
12,339,600     4.16     12.04    Iv._widen
 8,141,120     3.27     12.96    Iv.__mul__
12,339,602     3.09      3.95    Iv.__init__ (frozen-dataclass generated)
        1      2.32     21.07    count_eigenvalues_below_banded (banded.py)
12,339,600     1.43      2.02    Iv._down
12,339,600     1.34      1.91    Iv._up
24,679,200     1.17      1.17    math.nextafter
 8,270,976     0.90      0.90    builtins.min
 8,143,120     0.85      0.85    dict.get
```

`banded.py`'s own bookkeeping (`entry()`, the `lmat` dict, the staleness
cleanup) is a rounding error next to the `Iv` construction/validation cost —
`dict.get` is the largest non-`Iv` line at 0.85s of 21.07s (~4%). Roughly
85% of wall time is spent inside `Iv.__mul__`/`Iv._widen`/`Iv.__init__`:
frozen-dataclass object construction, the NaN/`lo>hi` validation in
`__post_init__`, and two `math.nextafter` calls per elementary operation.
That cost is inherent to `interval.py`'s representation and validation
strategy, not to anything avoidable in the code that calls it.

## What I did and did not change

**Did not touch `interval.py`, or any other trusted module's math.** Two
reasons, both load-bearing:

1. The profile shows there is no large win available *outside* that file —
   a `banded.py`-only restructuring (e.g. replacing the `(i,j)`-keyed dict
   with a ring buffer) could shave at most the ~4-8% currently spent on dict
   operations, not change the qualitative picture. Not worth the risk of a
   subtle bug in trusted bookkeeping code for a single-digit-percent win, so
   I left `banded.py` alone too.
2. The only levers that would meaningfully cut the ~85% figure are (a) a
   compiled hot loop, which is exactly the trust-boundary-widening move this
   bead's own description already declines, or (b) changing `interval.py`'s
   per-operation representation or validation strategy. `interval.py` is one
   of the two files (`backward_error.py` is the other) that `certkit-jcb`
   has flagged as needing an independent human review of its derivations —
   a review that has not happened. Landing unreviewed, performance-motivated
   edits to that file in a session before that review is exactly the wrong
   order of operations, and it would enlarge what the pending reviewer has
   to check without anyone having verified the change preserves the outward-
   rounding soundness argument. I am not the second reviewer `certkit-jcb`
   asks for, and touching the file doesn't make me one.

**Did:**
- Wrote `sandbox-handoffs/certkit-ryd-bench.py`, a reusable, dependency-free
  benchmark (runs under the no-dependency interpreter) for whoever next
  works on `interval.py` or considers a compiled core.
- Added a new "Known limits" bullet to README.md (after the existing
  "forward-enclosure routes still grow" bullet, which is the closest
  existing bullet topically) with the measured numbers and root cause above,
  replacing the bead description's unmeasured "60 seconds at n=2e5" folklore
  with reproducible numbers and a precise scope (which route, which
  bandwidth). This does not soften or upgrade any existing conclusion in the
  README — it adds a new, previously-undocumented data point. No existing
  bullet's wording or claimed limit was changed.

## Bounds, tolerances, guards touched

None. No constant, threshold, or tolerance anywhere in `certkit/` was added,
removed, or changed. `DENSE_LIMIT`, `MAX_BANDWIDTH`, `ETA`/`GAMMA`,
`MAX_REFINEMENTS` are all untouched.

## Test suite

```
uv sync --extra dev
uv run pytest tests -q
171 passed in 27.36s
```

(171, not the standing-context's 165 — `tests/test_exact_oracle.py` and
`sandbox-handoffs/certkit-kjy.md`/`tests/exact_oracle.py`/`issues.jsonl` were
already modified in the working tree when I started this session, from a
different, apparently-still-open bead (`certkit-9oa`, exact rational oracle
for Pauli-sum operators). Not my work, not reverted, not touched — I only
confirmed the suite is green with those changes present, which it is.)

Trust boundary specifically:

```
uv run pytest tests/test_trust_boundary.py -q
4 passed in 0.10s
```

No-dependency checker run:

```
PATH=/home/node/.local/share/uv/python/cpython-3.12-linux-aarch64-gnu/bin:$PATH \
  python3.12 -m certkit.cli check examples/sample/certificate.json examples/sample/operator.json -v
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

(`python3` was not on `PATH` at all in this container — `.venv/bin/python3`
is a broken symlink to a macOS path from whatever machine built the venv.
Worked around it by putting uv's managed CPython 3.12 directly on `PATH`,
per the spirit of the sandbox-cache workaround in the standing prompt's
Environment section. Did not fix the broken symlink — out of scope for this
bead, and not confident it's safe to touch without knowing why it's there.)

## Verdict changes

None. No certificate that verified before now abstains, or vice versa. This
bead was a measurement/documentation task, not a bug fix.

## What I decided not to do

- Did not optimize `interval.py`. See "What I did and did not change" above
  — this is the whole finding of the session, not an omission.
- Did not optimize `banded.py`'s dict-based bookkeeping. Profiled headroom
  there is ~4-8%, not worth the risk to trusted code for that return.
- Did not fix the broken `.venv/bin/python3` symlink. Orthogonal to this
  bead; filing it would be its own (very small) bead if it turns out to
  bite a future session harder than it bit this one.
- Did not attempt the compiled-core rewrite the bead names. Explicitly
  rejected by the bead's own description as trust-boundary-widening; nothing
  in this session's investigation changes that calculus.

## What I could not verify

- Whether the profiled ~85%/~4% split holds at other bandwidths and n — I
  checked it at one configuration (n=2000, b=64) that is representative of
  the expensive regime, and spot-checked the linear-in-n scaling model
  separately, but did not re-profile at every (n, b) pair in the table.
- Whether `MAX_BANDWIDTH=64` is itself well-chosen given these timings —
  out of scope here (that's a coverage/soundness question `certkit-ph1`
  already investigated from a different angle; this session only adds the
  raw wall-clock cost of running at that bandwidth, doesn't second-guess the
  cap).

## Handoff

- `bd close certkit-ryd` — investigation complete, documented, no unsafe
  changes made, tradeoff reaffirmed with real numbers replacing folklore.
- Files changed: `README.md` (new "Known limits" bullet, one prior bullet's
  wording untouched), `sandbox-handoffs/certkit-ryd-bench.py` (new),
  `sandbox-handoffs/certkit-ryd.md` (this file, new), `issues.jsonl` (bead
  claim + close, via `bd export`).
- Git policy: not committed, not pushed, per standing instructions. Suggested
  commands for a human:

  ```
  git add README.md sandbox-handoffs/certkit-ryd-bench.py \
          sandbox-handoffs/certkit-ryd.md issues.jsonl
  git commit -m "certkit-ryd: measure and document the pure-Python interval-loop cost"
  ```

  (Left `tests/exact_oracle.py`, `tests/test_exact_oracle.py`,
  `sandbox-handoffs/certkit-9oa.md`, and `sandbox-handoffs/certkit-kjy.md`
  out of that `git add` list deliberately — those are `certkit-9oa`'s
  in-progress work, not mine to stage or claim credit for.)
