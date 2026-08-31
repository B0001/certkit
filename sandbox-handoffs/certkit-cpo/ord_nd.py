"""Nested-dissection elimination ordering for certkit-cpo.

Contract (see harness.py):
    NAME
    order(n, masks, time_budget_s=120.0) -> permutation of range(n)

The ordering is pure ND: partition the current vertex subset into A | S | B
with S a genuine vertex separator, order A, then B, then S LAST.

Two partitioners:
  (a) exact Hamming-layer cut, used only when the current subset is the whole
      hypercube and the masks are exactly the single-bit generators (the
      precondition is verified, never assumed);
  (b) generic BFS level-set separator from a pseudo-peripheral vertex, plus a
      greedy shrink of the separator, used everywhere else. Disconnected
      subgraphs are split component-wise with an empty separator.

ponytail: no METIS-style multilevel FM refinement -- BFS level sets + greedy
shrink is the standard fallback partitioner; add multilevel only if the grid
positive control's fitted exponent stops being ~1.5.
"""

import math
import time

NAME = "nested dissection"

LEAF = 32  # subsets this small are emitted directly


# ---------------------------------------------------------------- graph utils

def build_adj_local(n, masks):
    """Cayley graph adjacency (same as harness.build_adj; local copy so this
    module is importable standalone)."""
    ms = sorted({m for m in masks if m})
    adj = [set() for _ in range(n)]
    for i in range(n):
        for m in ms:
            adj[i].add(i ^ m)
        adj[i].discard(i)
    return adj


def validate_separator(adj, sub, A, S, B):
    """True iff (A, S, B) partitions `sub` and no edge of the induced subgraph
    joins A to B. Raises AssertionError with a specific message otherwise."""
    A, S, B = set(A), set(S), set(B)
    assert A | S | B == set(sub), "A|S|B does not cover sub"
    assert len(A) + len(S) + len(B) == len(sub), "A/S/B overlap"
    for v in A:
        for u in adj[v]:
            assert u not in B, f"edge {v}-{u} crosses A|B with S removed"
    return True


def _components(adj, sub):
    seen = set()
    comps = []
    for start in sub:
        if start in seen:
            continue
        comp = [start]
        seen.add(start)
        stack = [start]
        while stack:
            v = stack.pop()
            for u in adj[v]:
                if u in sub and u not in seen:
                    seen.add(u)
                    comp.append(u)
                    stack.append(u)
        comps.append(comp)
    return comps


def _bfs_levels(adj, sub, root):
    levels = [[root]]
    seen = {root}
    while True:
        nxt = []
        for v in levels[-1]:
            for u in adj[v]:
                if u in sub and u not in seen:
                    seen.add(u)
                    nxt.append(u)
        if not nxt:
            break
        levels.append(nxt)
    return levels


def _pseudo_peripheral(adj, sub, rounds=3):
    root = min(sub)
    levels = _bfs_levels(adj, sub, root)
    for _ in range(rounds):
        cand = min(levels[-1], key=lambda v: len({u for u in adj[v] if u in sub}))
        new = _bfs_levels(adj, sub, cand)
        if len(new) <= len(levels):
            break
        root, levels = cand, new
    return root, levels


# ------------------------------------------------------------- partitioners

def _generic_separator(adj, sub):
    """BFS level-set separator with greedy shrink. Returns (A, S, B) as sets,
    or None if no non-trivial split was found (caller should bottom out)."""
    sub = set(sub)
    comps = _components(adj, sub)
    if len(comps) > 1:
        # No separator needed: pack components largest-first into two sides.
        A, B = set(), set()
        for comp in sorted(comps, key=len, reverse=True):
            (A if len(A) <= len(B) else B).update(comp)
        if A and B:
            return A, set(), B

    root, levels = _pseudo_peripheral(adj, comps[0] if len(comps) == 1 else sub)
    if len(comps) > 1:  # only the first component got levelled; give up here
        return None
    if len(levels) < 3:
        return None

    sizes = [len(l) for l in levels]
    total = len(sub)
    best = None
    for k in range(1, len(levels) - 1):
        a = sum(sizes[:k])
        b = sum(sizes[k + 1:])
        # prefer small separators, then balance
        score = (sizes[k] + max(a, b), max(a, b))
        if max(a, b) > 0.85 * total:
            score = (score[0] + total, score[1])
        if best is None or score < best[0]:
            best = (score, k)
    k = best[1]
    A = set().union(*levels[:k])
    S = set(levels[k])
    B = set().union(*levels[k + 1:])

    # Greedy shrink: a separator vertex with no neighbour on one side can join
    # the other side. Checked against the live sets, so moves stay consistent.
    for v in sorted(S):
        nb = [u for u in adj[v] if u in sub]
        if not any(u in B for u in nb):
            S.discard(v)
            A.add(v)
        elif not any(u in A for u in nb):
            S.discard(v)
            B.add(v)
    if not A or not B:
        return None
    return A, S, B


def _hypercube_layer_separator(q, sub):
    """Exact middle-layer cut of the full hypercube Q_q (session-6 Result 1)."""
    L = q // 2
    A, S, B = set(), set(), set()
    for v in sub:
        w = v.bit_count()
        (A if w < L else (S if w == L else B)).add(v)
    return A, S, B


# ------------------------------------------------------------------ ordering

def order_from_adj(adj, sub=None, time_budget_s=120.0, validate=False,
                   exact_hypercube_q=None):
    """Nested-dissection order over the graph `adj`, restricted to `sub`.

    exact_hypercube_q: if not None, `sub` is the full vertex set of Q_q and the
    exact Hamming-layer cut is used at the top level (precondition checked by
    the caller).
    """
    if sub is None:
        sub = set(range(len(adj)))
    else:
        sub = set(sub)
    deadline = time.time() + time_budget_s
    perm = []
    stack = [("split", sub, exact_hypercube_q)]
    while stack:
        kind, payload, hq = stack.pop()
        if kind == "emit":
            perm.extend(payload)
            continue
        cur = payload
        if len(cur) <= LEAF or time.time() > deadline:
            perm.extend(sorted(cur))
            continue
        if hq is not None:
            A, S, B = _hypercube_layer_separator(hq, cur)
            if not A or not B:  # q <= 1; nothing to dissect
                perm.extend(sorted(cur))
                continue
        else:
            part = _generic_separator(adj, cur)
            if part is None:
                perm.extend(sorted(cur))
                continue
            A, S, B = part
        if validate:
            validate_separator(adj, cur, A, S, B)
        # popped LIFO: A first, then B, separator LAST
        stack.append(("emit", sorted(S), None))
        stack.append(("split", B, None))
        stack.append(("split", A, None))
    return perm


def order(n, masks, time_budget_s=120.0, validate=False):
    adj = build_adj_local(n, masks)
    ms = {m for m in masks if m}
    q = n.bit_length() - 1
    hq = None
    if (1 << q) == n and ms == {1 << k for k in range(q)}:
        hq = q  # genuine hypercube: exact middle-layer cut applies
    perm = order_from_adj(adj, None, time_budget_s, validate, hq)
    assert sorted(perm) == list(range(n)), "not a permutation"
    return perm


# ----------------------------------------------------------------- self-check

def _eliminate_adj(adj_in, perm, time_budget_s=300.0):
    """Symbolic LDL^T in the fixed order `perm`; same accounting as
    harness.eliminate_with_perm / session-6 min_degree_fill, but takes
    adjacency directly (needed for the grid positive control, which is not
    expressible as a mask set)."""
    adj = [set(s) for s in adj_in]
    remaining = set(range(len(adj)))
    total_fill = total_ops = max_deg = steps = 0
    t0 = time.time()
    for v in perm:
        if time.time() - t0 > time_budget_s:
            return total_fill, total_ops, max_deg, False, steps
        nbrs = [u for u in adj[v] if u in remaining]
        d = len(nbrs)
        max_deg = max(max_deg, d)
        total_ops += d * d
        for i in range(d):
            a = nbrs[i]
            for j in range(i + 1, d):
                b = nbrs[j]
                if b not in adj[a]:
                    adj[a].add(b)
                    adj[b].add(a)
                    total_fill += 1
        for u in nbrs:
            adj[u].discard(v)
        remaining.discard(v)
        steps += 1
    return total_fill, total_ops, max_deg, True, steps


def _grid_adj(r, c):
    n = r * c
    adj = [set() for _ in range(n)]
    for i in range(r):
        for j in range(c):
            v = i * c + j
            if i + 1 < r:
                u = v + c
                adj[v].add(u)
                adj[u].add(v)
            if j + 1 < c:
                u = v + 1
                adj[v].add(u)
                adj[u].add(v)
    return adj


def _lattice2d_masks(qx, qy):
    """2D-lattice-shaped mask family: single-qubit X on a qx*qy qubit lattice
    (the mask set is still the single-bit generators, so add 2-qubit XX masks
    on lattice bonds to make it a non-hypercube Cayley graph)."""
    masks = set()
    for x in range(qx):
        for y in range(qy):
            k = x * qy + y
            masks.add(1 << k)
            if x + 1 < qx:
                masks.add((1 << k) | (1 << ((x + 1) * qy + y)))
            if y + 1 < qy:
                masks.add((1 << k) | (1 << (x * qy + y + 1)))
    return sorted(masks)


def _fit_exponent(ns, ys):
    lx = [math.log(v) for v in ns]
    ly = [math.log(v) for v in ys]
    mx = sum(lx) / len(lx)
    my = sum(ly) / len(ly)
    num = sum((a - mx) * (b - my) for a, b in zip(lx, ly))
    den = sum((a - mx) ** 2 for a in lx)
    return num / den


if __name__ == "__main__":
    try:
        import harness
        elim = harness.eliminate_with_perm
    except ImportError:
        harness = None
        elim = None

    ok = True

    print("=== 1. permutation validity ===")
    cases = [(16, [1, 2, 4, 8]), (64, [1, 2, 4, 8, 16, 32]),
             (256, [1, 2, 4, 8, 16, 32, 64, 128]),
             (256, _lattice2d_masks(4, 2)), (128, [1, 3, 6, 12, 24, 48, 96])]
    for n, masks in cases:
        p = order(n, masks, time_budget_s=60.0)
        good = sorted(p) == list(range(n))
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'} n={n:>5} |masks|={len(masks):>3} perm ok")

    print()
    print("=== 2. validate_separator at every recursion level (debug mode) ===")
    for q in range(4, 9):
        n = 1 << q
        try:
            order(n, [1 << k for k in range(q)], time_budget_s=60.0, validate=True)
            print(f"  PASS hypercube q={q} (n={n}) all separators genuine")
        except AssertionError as e:
            ok = False
            print(f"  FAIL hypercube q={q}: {e}")
    for (qx, qy) in [(3, 2), (4, 2), (3, 3)]:
        masks = _lattice2d_masks(qx, qy)
        n = 1 << (qx * qy)
        try:
            order(n, masks, time_budget_s=60.0, validate=True)
            print(f"  PASS lattice2d {qx}x{qy} (n={n}, |masks|={len(masks)}) all separators genuine")
        except AssertionError as e:
            ok = False
            print(f"  FAIL lattice2d {qx}x{qy}: {e}")

    print()
    print("=== 3. POSITIVE CONTROL: 2D grid, ND must be sub-cubic ===")
    print(f"  {'grid':>9} {'n':>6} {'fill':>10} {'ops':>12} {'max_deg':>8}")
    GRIDS = [12, 17, 24, 34]
    ns, opss, sepfirst_ops, natural_ops = [], [], [], []
    for k in GRIDS:
        adj = _grid_adj(k, k)
        n = k * k
        perm = order_from_adj(adj, None, time_budget_s=60.0, validate=True)
        assert sorted(perm) == list(range(n))
        fill, ops, maxd, done, _ = _eliminate_adj(adj, perm)
        assert done
        ns.append(n)
        opss.append(ops)
        print(f"  {k:>4}x{k:<4} {n:>6} {fill:>10} {ops:>12} {maxd:>8}")
    expo = _fit_exponent(ns, opss)
    # Gate at 1.8, not 2.2: measured, a deliberately broken ND that emits the
    # separator FIRST scores 2.05 on this grid, and so does the plain banded
    # natural order -- a 2.2 gate accepts both and only rejects a random order.
    good = expo < 1.8
    ok &= good
    print(f"  fitted ops exponent over {len(ns)} doublings: {expo:.3f} "
          f"({'PASS' if good else 'FAIL'} < 1.8; theory ~1.5)")

    print()
    print("=== 3b. NEGATIVE CONTROLS: the gate above must reject broken orders ===")
    for k in GRIDS:
        adj = _grid_adj(k, k)
        n = k * k
        # (i) separator emitted FIRST instead of last -- the classic ND bug.
        p, stack = [], [set(range(n))]
        while stack:
            cur = stack.pop()
            part = None if len(cur) <= LEAF else _generic_separator(adj, cur)
            if part is None:
                p.extend(sorted(cur))
                continue
            A, S, B = part
            p.extend(sorted(S))
            stack.append(B)
            stack.append(A)
        assert sorted(p) == list(range(n))
        sepfirst_ops.append(_eliminate_adj(adj, p)[1])
        # (ii) plain natural (banded) order.
        natural_ops.append(_eliminate_adj(adj, list(range(n)))[1])
    for label, ys in (("separator-FIRST", sepfirst_ops), ("natural order", natural_ops)):
        e = _fit_exponent(ns, ys)
        rejected = e >= 1.8
        ok &= rejected
        print(f"  {label:>16}: exponent {e:.3f} "
              f"({'PASS' if rejected else 'FAIL'} -- must be >= 1.8 or the "
              f"positive control is vacuous)")

    print()
    print("=== 4. generic partitioner vs exact middle-layer cut, hypercube ===")
    print(f"  {'q':>3} {'n':>6} {'generic |S|':>12} {'C(q,q//2)':>11} {'ratio':>7} {'balance':>16}")
    for q in range(6, 13):
        n = 1 << q
        adj = build_adj_local(n, [1 << k for k in range(q)])
        part = _generic_separator(adj, set(range(n)))
        exact = math.comb(q, q // 2)
        if part is None:
            print(f"  {q:>3} {n:>6} {'(none)':>12} {exact:>11}")
            continue
        A, S, B = part
        validate_separator(adj, set(range(n)), A, S, B)
        print(f"  {q:>3} {n:>6} {len(S):>12} {exact:>11} {len(S) / exact:>7.2f}"
              f" {f'{len(A)}/{len(B)}':>16}")

    print()
    if harness is not None:
        # Every q, not just the even ones: ops/n^3 is NON-monotone
        # (0.064/0.046/0.036/0.045/0.020/0.019/0.032 for q=6..12), so the
        # even-q subsequence alone reads as a spurious steady decrease.
        print("=== harness present: hypercube ND elimination ===")
        for q in [6, 7, 8, 9, 10, 11]:
            n = 1 << q
            masks = [1 << k for k in range(q)]
            perm = order(n, masks, time_budget_s=60.0)
            fill, ops, maxd, done, steps = elim(n, masks, perm, time_budget_s=120.0)
            print(f"  q={q} n={n} fill={fill} ops={ops} ops/n^3={ops / n ** 3:.5f} "
                  f"max_deg={maxd} complete={done}")
        print()
    print("ALL PASS" if ok else "SOME FAIL")
