"""
Turn sweep.json into the certkit-cpo verdict: fitted growth exponents per
(ordering, family), and a markdown table for sandbox-handoffs/certkit-ph1.md.

The decision rule, fixed BEFORE looking at the numbers so it cannot be
rationalised afterwards:

  ops ~ n^alpha.  alpha is fitted by least squares on log2(ops) vs log2(n),
  using only cells that COMPLETED (partial cells are excluded, never
  extrapolated). Dense LDL^T is alpha = 3.

    alpha >= 2.85                      -> cubic. No asymptotic win.
    2.5 <= alpha < 2.85                -> ambiguous, needs more n before any claim.
    alpha < 2.5                        -> genuinely sub-cubic: a real subclass.

  Reported alongside is the trend in ops/sector (ops normalised by the cost of
  dense-factorising each connected component, n^3/c^2). A CONSTANT ops/sector
  is the signature of "same growth order, smaller constant" -- which is what
  session 6 found for min-degree and is NOT good enough for the bead. A
  SHRINKING ops/sector is what a real win would look like.
"""
import json
import math
import sys
from collections import defaultdict


def fit_exponent(ns, ys):
    """Least-squares slope of log2(y) vs log2(n). Returns None if <3 points."""
    pts = [(math.log2(n), math.log2(y)) for n, y in zip(ns, ys) if y > 0]
    if len(pts) < 3:
        return None
    mx = sum(p[0] for p in pts) / len(pts)
    my = sum(p[1] for p in pts) / len(pts)
    num = sum((x - mx) * (y - my) for x, y in pts)
    den = sum((x - mx) ** 2 for x, _ in pts)
    return num / den if den else None


def classify(alpha):
    if alpha is None:
        return "insufficient-data"
    if alpha >= 2.85:
        return "CUBIC"
    if alpha >= 2.5:
        return "ambiguous"
    return "SUB-CUBIC"


def main(path="sweep.json"):
    rows = json.load(open(path))
    complete = [r for r in rows if r.get("completed") and "error" not in r]
    dropped = [r for r in rows if not (r.get("completed") and "error" not in r)]

    groups = defaultdict(list)
    for r in complete:
        groups[(r["ordering"], r["family"])].append(r)

    print(f"total cells: {len(rows)}   complete: {len(complete)}   "
          f"excluded (partial/error): {len(dropped)}")
    if dropped:
        print("EXCLUDED CELLS (not extrapolated, not averaged in):")
        for r in dropped:
            why = r.get("error") or f"partial {r.get('steps')}/{r['n']} pivots"
            print(f"   {r['ordering']:>18} {r['family']:>16} q={r['q']:<3} {why}")
    print()

    hdr = (f"{'ordering':>18} {'family':>16} {'pts':>4} {'comp':>5} "
           f"{'ops~n^a':>8} {'fill~n^b':>9} {'ops/sector first->last':>26} {'verdict':>16}")
    print(hdr)
    print("-" * len(hdr))

    subcubic = []
    for (o, f), rs in sorted(groups.items()):
        rs.sort(key=lambda r: r["n"])
        ns = [r["n"] for r in rs]
        a = fit_exponent(ns, [r["ops"] for r in rs])
        b = fit_exponent(ns, [r["fill"] for r in rs])
        sec = [r["ops_over_sector"] for r in rs]
        verdict = classify(a)
        trend = f"{sec[0]:.5f} -> {sec[-1]:.5f}" if sec else "n/a"
        astr = f"{a:.3f}" if a is not None else "  --"
        bstr = f"{b:.3f}" if b is not None else "  --"
        print(f"{o:>18} {f:>16} {len(rs):>4} {rs[0]['n_components']:>5} "
              f"{astr:>8} {bstr:>9} {trend:>26} {verdict:>16}")
        if verdict == "SUB-CUBIC":
            subcubic.append((o, f, a, sec))

    print()
    print("=" * 78)
    if subcubic:
        print("SUB-CUBIC CANDIDATES FOUND -- each needs a second look before any claim:")
        for o, f, a, sec in subcubic:
            print(f"  {o} x {f}: ops ~ n^{a:.3f}, ops/sector {sec[0]:.5f} -> {sec[-1]:.5f}")
    else:
        print("NO SUB-CUBIC (ordering x family) CELL. Every fitted exponent is >= 2.5.")
        print("This closes the ASYMPTOTIC question only. It does NOT close the coverage")
        print("question the bead actually asks: a constant-factor win still moves the n at")
        print("which an interval LDL^T is affordable, and DENSE_LIMIT is a runtime cap, not")
        print("a soundness cap. See Result 9 in sandbox-handoffs/certkit-ph1.md.")

    # best constant-factor win, which is the only thing on offer if all cubic
    best = min(complete, key=lambda r: r["ops_over_sector"])
    print()
    print(f"best per-sector constant seen: {best['ops_over_sector']:.5f} "
          f"({best['ordering']} x {best['family']}, q={best['q']}) "
          f"= {1/best['ops_over_sector']:.1f}x under dense-per-sector")


if __name__ == "__main__":
    main(*sys.argv[1:])
