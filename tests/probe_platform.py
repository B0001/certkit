#!/usr/bin/env python3
"""Probe the floating-point platform assumptions in certkit's TCB.md section 1.

Stdlib only. Fixed seed. Every oracle is exact integer/rational arithmetic;
the rounding oracle `rnd` is implemented here from integers (divmod + ldexp of
an exactly representable value), so it shares nothing with the FPU under test.
Exit status 0 iff every check passes.
"""
import math
import platform
import random
import struct
import sys
import sysconfig

SEED = 20260923
MAXF = sys.float_info.max


def bits(x):
    return struct.unpack("<Q", struct.pack("<d", x))[0]


def from_bits(b):
    return struct.unpack("<d", struct.pack("<Q", b))[0]


def ratio(x):
    return x.as_integer_ratio()  # exact; denominator is a power of two


def rnd(num, den):
    """Exact rational num/den (den > 0) -> nearest binary64, ties to even."""
    if num == 0:
        return 0.0
    neg, n = num < 0, abs(num)
    k = n.bit_length() - den.bit_length() - 52
    while True:
        kk = max(k, -1074)
        q, r = divmod(n, den << kk) if kk >= 0 else divmod(n << -kk, den)
        if kk == k and q.bit_length() < 53:
            k -= 1
            continue
        break
    d = den << kk if kk >= 0 else den  # the divisor r is a remainder of
    if 2 * r > d or (2 * r == d and q & 1):
        q += 1
    try:
        v = math.ldexp(q, kk)  # q <= 2^53, so exact unless it overflows
    except OverflowError:
        v = math.inf
    return -v if neg else v


def exact(op, a, b):
    (p, q), (r, s) = ratio(a), ratio(b)
    if op == "+":
        return p * s + r * q, q * s
    if op == "-":
        return p * s - r * q, q * s
    if op == "*":
        return p * r, q * s
    num, den = p * s, q * r  # "/"
    return (-num, -den) if den < 0 else (num, den)


def report(name, n, fails):
    first = f"  first counterexample: {fails[0]}" if fails else ""
    print(f"{'PASS' if not fails else 'FAIL'}  {name}: {n} checked, {len(fails)} failures{first}")
    return not fails


def rand_finite(rng, lo=1, hi=0x7FEFFFFFFFFFFFFF, signed=False):
    x = from_bits(rng.randint(lo, hi))
    return -x if signed and rng.random() < 0.5 else x


# -- 1. math.sqrt -----------------------------------------------------------
def check_sqrt(rng):
    xs = []
    xs += [math.ldexp(1.0, e) for e in range(-1074, 1024)]            # all powers of 2 (incl. 4^k)
    xs += [math.ldexp(1.0, e) for e in range(-1074, 1024, 2)]         # powers of 4 again, explicitly
    xs += [from_bits(rng.randint(1, 0x000FFFFFFFFFFFFF)) for _ in range(100_000)]  # subnormals
    for _ in range(100_000):                                          # exact squares and neighbours
        r = rand_finite(rng, 0x2000000000000000, 0x5FE0000000000000)
        r = math.ldexp(math.floor(math.ldexp(math.frexp(r)[0], 26)), math.frexp(r)[1] - 26)
        sq = r * r
        xs += [sq, math.nextafter(sq, 0.0), math.nextafter(sq, math.inf)]
    while len(xs) < 1_050_000:                                        # uniform over bit patterns = all binades
        xs.append(rand_finite(rng))
    fails = []
    for x in xs:
        r = math.sqrt(x)
        a, b = ratio(x)
        lo, hi = math.nextafter(r, 0.0), math.nextafter(r, math.inf)
        (p1, q1), (p0, q0), (p2, q2) = ratio(lo), ratio(r), ratio(hi)
        # midpoints (lo+r)/2 and (r+hi)/2 as num/den; x must lie strictly between their squares
        D = max(q0, q1); mlo = (p1 * (D // q1) + p0 * (D // q0), 2 * D)
        D = max(q0, q2); mhi = (p0 * (D // q0) + p2 * (D // q2), 2 * D)
        # ties are impossible for sqrt of a double, so strict inequalities are exact
        if not (mlo[0] ** 2 * b < a * mlo[1] ** 2 and a * mhi[1] ** 2 < mhi[0] ** 2 * b):
            fails.append(f"sqrt({x.hex()}) = {r.hex()}")
    special = [(0.0, 0.0), (-0.0, -0.0), (math.inf, math.inf)]
    for x, want in special:
        if bits(math.sqrt(x)) != bits(want):
            fails.append(f"sqrt({x!r}) = {math.sqrt(x)!r}")
    if not math.isnan(math.sqrt(math.nan)):
        fails.append("sqrt(nan) not nan")
    try:
        math.sqrt(-1.0)
        fails.append("sqrt(-1) did not raise")
    except ValueError:
        pass
    return report("math.sqrt correctly rounded", len(xs) + 5, fails)


# -- 2. math.nextafter ------------------------------------------------------
def key(x):  # monotone integer key over finite doubles and infinities; +0 and -0 both map to 0
    b = bits(x)
    return b if b < 1 << 63 else -(b - (1 << 63))


def unkey(k, neg_zero):
    if k == 0:
        return -0.0 if neg_zero else 0.0
    return from_bits(k) if k > 0 else from_bits((1 << 63) | -k)


def want_next(x, toward):
    if math.isnan(x) or math.isnan(toward):
        return math.nan
    if x == toward:
        return toward  # C99/IEEE: returns y, so nextafter(0.0, -0.0) is -0.0
    step = 1 if toward > x else -1
    k = key(x) + step
    # stepping onto zero keeps the sign of the side we came from
    return unkey(k, neg_zero=(k == 0 and x < 0))


def check_nextafter(rng):
    edges = [0.0, -0.0, 5e-324, -5e-324, from_bits(0x000FFFFFFFFFFFFF), from_bits(0x0010000000000000),
             1.0, -1.0, MAXF, -MAXF, math.inf, -math.inf, 2.0 ** -1022, -(2.0 ** -1022)]
    xs = edges + [rand_finite(rng, signed=True) for _ in range(500_000)] \
        + [rand_finite(rng, 1, 0x000FFFFFFFFFFFFF, signed=True) for _ in range(100_000)]
    fails, n = [], 0
    for x in xs:
        targets = (math.inf, -math.inf, x) if x not in edges else edges + [math.nan]
        for t in targets:
            got, want = math.nextafter(x, t), want_next(x, t)
            n += 1
            if not ((math.isnan(got) and math.isnan(want)) or bits(got) == bits(want)):
                fails.append(f"nextafter({x!r}, {t!r}) = {got!r}, want {want!r}")
    return report("math.nextafter == struct bit step", n, fails)


# -- 3. no FMA contraction / extended precision in a*b+c --------------------
def check_fma(rng):
    cases = [(1.0 + 2.0 ** -27, 1.0 - 2.0 ** -27, -1.0), (0.1, 10.0, -1.0), (1.0 / 3, 3.0, -1.0)]
    while len(cases) < 100_000:
        a, b = rand_finite(rng, 0x3000000000000000, 0x4F00000000000000, True), \
            rand_finite(rng, 0x3000000000000000, 0x4F00000000000000, True)
        c = -(a * b) if rng.random() < 0.5 else -(a * b) * (1 + rng.random() * 2.0 ** -20)
        cases.append((a, b, c))
    fails, discriminating, fma_differs, fma_fails = [], 0, 0, []
    has_fma = hasattr(math, "fma")
    for a, b, c in cases:
        (p, q), (r, s), (u, v) = ratio(a), ratio(b), ratio(c)
        fused = rnd(p * r * v + u * q * s, q * s * v)          # round(a*b + c)
        ab = rnd(p * r, q * s)
        (m, w) = ratio(ab)
        unfused = rnd(m * v + u * w, w * v)                     # round(round(a*b) + c)
        if bits(fused) != bits(unfused) and not (fused == 0 == unfused):
            discriminating += 1
        for expr, got in (("a*b+c", a * b + c), ("c+a*b", c + a * b), ("a*b-(-c)", a * b - (-c))):
            if bits(got) != bits(unfused) and not (got == 0 == unfused):
                fails.append(f"{expr} a={a.hex()} b={b.hex()} c={c.hex()}: got {got.hex()}, "
                             f"unfused {unfused.hex()}, fused {fused.hex()}")
        if has_fma:
            f = math.fma(a, b, c)
            if bits(f) != bits(fused) and not (f == 0 == fused):
                fma_fails.append(f"math.fma({a.hex()},{b.hex()},{c.hex()}) = {f.hex()}, want {fused.hex()}")
            if bits(f) != bits(a * b + c):
                fma_differs += 1
    # extended-range intermediate: in binary64 1e300*1e300 overflows; an 80-bit or fused
    # evaluation would bring it back to 1e300
    big = [1e300, 1e300, 1e-300]
    if big[0] * big[1] * big[2] != math.inf:
        fails.append(f"1e300*1e300*1e-300 = {big[0] * big[1] * big[2]!r}, want inf (extended range)")
    ok = report("a*b+c == round(round(a*b)+c) (no contraction/extended precision)", len(cases) * 3 + 1, fails)
    print(f"INFO  cases where fused != unfused (probe teeth): {discriminating}/{len(cases)}")
    if has_fma:
        ok &= report("math.fma == round(a*b+c) (oracle agrees with real FMA)", len(cases), fma_fails)
        print(f"INFO  math.fma differs from Python a*b+c on {fma_differs}/{len(cases)} cases")
    else:
        print("INFO  math.fma not available on this Python (added in 3.13); teeth shown by the count above")
    return ok and discriminating > len(cases) // 2


# -- 4. + - * / correctly rounded -------------------------------------------
def tie_pairs(rng, n):
    out = []
    while len(out) < n:  # a + b lands exactly on a midpoint: b is an odd multiple of half an ulp of a
        e = rng.randint(-1000, 1000)
        a = math.ldexp(1.0 + rng.getrandbits(52) * 2.0 ** -52, e)
        b = math.ldexp(2 * rng.randint(0, 2 ** 20) + 1, e - 53)
        out.append(("+", a, b))
        out.append(("-", a, -b))
        p = rng.getrandbits(27) | (1 << 26) | 1  # odd*odd products with 54-55 bits: some are exact ties
        q = rng.getrandbits(28) | (1 << 27) | 1
        out.append(("*", math.ldexp(p, rng.randint(-500, 450)), math.ldexp(q, rng.randint(-500, 450))))
    return out


def check_arith(rng):
    cases = []
    for _ in range(100_000):  # fully random: every binade, subnormals, overflow and underflow
        cases.append((rng.choice("+-*/"), rand_finite(rng, signed=True), rand_finite(rng, signed=True)))
    for _ in range(100_000):  # nearby exponents, so the rounding decision is non-trivial
        a = rand_finite(rng, signed=True)
        eb = min(max(math.frexp(a)[1] + rng.randint(-60, 60), -1073), 1023)
        b = math.copysign(math.ldexp(0.5 + rng.random() / 2, eb), rng.choice((-1.0, 1.0)))
        cases.append((rng.choice("+-*/"), a, b))
    for _ in range(20_000):  # subnormal results via products/quotients
        cases.append((rng.choice("*/"), rand_finite(rng, 0x0010000000000000, 0x2000000000000000, True),
                      rand_finite(rng, 0x1000000000000000, 0x7FE0000000000000, True) if rng.random() < 0.5
                      else rand_finite(rng, 0x0010000000000000, 0x2000000000000000, True)))
    cases += tie_pairs(rng, 20_000)
    ops = {"+": lambda a, b: a + b, "-": lambda a, b: a - b, "*": lambda a, b: a * b, "/": lambda a, b: a / b}
    fails, ties = [], 0
    for op, a, b in cases:
        num, den = exact(op, a, b)
        want = rnd(num, den)
        if num == 0:
            want = 0.0  # exact zero sum is +0 in round-to-nearest (operands here are never both zero)
        elif want == 0:
            want = math.copysign(0.0, num)
        got = ops[op](a, b)
        if want not in (0.0, math.inf, -math.inf):  # count exact midpoint cases
            x1, y1 = ratio(want)
            for nb in (math.nextafter(want, -math.inf), math.nextafter(want, math.inf)):
                x2, y2 = ratio(nb)  # tie iff num/den == (want + nb) / 2, cross-multiplied
                ties += num * 2 * y1 * y2 == den * (x1 * y2 + x2 * y1)
        if bits(got) != bits(want):
            fails.append(f"{a.hex()} {op} {b.hex()} = {got.hex()}, want {want.hex()}")
    ok = report("+ - * / correctly rounded (vs exact rationals, ties-to-even)", len(cases), fails)
    print(f"INFO  exact round-half-even ties exercised: {ties}")
    return ok and ties > 1000


def main():
    print(f"python   {sys.version}")
    print(f"impl     {platform.python_implementation()} {platform.python_compiler()}")
    print(f"platform {platform.platform()} machine={platform.machine()}")
    print(f"CFLAGS   {sysconfig.get_config_var('CFLAGS')}")
    print(f"float    {sys.float_info}")
    print(f"repr     {sys.float_repr_style}")
    print(f"seed     {SEED}")
    rng = random.Random(SEED)
    results = [check_sqrt(rng), check_nextafter(rng), check_fma(rng), check_arith(rng)]
    print("ALL PASS" if all(results) else "SOME CHECKS FAILED")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
