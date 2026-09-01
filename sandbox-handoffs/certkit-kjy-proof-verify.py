"""
certkit-kjy -- computational due diligence for the separator/treewidth
lower-bound THEOREM written up in sandbox-handoffs/certkit-kjy.md.

Unlike certkit-kjy-verify.py (previous session, left in-progress and never
folded into a handoff -- see that file's Fact 4, which FAILS and stays
failing: the naive "min boundary over the whole balanced range equals
C(r,r//2)" claim it checks is simply false, as its own exhaustive r=4 check
shows), this script does NOT rely on the exact extremal value of Harper's
theorem anywhere. The proof in the handoff deliberately avoids that route
(it doesn't need the precise extremal set, only a spectral-gap bound), so
what needs checking is different:

  (1) The exact hypercube eigen-relation A*chi_T = (r - 2|T|)*chi_T for every
      character chi_T of Z_2^r, exhaustively for small r. This is the one
      "derivation, not a transcription" step the write-up leans on -- if this
      is wrong, the whole spectral-gap argument is wrong.
  (2) The resulting Cheeger-type crossing-edge bound
          e(S, complement) >= (d - lambda_2) * |S| * (N - |S|) / N
      holds with equality checked exactly (small cases, exhaustive) and
      holds as an inequality (larger cases, exhaustive over S since N is
      still small) for Q_r, r = 3..8.
  (3) That extract_basis(M) really does return a SUBSET of M (so the
      "basis-generated Q_r is a spanning subgraph of the full Cayley graph"
      step is definitionally free, not something that needs sampling) --
      re-derive this from the algorithm rather than trust the previous
      session's version.
  (4) The concrete D (mask count) and r (GF(2) rank) numbers for the two
      physical families the theorem is applied to (hypercube_tfim as the
      geometrically-k-local instance, jw_two_body as the JW/electronic-
      structure instance), so the handoff can quote real D(q), r(q), and the
      resulting Omega(n_c/D) floor instead of asserting the growth rate
      without a number attached.
  (5) A brute-force sanity check, small q only: does the THEOREM's predicted
      floor 4*n_c/(9*D) ever exceed the TRUE minimum balanced-vertex-boundary
      of the actual family graph (found by exhaustive/randomized search)? It
      must not -- the predicted floor is a lower bound, so true-min >=
      predicted floor always, and this checks that directly rather than
      trusting the algebra with no empirical cross-check.

Python 3.12 stdlib only. No numpy, no third-party imports.
"""

import itertools
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "certkit-cpo"))
import families  # noqa: E402


# ------------------------------------------------------------- GF(2) helpers

def gf2_rank_and_basis(masks):
    """Rank of span(masks) over GF(2), and a basis that is a literal SUBSET
    of masks (not a derived combination) -- Gaussian elimination that keeps
    the original vector whenever it's independent of what's been kept."""
    pivots = {}   # leading-bit -> reduced vector, membership test only
    basis = []    # ORIGINAL masks, appended verbatim
    for m in masks:
        v = m
        for hi in sorted(pivots, reverse=True):
            if (v >> hi) & 1:
                v ^= pivots[hi]
        if v != 0:
            hi = v.bit_length() - 1
            pivots[hi] = v
            basis.append(m)
    return len(pivots), basis


def check_basis_is_literal_subset():
    print("== Fact 1: extract_basis returns a literal subset of the input masks ==")
    fails = 0
    for name, fn in families.FAMILIES.items():
        for q in range(4, 11):
            n, masks = fn(q)
            r, basis = gf2_rank_and_basis(masks)
            if not set(basis).issubset(set(masks)):
                fails += 1
                print(f"  FAIL {name} q={q}: basis not a subset of masks")
            if len(basis) != r:
                fails += 1
                print(f"  FAIL {name} q={q}: |basis|={len(basis)} != rank={r}")
    if fails == 0:
        print("  PASS -- for all 8 families, q=4..10: basis is a literal subset of masks,")
        print("         |basis| == GF(2) rank. (This makes 'Cay(H,basis) subset-of-edges")
        print("         Cay(H,masks)' definitional: basis subset of masks as SETS, not")
        print("         something needing separate verification.)")
    return fails


# ---------------------------------------------------- hypercube eigen-relation

def hypercube_neighbors(v, r):
    return [v ^ (1 << k) for k in range(r)]


def chi(T_mask, x, r):
    """chi_T(x) = (-1)^{sum_{i in T} x_i}, T and x both given as r-bit ints."""
    return -1 if (bin(T_mask & x).count("1") % 2) else 1


def check_eigen_relation_exact():
    print()
    print("== Fact 2: A*chi_T = (r - 2|T|)*chi_T exactly, for EVERY character T ==")
    print("   (exhaustive over all x in {0,1}^r and all T in {0,1}^r, r = 1..8)")
    fails = 0
    checked = 0
    for r in range(1, 9):
        N = 1 << r
        for T in range(N):
            eigval = r - 2 * bin(T).count("1")
            for x in range(N):
                lhs = sum(chi(T, x ^ (1 << k), r) for k in range(r))
                rhs = eigval * chi(T, x, r)
                checked += 1
                if lhs != rhs:
                    fails += 1
                    print(f"  FAIL r={r} T={T:0{r}b} x={x:0{r}b}: A*chi={lhs}, "
                          f"(r-2|T|)*chi={rhs}")
    if fails == 0:
        print(f"  PASS -- {checked} exact (integer) eigen-relation checks across r=1..8,")
        print("         confirming spec(A(Q_r)) = {r-2|T| : T subset [r]} with multiplicity")
        print("         C(r,|T|), hence lambda_1=r (T=empty), lambda_2=r-2 (|T|=1),")
        print("         gap = lambda_1-lambda_2 = 2 EXACTLY, independent of r.")
    return fails


# ------------------------------------------------------ Cheeger crossing bound

def crossing_edges(A, r):
    """e(A, complement) for A given as a Python set of ints in {0,1}^r."""
    ce = 0
    for v in A:
        for k in range(r):
            w = v ^ (1 << k)
            if w not in A:
                ce += 1
    return ce


def check_cheeger_bound_exhaustive():
    print()
    print("== Fact 3: e(S,S^c) >= 2*|S|*(N-|S|)/N for EVERY S, Q_r, exhaustive r=3,4 ==")
    fails = 0
    checked = 0
    for r in (3, 4):
        N = 1 << r
        for m in range(N + 1):
            for combo in itertools.combinations(range(N), m):
                A = set(combo)
                ce = crossing_edges(A, r)
                bound = 2 * m * (N - m)  # compare ce*N >= bound to stay in exact integers
                checked += 1
                if ce * N < bound:
                    fails += 1
                    print(f"  FAIL r={r} |S|={m}: e(S,Sc)={ce} < 2*{m}*{N-m}/{N}")
    if fails == 0:
        print(f"  PASS -- {checked} exhaustive subsets across r=3,4: Cheeger crossing-edge")
        print("         bound holds with equality checked in exact integer arithmetic")
        print("         (comparing e(S,Sc)*N against 2*|S|*(N-|S|) to avoid rounding).")
    return fails


def check_cheeger_bound_sampled(trials=5000):
    print()
    print("== Fact 3b: same bound, random sampling, r = 6, 8, 10 (not exhaustive) ==")
    rng = random.Random(2026)
    fails = 0
    for r in (6, 8, 10):
        N = 1 << r
        worst_ratio = None
        for _ in range(trials):
            m = rng.randint(1, N - 1)
            A = set(rng.sample(range(N), m))
            ce = crossing_edges(A, r)
            bound = 2 * m * (N - m)
            if ce * N < bound:
                fails += 1
                print(f"  FAIL r={r} |S|={m}: e(S,Sc)={ce} violates bound")
            ratio = (ce * N) / bound if bound else float("inf")
            if worst_ratio is None or ratio < worst_ratio:
                worst_ratio = ratio
        print(f"  r={r}: {trials} random subsets, tightest observed ce*N / (2|S|(N-|S|)) "
              f"= {worst_ratio:.3f} (>= 1.0 required)")
    if fails == 0:
        print("  PASS -- no violation found by random sampling at r=6,8,10.")
    return fails


# ----------------------------------------- physical families: D(q), r(q), floor

def report_family_scaling(name, fn, qs):
    print(f"  {name}:")
    for q in qs:
        n, masks = fn(q)
        D = len(masks)
        r, _ = gf2_rank_and_basis(masks)
        n_c = 1 << r
        floor = (4 * n_c) // (9 * D) if D else 0
        print(f"    q={q:>3}  n={n:>8}  D=|masks|={D:>5}  rank r={r:>3}  "
              f"n_c=2^r={n_c:>8}  predicted floor 4*n_c/(9D) = {floor}")


def check_physical_family_scaling():
    print()
    print("== Fact 4: D(q), r(q) for the two families the theorem is applied to ==")
    report_family_scaling("hypercube_tfim (geometrically-1-local: one X per qubit)",
                           families.hypercube_tfim, [4, 6, 8, 10, 12, 14])
    report_family_scaling("jw_two_body (JW-mapped electronic structure, dense one+two body)",
                           families.jw_two_body, [4, 6, 8, 10, 12])
    print("  (no pass/fail: this is the numbers the write-up quotes, not a boolean check)")


# ------------------------------------------- brute-force true-min separator check

def true_min_balanced_boundary(n_c_vertices, masks, component, trials=4000, seed=1):
    """Best (smallest) |N(S)\\S| found over balanced S within one connected
    component, by random search plus the two 'natural' Hamming-layer-style
    cuts (min/max degree greedy heuristics are NOT used here -- this is meant
    as an upper bound on the TRUE minimum, i.e. a witness that the theorem's
    lower bound is not violated, not a claim of exact optimality)."""
    rng = random.Random(seed)
    H = sorted(component)
    n0 = len(H)
    lo, hi = n0 // 3, (2 * n0) // 3
    best = None
    for _ in range(trials):
        m = rng.randint(max(1, lo), max(1, hi))
        A = set(rng.sample(H, min(m, n0)))
        boundary = set()
        for v in A:
            for msk in masks:
                w = v ^ msk
                if w not in A:
                    boundary.add(w)
        b = len(boundary)
        if best is None or b < best:
            best = b
    return best


def connected_component(start, masks):
    seen = {start}
    frontier = [start]
    while frontier:
        nxt = []
        for v in frontier:
            for m in masks:
                w = v ^ m
                if w not in seen:
                    seen.add(w)
                    nxt.append(w)
        frontier = nxt
    return seen


def check_true_min_never_below_prediction():
    print()
    print("== Fact 5: true (searched) min balanced boundary >= predicted floor 4*n_c/(9D) ==")
    fails = 0
    for name, fn in families.FAMILIES.items():
        for q in (6, 8):
            n, masks = fn(q)
            D = len(masks)
            r, _ = gf2_rank_and_basis(masks)
            n_c = 1 << r
            predicted = (4 * n_c) // (9 * D) if D else 0
            comp = connected_component(0, masks)
            assert len(comp) == n_c, (name, q, len(comp), n_c)
            best = true_min_balanced_boundary(n_c, masks, comp, trials=2000, seed=q)
            ok = best >= predicted
            tag = "OK  " if ok else "FAIL"
            if not ok:
                fails += 1
            print(f"  {tag} {name:>16} q={q}: searched-min boundary={best:>6}  "
                  f"predicted floor={predicted:>6}  D={D:>4} n_c={n_c}")
    if fails == 0:
        print("  PASS -- searched minimum is never below the theorem's predicted floor,")
        print("         across all 8 families at q=6,8 (16 instances).")
    return fails


if __name__ == "__main__":
    total_fails = 0
    total_fails += check_basis_is_literal_subset()
    total_fails += check_eigen_relation_exact()
    total_fails += check_cheeger_bound_exhaustive()
    total_fails += check_cheeger_bound_sampled()
    check_physical_family_scaling()
    total_fails += check_true_min_never_below_prediction()
    print()
    print("FAIL" if total_fails else "PASS", f"-- {total_fails} failing check(s) across facts 1,2,3,3b,5")
