"""Shared pytest configuration for the MRI Reader suite.

This file is intentionally self-contained: it sets the offscreen Qt platform
*before* any Qt import, puts the project root (and this directory) on
``sys.path`` so ``python -m pytest`` works even without the installed package,
and exposes the session-scoped ``qapp`` fixture.
"""

from __future__ import annotations

import os
import sys

# Qt must be told to run headless before PyQt5 is imported anywhere.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _path in (_ROOT, _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    """Session-scoped, offscreen ``QApplication`` shared by every GUI test."""
    pytest.importorskip("PyQt5", reason="PyQt5 is required for GUI tests")
    from PyQt5.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
