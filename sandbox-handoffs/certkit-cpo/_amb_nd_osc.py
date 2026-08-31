"""Why does ND's ops/n^3 oscillate with q?

Instruments the ND recursion (no budget, so nothing is truncated) and reports,
per q, the structure the partitioner actually produced:
  bail_nodes / bail_verts / bail_max -- subsets the generic partitioner could
      not split at all (returns None), so their vertices were emitted in plain
      index order. A big bail is a local dense block and blows ops up.
  top|S| / top balance -- the root separator.
  depth -- max recursion depth reached.
  seps_tot -- total separator vertices over the whole recursion.
Elimination uses the bitset eliminator (exact twin of harness, see
_amb_fastelim self-check).
"""
import math
import sys

import families
import ord_nd
from _amb_fastelim import eliminate_bits

FAMS = sys.argv[1:] or ["hypercube_tfim", "chain_1d_nn"]


def order_traced(n, masks):
    adj = ord_nd.build_adj_local(n, masks)
    ms = {m for m in masks if m}
    q = n.bit_length() - 1
    hq = q if (1 << q) == n and ms == {1 << k for k in range(q)} else None

    perm = []
    st = {"bail_nodes": 0, "bail_verts": 0, "bail_max": 0, "depth": 0,
          "seps_tot": 0, "top": None, "splits": 0}
    stack = [("split", set(range(n)), hq, 0)]
    while stack:
        kind, payload, h, dep = stack.pop()
        if kind == "emit":
            perm.extend(payload)
            continue
        cur = payload
        st["depth"] = max(st["depth"], dep)
        if len(cur) <= ord_nd.LEAF:
            perm.extend(sorted(cur))
            continue
        if h is not None:
            A, S, B = ord_nd._hypercube_layer_separator(h, cur)
            if not A or not B:
                perm.extend(sorted(cur))
                continue
        else:
            part = ord_nd._generic_separator(adj, cur)
            if part is None:
                st["bail_nodes"] += 1
                st["bail_verts"] += len(cur)
                st["bail_max"] = max(st["bail_max"], len(cur))
                perm.extend(sorted(cur))
                continue
            A, S, B = part
        st["splits"] += 1
        st["seps_tot"] += len(S)
        if dep == 0:
            st["top"] = (len(A), len(S), len(B))
        stack.append(("emit", sorted(S), None, dep))
        stack.append(("split", B, None, dep + 1))
        stack.append(("split", A, None, dep + 1))
    assert sorted(perm) == list(range(n))
    return perm, st


for fam in FAMS:
    print(f"=== nested_dissection x {fam} ===")
    print(f"{'q':>3} {'n':>6} {'ops':>15} {'ops/n^3':>9} {'localA':>7} "
          f"{'top A|S|B':>18} {'bailN':>6} {'bailV':>7} {'bailMax':>8} "
          f"{'depth':>6} {'splits':>7} {'sepsTot':>8}")
    prev = None
    for q in range(6, 14):
        n, masks = families.FAMILIES[fam](q)
        perm, st = order_traced(n, masks)
        fill, ops, maxd, _, _ = eliminate_bits(n, masks, perm)
        loc = "" if prev is None else \
            f"{math.log2(ops / prev[1]) / math.log2(n / prev[0]):.3f}"
        top = "-" if st["top"] is None else "|".join(map(str, st["top"]))
        print(f"{q:>3} {n:>6} {ops:>15} {ops / n**3:>9.5f} {loc:>7} {top:>18} "
              f"{st['bail_nodes']:>6} {st['bail_verts']:>7} {st['bail_max']:>8} "
              f"{st['depth']:>6} {st['splits']:>7} {st['seps_tot']:>8}")
        sys.stdout.flush()
        prev = (n, ops)
    print()
