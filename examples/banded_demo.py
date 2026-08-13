"""Where the counting route matters.

The gap hypothesis behind Temple's inequality is an eigenvalue count, and there
are now three rules that establish one. They prove the same claim, so
`temple_ref` consumes any of them without knowing the difference -- but their
reach is not remotely the same.

    inertia   full interval LDL^T                      O(n^3), dense only
    sturm     interval LDL^T inside the band           O(n b^2)
    sturm_be  float sweep + a runtime backward bound   O(n), tridiagonal

The second table is the interesting one: a 1D Laplacian, whose ground-state gap
shrinks like 1/n^2, is where forward enclosure gives out earliest.
"""

from __future__ import annotations

import time

import numpy as np

from certkit.checker import bundle_verdict, check, check_bundle
from certkit.backward_error import count_eigenvalues_below_backward
from certkit.banded import count_eigenvalues_below_banded
from certkit.interval import IntervalError
from certkit.operators import decode_operator
from certkit.producer import (
    certify_lambda_min,
    certify_lambda_min_backward,
    certify_lambda_min_banded,
    laplacian_1d,
    schrodinger_1d,
)


def exact_ground(enc: dict, iterations: int = 80):
    """Bisect on an exact rational Sturm count -- an oracle with no rounding."""
    from fractions import Fraction

    op = decode_operator(enc)
    n = op.n
    diag = [Fraction(op.row(i)[i].lo) for i in range(n)]

    def count_below(beta):
        d = diag[0] - beta
        c = 1 if d < 0 else 0
        for j in range(1, n):
            if d == 0:
                d = Fraction(1, 10**40)
            d = (diag[j] - beta) - 1 / d
            if d < 0:
                c += 1
        return c

    lo, hi = Fraction(0), Fraction(1)
    for _ in range(iterations):
        mid = (lo + hi) / 2
        if count_below(mid) >= 1:
            hi = mid
        else:
            lo = mid
    return lo, hi


def lapack_ground(enc: dict) -> float:
    op = decode_operator(enc)
    n = op.n
    diag = [op.row(i)[i].lo for i in range(n)]
    m = np.diag(diag) + np.diag([-1.0] * (n - 1), 1) + np.diag([-1.0] * (n - 1), -1)
    return float(np.linalg.eigvalsh(m)[0])


def main() -> None:
    print("Discrete 1D Schrodinger operator, tridiagonal, harmonic well\n")
    head = f"{'n':>7}  {'dense (inertia)':>18}  {'certified bound':>16}  {'width':>10}  {'s':>5}"
    print(head)
    print("-" * len(head))

    for n in (100, 400, 1000, 4000, 10000):
        enc = schrodinger_1d(n)

        dense = check(*certify_lambda_min(enc))
        dense_note = "verified" if dense.ok else (
            "n too large" if "materialise" in dense.reason else "abstain"
        )

        t0 = time.time()
        root = bundle_verdict(check_bundle(*certify_lambda_min_backward(enc)))
        dt = time.time() - t0

        status = "verified" if root.ok else "abstain"
        width = f"{root.width:.2e}" if root.ok else "--"
        print(f"{n:>7}  {dense_note:>18}  {status:>16}  {width:>10}  {dt:>5.1f}")

    print("\n1D Laplacian -- gap shrinks like 1/n^2, at the midpoint of the gap\n")
    head2 = f"{'n':>7}  {'gap':>10}  {'sturm (interval)':>18}  {'sturm_be (backward)':>21}"
    print(head2)
    print("-" * len(head2))
    for n in (30, 40, 200, 2000, 20000):
        enc = laplacian_1d(n)
        k = np.arange(1, n + 1)
        eigs = 2.0 - 2.0 * np.cos(k * np.pi / (n + 1))
        beta = float(0.5 * (eigs[0] + eigs[1]))
        op = decode_operator(enc)
        out = []
        for fn in (count_eigenvalues_below_banded, count_eigenvalues_below_backward):
            try:
                out.append(f"count={fn(op, beta)}")
            except IntervalError:
                out.append("abstain")
        print(f"{n:>7}  {eigs[1] - eigs[0]:>10.2e}  {out[0]:>18}  {out[1]:>21}")

    print(
        "\nThe dense route stops at n = 160 because an O(n^3) interval factorisation\n"
        "in pure Python is not a route. Counting is no longer the binding\n"
        "constraint anywhere below n = 100000; the producer's eigenvector is, and\n"
        "a poorly converged vector shows up as a wide interval rather than a wrong\n"
        "one.\n"
    )

    # Who is actually right at n = 400?
    enc = schrodinger_1d(400)
    root = bundle_verdict(check_bundle(*certify_lambda_min_banded(enc)))
    lo, hi = exact_ground(enc)
    c_lo, c_hi = root.rederived
    lapack = lapack_ground(enc)
    print("n = 400, checked against an exact rational Sturm bisection:")
    print(f"  exact lambda_1        {float(lo)!r}")
    print(f"  certified enclosure   [{c_lo!r}, {c_hi!r}]")
    print(f"  numpy.linalg.eigvalsh {lapack!r}")
    print(f"  exact value inside the certified enclosure: {c_lo <= float(lo) <= c_hi}")
    print(f"  LAPACK inside the certified enclosure:      {c_lo <= lapack <= c_hi}")
    print(
        "\nThe certified interval is narrower than LAPACK's own error here, so the\n"
        "library lands outside it. That is the case for having a checker at all."
    )


if __name__ == "__main__":
    main()
