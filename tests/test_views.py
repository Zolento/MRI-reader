"""Canonical view semantics (:mod:`src.core.views`) with an asymmetric volume.

All assertions encode the frozen contract, not whatever the current GUI happens
to do:

==========  ============  =======================  ===========
view        fixed axis    plane shape (per coil)   max index
==========  ============  =======================  ===========
axial       S             (H, W)                   S - 1
sagittal    W             (S, H)                   W - 1
coronal     H             (S, W)                   H - 1
==========  ============  =======================  ===========
"""

from __future__ import annotations

import numpy as np
import pytest

from src.core import views

C, S, H, W = 2, 8, 20, 30
VOLUME_SHAPE = (S, H, W)
CHANNELS_SHAPE = (C, S, H, W)

VIEW_TO_AXIS = {"axial": 0, "coronal": 1, "sagittal": 2}
VIEW_TO_PLANE = {"axial": (H, W), "sagittal": (S, H), "coronal": (S, W)}
VIEW_TO_MAX = {"axial": S - 1, "sagittal": W - 1, "coronal": H - 1}


@pytest.fixture
def volume():
    rng = np.random.RandomState(0)
    return rng.rand(*VOLUME_SHAPE)


@pytest.fixture
def channels():
    rng = np.random.RandomState(1)
    return rng.rand(*CHANNELS_SHAPE)


def test_view_types_and_axis_mapping():
    assert views.VIEW_TYPES == ("axial", "sagittal", "coronal")
    for view, axis in VIEW_TO_AXIS.items():
        assert views.view_axis(view) == axis


@pytest.mark.parametrize("view", ["axial", "sagittal", "coronal"])
def test_view_axis_is_case_insensitive(view):
    assert views.view_axis(view.upper()) == VIEW_TO_AXIS[view]


@pytest.mark.parametrize("view", ["axial", "sagittal", "coronal"])
def test_max_index_for_3d_and_4d_shapes(view):
    assert views.max_index(VOLUME_SHAPE, view) == VIEW_TO_MAX[view]
    assert views.max_index(CHANNELS_SHAPE, view) == VIEW_TO_MAX[view]


@pytest.mark.parametrize("view", ["axial", "sagittal", "coronal"])
def test_extract_view_plane_shape_and_values(volume, view):
    index = VIEW_TO_MAX[view] // 2
    plane = views.extract_view(volume, view, index)
    assert plane.shape == VIEW_TO_PLANE[view]
    axis = VIEW_TO_AXIS[view]
    assert np.array_equal(plane, np.take(volume, index, axis=axis))


@pytest.mark.parametrize("view", ["axial", "sagittal", "coronal"])
def test_extract_view_channels_plane_shape_and_values(channels, view):
    index = VIEW_TO_MAX[view] // 2
    planes = views.extract_view_channels(channels, view, index)
    expected_shape = (C,) + VIEW_TO_PLANE[view]
    assert planes.shape == expected_shape
    axis = VIEW_TO_AXIS[view] + 1  # skip the channel axis
    assert np.array_equal(planes, np.take(channels, index, axis=axis))


@pytest.mark.parametrize("view", ["axial", "sagittal", "coronal"])
def test_extract_view_channels_matches_per_channel_extract(channels, view):
    index = VIEW_TO_MAX[view] // 2
    planes = views.extract_view_channels(channels, view, index)
    for ch in range(C):
        assert np.array_equal(planes[ch], views.extract_view(channels[ch], view, index))


@pytest.mark.parametrize("view", ["axial", "sagittal", "coronal"])
def test_index_out_of_range_raises_index_error(volume, channels, view):
    with pytest.raises(IndexError):
        views.extract_view(volume, view, VIEW_TO_MAX[view] + 1)
    with pytest.raises(IndexError):
        views.extract_view(volume, view, -1)
    with pytest.raises((IndexError, ValueError)):
        views.extract_view_channels(channels, view, VIEW_TO_MAX[view] + 1)


def test_max_index_accepts_sequence():
    assert views.max_index([2, S, H, W], "axial") == S - 1
    assert views.max_index((S, H, W), "sagittal") == W - 1


@pytest.mark.parametrize("bad", ["axiall", "", "AXIAL ", "transverse", None, 3])
def test_invalid_view_type_raises(bad):
    with pytest.raises((ValueError, TypeError)):
        views.normalize_view_type(bad)
    with pytest.raises((ValueError, TypeError)):
        views.view_axis(bad)


@pytest.mark.parametrize("bad_shape", [(4,), (2, 3), (1, 2, 3, 4, 5)])
def test_max_index_rejects_bad_ndim(bad_shape):
    with pytest.raises(ValueError):
        views.max_index(bad_shape, "axial")


def test_extract_view_rejects_wrong_ndim(volume, channels):
    with pytest.raises(ValueError):
        views.extract_view(channels, "axial", 0)
    with pytest.raises(ValueError):
        views.extract_view_channels(volume, "axial", 0)


def test_rss_combine_single_coil_preserves_signed_values():
    signed = np.array([[[-3.0, 1.0], [2.0, -4.0]]])
    out = views.rss_combine(signed, axis=0)
    assert out.shape == (2, 2)
    assert np.array_equal(out, signed[0])
    assert out.min() < 0  # no magnitude is taken for a single coil


def test_rss_combine_multi_coil_formula():
    data = np.arange(3 * 4 * 5, dtype=np.float64).reshape(3, 4, 5) - 30.0
    out = views.rss_combine(data, axis=0)
    assert out.shape == (4, 5)
    assert np.allclose(out, np.sqrt(np.sum(np.abs(data) ** 2, axis=0)))


def test_rss_combine_complex_input_is_magnitude():
    data = np.arange(2 * 3 * 3, dtype=np.float64).reshape(2, 3, 3)
    out = views.rss_combine(data + 1j * data, axis=0)
    assert out.dtype == np.float64
    assert np.all(out >= 0)
    assert np.allclose(out, np.sqrt(np.sum(np.abs(data + 1j * data) ** 2, axis=0)))


def test_rss_combine_nonzero_axis():
    data = np.ones((3, 4, 5))
    assert views.rss_combine(data, axis=1).shape == (3, 5)
    assert np.allclose(views.rss_combine(data, axis=1), np.sqrt(4))


def test_rss_combine_complex_is_alias():
    assert views.rss_combine_complex is views.rss_combine


def test_rss_combine_matches_mainwindow_compat_seam():
    pytest.importorskip("PyQt5.QtWidgets")
    from src.main_window import MainWindow

    window = MainWindow.__new__(MainWindow)  # no Qt widget construction needed
    data = np.arange(3 * 8 * 8, dtype=np.float64).reshape(3, 8, 8)
    assert np.array_equal(window._combine_channels(data), views.rss_combine(data, axis=0))
    complex_data = data + 1j * data
    assert np.array_equal(
        window._combine_channels_complex(complex_data),
        views.rss_combine_complex(complex_data, axis=0),
    )


def test_empty_axis_max_index_is_zero():
    assert views.max_index((0, H, W), "axial") == 0
    assert views.max_index((C, 0, H, W), "axial") == 0
