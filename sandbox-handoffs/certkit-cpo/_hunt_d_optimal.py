"""
HUNT D: EXACT optimum over ALL n! orderings, by subset DP, for n <= 16.

If the sweep's heuristics are leaving a lot on the table, the optimum would show
it.  DP is exact because the eliminated graph on V\\S depends only on the SET S,
not the order within it (standard fill-in fact): after eliminating S, u~v iff
there is a u-v path all of whose interior vertices lie in S.

f(S) = min cost to eliminate the vertices of S first.
f({}) = 0;  f(S) = min_{v in S} f(S-v) + deg(v, S-v)^2
where deg(v,T) = #{u not in S : u reachable from v through T}.

The optimum is cross-checked against harness.eliminate_with_perm on the
recovered argmin permutation, so the DP cannot silently disagree with the
verified accounting.
"""
import harness
from _hunt_a_layered import ord_popcount_asc


def optimal(n, masks):
    adj = harness.build_adj(n, masks)
    full = (1 << n) - 1

    def deg(v, T):
        # vertices outside S=T|{v} reachable from v through T
        seen = 1 << v
        stack = [v]
        out = 0
        while stack:
            x = stack.pop()
            for u in adj[x]:
                if seen >> u & 1:
                    continue
                seen |= 1 << u
                if T >> u & 1:
                    stack.append(u)
                else:
                    out += 1
        return out

    f = [0] * (1 << n)
    choice = [-1] * (1 << n)
    for S in range(1, 1 << n):
        best = None
        s = S
        while s:
            b = s & -s
            v = b.bit_length() - 1
            s ^= b
            T = S ^ b
            c = f[T] + deg(v, T) ** 2
            if best is None or c < best:
                best, choice[S] = c, v
        f[S] = best
    perm = []
    S = full
    while S:
        v = choice[S]
        perm.append(v)
        S ^= 1 << v
    return f[full], perm[::-1]


if __name__ == "__main__":
    for q, name, masks in [
        (3, "Q_3", [1, 2, 4]),
        (4, "Q_4", [1, 2, 4, 8]),
        (4, "chain_open q=4", [3, 6, 12]),
        (4, "all_nonzero K_16", list(range(1, 16))),
        (4, "weight2 q=4", [3, 5, 6, 9, 10, 12]),
    ]:
        n = 1 << q
        opt, perm = optimal(n, masks)
        chk = harness.eliminate_with_perm(n, masks, perm, 60.0)
        assert chk[1] == opt, (name, opt, chk)
        md = harness.min_degree_fill(n, masks, 60.0)[1]
        pc = harness.eliminate_with_perm(n, masks, ord_popcount_asc(n, q), 60.0)[1]
        lex = harness.eliminate_with_perm(n, masks, list(range(n)), 60.0)[1]
        print(f"{name:<16} n={n:>3}  OPT={opt:>6} (verified via perm)  min_degree={md:>6} "
              f"popcount={pc:>6} lex={lex:>6}   OPT/n^3={opt/n**3:.5f}  md/OPT={md/opt:.3f}")
