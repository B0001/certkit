"""
HUNT C: mask families NOT in families.py, plus the honest-normalisation check.

For every candidate family we report, at each q:
  c    = number of connected components (BFS)
  d    = dim_GF2 span(masks)   (must satisfy c == 2^(q-d))
  ops  = min over {min_degree, popcount_asc, lex} of harness ops
  ops/n^3         -- the DISHONEST number (dense baseline on the whole space)
  ops*c^2/n^3     -- the HONEST number: dense-factorising each of the c sectors
                     costs c*(n/c)^3 = n^3/c^2, so this is the real ratio.

A family is only interesting if the HONEST ratio falls with q.
"""
import math
import sys
import harness
from _hunt_a_layered import ord_popcount_asc, ord_lex


def gf2_dim(masks):
    rows = []
    for m in masks:
        v = m
        for r in rows:
            v = min(v, v ^ r)
        if v:
            rows.append(v)
            rows.sort(reverse=True)
    return len(rows)


def n_components(n, masks):
    seen = [False] * n
    c = 0
    for s in range(n):
        if seen[s]:
            continue
        c += 1
        stack = [s]
        seen[s] = True
        while stack:
            v = stack.pop()
            for m in masks:
                u = v ^ m
                if not seen[u]:
                    seen[u] = True
                    stack.append(u)
    return c


# --- candidate families -----------------------------------------------------

def f_single(q):
    """One mask.  Trivial floor: 2^(q-1) disconnected edges."""
    return [1]


def f_few(q):
    """|masks| = 3 regardless of q -- deliberately sparse, many components."""
    return [1, 2, 4][:3]


def f_chain_open(q):
    """True open 1D chain, nearest-neighbour XX: masks (1<<i)|(1<<(i+1)),
    no wraparound.  q-1 independent masks."""
    return [(1 << i) | (1 << (i + 1)) for i in range(q - 1)]


def f_chain_ring(q):
    """Closed ring: the wraparound mask makes the set dependent."""
    return [(1 << i) | (1 << ((i + 1) % q)) for i in range(q)]


def f_lowdim(q):
    """All 2^3-1 nonzero masks supported on 3 bits: span dim 3, so 2^(q-3)
    components each a K_8."""
    return [m for m in range(1, 8)]


def f_tree(q):
    """Star / tree-shaped generator set: masks 1|(1<<i) -- the Cayley graph of a
    tree-structured coupling."""
    return [1 | (1 << i) for i in range(1, q)]


def f_prod_cycles(q):
    """'Product of small cycles': generators grouped in pairs, each pair
    generating a C_4.  Over Z_2 every generator is an involution, so this can
    only ever be a hypercube -- included to check that claim numerically."""
    return [1 << i for i in range(q)]


def f_indep_random(q):
    """q independent random masks (dense but full-rank)."""
    ms, rows = [], []
    x = 0x9E3779B9
    while len(ms) < q:
        x = (x * 1103515245 + 12345) & 0xFFFFFFFF
        m = (x >> 5) % (1 << q)
        v = m
        for r in rows:
            v = min(v, v ^ r)
        if v:
            rows.append(v); rows.sort(reverse=True); ms.append(m)
    return ms


def f_weight2_local(q):
    """All weight-2 masks with support distance <= 2 (a banded/local coupling)."""
    ms = set()
    for i in range(q):
        for j in range(i + 1, min(i + 3, q)):
            ms.add((1 << i) | (1 << j))
    return sorted(ms)


FAMS = {
    "single": f_single,
    "few3": f_few,
    "chain_open": f_chain_open,
    "chain_ring": f_chain_ring,
    "lowdim3": f_lowdim,
    "tree_star": f_tree,
    "prod_cycles": f_prod_cycles,
    "indep_random": f_indep_random,
    "weight2_local": f_weight2_local,
}


def main(qs, budget=600.0):
    hdr = f"{'family':<14}{'q':>3}{'|S|':>5}{'d':>4}{'c':>7}{'2^(q-d)':>9}{'ops':>13}{'ops/n^3':>11}{'honest':>11}"
    print(hdr)
    print("-" * len(hdr))
    honest = {}
    for name, fn in FAMS.items():
        honest[name] = []
        for q in qs:
            n = 1 << q
            masks = sorted(set(m for m in fn(q) if m))
            d = gf2_dim(masks)
            c = n_components(n, masks)
            best = None
            for oname, operm in (("mindeg", None), ("popcnt", ord_popcount_asc), ("lex", ord_lex)):
                if operm is None:
                    r = harness.min_degree_fill(n, masks, budget)
                else:
                    r = harness.eliminate_with_perm(n, masks, operm(n, q), budget)
                assert r[3] and r[4] == n, (name, q, oname, r[3], r[4])
                if best is None or r[1] < best[0]:
                    best = (r[1], oname)
            o = best[0]
            h = o * c * c / n ** 3
            honest[name].append((q, n, o, c, h))
            print(f"{name:<14}{q:>3}{len(masks):>5}{d:>4}{c:>7}{2**(q-d):>9}{o:>13}"
                  f"{o/n**3:>11.5f}{h:>11.5f}   best={best[1]}", flush=True)
    print("\nHONEST ratio ops*c^2/n^3, and its local exponent alpha over sector size n/c:")
    for name, cells in honest.items():
        alphas = []
        for i in range(len(cells) - 1):
            (q0, n0, o0, c0, _), (q1, n1, o1, c1, _) = cells[i], cells[i + 1]
            # exponent in the SECTOR size, which is what a sub-cubic claim is about
            s0, s1 = n0 / c0, n1 / c1
            alphas.append(math.log(o1 / o0) / math.log(s1 / s0) if s1 != s0 and o0 else float("nan"))
        print(f"  {name:<14} honest=" + " ".join(f"{h:.5f}" for *_, h in cells)
              + "   alpha_sector=" + " ".join(f"{a:.3f}" for a in alphas))


if __name__ == "__main__":
    main([int(x) for x in (sys.argv[1].split(",") if len(sys.argv) > 1 else "6,7,8,9,10".split(","))])
