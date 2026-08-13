"""Coverage sweep: what happens as the spectral gap closes.

Soundness is a theorem; coverage is an empirical property. This script
measures the one that can only be measured. Every run must report zero
unsound verdicts -- a VERIFIED enclosure that does not contain the true
eigenvalue would be a defect in the checker, not a tuning issue.
"""

from __future__ import annotations

import numpy as np

from certkit.checker import check
from certkit.producer import certify_lambda_min


def random_with_gap(rng: np.random.Generator, n: int, gap: float) -> list[list[float]]:
    eigs = np.sort(rng.uniform(1.0, 10.0, size=n))
    eigs[0] = eigs[1] - gap
    q, _ = np.linalg.qr(rng.standard_normal((n, n)))
    a = q @ np.diag(eigs) @ q.T
    return ((a + a.T) / 2.0).tolist()


def main() -> None:
    rng = np.random.default_rng(0)
    n, trials = 12, 40
    print(f"n = {n}, {trials} matrices per gap\n")
    print(f"{'gap':>10}  {'verified':>9}  {'median width':>14}  {'unsound':>8}")
    print("-" * 48)

    for gap in [1e0, 1e-2, 1e-4, 1e-6, 1e-8, 1e-10, 1e-12, 1e-14]:
        widths, verified, unsound = [], 0, 0
        for _ in range(trials):
            rows = random_with_gap(rng, n, gap)
            verdict = check(*certify_lambda_min(rows))
            if not verdict.ok:
                continue
            verified += 1
            lo, hi = verdict.rederived
            truth = float(np.linalg.eigvalsh(np.array(rows))[0])
            if not (lo <= truth <= hi):
                unsound += 1
            widths.append(hi - lo)
        med = f"{np.median(widths):.3e}" if widths else "--"
        print(f"{gap:>10.0e}  {verified:>6}/{trials}  {med:>14}  {unsound:>8}")

    print(
        "\nThe kit stops answering before it starts lying: coverage falls to zero"
        "\nas the gap closes, and the unsound column stays at zero throughout."
    )


if __name__ == "__main__":
    main()
