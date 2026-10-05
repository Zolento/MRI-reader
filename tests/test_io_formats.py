"""File format round-trips: .npy, .h5/.hdf5 and .mat, plus key selection."""

from __future__ import annotations

import os
from types import SimpleNamespace

import numpy as np
import pytest
from _helpers import TEST_DATA, require_file  # noqa: E402

from src.core.mri_data import DataDimension, DataType, MRIData


def _loader(window=None):
    from src.app.file_loader import FileLoader

    return FileLoader(window if window is not None else SimpleNamespace(mri_data=None))


# --------------------------------------------------------------------------- #
# .npy
# --------------------------------------------------------------------------- #
def test_npy_round_trip(tmp_path):
    array = np.random.RandomState(0).rand(3, 8, 12)
    path = tmp_path / "volume.npy"
    np.save(path, array)
    md = MRIData(str(path), dim3_interpretation="slice_hw")
    assert md.raw_data.shape == (3, 8, 12)
    assert md.processed_shape == (1, 3, 8, 12)
    assert np.array_equal(md.processed_data[0], array)


def test_npy_test_data_fixtures():
    path = require_file(os.path.join(TEST_DATA, "test_3d_image.npy"))
    md = MRIData(path)
    assert md.data_type == DataType.IMAGE
    assert md.dimension == DataDimension.DIM_3D


# --------------------------------------------------------------------------- #
# .h5 / .hdf5
# --------------------------------------------------------------------------- #
def test_h5_first_dataset_fixture():
    path = require_file(os.path.join(TEST_DATA, "test_2d_image.h5"))
    md = MRIData(path, dim3_interpretation="slice_hw")
    assert md.raw_data.shape == (10, 128, 128)
    assert md.dimension == DataDimension.DIM_3D


def test_h5_kspace_fixture():
    path = require_file(os.path.join(TEST_DATA, "test_3d_kspace.h5"))
    md = MRIData(path)
    assert md.data_type == DataType.KSPACE
    assert md.processed_shape == (4, 32, 128, 128)


def test_h5_multi_dataset_selection(tmp_path):
    h5py = pytest.importorskip("h5py")
    path = tmp_path / "multi.h5"
    volume = np.arange(2 * 3 * 4 * 5, dtype=float).reshape(2, 3, 4, 5)
    with h5py.File(path, "w") as handle:
        handle.create_dataset("header", data=np.array(7))  # scalar metadata
        handle.create_dataset("vol", data=volume)

    # Default selection skips the 0-D metadata dataset.
    md = MRIData(str(path))
    assert md.processed_shape == (2, 3, 4, 5)
    assert np.array_equal(md.processed_data, volume)

    # Explicit key selection.
    md_explicit = MRIData(str(path), h5_key="vol")
    assert md_explicit.processed_shape == (2, 3, 4, 5)


def test_h5_missing_key_raises_value_error(tmp_path):
    h5py = pytest.importorskip("h5py")
    path = tmp_path / "one.h5"
    with h5py.File(path, "w") as handle:
        handle.create_dataset("vol", data=np.zeros((4, 4)))

    with pytest.raises(ValueError):
        MRIData(str(path), h5_key="missing")
    with pytest.raises(ValueError):
        _loader().load_h5_file(str(path), "missing")


def test_file_loader_h5_key_selection(tmp_path):
    h5py = pytest.importorskip("h5py")
    path = tmp_path / "two.h5"
    first = np.zeros((3, 4, 5))
    second = np.ones((2, 6, 7))
    with h5py.File(path, "w") as handle:
        handle.create_dataset("first", data=first)
        handle.create_dataset("second", data=second)

    window = SimpleNamespace(mri_data=None)
    _loader(window).load_h5_file(str(path), "second")
    assert window.mri_data.raw_data.shape == (2, 6, 7)
    assert np.all(window.mri_data.raw_data == 1.0)


def test_h5_empty_file_raises_value_error(tmp_path):
    h5py = pytest.importorskip("h5py")
    path = tmp_path / "empty.h5"
    with h5py.File(path, "w"):
        pass
    with pytest.raises(ValueError):
        MRIData(str(path))


# --------------------------------------------------------------------------- #
# .mat
# --------------------------------------------------------------------------- #
def test_mat_round_trip(tmp_path):
    io = pytest.importorskip("scipy.io")
    array = np.arange(3 * 8 * 12, dtype=float).reshape(3, 8, 12)
    path = tmp_path / "volume.mat"
    io.savemat(str(path), {"vol": array})

    window = SimpleNamespace(mri_data=None)
    _loader(window).load_mat_file(str(path), "vol", dim3_interpretation="slice_hw")
    md = window.mri_data
    assert md.processed_shape == (1, 3, 8, 12)
    assert np.allclose(md.processed_data[0], array)


def test_mat_squeezes_singleton_dimensions(tmp_path):
    io = pytest.importorskip("scipy.io")
    array = np.arange(4 * 6, dtype=float).reshape(1, 4, 6)
    path = tmp_path / "squeezed.mat"
    io.savemat(str(path), {"vol": array})

    window = SimpleNamespace(mri_data=None)
    _loader(window).load_mat_file(str(path), "vol", dim3_interpretation="slice_hw")
    md = window.mri_data
    assert md.raw_data.shape == (4, 6)  # singleton dim squeezed away


def test_mat_missing_key_raises_value_error(tmp_path):
    io = pytest.importorskip("scipy.io")
    path = tmp_path / "volume.mat"
    io.savemat(str(path), {"vol": np.zeros((4, 4))})
    with pytest.raises(ValueError):
        _loader().load_mat_file(str(path), "nope")
