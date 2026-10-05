"""Runnable wrapper for the project's non-GUI core test suite.

Historically this file held ad-hoc assertions; it is now a thin entry point that
delegates to the pytest suite under ``tests/`` (the single source of truth)
while keeping ``python test_core.py`` working, as referenced by README/AGENTS.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def main() -> int:
    import pytest

    args = [
        "-q",
        "-p",
        "no:cacheprovider",
        "-c",
        os.path.join(ROOT, "pyproject.toml"),
        "--rootdir",
        ROOT,
        "-m",
        "not gui and not perf",
        os.path.join(ROOT, "tests"),
    ]
    print("MRI Reader - Core Functionality Tests (non-GUI)")
    print("=" * 50)
    code = pytest.main(args)
    print("=" * 50)
    return int(code)


if __name__ == "__main__":
    sys.exit(main())
