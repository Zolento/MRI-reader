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


def test_mat_preserves_singleton_dimensions(tmp_path):
    """A size-1 axis is real information; the loader must not squeeze it away.

    ``np.squeeze`` used to collapse a meaningful leading singleton (e.g. a
    single-coil volume) and silently reinterpret the slice axis as channels.
    Re-expressing the same outcome with a ``(1, 4, 6)`` 3-D variable: the raw
    array keeps its shape, and the user's explicit ``dim3`` choice then produces
    the displayed volume.
    """
    io = pytest.importorskip("scipy.io")
    array = np.arange(4 * 6, dtype=float).reshape(1, 4, 6)
    path = tmp_path / "singleton.mat"
    io.savemat(str(path), {"vol": array})

    window = SimpleNamespace(mri_data=None)
    _loader(window).load_mat_file(str(path), "vol", dim3_interpretation="slice_hw")
    md = window.mri_data
    # The fix: the leading size-1 axis survives (a squeeze would give (4, 6)).
    assert md.raw_data.shape == (1, 4, 6)
    # The user-visible volume follows from that preserved shape + dim3 choice.
    assert md.processed_shape == (1, 1, 4, 6)
    assert md.num_slices == 1
    assert (md.height, md.width) == (4, 6)
    assert np.array_equal(md.processed_data[0, 0], array[0])


@pytest.mark.parametrize(
    "raw_shape,dim4_interpretation,expected_channels,expected_slices",
    [
        ((1, 5, 7, 11), "coil_slice_hw", 1, 5),  # leading single coil
        ((5, 1, 7, 11), "slice_coil_hw", 1, 5),  # symmetric single coil
        ((2, 5, 7, 11), "coil_slice_hw", 2, 5),  # non-singleton control
    ],
    ids=["1x5x7x11-coil", "5x1x7x11-slice", "2x5x7x11-control"],
)
def test_mat_4d_singleton_axes_are_not_squeezed(
    tmp_path, raw_shape, dim4_interpretation, expected_channels, expected_slices
):
    """D-MAT: an explicit 4-D interpretation must see the true axis sizes."""
    io = pytest.importorskip("scipy.io")
    array = np.arange(np.prod(raw_shape), dtype=float).reshape(raw_shape)
    path = tmp_path / f"vol_{'x'.join(map(str, raw_shape))}.mat"
    io.savemat(str(path), {"vol": array})

    window = SimpleNamespace(mri_data=None)
    _loader(window).load_mat_file(str(path), "vol", dim4_interpretation=dim4_interpretation)
    md = window.mri_data
    assert md.raw_data.shape == raw_shape
    assert (md.num_channels, md.num_slices) == (expected_channels, expected_slices)
    assert md.processed_shape == (expected_channels, expected_slices, 7, 11)

    # Channel 0 must be the first coil, slice axis the second raw axis.
    for sl in range(expected_slices):
        if dim4_interpretation == "slice_coil_hw":
            expected = array[sl, 0]
        else:
            expected = array[0, sl]
        assert np.array_equal(md.processed_data[0, sl], expected)


def test_mat_2d_variable_unchanged(tmp_path):
    """2-D .mat variables keep their previous interpretation."""
    io = pytest.importorskip("scipy.io")
    array = np.arange(7 * 11, dtype=float).reshape(7, 11)
    path = tmp_path / "flat.mat"
    io.savemat(str(path), {"vol": array})

    window = SimpleNamespace(mri_data=None)
    _loader(window).load_mat_file(str(path), "vol")
    md = window.mri_data
    assert md.raw_data.shape == (7, 11)
    assert md.processed_shape == (1, 1, 7, 11)
    assert np.array_equal(md.processed_data[0, 0], array)


def test_prepare_preloaded_array_rejects_0d_and_1d():
    """The loader's shape policy: 0-D/1-D input fails with a clear ValueError.

    ``scipy.io.savemat`` promotes 1-D variables to ``(1, N)`` and scalars to
    ``(1, 1)``, so a ``.mat`` file cannot carry a true 0-D/1-D variable; the
    policy is still exercised directly on the helper (and via the H5 eager
    fallback, which shares it).
    """
    from src.app.file_loader import FileLoader

    for bad in (np.array(5.0), np.arange(5)):
        with pytest.raises(ValueError, match="Unsupported data dimension"):
            FileLoader._prepare_preloaded_array(bad)


def test_prepare_preloaded_array_trailing_singletons():
    """Trailing size-1 axes are stripped; leading ones and >4-D are policed."""
    from src.app.file_loader import FileLoader

    stripped = FileLoader._prepare_preloaded_array(np.zeros((1, 5, 7, 11, 1)))
    assert stripped.shape == (1, 5, 7, 11)
    assert FileLoader._prepare_preloaded_array(np.zeros((2, 3, 4, 5))).shape == (2, 3, 4, 5)
    with pytest.raises(ValueError, match="Unsupported data dimension"):
        FileLoader._prepare_preloaded_array(np.zeros((2, 3, 4, 5, 6)))


def test_prepare_preloaded_array_strips_trailing_singleton_3d():
    """MATLAB pads plain 2-D variables to ``(H, W, 1)``.

    Such a trailing singleton carries no indexing information, so it is stripped
    and the variable is read as the 2-D image ``(H, W)`` -- the historical
    behaviour.  Keeping it as 3-D would send it down the ``dim3`` branch and
    display a single column instead of the image.
    """
    from src.app.file_loader import FileLoader

    assert FileLoader._prepare_preloaded_array(np.zeros((4, 6, 1))).shape == (4, 6)
    assert FileLoader._prepare_preloaded_array(np.zeros((4, 6, 1, 1))).shape == (4, 6)
    # A leading singleton is real information and must survive.
    assert FileLoader._prepare_preloaded_array(np.zeros((1, 4, 6))).shape == (1, 4, 6)
    # Four-dimensional volumes keep their (Coil, Slice, H, W) shape.
    assert FileLoader._prepare_preloaded_array(np.zeros((1, 5, 7, 11))).shape == (1, 5, 7, 11)
    # Never strip below two dimensions.
    assert FileLoader._prepare_preloaded_array(np.zeros((7, 1))).shape == (7, 1)


def test_mat_missing_key_raises_value_error(tmp_path):
    io = pytest.importorskip("scipy.io")
    path = tmp_path / "volume.mat"
    io.savemat(str(path), {"vol": np.zeros((4, 4))})
    with pytest.raises(ValueError):
        _loader().load_mat_file(str(path), "nope")
