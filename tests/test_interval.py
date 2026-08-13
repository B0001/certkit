"""Soundness fuzz for the interval core, against exact rational arithmetic.

An IEEE double is exactly a rational, so `fractions.Fraction` gives us an
oracle with no rounding at all. For every sampled pair of points inside the
input intervals, the exact result must lie inside the output interval.
"""

from __future__ import annotations

import math
import random
from fractions import Fraction

import pytest

from certkit.interval import Iv, IntervalError

TRIALS = 3000


def _rand_float(rng: random.Random) -> float:
    kind = rng.random()
    if kind < 0.25:
        return rng.uniform(-1e-8, 1e-8)
    if kind < 0.5:
        return rng.uniform(-1e8, 1e8)
    if kind < 0.75:
        return rng.uniform(-1.0, 1.0)
    return rng.choice([0.0, -0.0, 1.0, -1.0, 2.0**-52, 2.0**52])


def _rand_iv(rng: random.Random) -> Iv:
    a, b = _rand_float(rng), _rand_float(rng)
    return Iv(min(a, b), max(a, b))


def _points(iv: Iv, rng: random.Random) -> list[float]:
    pts = [iv.lo, iv.hi]
    for _ in range(2):
        t = rng.random()
        p = iv.lo + t * (iv.hi - iv.lo)
        pts.append(min(max(p, iv.lo), iv.hi))
    return pts


@pytest.mark.parametrize("op_name", ["add", "sub", "mul", "div"])
def test_binary_ops_enclose_exact_result(op_name):
    rng = random.Random(20260813 + hash(op_name) % 1000)
    exact = {
        "add": lambda p, q: p + q,
        "sub": lambda p, q: p - q,
        "mul": lambda p, q: p * q,
        "div": lambda p, q: p / q,
    }[op_name]
    applied = {
        "add": lambda a, b: a + b,
        "sub": lambda a, b: a - b,
        "mul": lambda a, b: a * b,
        "div": lambda a, b: a / b,
    }[op_name]

    checked = 0
    for _ in range(TRIALS):
        a, b = _rand_iv(rng), _rand_iv(rng)
        try:
            r = applied(a, b)
        except IntervalError:
            continue  # abstention is always allowed; unsoundness is not
        if not r.is_finite:
            continue
        lo, hi = Fraction(r.lo), Fraction(r.hi)
        for p in _points(a, rng):
            for q in _points(b, rng):
                if op_name == "div" and q == 0.0:
                    continue
                val = exact(Fraction(p), Fraction(q))
                assert lo <= val <= hi, (op_name, a, b, p, q, r, float(val))
                checked += 1
    assert checked > 1000


def test_sqrt_encloses_exact_result():
    rng = random.Random(7)
    for _ in range(TRIALS):
        a = _rand_iv(rng)
        if a.hi < 0:
            with pytest.raises(IntervalError):
                a.sqrt()
            continue
        r = a.sqrt()
        for p in _points(a, rng):
            if p < 0:
                continue
            # sqrt(p) is irrational in general; bracket it by squaring.
            assert r.lo <= 0.0 or Fraction(r.lo) ** 2 <= Fraction(p)
            assert Fraction(r.hi) ** 2 >= Fraction(p)


def test_rejects_nan_and_inverted():
    with pytest.raises(IntervalError):
        Iv(1.0, 0.0)
    with pytest.raises(IntervalError):
        Iv(math.nan, 1.0)


def test_division_by_straddling_zero_abstains():
    with pytest.raises(IntervalError):
        Iv(1.0, 2.0) / Iv(-1.0, 1.0)
    with pytest.raises(IntervalError):
        Iv(1.0, 2.0) / Iv(0.0, 1.0)


def test_widening_is_strict_where_it_must_be():
    # 0.1 + 0.2 is not 0.3 in binary; the enclosure must still contain 0.3's
    # exact real value as computed from the exact operands.
    r = Iv.exact(0.1) + Iv.exact(0.2)
    exact = Fraction(0.1) + Fraction(0.2)
    assert Fraction(r.lo) <= exact <= Fraction(r.hi)
