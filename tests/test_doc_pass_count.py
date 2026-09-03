"""Pinned pytest pass-counts in checked-in docs drift as tests are added.

certkit-j82, certkit-shj, and certkit-bba each fixed a doc that had fallen
out of sync with the real count. This test parses every doc location that
still pins a literal count and asserts it against a live collection, so the
fourth drift fails CI instead of waiting for a human to notice.

Locations that instead say "re-measure yourself" (sandbox-prompt.md, per
certkit-shj) carry no number to check and are intentionally not listed here.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOC_PATTERNS = {
    "CLAUDE.md": re.compile(r"pytest tests\s+# (\d+) passing"),
    "AGENTS.md": re.compile(r"pytest tests\s+# (\d+) passing"),
    "README.md": re.compile(r"tests/\s+(\d+) tests:"),
}


def _collected_test_count() -> int:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "--collect-only", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    match = re.search(r"^(\d+) tests? collected", result.stdout, re.MULTILINE)
    assert match, f"could not parse collected test count from:\n{result.stdout}"
    return int(match.group(1))


def test_doc_pinned_pass_counts_match_collected_count():
    actual = _collected_test_count()
    mismatches = []
    for filename, pattern in DOC_PATTERNS.items():
        text = (ROOT / filename).read_text()
        match = pattern.search(text)
        assert match, f"{filename}: expected pattern {pattern.pattern!r} not found"
        stated = int(match.group(1))
        if stated != actual:
            mismatches.append(f"{filename}: doc says {stated}, live collection says {actual}")
    assert not mismatches, "stale pytest counts:\n" + "\n".join(mismatches)
