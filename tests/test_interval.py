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

from certkit.interval import CIv, IntervalError, Iv, cdot, csqnorm

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


# -- complex interval arithmetic (CIv) ------------------------------------
def _rand_civ(rng: random.Random) -> CIv:
    return CIv(_rand_iv(rng), _rand_iv(rng))


def _cpoints(civ: CIv, rng: random.Random) -> list[tuple[Fraction, Fraction]]:
    """A few exact (re, im) points drawn from the rectangle, as Fractions."""
    re_pts = _points(civ.re, rng)
    im_pts = _points(civ.im, rng)
    return [(Fraction(re), Fraction(im)) for re in re_pts for im in im_pts]


def _cmul(p: tuple[Fraction, Fraction], q: tuple[Fraction, Fraction]) -> tuple[Fraction, Fraction]:
    a, b = p
    c, d = q
    return a * c - b * d, a * d + b * c


@pytest.mark.parametrize("op_name", ["add", "sub", "mul"])
def test_civ_binary_ops_enclose_exact_result(op_name):
    rng = random.Random(20260826 + hash(op_name) % 1000)
    exact = {
        "add": lambda p, q: (p[0] + q[0], p[1] + q[1]),
        "sub": lambda p, q: (p[0] - q[0], p[1] - q[1]),
        "mul": _cmul,
    }[op_name]
    applied = {
        "add": lambda a, b: a + b,
        "sub": lambda a, b: a - b,
        "mul": lambda a, b: a * b,
    }[op_name]

    checked = 0
    for _ in range(TRIALS):
        a, b = _rand_civ(rng), _rand_civ(rng)
        r = applied(a, b)
        if not (math.isfinite(r.re.lo) and math.isfinite(r.re.hi)
                and math.isfinite(r.im.lo) and math.isfinite(r.im.hi)):
            continue
        re_lo, re_hi = Fraction(r.re.lo), Fraction(r.re.hi)
        im_lo, im_hi = Fraction(r.im.lo), Fraction(r.im.hi)
        for p in _cpoints(a, rng):
            for q in _cpoints(b, rng):
                re_val, im_val = exact(p, q)
                assert re_lo <= re_val <= re_hi, (op_name, a, b, p, q, r)
                assert im_lo <= im_val <= im_hi, (op_name, a, b, p, q, r)
                checked += 1
    assert checked > 1000


def test_civ_conj_negates_imaginary_part_only():
    rng = random.Random(11)
    for _ in range(200):
        z = _rand_civ(rng)
        c = z.conj()
        assert c.re == z.re
        for im_lo, im_hi in ((c.im.lo, c.im.hi),):
            assert im_lo == -z.im.hi and im_hi == -z.im.lo


def test_civ_mag_ub_is_a_sound_upper_bound():
    rng = random.Random(2026)
    checked = 0
    for _ in range(TRIALS):
        z = _rand_civ(rng)
        bound = z.mag_ub
        if not math.isfinite(bound):
            continue
        for re, im in _cpoints(z, rng):
            # Compare squared magnitudes as exact Fractions to avoid any
            # float sqrt rounding in the test itself.
            assert re * re + im * im <= Fraction(bound) ** 2, (z, re, im, bound)
            checked += 1
    assert checked > 1000


def test_civ_exact_round_trips_a_python_complex():
    z = CIv.exact(3.5 - 2.25j)
    assert z.re == Iv.exact(3.5)
    assert z.im == Iv.exact(-2.25)


def test_civ_division_by_straddling_real_interval_abstains():
    with pytest.raises(IntervalError):
        CIv.exact(1 + 1j) / Iv(-1.0, 1.0)


def _rand_cvec(rng: random.Random, n: int) -> list[CIv]:
    return [_rand_civ(rng) for _ in range(n)]


def test_cdot_encloses_the_hermitian_inner_product():
    rng = random.Random(99)
    checked = 0
    for _ in range(400):
        n = rng.randint(1, 4)
        u, v = _rand_cvec(rng, n), _rand_cvec(rng, n)
        r = cdot(u, v)
        if not (math.isfinite(r.re.lo) and math.isfinite(r.re.hi)
                and math.isfinite(r.im.lo) and math.isfinite(r.im.hi)):
            continue
        re_lo, re_hi = Fraction(r.re.lo), Fraction(r.re.hi)
        im_lo, im_hi = Fraction(r.im.lo), Fraction(r.im.hi)
        # One sampled point per component is enough here; the pairwise-corner
        # exhaustion above already pins down `__mul__`/`__add__` themselves.
        u_pts = [_cpoints(a, rng)[0] for a in u]
        v_pts = [_cpoints(b, rng)[0] for b in v]
        acc = (Fraction(0), Fraction(0))
        for (ur, ui), (vr, vi) in zip(u_pts, v_pts):
            # conj(u_i) * v_i
            term = _cmul((ur, -ui), (vr, vi))
            acc = (acc[0] + term[0], acc[1] + term[1])
        assert re_lo <= acc[0] <= re_hi, (u, v, acc, r)
        assert im_lo <= acc[1] <= im_hi, (u, v, acc, r)
        checked += 1
    assert checked > 200


def test_cdot_of_a_vector_with_itself_is_real():
    rng = random.Random(5)
    for _ in range(200):
        n = rng.randint(1, 5)
        x = _rand_cvec(rng, n)
        r = cdot(x, x)
        if not (math.isfinite(r.im.lo) and math.isfinite(r.im.hi)):
            continue
        # <x|x> = sum |x_i|^2 is exactly real; the enclosure of its
        # imaginary part must therefore contain zero.
        assert r.im.contains_zero, (x, r)


def test_csqnorm_encloses_sum_of_squared_magnitudes_and_is_nonnegative():
    rng = random.Random(37)
    checked = 0
    for _ in range(400):
        n = rng.randint(1, 5)
        x = _rand_cvec(rng, n)
        r = csqnorm(x)
        assert r.lo >= 0.0
        if not (math.isfinite(r.lo) and math.isfinite(r.hi)):
            continue
        x_pts = [_cpoints(a, rng)[0] for a in x]
        exact = sum(re * re + im * im for re, im in x_pts)
        assert Fraction(r.lo) <= exact <= Fraction(r.hi), (x, exact, r)
        checked += 1
    assert checked > 200
