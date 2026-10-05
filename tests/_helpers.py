"""Shared constants and helpers for the MRI Reader pytest suite.

The axis expectations below are the *same* values asserted by the frozen
``.artifacts/gui_smoke.py`` gate (see ``tests/test_regression_axis.py``, which
cross-checks the two tables so they cannot drift apart).
"""

from __future__ import annotations

import hashlib
import os

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
TEST_DATA = os.path.join(ROOT, "test_data")
BRAIN_H5 = os.path.join(TEST_DATA, "file_brain_AXT2_201_2010261.h5")

#: Canonical asymmetric volume ``(C, S, H, W)``.  Every axis has a distinct
#: size, so a sagittal/coronal axis mix-up cannot hide behind a square plane.
ASYMMETRIC_SHAPE = (2, 8, 20, 30)

#: Canonical axis expectations: ``(tab index, view, max index, plane shape)``.
AXIS_EXPECTATIONS = (
    (0, "axial", 7, (20, 30)),
    (1, "sagittal", 29, (8, 20)),
    (2, "coronal", 19, (8, 30)),
)


def make_asymmetric_volume() -> np.ndarray:
    """Deterministic ``(2, 8, 20, 30)`` image volume (same recipe as gui_smoke)."""
    rng = np.random.RandomState(7)
    zz, yy, xx = np.ogrid[:8, :20, :30]
    data = np.zeros(ASYMMETRIC_SHAPE, dtype=np.float64)
    for c in range(ASYMMETRIC_SHAPE[0]):
        blob = np.exp(-(((zz - 4) ** 2) / 8 + ((yy - 10) ** 2) / 30 + ((xx - 15) ** 2) / 60))
        data[c] = blob + rng.normal(0, 0.01, blob.shape)
    return data


def save_asymmetric_volume(path) -> str:
    """Write the asymmetric fixture to ``path`` and return it as a string."""
    np.save(path, make_asymmetric_volume())
    return str(path)


def fingerprint(array) -> dict:
    """Compact numeric fingerprint, identical to capture_baseline.py's ``ck``."""
    arr = np.asarray(array)
    abs_arr = np.abs(arr).astype(np.float64)
    return {
        "shape": list(arr.shape),
        "dtype": str(arr.dtype),
        "sum": float(np.abs(arr).sum()),
        "mean": float(np.abs(arr).mean()),
        "max": float(np.abs(arr).max()),
        "sha1": hashlib.sha1(np.ascontiguousarray(abs_arr).tobytes()).hexdigest()[:16],
    }


def stub_mainwindow_dialogs(
    monkeypatch,
    is_kspace: bool = False,
    acquisition_mode: str = "2d",
    dim3_interpretation: str = "coil_hw",
    dim4_interpretation: str = "coil_slice_hw",
    h5_key=None,
) -> None:
    """Patch the frozen dialog seams on the ``MainWindow`` *class*.

    Class-level patching matters: the app layer delegates through the window
    instance, so an instance-level patch would not stop a real modal dialog from
    appearing and hanging a headless run.
    """
    from src.main_window import MainWindow

    monkeypatch.setattr(
        MainWindow,
        "_ask_data_type_with_options",
        lambda self, path: (
            is_kspace,
            acquisition_mode,
            dim3_interpretation,
            dim4_interpretation,
        ),
    )
    monkeypatch.setattr(MainWindow, "_ask_mat_key", lambda self, path: None)
    monkeypatch.setattr(MainWindow, "_ask_h5_key", lambda self, path: h5_key)


def require_file(path: str):
    """Return ``path`` or skip the test when the local fixture is missing."""
    import pytest

    if not os.path.exists(path):
        pytest.skip(f"test fixture not available: {path}")
    return path
