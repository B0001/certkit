"""Reverse Cuthill-McKee ordering module for the certkit-cpo fill-reducing harness.

Contract: NAME, order(n, masks, time_budget_s=120.0) -> permutation of range(n).

NOTE FOR THE NEXT READER: on a Cayley graph over Z_2^q (which is what every
mask-generated sparsity graph here is) the graph is vertex-transitive -- every
vertex has the same degree and the same eccentricity -- so the George-Liu
pseudo-peripheral search terminates almost immediately and effectively just
returns the first candidate. That is CORRECT, not a bug; do not "fix" it. The
heuristic is kept because the module is also exercised on non-Cayley graphs
(see the path-graph self-check) where it does real work.

Python 3.12 stdlib only.
"""
import time

NAME = "rcm"


def _build_adj(n, masks):
    ms = {m for m in masks if m}
    adj = [set() for _ in range(n)]
    for i in range(n):
        for m in ms:
            adj[i].add(i ^ m)
        adj[i].discard(i)
    return adj


def _bfs_levels(adj, start, seen_global):
    """BFS from start over vertices not in seen_global.

    Returns (order_visited, last_level) where order_visited is the component's
    vertices in BFS order with each level's neighbours taken in increasing
    (degree, index) order, and last_level is the final BFS level.
    """
    visited = {start}
    order_visited = [start]
    level = [start]
    while True:
        nxt = []
        for v in level:
            cand = [u for u in adj[v] if u not in visited and u not in seen_global]
            cand.sort(key=lambda u: (len(adj[u]), u))
            for u in cand:
                visited.add(u)
                nxt.append(u)
        if not nxt:
            return order_visited, level, visited
        order_visited.extend(nxt)
        level = nxt


def _pseudo_peripheral(adj, comp_seed, seen_global, deadline):
    """George-Liu: BFS, jump to a min-degree vertex of the last level, repeat
    while the eccentricity (number of levels - 1) strictly increases."""
    v = comp_seed
    _, last, _ = _bfs_levels(adj, v, seen_global)
    # eccentricity proxy: rerun and count levels
    ecc = _ecc(adj, v, seen_global)
    while True:
        if time.time() > deadline:
            return v
        w = min(last, key=lambda u: (len(adj[u]), u))
        ecc_w = _ecc(adj, w, seen_global)
        if ecc_w <= ecc:
            return v
        v, ecc = w, ecc_w
        _, last, _ = _bfs_levels(adj, v, seen_global)


def _ecc(adj, start, seen_global):
    visited = {start}
    level = [start]
    depth = 0
    while True:
        nxt = []
        for v in level:
            for u in adj[v]:
                if u not in visited and u not in seen_global:
                    visited.add(u)
                    nxt.append(u)
        if not nxt:
            return depth
        depth += 1
        level = nxt


def order_from_adj(adj, time_budget_s=120.0):
    """RCM on an explicit adjacency list (module-private helper, also used to
    test on non-Cayley graphs such as a path)."""
    n = len(adj)
    deadline = time.time() + time_budget_s
    seen = set()
    seq = []
    # Components in increasing (degree, index) order of their seed, so the
    # result is deterministic and independent of dict/set iteration order.
    for s in sorted(range(n), key=lambda u: (len(adj[u]), u)):
        if s in seen:
            continue
        start = _pseudo_peripheral(adj, s, seen, deadline)
        comp, _, visited = _bfs_levels(adj, start, seen)
        seq.extend(comp)
        seen |= visited
    seq.reverse()
    return seq


def order(n, masks, time_budget_s=120.0):
    return order_from_adj(_build_adj(n, masks), time_budget_s)


# --------------------------------------------------------------------------
if __name__ == "__main__":
    ok = True

    def check(label, cond):
        global ok
        ok = ok and bool(cond)
        print(("PASS  " if cond else "FAIL  ") + label)

    def bandwidth(adj, perm):
        pos = {v: i for i, v in enumerate(perm)}
        return max((abs(pos[i] - pos[j]) for i in range(len(adj)) for j in adj[i]), default=0)

    # 1. valid permutations for several (n, masks)
    for q, masks in [(3, [1, 2, 4]), (4, [1, 2, 4, 8]), (6, [1 << k for k in range(6)]),
                     (5, [1, 3, 6, 12]), (4, [5, 10])]:
        n = 1 << q
        p = order(n, masks)
        check(f"valid permutation q={q} masks={masks}", sorted(p) == list(range(n)))

    # 2. path graph (non-Cayley): RCM must be monotone and give bandwidth 1
    N = 12
    padj = [set() for _ in range(N)]
    for i in range(N - 1):
        padj[i].add(i + 1)
        padj[i + 1].add(i)
    pp = order_from_adj(padj)
    check("path: valid permutation", sorted(pp) == list(range(N)))
    check("path: monotone traversal", pp == list(range(N)) or pp == list(range(N - 1, -1, -1)))
    check("path: bandwidth 1", bandwidth(padj, pp) == 1)

    # 2b. disconnected graph: two paths
    d2 = [set() for _ in range(8)]
    for i in (0, 1, 2, 4, 5, 6):
        d2[i].add(i + 1)
        d2[i + 1].add(i)
    dp = order_from_adj(d2)
    check("disconnected: valid permutation", sorted(dp) == list(range(8)))
    check("disconnected: bandwidth 1", bandwidth(d2, dp) == 1)

    # 2c. RANDOMLY RELABELLED GRID (the real anti-stub control).
    #     Everything above passes for an `order()` that ignores its input and
    #     returns range(n) reversed -- verified by mutation, so it was vacuous.
    #     A grid whose vertex labels are shuffled with a fixed seed has huge
    #     natural-order bandwidth; only an ordering that actually reads the
    #     graph can recover the narrow one.
    import random as _random
    for R, C, want in ((3, 40, 8), (4, 25, 10)):
        lab = list(range(R * C))
        _random.Random(7).shuffle(lab)
        g = [set() for _ in range(R * C)]
        for r in range(R):
            for c in range(C):
                if r + 1 < R:
                    g[lab[r * C + c]].add(lab[(r + 1) * C + c])
                    g[lab[(r + 1) * C + c]].add(lab[r * C + c])
                if c + 1 < C:
                    g[lab[r * C + c]].add(lab[r * C + c + 1])
                    g[lab[r * C + c + 1]].add(lab[r * C + c])
        gp = order_from_adj(g)
        bw_rcm, bw_nat = bandwidth(g, gp), bandwidth(g, list(range(R * C)))
        check(f"shuffled {R}x{C} grid: valid permutation",
              sorted(gp) == list(range(R * C)))
        check(f"shuffled {R}x{C} grid: RCM bandwidth {bw_rcm} <= {want} "
              f"(natural order: {bw_nat})", bw_rcm <= want)

    # 3. determinism
    a = order(1 << 6, [1 << k for k in range(6)])
    b = order(1 << 6, [1 << k for k in range(6)])
    check("deterministic across runs", a == b)

    # 4. q=6 hypercube bandwidth, RCM vs natural order -- now ASSERTED, not
    #    just printed.  RCM only manages ~1.4x here (Theta(n) either way, which
    #    is the finding), but a graph-ignoring order gets exactly 1.0x.
    q = 6
    n = 1 << q
    hm = [1 << k for k in range(q)]
    hadj = _build_adj(n, hm)
    bw_nat, bw_rcm = bandwidth(hadj, list(range(n))), bandwidth(hadj, order(n, hm))
    print(f"\nq={q} hypercube (n={n}): natural-order bandwidth = {bw_nat}, "
          f"RCM bandwidth = {bw_rcm}")
    check(f"q=6 hypercube: RCM bandwidth {bw_rcm} < natural {bw_nat}", bw_rcm < bw_nat)

    # 5. Integration with the harness (was an open caveat: harness.py did not
    #    exist when this module was written).  Skipped cleanly if absent.
    try:
        import harness
    except ImportError:
        print("SKIP  harness integration (harness.py not importable)")
    else:
        for q in (4, 5, 6):
            n = 1 << q
            for ms in ([1 << k for k in range(q)], [1, 3, 7], [5, 10]):
                p = order(n, ms)
                assert p == order(n, ms)
                f, o, d, done, steps = harness.eliminate_with_perm(n, ms, p, 60.0)
                check(f"harness elimination completes on q={q} masks={ms} "
                      f"(fill={f}, ops={o})", done and steps == n)
        # sanity: the greedy min-degree anchor must not be beaten by a static
        # RCM order on the hypercube.  If it ever is, one of the two is wrong.
        n, ms = 1 << 6, [1 << k for k in range(6)]
        md_ops = harness.min_degree_fill(n, ms, 60.0)[1]
        rcm_ops = harness.eliminate_with_perm(n, ms, order(n, ms), 60.0)[1]
        check(f"q=6: min-degree ops {md_ops} <= RCM ops {rcm_ops}", md_ops <= rcm_ops)

    print("\nALL PASS" if ok else "\nSOME FAILED")
    raise SystemExit(0 if ok else 1)
