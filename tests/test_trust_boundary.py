"""The trust boundary is an invariant, so it gets a test, not a comment.

If someone later "helpfully" imports the producer into the checker to reuse
a Rayleigh quotient, this test fails. That is the entire mechanism by which
the guarantee stays true a year from now.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "certkit"
TRUSTED = {"checker.py", "interval.py", "schema.py", "operators.py", "banded.py",
           "backward_error.py"}
ALLOWED_INTERNAL = {
    "interval", "schema", "operators", "banded", "backward_error",
    "certkit.interval", "certkit.schema", "certkit.operators",
    "certkit.banded", "certkit.backward_error",
}
BANNED_EXTERNAL = {"numpy", "scipy", "certkit.producer", "producer"}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
    return names


def test_trusted_modules_do_not_import_the_producer():
    for name in TRUSTED:
        for mod in _imports(PKG / name):
            assert mod not in BANNED_EXTERNAL, f"{name} imports {mod}"


def test_trusted_modules_import_only_stdlib_and_each_other():
    stdlib = set(sys.stdlib_module_names)
    for name in TRUSTED:
        for mod in _imports(PKG / name):
            root = mod.split(".")[0]
            assert (
                mod in ALLOWED_INTERNAL or root in stdlib or root == ""
            ), f"{name} imports third-party module {mod}"


def test_checker_runs_in_a_process_where_numpy_is_unimportable():
    """The checker must be shippable and auditable on its own."""
    script = """
import sys, json
class Block:
    def find_module(self, name, path=None):
        if name.split('.')[0] in ('numpy', 'scipy'):
            raise ImportError('blocked: ' + name)
sys.meta_path.insert(0, Block())
from certkit.checker import check
cert = json.load(open(sys.argv[1])); op = json.load(open(sys.argv[2]))
v = check(cert, op)
print(v.status)
"""
    import json
    import tempfile

    import numpy as np

    from certkit.producer import certify_lambda_min

    rng = np.random.default_rng(2)
    m = rng.standard_normal((5, 5))
    cert, op = certify_lambda_min(((m + m.T) / 2).tolist())

    with tempfile.TemporaryDirectory() as d:
        cp, op_p = Path(d) / "c.json", Path(d) / "o.json"
        cp.write_text(json.dumps(cert))
        op_p.write_text(json.dumps(op))
        out = subprocess.run(
            [sys.executable, "-c", script, str(cp), str(op_p)],
            capture_output=True,
            text=True,
            cwd=str(PKG.parent),
        )
        assert out.returncode == 0, out.stderr
        assert out.stdout.strip() == "VERIFIED", out.stdout + out.stderr


def test_witness_carries_no_producer_computed_bound():
    """A minimal witness cannot leak a number the checker might lean on."""
    import numpy as np

    from certkit.producer import certify_lambda_min

    rng = np.random.default_rng(4)
    m = rng.standard_normal((4, 4))
    cert, _ = certify_lambda_min(((m + m.T) / 2).tolist())
    assert set(cert["witness"]) <= {"rule", "vector", "beta"}
