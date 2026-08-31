"""
HUNT F: is the d-cube a FLOOR for every mask family?

Claim: for masks S with GF(2)-rank d, the Cayley graph has 2^(q-d) components,
each isomorphic to Cay(Z_2^d, S') which CONTAINS a spanning Q_d.  Elimination
cost is monotone under adding edges for a fixed order, so
    OPT(one sector of any rank-d family)  >=  OPT(Q_d).
If true, no mask family can ever beat the cube per sector, and the only hope
for sub-cubic is a better ordering on the cube -- which HUNT D shows min_degree
already attains exactly at n=16.

Checked here by exhaustive EXACT optimum (HUNT D's DP) over random rank-d mask
sets at sector size 8 and 16.
"""
import random
import harness
from _hunt_d_optimal import optimal
from _hunt_c_families import gf2_dim, n_components


def sector_masks(masks):
    """Rewrite S in a basis of span(S): returns (d, S') on Z_2^d, the graph of
    one component."""
    rows = {}
    for m in masks:
        v, coeff = m, 0
        for p in sorted(rows, reverse=True):
            if v >> p & 1:
                v ^= rows[p][0]
                coeff ^= rows[p][1]
        if v:
            rows[v.bit_length() - 1] = (v, coeff | (1 << len(rows)))
    d = len(rows)
    out = []
    for m in masks:
        v, coeff = m, 0
        for p in sorted(rows, reverse=True):
            if v >> p & 1:
                v ^= rows[p][0]
                coeff ^= rows[p][1]
        assert v == 0, "mask outside its own span"
        out.append(coeff)
    return d, sorted(set(x for x in out if x))


if __name__ == "__main__":
    cube_opt = {}
    for d in (1, 2, 3, 4):
        cube_opt[d] = optimal(1 << d, [1 << i for i in range(d)])[0]
    print("EXACT OPT for Q_d:", {d: v for d, v in cube_opt.items()})

    rng = random.Random(90909)
    tested = viol = 0
    for _ in range(300):
        q = rng.choice([3, 4, 5])
        n = 1 << q
        S = sorted(set(rng.randrange(1, n) for _ in range(rng.randint(1, 5))))
        d, S2 = sector_masks(S)
        if d > 4:
            continue
        assert d == gf2_dim(S)
        assert n_components(n, S) == 2 ** (q - d), (S, q, d)
        sec_opt, perm = optimal(1 << d, S2)
        # full graph must be exactly 2^(q-d) disjoint copies of the sector
        full_opt = optimal(n, S)[0] if q <= 4 else None
        if full_opt is not None:
            assert full_opt == sec_opt * 2 ** (q - d), (S, full_opt, sec_opt, d, q)
        if sec_opt < cube_opt[d]:
            viol += 1
            print("VIOLATION: sector beats Q_d!", S, "->", S2, "d=", d,
                  "sec_opt=", sec_opt, "cube_opt=", cube_opt[d])
        tested += 1
    print(f"tested {tested} random mask sets: {viol} beat their own Q_d "
          f"(0 == cube is the floor); component count == 2^(q-d) in all cases; "
          f"full-graph OPT == 2^(q-d) * sector OPT in all q<=4 cases")
