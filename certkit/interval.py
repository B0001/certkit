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


# -- complex interval arithmetic -----------------------------------------
@dataclass(frozen=True)
class CIv:
    """A closed axis-aligned rectangle in the complex plane: `re + i*im` for
    `re` in the interval `re`, `im` in the interval `im`.

    Every operation returns a rectangle that provably contains the exact
    complex result for every pair of complex numbers drawn from the input
    rectangles -- built entirely from `Iv`'s already-proven-sound real
    arithmetic, so no new rounding argument is needed: each real sub-op
    (a product, a sum) is itself an `Iv` operation and inherits its
    soundness.
    """

    re: Iv
    im: Iv

    @staticmethod
    def exact(z: complex) -> "CIv":
        """The degenerate rectangle {z}. A complex double pair *is* exact."""
        return CIv(Iv.exact(z.real), Iv.exact(z.imag))

    def conj(self) -> "CIv":
        return CIv(self.re, -self.im)

    def __add__(self, o: "CIv") -> "CIv":
        return CIv(self.re + o.re, self.im + o.im)

    def __sub__(self, o: "CIv") -> "CIv":
        return CIv(self.re - o.re, self.im - o.im)

    def __neg__(self) -> "CIv":
        return CIv(-self.re, -self.im)

    def __mul__(self, o: "CIv") -> "CIv":
        # (a+bi)(c+di) = (ac-bd) + (ad+bc)i, each term an already-sound Iv op.
        return CIv(self.re * o.re - self.im * o.im, self.re * o.im + self.im * o.re)

    def __truediv__(self, o: Iv) -> "CIv":
        """Division by a *real* interval only (all this checker ever needs:
        normalising by a positive squared-norm). General complex/complex
        interval division is not implemented -- it is unused here, and a
        sound version is materially trickier to get right than this module
        should carry untested.
        """
        return CIv(self.re / o, self.im / o)

    @property
    def mag_ub(self) -> float:
        """A sound upper bound on |z| for every z in the rectangle.

        max(|re.lo|, |re.hi|) and max(|im.lo|, |im.hi|) each bound the real
        and imaginary magnitude; sqrt(re_mag^2 + im_mag^2), computed with
        outward-rounded `Iv` arithmetic and taking the upper endpoint, bounds
        the modulus of every point in the rectangle (the true corner-point
        modulus can only be smaller, since re_mag/im_mag already dominate
        every point's coordinates).
        """
        re_m = self.re.mag_ub
        im_m = self.im.mag_ub
        sq = Iv.exact(re_m) * Iv.exact(re_m) + Iv.exact(im_m) * Iv.exact(im_m)
        return sq.sqrt().hi

    def __repr__(self) -> str:  # pragma: no cover - display only
        return f"({self.re!r} + i*{self.im!r})"


CZERO = CIv(ZERO, ZERO)


def cdot(u: Sequence[CIv], v: Sequence[CIv]) -> CIv:
    """The Hermitian inner product sum_i conj(u_i) * v_i.

    Conjugate-linear in the first argument, matching the physics convention
    <u|v>. `cdot(x, x)` is therefore an enclosure of a real, non-negative
    number (a sum of |x_i|^2 terms) even though it is returned as a `CIv` --
    callers that need that fact as an `Iv` should use `csqnorm` instead, which
    proves it directly rather than relying on the imaginary part rounding to
    contain zero.
    """
    if len(u) != len(v):
        raise IntervalError("dimension mismatch in cdot")
    acc = CZERO
    for a, b in zip(u, v):
        acc = acc + a.conj() * b
    return acc


def csqnorm(u: Sequence[CIv]) -> Iv:
    """Enclosure of sum |u_i|^2 = sum (re_i^2 + im_i^2); non-negative by
    construction, and real by construction (no complex multiplication or
    conjugate-symmetry argument needed, unlike `cdot`).
    """
    acc = ZERO
    for a in u:
        acc = acc + a.re * a.re + a.im * a.im
    return acc.meet_nonneg()
