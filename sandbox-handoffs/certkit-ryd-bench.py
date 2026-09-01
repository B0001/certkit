"""Benchmark for certkit-ryd ("Performance: the checker is pure Python").

Measures the actual wall-clock cost of the pure-Python interval loops,
rather than assume the bead description's "60 seconds at n = 2e5" folklore
figure. See the README "Known limits" bullet this script backs.

Trust-boundary-clean: only imports certkit.interval / certkit.operators /
certkit.banded (all TRUSTED, stdlib-only). Runs fine under the
no-dependency interpreter (no uv, no numpy) -- this script itself has no
dependencies either, deliberately, so a timing run is evidence about the
trusted code, not about anything the benchmark harness added:

    PYTHONPATH=. python3 sandbox-handoffs/certkit-ryd-bench.py
    PYTHONPATH=. python3 sandbox-handoffs/certkit-ryd-bench.py --wide-band

The default run is the tridiagonal (b=1) case, seconds. `--wide-band` runs
the b=16 and b=64 (MAX_BANDWIDTH) cases, which are slow by design -- expect
tens of seconds total.

Every case picks beta below the spectrum of every leading principal
submatrix (all pivots stay positive, none straddle zero), specifically so
the timing measures the arithmetic cost alone and does not get cut short by
an (expected, correct) abstention from pivot width blowup -- see the
`sturm`/`sturm_be` discussion in README.md for why an in-spectrum beta
usually abstains long before n = 2e5 on the interval route.
"""

import random
import sys
import time

from certkit.banded import count_eigenvalues_below_banded
from certkit.operators import SparseCSRSymmetric


def tridiagonal(n: int, seed: int = 0) -> SparseCSRSymmetric:
    """Diagonally dominant tridiagonal operator: safely positive definite."""
    rng = random.Random(seed)
    indptr = [0]
    indices = []
    data = []
    for i in range(n):
        if i > 0:
            indices.append(i - 1)
            data.append(-1.0 - 0.0001 * rng.random())
        indices.append(i)
        data.append(4.0 + 0.01 * rng.random())
        if i < n - 1:
            indices.append(i + 1)
            data.append(-1.0 - 0.0001 * rng.random())
        indptr.append(len(indices))
    return SparseCSRSymmetric(n, indptr, indices, data)


def banded(n: int, b: int, seed: int = 0) -> SparseCSRSymmetric:
    """Diagonally dominant operator of bandwidth b: safely positive definite."""
    rng = random.Random(seed)
    indptr = [0]
    indices = []
    data = []
    for i in range(n):
        lo, hi = max(0, i - b), min(n - 1, i + b)
        for j in range(lo, hi + 1):
            indices.append(j)
            data.append(20.0 * b if j == i else -0.01 * rng.random())
        indptr.append(len(indices))
    return SparseCSRSymmetric(n, indptr, indices, data)


def run(label: str, op: SparseCSRSymmetric) -> None:
    t0 = time.perf_counter()
    count = count_eigenvalues_below_banded(op, 0.0)
    dt = time.perf_counter() - t0
    print(f"{label:<24} {dt:>10.3f}s   count={count}")


def main() -> None:
    if "--wide-band" in sys.argv:
        for n, b in ((2000, 64), (5000, 64), (10000, 64), (20000, 16)):
            run(f"n={n} b={b}", banded(n, b))
        return
    for n in (1_000, 5_000, 20_000, 50_000, 100_000, 200_000):
        run(f"n={n} b=1 (tridiag)", tridiagonal(n))


if __name__ == "__main__":
    main()
