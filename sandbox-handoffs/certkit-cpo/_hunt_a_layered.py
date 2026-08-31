"""
HUNT A: the untested orderings, on the hypercube.

Tests: popcount-ascending, middle-layer-last, Gray code, bit-reversal,
lexicographic (=identity), and greedy min-degree as the incumbent baseline.
All driven through harness.eliminate_with_perm so the accounting is the
verified one.
"""
import sys
import harness

# --- orderings --------------------------------------------------------------

def ord_lex(n, q):
    return list(range(n))

def ord_popcount_asc(n, q):
    return sorted(range(n), key=lambda v: (bin(v).count("1"), v))

def ord_middle_last(n, q):
    """Extreme Hamming layers first, middle layer eliminated last.  This is the
    order the C(q,q//2) middle-layer separator argument suggests."""
    return sorted(range(n), key=lambda v: (-abs(bin(v).count("1") - q / 2.0), v))

def ord_gray(n, q):
    """Reflected binary: vertex at Gray position k is k ^ (k>>1)."""
    return [k ^ (k >> 1) for k in range(n)]

def ord_bitrev(n, q):
    def rev(v):
        r = 0
        for b in range(q):
            r = (r << 1) | ((v >> b) & 1)
        return r
    return [rev(k) for k in range(n)]

def ord_nested_bisect(n, q):
    """True recursive bisection of the cube by coordinate: split on bit q-1,
    order each half recursively, and put nothing in the separator (a cube has
    no small vertex separator on a coordinate split -- the 'separator' is the
    whole half-boundary).  Included as a control."""
    def rec(prefix, bits):
        if not bits:
            return [prefix]
        b = bits[0]
        return rec(prefix, bits[1:]) + rec(prefix | (1 << b), bits[1:])
    return rec(0, list(range(q)))

ORDERS = {
    "lex": ord_lex,
    "popcount_asc": ord_popcount_asc,
    "middle_last": ord_middle_last,
    "gray": ord_gray,
    "bitrev": ord_bitrev,
    "nested_bisect": ord_nested_bisect,
}


def run(masks_fn, label, qs, budget=600.0):
    print(f"\n=== {label} ===")
    print(f"{'ord':<16}" + "".join(f"{'q=%d' % q:>14}" for q in qs))
    rows = {}
    for name, fn in list(ORDERS.items()) + [("min_degree", None)]:
        cells = []
        for q in qs:
            n = 1 << q
            masks = masks_fn(q)
            if fn is None:
                f, o, d, c, s = harness.min_degree_fill(n, masks, budget)
            else:
                f, o, d, c, s = harness.eliminate_with_perm(n, masks, fn(n, q), budget)
            assert c and s == n, (name, q, c, s)
            cells.append((q, n, o))
            print(f"  {name} q={q} n={n} ops={o} ops/n^3={o / n**3:.5f}", flush=True)
        rows[name] = cells
    print(f"\n{'ord':<16}" + "".join(f"{'q=%d' % q:>12}" for q in qs) + "   (ops/n^3)")
    for name, cells in rows.items():
        print(f"{name:<16}" + "".join(f"{o / n**3:>12.5f}" for _, n, o in cells))
    return rows


if __name__ == "__main__":
    qs = [int(x) for x in sys.argv[1:]] or [4, 5, 6, 7, 8, 9, 10]
    run(lambda q: [1 << i for i in range(q)], "hypercube Q_q", qs)
