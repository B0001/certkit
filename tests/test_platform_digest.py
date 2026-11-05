"""tests/platform_digest.txt must list every conformance case, in manifest order.

CI's conformance job diffs `python tests/digest_outputs.py` against this golden
(recorded on macOS arm64, certkit-8hn). certkit-2sc added two cases without
regenerating it, and CI stayed red for five weeks while this suite stayed green
(certkit-2pj). This checks coverage only; re-deriving the hashes is CI's job.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_golden_digest_lists_every_conformance_case():
    manifest = json.loads((ROOT / "conformance" / "manifest.json").read_text())
    golden = (ROOT / "tests" / "platform_digest.txt").read_text().splitlines()
    assert [line.partition(" ")[0] for line in golden] == [
        case["name"] for case in manifest["cases"]
    ] + ["OVERALL"], (
        "tests/platform_digest.txt is out of step with conformance/manifest.json; "
        "regenerate it on an arm64 Mac: python tests/digest_outputs.py > tests/platform_digest.txt"
    )
