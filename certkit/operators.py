"""Operator backends.

The checker never sees a matrix. It sees an `Operator` -- something it can
apply to an interval vector and extract rows from. That is the whole
interface, and it is exactly what a Krylov method needs, so the same
certificate machinery covers a 6x6 test matrix and a matrix-free qubit
Hamiltonian of dimension 2^q.

Three backends:

    dense_symmetric_real       explicit rows
    sparse_csr_symmetric_real  CSR, symmetry checked exactly
    pauli_sum_real             matrix-free; never materialised

Each backend must supply:

    apply(x)          interval matvec
    row(i)            column -> interval, for Gershgorin
    interval_rows()   enclosed rows for O(n^3) routes, or None if refused
    dense_rows()      float rows, for the untrusted producer only

`interval_rows()` returning None is not a limitation to route around. It is the
backend telling the checker that one discharge route (inertia counting, which
is O(n^3)) is unavailable, and the checker must then find another route or
abstain.

Note that the rows are *intervals*, not floats. A Pauli-sum diagonal entry is a
sum of many coefficients and is not exactly representable, so a float row would
describe a slightly different operator than the one the certificate is about --
and an inertia count on the wrong matrix is exactly the kind of silent
substitution this design exists to prevent.

This module is TRUSTED: standard library only, no producer imports.
"""

from __future__ import annotations

from typing import Any, Iterator, Sequence

from .interval import Iv, IntervalError
from .schema import SchemaError, digest, f2h, h2f, require

# Refuse to materialise anything larger than this for O(n^3) routes. Interval
# LDL^T is cubic in pure Python, so the ceiling is low and deliberately so: a
# route that would take an hour is not a route, and pretending otherwise just
# moves the failure somewhere less visible.
DENSE_LIMIT = 160


class Operator:
    """Interface. Subclasses are constructed only by `decode_operator`."""

    kind: str = ""
    n: int = 0

    def apply(self, x: Sequence[Iv]) -> list[Iv]:
        raise NotImplementedError

    def row(self, i: int) -> dict[int, Iv]:
        raise NotImplementedError

    def interval_rows(self) -> list[list[Iv]] | None:
        """Enclosures of the explicit rows, or None if materialising is refused."""
        return None

    def dense_rows(self) -> list[list[float]] | None:
        """Float rows. For the untrusted producer; the checker uses intervals."""
        return None

    def check_symmetric(self) -> None:
        """Raise SchemaError unless the operator is exactly symmetric."""
        raise NotImplementedError


# -- dense ----------------------------------------------------------------
class DenseSymmetric(Operator):
    kind = "dense_symmetric_real"

    def __init__(self, rows: list[list[float]]):
        self.rows = rows
        self.n = len(rows)
        self._iv = [[Iv.exact(v) for v in r] for r in rows]

    def apply(self, x: Sequence[Iv]) -> list[Iv]:
        if len(x) != self.n:
            raise IntervalError("dimension mismatch")
        out = []
        for r in self._iv:
            acc = Iv.exact(0.0)
            for a, b in zip(r, x):
                acc = acc + a * b
            out.append(acc)
        return out

    def row(self, i: int) -> dict[int, Iv]:
        return {j: self._iv[i][j] for j in range(self.n)}

    def interval_rows(self) -> list[list[Iv]] | None:
        return self._iv if self.n <= DENSE_LIMIT else None

    def dense_rows(self) -> list[list[float]] | None:
        return self.rows if self.n <= DENSE_LIMIT else None

    def check_symmetric(self) -> None:
        for i in range(self.n):
            for j in range(i):
                if self.rows[i][j] != self.rows[j][i]:
                    raise SchemaError("operator is not exactly symmetric")


# -- sparse CSR -----------------------------------------------------------
class SparseCSRSymmetric(Operator):
    kind = "sparse_csr_symmetric_real"

    def __init__(self, n: int, indptr: list[int], indices: list[int], data: list[float]):
        self.n = n
        self.indptr = indptr
        self.indices = indices
        self.data = data
        self._iv = [Iv.exact(v) for v in data]

    def _entries(self, i: int) -> Iterator[tuple[int, int]]:
        yield from ((k, self.indices[k]) for k in range(self.indptr[i], self.indptr[i + 1]))

    def apply(self, x: Sequence[Iv]) -> list[Iv]:
        if len(x) != self.n:
            raise IntervalError("dimension mismatch")
        out = []
        for i in range(self.n):
            acc = Iv.exact(0.0)
            for k, j in self._entries(i):
                acc = acc + self._iv[k] * x[j]
            out.append(acc)
        return out

    def row(self, i: int) -> dict[int, Iv]:
        acc: dict[int, Iv] = {}
        for k, j in self._entries(i):
            acc[j] = acc[j] + self._iv[k] if j in acc else self._iv[k]
        return acc

    def interval_rows(self) -> list[list[Iv]] | None:
        if self.n > DENSE_LIMIT:
            return None
        rows = [[Iv.exact(0.0)] * self.n for _ in range(self.n)]
        for i in range(self.n):
            for j, v in self.row(i).items():
                rows[i][j] = v
        return rows

    def dense_rows(self) -> list[list[float]] | None:
        if self.n > DENSE_LIMIT:
            return None
        rows = [[0.0] * self.n for _ in range(self.n)]
        for i in range(self.n):
            for k, j in self._entries(i):
                rows[i][j] += self.data[k]
        return rows

    def check_symmetric(self) -> None:
        seen: dict[tuple[int, int], float] = {}
        for i in range(self.n):
            for k, j in self._entries(i):
                seen[(i, j)] = seen.get((i, j), 0.0) + self.data[k]
        for (i, j), v in seen.items():
            if seen.get((j, i), 0.0) != v:
                raise SchemaError(f"sparse operator asymmetric at ({i}, {j})")


# -- matrix-free Pauli sum ------------------------------------------------
class PauliSumReal(Operator):
    """H = sum_t c_t P_t, with each P_t a Pauli string over q qubits.

    A Pauli string acts on a computational basis state as a bit-flip plus a
    phase, so `apply` costs O(terms * 2^q) with no matrix anywhere. Terms are
    required to carry an even number of Y factors, which is exactly the
    condition for the string to be real -- and a real Hermitian matrix is
    symmetric, which is what the eigenvalue rules assume.
    """

    kind = "pauli_sum_real"

    def __init__(self, qubits: int, terms: list[tuple[float, str]]):
        self.qubits = qubits
        self.n = 1 << qubits
        self.terms = terms
        self._compiled = []
        for coeff, s in terms:
            mask = zy = ny = 0
            for k, p in enumerate(s):
                bit = 1 << k
                if p in ("X", "Y"):
                    mask |= bit
                if p in ("Z", "Y"):
                    zy |= bit
                if p == "Y":
                    ny += 1
            sign = -1.0 if (ny // 2) % 2 else 1.0
            self._compiled.append((Iv.exact(coeff * sign), mask, zy))

    def _phase_parity(self, j: int, zy: int) -> int:
        return bin(j & zy).count("1") & 1

    def apply(self, x: Sequence[Iv]) -> list[Iv]:
        if len(x) != self.n:
            raise IntervalError("dimension mismatch")
        out = [Iv.exact(0.0)] * self.n
        for c, mask, zy in self._compiled:
            for i in range(self.n):
                j = i ^ mask
                term = c * x[j]
                if self._phase_parity(j, zy):
                    term = -term
                out[i] = out[i] + term
        return out

    def row(self, i: int) -> dict[int, Iv]:
        acc: dict[int, Iv] = {}
        for c, mask, zy in self._compiled:
            j = i ^ mask
            term = -c if self._phase_parity(j, zy) else c
            acc[j] = acc[j] + term if j in acc else term
        return acc

    def interval_rows(self) -> list[list[Iv]] | None:
        if self.n > DENSE_LIMIT:
            return None
        rows = [[Iv.exact(0.0)] * self.n for _ in range(self.n)]
        for i in range(self.n):
            for j, v in self.row(i).items():
                rows[i][j] = v
        return rows

    def dense_rows(self) -> list[list[float]] | None:
        if self.n > DENSE_LIMIT:
            return None
        rows = [[0.0] * self.n for _ in range(self.n)]
        for i in range(self.n):
            for j, v in self.row(i).items():
                rows[i][j] = 0.5 * (v.lo + v.hi)
        return rows

    def check_symmetric(self) -> None:
        for coeff, s in self.terms:
            if len(s) != self.qubits or any(p not in "IXYZ" for p in s):
                raise SchemaError(f"malformed Pauli string {s!r}")
            if s.count("Y") % 2:
                raise SchemaError(
                    f"Pauli string {s!r} has an odd number of Y factors and is not real"
                )


# -- encode / decode ------------------------------------------------------
def encode_dense(rows: Sequence[Sequence[float]]) -> dict:
    n = len(rows)
    if n == 0 or any(len(r) != n for r in rows):
        raise SchemaError("operator must be a non-empty square matrix")
    return {
        "kind": "dense_symmetric_real",
        "n": n,
        "rows": [[f2h(v) for v in row] for row in rows],
    }


def encode_csr(n: int, indptr, indices, data) -> dict:
    return {
        "kind": "sparse_csr_symmetric_real",
        "n": int(n),
        "indptr": [int(v) for v in indptr],
        "indices": [int(v) for v in indices],
        "data": [f2h(float(v)) for v in data],
    }


def encode_pauli(qubits: int, terms: Sequence[tuple[float, str]]) -> dict:
    return {
        "kind": "pauli_sum_real",
        "qubits": int(qubits),
        "terms": [{"coeff": f2h(float(c)), "string": str(s)} for c, s in terms],
    }


def _decode_dense(obj: Any) -> DenseSymmetric:
    n, rows = obj.get("n"), obj.get("rows")
    require(isinstance(n, int) and isinstance(rows, list) and len(rows) == n,
            "operator shape mismatch")
    out = []
    for r in rows:
        require(isinstance(r, list) and len(r) == n, "operator shape mismatch")
        out.append([h2f(v) for v in r])
    return DenseSymmetric(out)


def _decode_csr(obj: Any) -> SparseCSRSymmetric:
    n, indptr, indices, data = (obj.get(k) for k in ("n", "indptr", "indices", "data"))
    require(isinstance(n, int) and n > 0, "bad sparse dimension")
    require(isinstance(indptr, list) and len(indptr) == n + 1, "bad indptr length")
    require(isinstance(indices, list) and isinstance(data, list), "bad CSR arrays")
    require(len(indices) == len(data), "indices/data length mismatch")
    require(all(isinstance(v, int) for v in indptr + indices), "non-integer CSR index")
    require(indptr[0] == 0 and indptr[-1] == len(data), "indptr does not span data")
    require(all(indptr[i] <= indptr[i + 1] for i in range(n)), "indptr not monotone")
    require(all(0 <= j < n for j in indices), "column index out of range")
    return SparseCSRSymmetric(n, indptr, indices, [h2f(v) for v in data])


def _decode_pauli(obj: Any) -> PauliSumReal:
    q, terms = obj.get("qubits"), obj.get("terms")
    require(isinstance(q, int) and 0 < q <= 24, "bad qubit count")
    require(isinstance(terms, list) and terms, "missing Pauli terms")
    out = []
    for t in terms:
        require(isinstance(t, dict), "malformed Pauli term")
        out.append((h2f(t.get("coeff")), t.get("string")))
    return PauliSumReal(q, out)


_DECODERS = {
    "dense_symmetric_real": _decode_dense,
    "sparse_csr_symmetric_real": _decode_csr,
    "pauli_sum_real": _decode_pauli,
}


def decode_operator(obj: Any) -> Operator:
    if not isinstance(obj, dict):
        raise SchemaError("operator encoding is not an object")
    kind = obj.get("kind")
    if kind not in _DECODERS:
        raise SchemaError(f"unsupported operator kind {kind!r}")
    op = _DECODERS[kind](obj)
    op.check_symmetric()
    return op


def operator_ref(obj: dict) -> str:
    return "blake2b16:" + digest(obj)
