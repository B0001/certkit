# Handoff: certkit-l7r (raise `DENSE_LIMIT` from 160 to 256)

## Outcome

**Done. `DENSE_LIMIT` raised from 160 to 256 in `certkit/operators.py:50`.**
Full test suite green (165 passed, unchanged from baseline). The trust
boundary (no third-party imports reachable from the checker) is unaffected —
verified by rerunning the checker in a subprocess with numpy/scipy blocked
from `sys.meta_path`, same output as before the change.

This closes the bead's own acceptance criteria: an n=256 (8-qubit)
JW-two-body-shaped Pauli sum now takes the `temple_inertia` route instead of
abstaining, the resulting enclosure is sound (contains the independently
computed true ground energy) and its width is ~10⁻¹¹ of the 1.6 mHa
chemical-accuracy bar, and runtime/memory for both a single beta and a
12-beta workload are measured below.

## What "H4" means here

There is no molecular-integral H4 fixture anywhere in this repo — every prior
ph1/487/bz5 session says so explicitly, and I did not build one either. The
bead's own evidence (`sandbox-handoffs/certkit-ph1.md` Result 10) uses "H4"
loosely to mean "n=256, the size an 8-qubit case needs", and separately
identifies the *shape* that matters for this bead as `jw_two_body` (JW-mapped
one- and two-body fermionic terms), not the TFIM shape the repo's existing
`tfim_hamiltonian` helper produces. I built a synthetic operator matching that
shape and size — real orbitals, one- and two-body JW-mapped terms, M=8
qubits, n=256 — rather than reuse `tfim_hamiltonian(8)`, so the test case here
is the one the bead's own justification is actually about.

Script: `sandbox-handoffs/certkit-l7r/build_h4_shaped.py`. It reuses the
from-scratch, numpy-free JW ladder-operator algebra written for certkit-ph1
session 5 (`sandbox-handoffs/certkit-ph1-jw-termcount-experiment.py`) — but
**not** that script's two-body loop verbatim: that loop only sums two
representative index orderings per canonical class, which counts terms fine
but does not actually produce a Hermitian operator (verified — diagonalizing
it directly gave `max|imag|=0.765`, nonzero odd-Y-string mass). Fixed by
canonicalizing each `(p,q,r,s)` quadruple together with its Hermitian-conjugate
partner `(r,s,p,q)` (assigning them the same random coefficient) and summing
over every ordered quadruple, not just two representatives — this is the
minimal fix that makes `h_pqrs = h_rspq` hold exactly, which is precisely
what makes `a_p^† a_q^† a_r a_s` and its own h.c. carry equal coefficients.
After the fix: `max|imag|=1.11e-16`, odd-Y mass `1.11e-16` (both machine
epsilon), 989 surviving real, even-Y-count terms. Independently verified
Hermitian and real via a from-scratch dense construction
(`dense_matrix_from_terms`, plain `numpy.kron`, not `certkit.operators` — this
is meant to check that code, so it deliberately doesn't reuse it).

The raw Hamiltonian's ground-state gap came out to 0.8507; I rescaled every
coefficient by a single constant (eigenvalues scale linearly under a uniform
rescale of a linear operator) to bring the gap to 1.46e-3, matching the figure
`certkit-ph1.md` Result 10 cites for its own H4 case. I could not find a
script under `sandbox-handoffs/certkit-ph1*` or `sandbox-handoffs/certkit-cpo`
that reproduces that session's exact 1.46e-3/5.40s/23MB numbers — they appear
to have been computed inline and not saved. I am **not** claiming to have
reproduced that session's exact case; I built my own, chose the same gap value
for continuity with the bead's citation, and measured it independently below.
Both `operator.json` (the encoded `pauli_sum_real` operator) and `truth.json`
(the independently-computed `lambda_0`, `lambda_1`, gap) are written to
`sandbox-handoffs/certkit-l7r/`.

## The verdict change

Before (`DENSE_LIMIT=160`, `sandbox-handoffs/certkit-l7r/run_before.py`
against the unmodified source):

```
DENSE_LIMIT = 160
operator n = 256, true gap = 1.460000e-03
verdict: ABSTAIN  rule=temple_inertia  time=0.32s
reason: backend 'pauli_sum_real' (n=256) will not materialise; inertia
counting unavailable -- use gershgorin_rayleigh, or reference a count
certificate with temple_ref
```

The only route that *does* apply at n=256 under the old limit is Gershgorin
(`certify_lambda_min_matrixfree`): VERIFIED, but width `0.0504`, i.e. ~31.5×
the 1.6 mHa chemical-accuracy bar — worse than the accuracy the bead exists to
reach, consistent with the README's documented "Gershgorin is a floor, not a
good bound."

After (`DENSE_LIMIT=256`, same script against the edited source):

```
DENSE_LIMIT = 256
operator n = 256, true gap = 1.460000e-03
verdict: VERIFIED  rule=temple_inertia  time=4.87s
enclosure: (-0.030044123523186292, -0.03004412352317654)  width=9.753e-15
```

Soundness check against the independently-computed truth (not `certkit` code,
see above): true `lambda_0 = -0.03004412352318148`, which lies inside
`[-0.030044123523186292, -0.03004412352317654]`. **Sound.**
`width / 1.6e-3 = 6.1e-12` — about eleven orders of magnitude tighter than
chemical accuracy requires, versus 31.5× *worse* than it via Gershgorin.

I also reconfirmed a case just above the new limit still correctly abstains
(n=512, `tfim_hamiltonian(9)`, `DENSE_LIMIT=256`):
`ABSTAIN: backend 'pauli_sum_real' (n=512) will not materialise` — the raise
does not silently extend past where it was measured.

## What I touched, and the derivation for each

**`certkit/operators.py:50` — `DENSE_LIMIT`, 160 → 256.** Derivation: this is
a pure runtime/memory budget choice, not a soundness-affecting bound (the
constant only gates whether `interval_rows()`/`dense_rows()` return data or
`None`; every rule downstream of a non-`None` return is exactly the same
inertia-counting code that already existed and is already exercised by the
existing test suite at smaller `n`). I picked 256, not some larger round
number, because that is exactly what the motivating 8-qubit case needs and no
more — I did not measure n=512 and the comment says so explicitly, so a
future session is not tempted to assume linear extrapolation holds. Measured
cost at n=256 (below) is seconds and single-digit megabytes, nowhere near the
"would take an hour" territory `DENSE_LIMIT` exists to keep the tight route
out of.

**`README.md`, "Known limits" section.** Updated the `DENSE_LIMIT` bullet with
the new value and the measurement backing it. Split the Gershgorin-fallback
bullet's "H4/N2-scale Hamiltonians" into "N2-scale Hamiltonians (n=4096,
still far past `DENSE_LIMIT`)" — the 100–1600× chemical-accuracy figure there
predates this bead, I did not re-derive it, and I have no basis to know how
much of that range came from H4 versus N2, so I left the number untouched and
only narrowed which case it still describes. Added that H4-scale (n=256) is
now covered by the same dense route as everything else, with the measured
width figure.

**`examples/banded_demo.py`** — one comment ("dense route stops at n = 160")
updated to 256 to match the new constant; no logic changed.

**`sandbox-prompt.md`** — one line updated (`DENSE_LIMIT = 160` → `256`) so
this file's quotation of the README stays accurate for future sessions; this
file is the standing-context template this very session's prompt was built
from, and leaving it stale would hand the next session a false fact about
current README content.

## What I did NOT touch, and why

- **Did not touch `checker.py`, `interval.py`, `schema.py`, `banded.py`, or
  `backward_error.py`.** Nothing in the trust boundary's actual logic needed
  to change — `DENSE_LIMIT` is the only knob this bead's evidence identified,
  and raising it exercises code paths (`count_eigenvalues_below`,
  `_rule_temple_inertia`) that already run today for smaller `n` and are
  already covered by the existing suite.
- **Did not implement the fill-reducing sparse LDL^T route** that
  `sandbox-handoffs/certkit-ph1.md` sessions 6/7 investigated. That was
  explicitly out of scope (the bead says "no new route needed") and Result 10
  explicitly recommends against it (a substantial new implementation for a
  further 232–336 raise, while n=4096 is still missed by ~45×). Nothing here
  changes that recommendation.
- **Did not raise `DENSE_LIMIT` past 256.** No case in this bead's scope
  needs more, and I have no measurement past n=256 to justify a larger value
  — the comment in `operators.py` says this explicitly so a future session
  doesn't assume the cost scales the same way past this point (it's cubic; it
  does not).
- **Did not build a real quantum-chemistry (basis-set, actual H4 molecule)
  fixture.** Same limitation every prior ph1/487/bz5 session flagged; a real
  bridge to a chemistry package is out of scope for a `DENSE_LIMIT` bead.
- **Did not touch the 100–1600× N2-scale Gershgorin figure in the README.**
  I could not find its derivation script to re-verify it, and re-deriving it
  is out of this bead's scope (it concerns n=4096, not n=256). I only
  narrowed the sentence's scope to the case it still applies to.

## Runtime and memory at n=256, several-beta usage

The bead's acceptance criteria explicitly asks for this "not just one beta."
Measured in `sandbox-handoffs/certkit-l7r/measure.py` (DENSE_LIMIT patched to
256 in-process, same code path as the real source change):

```
single-beta certify+check: verdict=VERIFIED rule=temple_inertia time=4.77s peak_rss=47.0MB
  enclosure=[-0.030044123523186292, -0.03004412352317654]  width=9.753e-15
  sound: True
  width vs 1.6e-3 chemical accuracy: 6.095e-12x

12-beta count_eigenvalues_below batch: total_time=51.20s (4.267s/beta) peak_rss=47.0MB
  counts: [ABSTAIN(pivot 248 straddles), 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, ABSTAIN(pivot 252 straddles)]
```

The dense inertia route does not reuse any factorisation across betas — each
beta re-forms `A - beta*I` and re-runs the full O(n³) interval LDL^T from
scratch — so cost is linear in the number of betas queried: ~4.27s/beta
across the 12-beta sweep, matching the single-beta figure. **This is the
honest cost model to plan around for any caller that queries several betas at
n≈256, not just the best case.** The 2 abstentions are both at betas placed
deep in the spectral bulk (endpoints of a uniform 12-point grid spanning
`[lambda_0, lambda_1]`, which for a dense n=256 spectrum lands most of the
grid inside the bulk, not at the ground-state gap) — correctly refusing
where the true local gap is below interval resolution, the same "correct
abstention, not a defect" finding `certkit-ph1.md` Result 9 made at n=512.

Peak-RSS (`resource.getrusage`, whole-process, includes Python/numpy import
baseline) was 47.0MB for both the single-beta and 12-beta runs — the dense
`n×n` interval matrix (`Iv` pairs of floats, `n=256` → ~2MB of raw floats,
more with Python object/interval overhead) is not the dominant cost against
interpreter/numpy baseline at this scale. A tighter, traced-only measurement
(`sandbox-handoffs/certkit-l7r/measure_memory.py`, `tracemalloc`, isolating
just `interval_rows()` + one `count_eigenvalues_below` call from process
baseline) gives **9.18MB** for a single beta — this is the number to trust
for "how much memory does the dense route itself need at n=256," separate
from whatever else is resident in the process.

These numbers (4.8s/9-47MB) are in the same ballpark as, but not identical
to, `certkit-ph1.md`'s cited 5.40s/23MB — expected, since that was a
different operator instance (I could not find its generating script to
reproduce it exactly; see above) and I'm reporting memory two different ways.
Both figures land in "seconds, single-digit-to-tens of megabytes," which is
what matters for the "not an hour" bar `DENSE_LIMIT` exists to enforce.

## What I could not verify

- The exact `sandbox-handoffs/certkit-ph1.md` Result 10 case (its own
  1.46e-3-gap, 5.40s, 23MB H4 measurement) — no backing script was found
  under `sandbox-handoffs/`, so I could not rerun it directly. I built an
  independent case targeting the same cited gap value instead, and it
  corroborates the qualitative claim (seconds, sound, chemical-accuracy width)
  even though the exact numbers differ.
- Whether n between 257 and 511 would also comfortably fit the "seconds, not
  hours" budget. Plausible by cubic scaling from the n=256 figure (n=384
  would be ~1.35³≈2.5× slower, i.e. still seconds), but not measured, and the
  `operators.py` comment says so rather than implying it.
- The provenance of the README's pre-existing "100–1600× chemical accuracy on
  H4/N2-scale Hamiltonians" figure — re-scoped its wording to N2 only, did
  not re-derive the number itself.

## Test suite / trust boundary

```
$ uv sync --extra dev
 + certkit==0.1.0 (from file:///workspace)
 + numpy==2.5.2, scipy==1.18.1 ... (8 packages total)
$ uv run pytest tests
============================= 165 passed in 22.56s =============================
```

(Baseline before any change, same command: `165 passed in 23.27s` — no
regressions, no new failures, timing difference is noise.)

No system `python3` exists in this container outside the uv-managed venv
(same as every prior session). Fallback: block numpy/scipy via
`sys.meta_path` in a subprocess (`uv run --no-project python3`), then invoke
`certkit.cli.main` exactly as the documented no-dependency command would:

```
VERIFIED  lambda_min_enclosure via temple_inertia  [-3.095316431033709, -3.0953164248430762]
  re-derived: [-3.0953164279384016, -3.095316427938384]
```

Identical to every prior session's reconfirmation of this fixture — expected,
since `DENSE_LIMIT` does not affect the small (n=6) sample operator, and the
trust boundary itself was not touched.

## Working tree

```
$ git status --short
 M README.md
 M certkit/operators.py
 M examples/banded_demo.py
 M sandbox-prompt.md
?? sandbox-handoffs/certkit-l7r/
```

`sandbox-handoffs/certkit-l7r/` contains: `build_h4_shaped.py`,
`run_before.py`, `measure.py`, `measure_memory.py` (all scratch, rerunnable),
plus their outputs `operator.json` and `truth.json`.

## Suggested next commands (none run — git policy)

```
git add certkit/operators.py README.md examples/banded_demo.py \
        sandbox-prompt.md sandbox-handoffs/certkit-l7r/ \
        sandbox-handoffs/certkit-l7r.md issues.jsonl
git commit -m "certkit-l7r: raise DENSE_LIMIT 160 -> 256, reaches n=256 chemistry-shaped case with existing dense route"
```

## bd state

`certkit-l7r` claimed, work complete against its acceptance criteria, closing
with this handoff as the evidence record. `bd export -o issues.jsonl` run
since the bead's notes/status changed meaningfully.
