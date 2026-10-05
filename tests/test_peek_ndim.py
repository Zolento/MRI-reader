"""D4 regression: dimension peeking must never load bodies or crash on Groups.

``FileLoader.peek_file_ndim`` (frozen ``MainWindow._peek_file_ndim`` seam) only
needs the dimensionality:

* HDF5: top-level ``Dataset`` objects only -- ``Group`` metadata containers are
  skipped (the old code called ``.shape``/``.ndim`` on them and crashed).
* ``.npy``: header only (``numpy.lib.format``), never the array body.
* ``.mat``: ``scipy.io.loadmat`` has no header-only mode, so the whole container
  is still parsed -- malformed content degrades to ``0`` instead of raising.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pytest
from _helpers import ROOT, TEST_DATA, require_file  # noqa: E402


def _peek(file_path):
    """Call the frozen ``MainWindow._peek_file_ndim`` seam without building Qt."""
    from src.app.file_loader import FileLoader
    from src.main_window import MainWindow

    window = MainWindow.__new__(MainWindow)
    window.file_loader = FileLoader(window)
    return window._peek_file_ndim(str(file_path))


def _loader(window=None):
    from src.app.file_loader import FileLoader

    return FileLoader(window if window is not None else SimpleNamespace(mri_data=None))


# --------------------------------------------------------------------------- #
# D4a: HDF5 Groups must not crash the peek
# --------------------------------------------------------------------------- #
def test_grouped_h5_returns_first_dataset_ndim(tmp_path):
    h5py = pytest.importorskip("h5py")
    path = tmp_path / "grouped.h5"
    with h5py.File(path, "w") as handle:
        handle.create_group("aaa_meta")  # sorts first: the old code crashed on it
        handle.create_dataset("kspace", data=np.zeros((2, 3, 4)))

    assert _peek(path) == 3  # dataset ndim is 3, not 4


def test_h5_only_groups_returns_zero(tmp_path):
    h5py = pytest.importorskip("h5py")
    path = tmp_path / "groups_only.h5"
    with h5py.File(path, "w") as handle:
        handle.create_group("meta")
        handle.create_group("header")

    assert _peek(path) == 0


def test_h5_scalar_then_4d_returns_four(tmp_path):
    h5py = pytest.importorskip("h5py")
    path = tmp_path / "brain_like.h5"
    with h5py.File(path, "w") as handle:
        handle.create_dataset("ismrmrd_header", data=np.array(1))  # 0-D metadata
        handle.create_dataset("kspace", data=np.zeros((2, 3, 4, 5)))

    assert _peek(path) == 4


def test_h5_single_1d_dataset_returns_one(tmp_path):
    h5py = pytest.importorskip("h5py")
    path = tmp_path / "one_d.h5"
    with h5py.File(path, "w") as handle:
        handle.create_dataset("vec", data=np.zeros((5,)))

    assert _peek(path) == 1


def test_h5_missing_or_empty_file_returns_zero(tmp_path):
    assert _peek(tmp_path / "nope.h5") == 0
    h5py = pytest.importorskip("h5py")
    empty = tmp_path / "empty.h5"
    with h5py.File(empty, "w"):
        pass
    assert _peek(empty) == 0


@pytest.mark.gui
def test_ask_h5_key_skips_groups_and_reaches_dialog(tmp_path, qapp, monkeypatch):
    """The dialog listing must ignore Groups instead of raising AttributeError."""
    h5py = pytest.importorskip("h5py")
    from PyQt5.QtWidgets import QDialog, QMessageBox, QWidget

    path = tmp_path / "grouped_keys.h5"
    with h5py.File(path, "w") as handle:
        handle.create_group("meta")
        handle.create_dataset("kspace", data=np.zeros((2, 3)))

    calls = {"exec": 0}

    def fake_exec(self):
        calls["exec"] += 1
        return QDialog.Rejected  # listing already completed by now

    monkeypatch.setattr(QDialog, "exec_", fake_exec)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)

    parent = QWidget()  # a real parent: QDialog needs a QWidget
    try:
        assert _loader(parent).ask_h5_key(str(path)) is None  # stub rejected the dialog
    finally:
        parent.close()
    assert calls["exec"] == 1, "Group+Dataset file should still open the key dialog"


def test_ask_h5_key_only_groups_returns_none_without_dialog(tmp_path, monkeypatch):
    h5py = pytest.importorskip("h5py")
    from PyQt5.QtWidgets import QDialog, QMessageBox

    path = tmp_path / "only_groups.h5"
    with h5py.File(path, "w") as handle:
        handle.create_group("meta")

    monkeypatch.setattr(
        QDialog, "exec_", lambda self: pytest.fail("no dataset -> no dialog expected")
    )
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)

    assert _loader().ask_h5_key(str(path)) is None


# --------------------------------------------------------------------------- #
# D4b: .npy peeking is header-only
# --------------------------------------------------------------------------- #
def test_npy_header_only_never_reads_body(tmp_path):
    """Measure the peek in a subprocess so ``ru_maxrss`` has a clean baseline.

    ``ru_maxrss`` is a *peak* that never decreases, so an in-process "before"
    reading can be polluted by earlier tests.  A fresh subprocess gives an
    exact bound: a header-only peek must not move peak RSS by the 32 MB body.
    """
    path = tmp_path / "big.npy"
    np.save(path, np.zeros((2000, 2000), dtype=np.float64))  # ~32 MB
    assert path.stat().st_size > 30 * 1024 * 1024

    driver = f"""
import json, resource, sys, time
sys.path.insert(0, {ROOT!r})
from src.app.file_loader import FileLoader
rss0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
t0 = time.perf_counter()
ndim = FileLoader._peek_npy_ndim({str(path)!r})
elapsed = time.perf_counter() - t0
rss1 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
print("PEEK_JSON:" + json.dumps({{"ndim": ndim, "delta_kb": rss1 - rss0, "elapsed_s": elapsed}}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", driver], capture_output=True, text=True, timeout=120
    )
    assert completed.returncode == 0, completed.stderr[-1000:]
    payload = None
    for line in completed.stdout.splitlines():
        if line.startswith("PEEK_JSON:"):
            payload = json.loads(line[len("PEEK_JSON:") :])
    assert payload is not None, completed.stdout[-1000:]

    assert payload["ndim"] == 2
    assert (
        payload["delta_kb"] < 5 * 1024
    ), f"peek raised peak RSS by {payload['delta_kb']} KB; the .npy body was read"
    assert payload["elapsed_s"] < 0.5


def test_invalid_npy_returns_zero(tmp_path):
    path = tmp_path / "broken.npy"
    path.write_bytes(b"not a npy")
    assert _peek(path) == 0


def test_npy_ndim_per_dimensionality(tmp_path):
    cases = {
        "vec1d.npy": (np.zeros((5,)), 1),
        "mat2d.npy": (np.zeros((4, 6)), 2),
        "vol3d.npy": (np.zeros((3, 4, 6)), 3),
        "vol4d.npy": (np.zeros((2, 3, 4, 6)), 4),
    }
    for name, (array, expected) in cases.items():
        path = tmp_path / name
        np.save(path, array)
        assert _peek(path) == expected


@pytest.mark.parametrize(
    "file_name,expected",
    [
        ("test_2d_image.npy", 3),
        ("test_3d_image.npy", 4),
        ("test_2d_kspace.npy", 2),
        ("test_3d_kspace.npy", 4),
    ],
)
def test_npy_test_data_matches_legacy_values(file_name, expected):
    path = require_file(os.path.join(TEST_DATA, file_name))
    assert _peek(path) == expected


# --------------------------------------------------------------------------- #
# .mat / unknown extensions degrade gracefully
# --------------------------------------------------------------------------- #
def test_mat_ndim(tmp_path):
    io = pytest.importorskip("scipy.io")
    path = tmp_path / "vol.mat"
    io.savemat(str(path), {"vol": np.zeros((3, 8, 12))})
    assert _peek(path) == 3


def test_invalid_mat_returns_zero(tmp_path):
    path = tmp_path / "broken.mat"
    path.write_bytes(b"not a mat file")
    assert _peek(path) == 0


def test_unknown_extension_returns_zero(tmp_path):
    path = tmp_path / "data.txt"
    path.write_text("hello")
    assert _peek(path) == 0
