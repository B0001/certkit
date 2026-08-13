"""certkit -- certified numerical claims with an independent checker.

Producer emits (claim, witness). Checker re-derives the claim from the witness
in rigorous interval arithmetic and returns VERIFIED or ABSTAIN. The two sides
share only the certificate format.
"""

from .backward_error import count_eigenvalues_below_backward
from .banded import count_eigenvalues_below_banded
from .checker import (
    Verdict,
    bundle_verdict,
    check,
    check_bundle,
    count_eigenvalues_below,
)
from .interval import Iv, IntervalError
from .operators import (
    Operator,
    decode_operator,
    encode_csr,
    encode_dense,
    encode_pauli,
    operator_ref,
)
from .schema import SCHEMA_VERSION, SchemaError

__all__ = [
    "Verdict",
    "check",
    "check_bundle",
    "bundle_verdict",
    "count_eigenvalues_below",
    "count_eigenvalues_below_banded",
    "count_eigenvalues_below_backward",
    "Iv",
    "IntervalError",
    "Operator",
    "decode_operator",
    "encode_dense",
    "encode_csr",
    "encode_pauli",
    "operator_ref",
    "SCHEMA_VERSION",
    "SchemaError",
]
