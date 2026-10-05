"""k-space -> image conversion: forward/inverse consistency and output contract.

The converter assumes DC-centred k-space, so the round-trip fixture is built as
``fftshift(fftn(ifftshift(image), norm="ortho"))`` and then inverted by
``KSpaceConverter.ifft_2d`` / ``ifft_3d``.
"""

from __future__ import annotations

import os

import numpy as np
import pytest
from _helpers import TEST_DATA, require_file  # noqa: E402

from src.core.kspace_converter import KSpaceConverter
from src.core.mri_data import DataType, MRIData


def centered_kspace(volume: np.ndarray) -> np.ndarray:
    """DC-centred, orthonormal k-space of ``volume`` (any number of axes)."""
    axes = tuple(range(volume.ndim))
    shifted = np.fft.ifftshift(volume, axes=axes)
    return np.fft.fftshift(np.fft.fftn(shifted, axes=axes, norm="ortho"), axes=axes)


def centered_kspace_2d_acquired(volume: np.ndarray) -> np.ndarray:
    """Per-slice DC-centred 2D k-space: (S, H, W) -> (S, H, W)."""
    return np.stack([centered_kspace(volume[sl]) for sl in range(volume.shape[0])])


def test_ifft_2d_round_trip_real_image():
    rng = np.random.RandomState(0)
    image = rng.rand(24, 40)  # non-square: catches an axis mix-up
    kspace = centered_kspace(image)
    recovered = KSpaceConverter.ifft_2d(kspace)
    assert recovered.shape == image.shape
    assert np.allclose(recovered, image, atol=1e-10, rtol=0)


def test_ifft_3d_round_trip_real_volume():
    rng = np.random.RandomState(1)
    volume = rng.rand(5, 12, 16)
    kspace = centered_kspace(volume)
    recovered = KSpaceConverter.ifft_3d(kspace)
    assert recovered.shape == volume.shape
    assert np.allclose(recovered, volume, atol=1e-10, rtol=0)


def test_ifft_2d_only_touches_last_two_axes():
    rng = np.random.RandomState(2)
    volume = rng.rand(4, 8, 10)
    out = KSpaceConverter.ifft_2d(volume + 0j)
    assert out.shape == volume.shape
    for sl in range(volume.shape[0]):
        assert np.allclose(out[sl], KSpaceConverter.ifft_2d(volume[sl] + 0j))


def _kspace_volume():
    """Return ``(image, kspace_2d_acquired, kspace_3d_acquired)``."""
    rng = np.random.RandomState(3)
    image = rng.rand(6, 10, 14)  # (S, H, W)
    return image, centered_kspace_2d_acquired(image), centered_kspace(image)


def _md(kspace, acquisition_mode="2d"):
    return MRIData(
        "synthetic",
        preloaded_data=np.asarray(kspace).astype(np.complex128),
        dim3_interpretation="slice_hw",
        acquisition_mode=acquisition_mode,
    )


def test_convert_2d_acquisition_recovers_magnitude():
    image, kspace, _ = _kspace_volume()
    md = _md(kspace)
    assert md.data_type == DataType.KSPACE
    out = KSpaceConverter.convert(md, mode_3d=False)
    assert out.shape == (1, 6, 10, 14)
    assert out.dtype == np.float64
    assert np.all(out >= 0)
    assert np.allclose(out[0], np.abs(image), atol=1e-10, rtol=0)


def test_convert_3d_acquisition_recovers_magnitude():
    image, _, kspace = _kspace_volume()
    md = _md(kspace, acquisition_mode="3d")
    out = KSpaceConverter.convert(md, mode_3d=True)
    assert out.shape == (1, 6, 10, 14)
    assert out.dtype == np.float64
    assert np.all(out >= 0)
    assert np.allclose(out[0], np.abs(image), atol=1e-10, rtol=0)


def test_convert_mode_defaults_to_acquisition_mode():
    _, kspace_2d, kspace_3d = _kspace_volume()
    md_2d = _md(kspace_2d, acquisition_mode="2d")
    md_3d = _md(kspace_3d, acquisition_mode="3d")
    # Both modes must recover the source image; the auto-detected default must
    # match the explicitly requested mode.
    assert np.allclose(
        KSpaceConverter.convert(md_2d), KSpaceConverter.convert(md_2d, mode_3d=False)
    )
    assert np.allclose(KSpaceConverter.convert(md_3d), KSpaceConverter.convert(md_3d, mode_3d=True))


def test_convert_rejects_non_kspace_data():
    md = MRIData("synthetic", preloaded_data=np.zeros((8, 8)), dim3_interpretation="coil_hw")
    assert md.data_type == DataType.IMAGE
    with pytest.raises(ValueError):
        KSpaceConverter.convert(md, mode_3d=False)


def test_convert_slice_matches_convert_2d_each_plane():
    _, kspace, _ = _kspace_volume()
    md = MRIData(
        "synthetic",
        preloaded_data=kspace.astype(np.complex128),
        dim3_interpretation="slice_hw",
    )
    if not hasattr(KSpaceConverter, "convert_slice"):
        pytest.skip("KSpaceConverter.convert_slice not provided yet (core-dev)")
    whole = KSpaceConverter.convert(md, mode_3d=False)
    for ch in range(md.num_channels):
        for sl in range(md.num_slices):
            assert np.array_equal(KSpaceConverter.convert_slice(md, ch, sl), whole[ch, sl])


def test_convert_slice_by_slice_matches_2d_path():
    _, kspace, _ = _kspace_volume()
    md = MRIData(
        "synthetic",
        preloaded_data=kspace.astype(np.complex128),
        dim3_interpretation="slice_hw",
    )
    assert np.array_equal(
        KSpaceConverter.convert_slice_by_slice(md),
        KSpaceConverter.convert(md, mode_3d=False),
    )


# --------------------------------------------------------------------------- #
# Real test_data fixtures
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "name,mode_3d",
    [("test_2d_kspace.npy", False), ("test_3d_kspace.npy", False), ("test_3d_kspace.npy", True)],
)
def test_convert_real_fixture_output_contract(name, mode_3d):
    path = require_file(os.path.join(TEST_DATA, name))
    md = MRIData(path, acquisition_mode="3d" if mode_3d else "2d")
    out = KSpaceConverter.convert(md, mode_3d=mode_3d)
    assert out.shape == md.processed_data.shape
    assert out.dtype == np.float64
    assert np.all(out >= 0)
    assert np.isfinite(out).all()


def test_convert_slice_real_fixture_matches_whole_volume():
    path = require_file(os.path.join(TEST_DATA, "test_3d_kspace.npy"))
    md = MRIData(path)
    if not hasattr(KSpaceConverter, "convert_slice"):
        pytest.skip("KSpaceConverter.convert_slice not provided yet (core-dev)")
    whole = KSpaceConverter.convert(md, mode_3d=False)
    sl = md.num_slices // 2
    assert np.array_equal(KSpaceConverter.convert_slice(md, 0, sl), whole[0, sl])
