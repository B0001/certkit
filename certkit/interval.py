"""Rigorous interval arithmetic on IEEE-754 doubles.

Soundness contract
------------------
Every operation returns an interval that *provably contains* the exact
real-arithmetic result, for every pair of reals in the input intervals.

Python gives no access to the FPU rounding mode, so we use the standard
nextafter widening: an IEEE double operation errs by at most half an ulp,
so widening each endpoint by one ulp in the outward direction is a valid
enclosure. `math.nextafter` also does the right thing on overflow
(nextafter(inf, -inf) is the largest finite double, which is a valid lower
bound for a quantity that overflowed), so overflow degrades to a wide but
sound interval rather than to nonsense.

This module is imported by the checker. It must never import anything from
the producer side.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


class IntervalError(Exception):
    """Raised when an enclosure cannot be produced soundly (NaN, div by zero...).

    The checker treats this as ABSTAIN, never as a recoverable condition.
    """


def _down(x: float) -> float:
    if x != x:
        raise IntervalError("NaN endpoint")
    return math.nextafter(x, -math.inf)


def _up(x: float) -> float:
    if x != x:
        raise IntervalError("NaN endpoint")
    return math.nextafter(x, math.inf)


@dataclass(frozen=True)
class Iv:
    """A closed interval [lo, hi] of reals, represented by two doubles."""

    lo: float
    hi: float

    def __post_init__(self) -> None:
        if self.lo != self.lo or self.hi != self.hi:
            raise IntervalError("NaN endpoint")
        if self.lo > self.hi:
            raise IntervalError(f"inverted interval [{self.lo}, {self.hi}]")

    # -- construction ----------------------------------------------------
    @staticmethod
    def exact(x: float) -> "Iv":
        """The degenerate interval [x, x]. Exact: a double *is* a real."""
        return Iv(x, x)

    @staticmethod
    def _widen(lo: float, hi: float) -> "Iv":
        return Iv(_down(lo), _up(hi))

    # -- predicates ------------------------------------------------------
    @property
    def is_finite(self) -> bool:
        return math.isfinite(self.lo) and math.isfinite(self.hi)

    @property
    def contains_zero(self) -> bool:
        return self.lo <= 0.0 <= self.hi

    @property
    def is_positive(self) -> bool:
        return self.lo > 0.0

    @property
    def is_negative(self) -> bool:
        return self.hi < 0.0

    def contains(self, x: float) -> bool:
        return self.lo <= x <= self.hi

    def encloses(self, other: "Iv") -> bool:
        """True iff every real in `other` is in `self`."""
        return self.lo <= other.lo and other.hi <= self.hi

    @property
    def mag_ub(self) -> float:
        """An upper bound on |v| for every v in the interval."""
        return max(abs(self.lo), abs(self.hi))

    # -- arithmetic ------------------------------------------------------
    def __add__(self, o: "Iv") -> "Iv":
        return Iv._widen(self.lo + o.lo, self.hi + o.hi)

    def __sub__(self, o: "Iv") -> "Iv":
        return Iv._widen(self.lo - o.hi, self.hi - o.lo)

    def __neg__(self) -> "Iv":
        return Iv(-self.hi, -self.lo)

    def __mul__(self, o: "Iv") -> "Iv":
        corners = (
            self.lo * o.lo,
            self.lo * o.hi,
            self.hi * o.lo,
            self.hi * o.hi,
        )
        for c in corners:
            if c != c:
                raise IntervalError("NaN in multiplication (0 * inf)")
        return Iv._widen(min(corners), max(corners))

    def __truediv__(self, o: "Iv") -> "Iv":
        if o.contains_zero:
            raise IntervalError("division by an interval containing zero")
        corners = (
            self.lo / o.lo,
            self.lo / o.hi,
            self.hi / o.lo,
            self.hi / o.hi,
        )
        for c in corners:
            if c != c:
                raise IntervalError("NaN in division")
        return Iv._widen(min(corners), max(corners))

    def sqrt(self) -> "Iv":
        if self.hi < 0.0:
            raise IntervalError("sqrt of a strictly negative interval")
        lo = self.lo if self.lo > 0.0 else 0.0
        return Iv._widen(math.sqrt(lo), math.sqrt(self.hi))

    def meet_nonneg(self) -> "Iv":
        """Intersect with [0, inf).

        Only sound where the enclosed quantity is provably non-negative in
        exact arithmetic (a sum of squares, say). Call sites must justify it.
        """
        if self.hi < 0.0:
            raise IntervalError("provably-nonneg quantity enclosed below zero")
        return Iv(max(self.lo, 0.0), self.hi)

    def __repr__(self) -> str:  # pragma: no cover - display only
        return f"[{self.lo!r}, {self.hi!r}]"


ZERO = Iv.exact(0.0)


# -- linear algebra over intervals ---------------------------------------
def dot(u: Sequence[Iv], v: Sequence[Iv]) -> Iv:
    if len(u) != len(v):
        raise IntervalError("dimension mismatch in dot")
    acc = ZERO
    for a, b in zip(u, v):
        acc = acc + a * b
    return acc


def matvec(a: Sequence[Sequence[Iv]], x: Sequence[Iv]) -> list[Iv]:
    n = len(x)
    if any(len(row) != n for row in a) or len(a) != n:
        raise IntervalError("dimension mismatch in matvec")
    return [dot(row, x) for row in a]


def sqnorm(u: Sequence[Iv]) -> Iv:
    """Enclosure of sum of squares; non-negative by construction."""
    acc = ZERO
    for a in u:
        acc = acc + a * a
    return acc.meet_nonneg()
