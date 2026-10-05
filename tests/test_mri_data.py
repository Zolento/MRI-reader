"""Shape-normalization matrix and view API of :class:`src.core.mri_data.MRIData`.

The internal volume is always ``(C, S, H, W)``; the view accessors must agree
with :mod:`src.core.views`, which is the single source of truth.
"""

from __future__ import annotations

import os

import numpy as np
import pytest
from _helpers import (  # noqa: E402
    ASYMMETRIC_SHAPE,
    TEST_DATA,
    require_file,
    stub_mainwindow_dialogs,
)

from src.core import views
from src.core.mri_data import DataDimension, DataType, MRIData

C, S, H, W = ASYMMETRIC_SHAPE


def preload(array, **kwargs):
    return MRIData("synthetic", preloaded_data=array, **kwargs)


# --------------------------------------------------------------------------- #
# Shape normalization matrix
# --------------------------------------------------------------------------- #
def test_2d_array_becomes_single_channel_single_slice():
    md = preload(np.zeros((H, W), dtype=np.float64))
    assert md.dimension == DataDimension.DIM_2D
    assert (md.num_channels, md.num_slices, md.height, md.width) == (1, 1, H, W)
    assert md.processed_shape == (1, 1, H, W)
    assert md.processed_data.shape == (1, 1, H, W)


def test_3d_coil_hw_is_two_dimensional_multi_channel():
    md = preload(np.zeros((C, H, W)), dim3_interpretation="coil_hw")
    assert md.dimension == DataDimension.DIM_2D
    assert (md.num_channels, md.num_slices, md.height, md.width) == (C, 1, H, W)
    assert md.processed_shape == (C, 1, H, W)


def test_3d_slice_hw_is_three_dimensional_single_channel():
    md = preload(np.zeros((S, H, W)), dim3_interpretation="slice_hw")
    assert md.dimension == DataDimension.DIM_3D
    assert (md.num_channels, md.num_slices, md.height, md.width) == (1, S, H, W)
    assert md.processed_shape == (1, S, H, W)


def test_4d_coil_slice_hw_is_preserved():
    raw = np.random.RandomState(0).rand(C, S, H, W)
    md = preload(raw, dim4_interpretation="coil_slice_hw")
    assert md.dimension == DataDimension.DIM_3D
    assert (md.num_channels, md.num_slices, md.height, md.width) == (C, S, H, W)
    assert np.array_equal(md.processed_data, raw)


def test_4d_slice_coil_hw_is_transposed_to_cshw():
    raw = np.random.RandomState(1).rand(S, C, H, W)
    md = preload(raw, dim4_interpretation="slice_coil_hw")
    assert md.dimension == DataDimension.DIM_3D
    assert (md.num_channels, md.num_slices, md.height, md.width) == (C, S, H, W)
    assert np.array_equal(md.processed_data, np.transpose(raw, (1, 0, 2, 3)))


@pytest.mark.parametrize("bad", [np.zeros(4), np.zeros((2, 3, 4, 5, 6))])
def test_unsupported_ndim_raises_value_error(bad):
    with pytest.raises(ValueError):
        preload(bad)


def test_dtype_is_normalized_to_float64_or_complex128():
    assert preload(np.zeros((H, W), dtype=np.float32)).raw_data.dtype == np.float64
    assert preload(np.zeros((H, W), dtype=np.int16)).raw_data.dtype == np.float64
    assert preload(np.zeros((H, W), dtype=np.complex64)).raw_data.dtype == np.complex128


def test_detects_complex_data_as_kspace():
    md = preload(np.zeros((S, H, W), dtype=np.complex128), dim3_interpretation="slice_hw")
    assert md.data_type == DataType.KSPACE
    assert "Is Complex: Yes" in md.get_info()


def test_detects_smooth_real_data_as_image():
    md = preload(np.random.RandomState(2).rand(H, W))
    assert md.data_type == DataType.IMAGE


# --------------------------------------------------------------------------- #
# Slice accessor bounds
# --------------------------------------------------------------------------- #
def test_get_slice_bounds_raise_value_error():
    md = preload(np.random.RandomState(3).rand(C, S, H, W))
    assert md.get_slice(0).shape == (H, W)
    with pytest.raises(ValueError):
        md.get_slice(S)
    with pytest.raises(ValueError):
        md.get_slice(-1)
    with pytest.raises(ValueError):
        md.get_slice(0, channel=C)


def test_2d_get_view_returns_the_single_plane():
    md = preload(np.random.RandomState(4).rand(H, W))
    for view in views.VIEW_TYPES:
        assert md.get_view(view, 0).shape == (H, W)


# --------------------------------------------------------------------------- #
# View API agrees with src.core.views
# --------------------------------------------------------------------------- #
@pytest.fixture
def volume_4d():
    return preload(np.random.RandomState(5).rand(*ASYMMETRIC_SHAPE))


@pytest.mark.parametrize("view", ["axial", "sagittal", "coronal"])
def test_get_view_matches_views_extract_view(volume_4d, view):
    md = volume_4d
    if not hasattr(md, "get_view_max_index"):
        pytest.skip("MRIData.get_view_max_index not provided yet (core-dev)")
    for index in (0, md.get_view_max_index(view)):
        for channel in range(md.num_channels):
            got = md.get_view(view, index, channel)
            want = views.extract_view(md.processed_data[channel], view, index)
            assert got.shape == want.shape
            assert np.allclose(got, want)


@pytest.mark.parametrize("view", ["axial", "sagittal", "coronal"])
def test_get_view_max_index_matches_views_max_index(volume_4d, view):
    md = volume_4d
    if not hasattr(md, "get_view_max_index"):
        pytest.skip("MRIData.get_view_max_index not provided yet (core-dev)")
    assert md.get_view_max_index(view) == views.max_index(ASYMMETRIC_SHAPE, view)


@pytest.mark.parametrize("view", ["axial", "sagittal", "coronal"])
def test_get_view_channels_matches_views_extract_view_channels(volume_4d, view):
    md = volume_4d
    if not hasattr(md, "get_view_channels"):
        pytest.skip("MRIData.get_view_channels not provided yet (core-dev)")
    index = md.get_view_max_index(view) // 2
    got = md.get_view_channels(view, index)
    want = views.extract_view_channels(md.processed_data, view, index)
    assert got.shape == want.shape
    assert np.allclose(got, want)


def test_get_view_out_of_range_behaviour(volume_4d):
    md = volume_4d
    with pytest.raises((IndexError, ValueError)):
        md.get_view("axial", S)
    with pytest.raises((IndexError, ValueError)):
        md.get_view("sagittal", W)
    with pytest.raises((IndexError, ValueError)):
        md.get_view("coronal", H)


# --------------------------------------------------------------------------- #
# File-backed loading (test_data fixtures)
# --------------------------------------------------------------------------- #
def test_load_2d_image_npy_slice_hw():
    path = require_file(os.path.join(TEST_DATA, "test_2d_image.npy"))
    md = MRIData(path, dim3_interpretation="slice_hw")
    assert md.data_type == DataType.IMAGE
    assert md.dimension == DataDimension.DIM_3D
    assert (md.num_channels, md.num_slices, md.height, md.width) == (1, 10, 128, 128)


def test_load_3d_image_npy():
    path = require_file(os.path.join(TEST_DATA, "test_3d_image.npy"))
    md = MRIData(path)
    assert md.data_type == DataType.IMAGE
    assert (md.num_channels, md.num_slices, md.height, md.width) == (2, 16, 64, 64)


def test_load_2d_kspace_npy():
    path = require_file(os.path.join(TEST_DATA, "test_2d_kspace.npy"))
    md = MRIData(path)
    assert md.data_type == DataType.KSPACE
    assert md.dimension == DataDimension.DIM_2D
    assert (md.num_channels, md.num_slices, md.height, md.width) == (1, 1, 128, 128)


def test_load_3d_kspace_npy():
    path = require_file(os.path.join(TEST_DATA, "test_3d_kspace.npy"))
    md = MRIData(path)
    assert md.data_type == DataType.KSPACE
    assert md.dimension == DataDimension.DIM_3D
    assert (md.num_channels, md.num_slices, md.height, md.width) == (1, 16, 64, 64)


def test_missing_npy_raises_value_error(tmp_path):
    with pytest.raises(ValueError):
        MRIData(str(tmp_path / "does_not_exist.npy"))


# --------------------------------------------------------------------------- #
# MainWindow compatibility seam (uses the frozen _load_file signature)
# --------------------------------------------------------------------------- #
def test_mainwindow_load_file_seam_loads_asymmetric_npy(qapp, monkeypatch, tmp_path):
    from _helpers import save_asymmetric_volume

    from src.main_window import MainWindow

    stub_mainwindow_dialogs(monkeypatch, is_kspace=False)
    path = save_asymmetric_volume(tmp_path / "asym.npy")
    window = MainWindow()
    try:
        window._load_file(path, is_kspace=False, dim3_interpretation="coil_hw")
        assert window.mri_data is not None
        assert window.mri_data.processed_shape == ASYMMETRIC_SHAPE
    finally:
        window.close()
