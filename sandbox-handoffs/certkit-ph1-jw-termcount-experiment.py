"""
Scratch experiment for certkit-ph1 (session 5).

Session 4's handoff reasoned, but did NOT check against actual computation,
that JW-mapped chemistry Hamiltonians have Pauli term count T ~ O(q^4),
comparable to or exceeding n = 2^q for q in [8,14] -- the bead's relevant
range -- and concluded that a rule exploiting "low term count" is therefore
not a promising angle in that range.

This script actually performs the Jordan-Wigner transform on a randomly
generated real electronic-structure-shaped Hamiltonian (one- and two-body
terms with the standard 8-fold real-orbital symmetry) for various qubit
counts M, and counts the number of *distinct, non-cancelling* Pauli strings
that survive after combining like terms -- rather than trusting the naive
asymptotic O(M^4) formula, which could in principle overcount if many
fermionic terms collide onto the same Pauli string.

No numpy needed -- plain Python complex arithmetic and dicts.
"""
import random

def mul_pauli_char(a, b):
    # returns (phase, resulting_char) for single-qubit Pauli a*b
    if a == "I":
        return 1.0, b
    if b == "I":
        return 1.0, a
    if a == b:
        return 1.0, "I"
    table = {
        ("X", "Y"): (1j, "Z"), ("Y", "X"): (-1j, "Z"),
        ("Y", "Z"): (1j, "X"), ("Z", "Y"): (-1j, "X"),
        ("Z", "X"): (1j, "Y"), ("X", "Z"): (-1j, "Y"),
    }
    return table[(a, b)]

def mul_strings(s1, c1, s2, c2):
    # multiply two Pauli strings (tuples of chars) with coefficients
    phase = 1.0
    out = []
    for a, b in zip(s1, s2):
        p, r = mul_pauli_char(a, b)
        phase *= p
        out.append(r)
    return tuple(out), c1 * c2 * phase

def jw_ladder(p, M, dagger):
    # a_p^dagger or a_p as a list of (string, coeff)
    zstring = ["Z"] * p + ["I"] * (M - p)
    xpart = list(zstring); xpart[p] = "X"
    ypart = list(zstring); ypart[p] = "Y"
    # a_p^dagger = 0.5*(X_p - i Y_p) * Z-string;  a_p = 0.5*(X_p + i Y_p) * Z-string
    sign = -1j if dagger else 1j
    return [(tuple(xpart), 0.5), (tuple(ypart), 0.5 * sign)]

def mul_terms(t1, t2):
    out = {}
    for s1, c1 in t1:
        for s2, c2 in t2:
            s, c = mul_strings(s1, c1, s2, c2)
            out[s] = out.get(s, 0) + c
    return list(out.items())

def add_into(acc, terms, coeff):
    for s, c in terms:
        acc[s] = acc.get(s, 0) + coeff * c

def count_terms(M, seed, two_body=True, tol=1e-9):
    rng = random.Random(seed)
    acc = {}

    # one-body h_pq a_p^dagger a_q, hermitian h_pq = h_qp (real orbitals)
    h1 = [[0.0] * M for _ in range(M)]
    for p in range(M):
        for q in range(p, M):
            v = rng.uniform(-1, 1)
            h1[p][q] = v
            h1[q][p] = v
    for p in range(M):
        for q in range(M):
            if h1[p][q] == 0.0:
                continue
            terms = mul_terms(jw_ladder(p, M, True), jw_ladder(q, M, False))
            add_into(acc, terms, h1[p][q])

    if two_body:
        # two-body (1/2) h_pqrs a_p^dagger a_q^dagger a_r a_s
        # real-orbital 8-fold symmetry: h_pqrs = h_qpsr = h_rspq = h_srqp
        # generate independent values for canonical (p<q or p==q, handled via
        # simple restriction p<=q, r<=s, (p,q)<=(r,s)) representatives only,
        # to keep the random Hamiltonian at least plausibly Hermitian-shaped;
        # exact chemical symmetry isn't needed for a term-count experiment.
        seen = {}
        for p in range(M):
            for q in range(M):
                for r in range(M):
                    for s in range(M):
                        if p == q or r == s:
                            continue
                        key = tuple(sorted([(p, q), (r, s)]))
                        # canonical symmetry class: (p,q,r,s) ~ (q,p,s,r)
                        canon = min((p, q, r, s), (q, p, s, r))
                        if canon not in seen:
                            seen[canon] = rng.uniform(-1, 1)
                        v = seen[canon]
                        if (p, q, r, s) not in [canon, (canon[1], canon[0], canon[3], canon[2])]:
                            continue
                        if v == 0.0:
                            continue
                        terms = mul_terms(
                            mul_terms(jw_ladder(p, M, True), jw_ladder(q, M, True)),
                            mul_terms(jw_ladder(r, M, False), jw_ladder(s, M, False)),
                        )
                        add_into(acc, terms, 0.5 * v)

    nonzero = sum(1 for c in acc.values() if abs(c) > tol)
    return nonzero, len(acc)

if __name__ == "__main__":
    # M=18 takes ~4s; larger M grows roughly as M^5 per the nested p,q,r,s
    # loop composing two 2-term ladder products into a 4x4=16-term product,
    # so M=20+ is left out to keep this a quick rerun, not a benchmark.
    print(f"{'M':>4} {'n=2^M':>10} {'T (1-body only)':>18} {'T (1+2-body)':>14} {'T/n':>10}")
    for M in [4, 6, 8, 10, 12, 14, 16, 18]:
        t1, _ = count_terms(M, seed=1, two_body=False)
        t2, _ = count_terms(M, seed=1, two_body=True)
        n = 1 << M
        print(f"{M:>4} {n:>10} {t1:>18} {t2:>14} {t2 / n:>10.4f}")
