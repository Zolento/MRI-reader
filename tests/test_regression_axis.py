"""Axis regression table shared with the frozen ``.artifacts/gui_smoke.py`` gate.

``.artifacts/`` is gitignored, so the literal expectations live in
``tests/_helpers.py`` (also used by ``test_gui_smoke.py``).  When the frozen gate
is present we additionally parse its expectations block and fail if the two
tables ever disagree, so the two gates cannot silently drift apart.
"""

from __future__ import annotations

import os
import re

import numpy as np
import pytest
from _helpers import ASYMMETRIC_SHAPE, AXIS_EXPECTATIONS, ROOT

from src.core import views

GUI_SMOKE = os.path.join(ROOT, ".artifacts", "gui_smoke.py")

_EXPECTATION_RE = re.compile(
    r'\(\s*(\d+)\s*,\s*"(\w+)"\s*,\s*(\d+)\s*,\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)\s*\)'
)


def test_canonical_max_index_matches_shared_table():
    for _tab, view, want_max, _shape in AXIS_EXPECTATIONS:
        assert views.max_index(ASYMMETRIC_SHAPE, view) == want_max


def test_canonical_plane_shape_matches_shared_table():
    volume = np.zeros(ASYMMETRIC_SHAPE[1:])
    for _tab, view, _want_max, want_shape in AXIS_EXPECTATIONS:
        assert views.extract_view(volume, view, 0).shape == want_shape


def test_gui_smoke_gate_expectations_agree():
    if not os.path.exists(GUI_SMOKE):
        pytest.skip(f"frozen GUI gate not present: {GUI_SMOKE}")
    with open(GUI_SMOKE, encoding="utf-8") as handle:
        source = handle.read()

    parsed = [
        (int(tab), view, int(want_max), (int(h), int(w)))
        for tab, view, want_max, h, w in _EXPECTATION_RE.findall(source)
        if view in views.VIEW_TYPES
    ]
    assert parsed, "no expectations parsed out of .artifacts/gui_smoke.py"
    assert tuple(parsed) == AXIS_EXPECTATIONS, (
        "tests/_helpers.AXIS_EXPECTATIONS drifted from .artifacts/gui_smoke.py: " f"parsed {parsed}"
    )
