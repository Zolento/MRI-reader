"""Characterization lock: optimizations must not change numeric behaviour.

The expected fingerprints below are *inlined literals* captured from the
pre-optimization baseline (``.artifacts/baseline.json``, produced by
``.artifacts/capture_baseline.py``).  ``.artifacts/`` is gitignored, so this test
is fully self-contained and never reads it at runtime.

Why tolerances instead of bit-exact hashes
------------------------------------------
The array values come from pocketfft (NumPy) and ``scipy.ndimage`` (rotate/zoom).
Those libraries legitimately differ in the last ULP across NumPy/SciPy versions,
CPU SIMD paths and BLAS builds, and CI runs Python 3.9 and 3.11 on
``ubuntu-latest`` while this baseline was recorded locally.  A bit-exact SHA-1
lock would therefore turn environment drift into false "regression" failures.

So the *assertions* use a tight tolerance -- ``rtol=1e-6``, ``atol=1e-9`` on
``sum``/``mean``/``max`` plus explicit element-wise ``allclose`` anchors for the
kspace and rss paths.  That still catches real regressions, which are orders of
magnitude larger (an axis swap or a wrong IFFT norm changes the values by
percent, not by 1e-16).  Exact quantities -- ``shape``, ``dtype`` and the loader
metadata (C/S/H/W/dimension/type) -- stay exact assertions.  The SHA-1 is kept
only as a *non-fatal diagnostic*: a mismatch emits a warning, never a failure.
"""

from __future__ import annotations

import math
import os
import warnings

import numpy as np
import pytest
from _helpers import TEST_DATA, fingerprint, require_file  # noqa: E402

from src.core.image_processor import ImageProcessor
from src.core.kspace_converter import KSpaceConverter
from src.core.mri_data import MRIData

#: Tight enough to catch a wrong axis/formula (those differ by >>1e-6) while
#: absorbing last-ULP differences between NumPy/SciPy versions and CPUs.
RTOL = 1e-6
ATOL = 1e-9

# --------------------------------------------------------------------------- #
# k-space conversion (3 cases from the baseline)
# --------------------------------------------------------------------------- #
KSPACE_CASES = [
    (
        "2d_kspace",
        "test_2d_kspace.npy",
        False,
        {
            "shape": [1, 1, 128, 128],
            "dtype": "float64",
            "sum": 361088.0000000001,
            "mean": 22.039062500000007,
            "max": 128.00000000000006,
            "sha1": "e64b5f97459072c3",
        },
    ),
    (
        "3d_kspace",
        "test_3d_kspace.npy",
        False,
        {
            "shape": [1, 16, 64, 64],
            "dtype": "float64",
            "sum": 2723456.0,
            "mean": 41.556640625,
            "max": 64.00000000000003,
            "sha1": "8bd18741de07bffa",
        },
    ),
    (
        "3d_kspace",
        "test_3d_kspace.npy",
        True,
        {
            "shape": [1, 16, 64, 64],
            "dtype": "float64",
            "sum": 1778358.0649001966,
            "mean": 27.135590589907785,
            "max": 256.0,
            "sha1": "ddbd139225e69855",
        },
    ),
]

# --------------------------------------------------------------------------- #
# ImageProcessor (9 cases from the baseline)
# --------------------------------------------------------------------------- #
PROCESSOR_INPUT = np.random.RandomState(1234).rand(64, 64)

PROCESSOR_CASES = [
    (
        "identity",
        {},
        {
            "shape": [64, 64],
            "dtype": "float64",
            "sum": 2052.64908701929,
            "mean": 0.5011350310105689,
            "max": 1.0,
            "sha1": "eed29a00887d5a53",
        },
    ),
    (
        "contrast2_bright0.1",
        {"contrast": 2.0, "brightness": 0.1},
        {
            "shape": [64, 64],
            "dtype": "float64",
            "sum": 3256.659727967182,
            "mean": 0.7950829413982378,
            "max": 1.0,
            "sha1": "e10ab691c7ee03bc",
        },
    ),
    (
        "log",
        {"use_log": True},
        {
            "shape": [64, 64],
            "dtype": "float64",
            "sum": 3703.5810037592687,
            "mean": 0.9041945809959152,
            "max": 1.0,
            "sha1": "8dd15aba5f0a466a",
        },
    ),
    (
        "rotate45",
        {"rotation_angle": 45.0},
        {
            "shape": [64, 64],
            "dtype": "float64",
            "sum": 1678.1942420843527,
            "mean": 0.4097153911338752,
            "max": 0.9896873139114654,
            "sha1": "6ee67aa77333688f",
        },
    ),
    (
        "zoom1.5",
        {"zoom_factor": 1.5},
        {
            "shape": [64, 64],
            "dtype": "float64",
            "sum": 2047.4760456377703,
            "mean": 0.49987208145453377,
            "max": 0.9606820492020225,
            "sha1": "a6e6cc491fa142c7",
        },
    ),
    (
        "rot90x1",
        {"rotation_90_times": 1},
        {
            "shape": [64, 64],
            "dtype": "float64",
            "sum": 2052.64908701929,
            "mean": 0.5011350310105689,
            "max": 1.0,
            "sha1": "5057c9c7a1773078",
        },
    ),
    (
        "fliph",
        {"flip_h": True},
        {
            "shape": [64, 64],
            "dtype": "float64",
            "sum": 2052.64908701929,
            "mean": 0.5011350310105689,
            "max": 1.0,
            "sha1": "dc0541f93d80c54f",
        },
    ),
    (
        "flipv",
        {"flip_v": True},
        {
            "shape": [64, 64],
            "dtype": "float64",
            "sum": 2052.64908701929,
            "mean": 0.5011350310105689,
            "max": 1.0,
            "sha1": "ba40ca1ab90c57ea",
        },
    ),
    (
        "combo",
        {
            "contrast": 1.7,
            "brightness": -0.2,
            "use_log": True,
            "rotation_angle": 30.0,
            "zoom_factor": 0.8,
            "flip_h": True,
        },
        {
            "shape": [64, 64],
            "dtype": "float64",
            "sum": 2136.2577790386263,
            "mean": 0.5215473093356021,
            "max": 1.0,
            "sha1": "481067add0e2005f",
        },
    ),
]

# --------------------------------------------------------------------------- #
# rss_combine (2 cases from the baseline)
# --------------------------------------------------------------------------- #
RSS_INPUT = np.arange(3 * 8 * 8, dtype=np.float64).reshape(3, 8, 8)

RSS_CASES = [
    (
        "rss_combine",
        RSS_INPUT,
        {
            "shape": [8, 8],
            "dtype": "float64",
            "sum": 12109.032684510647,
            "mean": 189.20363569547885,
            "max": 237.86340618094243,
            "sha1": "7ed26d651b2aae25",
        },
    ),
    (
        "rss_combine_complex",
        RSS_INPUT + 1j * RSS_INPUT,
        {
            "shape": [8, 8],
            "dtype": "float64",
            "sum": 17124.75824965404,
            "mean": 267.5743476508444,
            "max": 336.3896550133491,
            "sha1": "75b3fabe56f47221",
        },
    ),
]

# --------------------------------------------------------------------------- #
# Loader metadata (shape/type only; the core view semantics are covered
# elsewhere and were deliberately left out of the frozen baseline).
# --------------------------------------------------------------------------- #
LOAD_CASES = [
    (
        "test_2d_image.npy",
        {"dim3_interpretation": "slice_hw"},
        (1, 10, 128, 128),
        "3D",
        "image",
        "float64",
    ),
    ("test_3d_image.npy", {}, (2, 16, 64, 64), "3D", "image", "float64"),
    ("test_2d_kspace.npy", {}, (1, 1, 128, 128), "2D", "k-space", "complex128"),
    ("test_3d_kspace.npy", {}, (1, 16, 64, 64), "3D", "k-space", "complex128"),
]


def assert_matches_baseline(got, expected, context):
    """Exact shape/dtype, tolerance-compared values, non-fatal sha1 diagnostic."""
    assert got["shape"] == expected["shape"], f"{context}: shape {got['shape']}"
    assert got["dtype"] == expected["dtype"], f"{context}: dtype {got['dtype']}"
    for key in ("sum", "mean", "max"):
        assert math.isclose(got[key], expected[key], rel_tol=RTOL, abs_tol=ATOL), (
            f"{context}: {key} {got[key]!r} != baseline {expected[key]!r} "
            f"(rtol={RTOL}, atol={ATOL})"
        )
    if got["sha1"] != expected["sha1"]:
        # Diagnostic only: the array hash is the strictest possible lock, so a
        # mismatch is worth surfacing, but it is not a failure condition.
        warnings.warn(
            f"{context}: sha1 {got['sha1']} != baseline {expected['sha1']} "
            "(diagnostic only; values are asserted within tolerance)",
            RuntimeWarning,
            stacklevel=2,
        )


@pytest.mark.parametrize(
    "name,file_name,mode_3d,expected",
    KSPACE_CASES,
    ids=[f"{n}-3d={m}" for n, _, m, _ in KSPACE_CASES],
)
def test_kspace_conversion_matches_baseline(name, file_name, mode_3d, expected):
    path = require_file(os.path.join(TEST_DATA, file_name))
    md = MRIData(path, acquisition_mode="3d" if mode_3d else "2d")
    got = fingerprint(KSpaceConverter.convert(md, mode_3d=mode_3d))
    assert_matches_baseline(got, expected, f"kspace[{name}, mode_3d={mode_3d}]")


@pytest.mark.parametrize(
    "label,params,expected", PROCESSOR_CASES, ids=[c[0] for c in PROCESSOR_CASES]
)
def test_image_processor_matches_baseline(label, params, expected):
    processor = ImageProcessor()
    for key, value in params.items():
        setattr(processor, key, value)
    got = fingerprint(processor.process(PROCESSOR_INPUT))
    assert_matches_baseline(got, expected, f"processor[{label}]")


@pytest.mark.parametrize("label,data,expected", RSS_CASES, ids=[c[0] for c in RSS_CASES])
def test_rss_combine_matches_baseline(label, data, expected):
    from src.core import views

    combine = views.rss_combine if label == "rss_combine" else views.rss_combine_complex
    got = fingerprint(combine(data, axis=0))
    assert_matches_baseline(got, expected, f"{label}")


@pytest.mark.parametrize(
    "file_name,kwargs,shape,dimension,data_type,dtype", LOAD_CASES, ids=[c[0] for c in LOAD_CASES]
)
def test_loader_metadata_matches_baseline(file_name, kwargs, shape, dimension, data_type, dtype):
    path = require_file(os.path.join(TEST_DATA, file_name))
    md = MRIData(path, **kwargs)
    assert md.processed_shape == shape
    assert md.dimension.value == dimension
    assert md.data_type.value == data_type
    assert str(md.raw_data.dtype) == dtype


# --------------------------------------------------------------------------- #
# Element-wise tolerance anchors (non-circular: re-derived from the same input
# with plain NumPy arithmetic in the same process, so library-version drift
# cancels out while a wrong axis or formula does not).
# --------------------------------------------------------------------------- #
def _reference_convert(kspace: np.ndarray, mode_3d: bool) -> np.ndarray:
    """Reference magnitude image derived directly from ``np.fft``."""
    kspace = np.asarray(kspace)
    if mode_3d:
        axes = [-3, -2, -1]
        shifted = np.fft.ifftshift(kspace, axes=axes)
        image = np.fft.ifftn(shifted, axes=axes, norm="ortho")
        return np.abs(np.fft.fftshift(image, axes=axes))

    out = np.empty(kspace.shape, dtype=np.complex128)
    for ch in range(kspace.shape[0]):
        for sl in range(kspace.shape[1]):
            plane = kspace[ch, sl]
            image = np.fft.ifftn(np.fft.ifftshift(plane), norm="ortho")
            out[ch, sl] = np.fft.fftshift(image)
    return np.abs(out)


@pytest.mark.parametrize(
    "name,file_name,mode_3d",
    [(n, f, m) for n, f, m, _ in KSPACE_CASES],
    ids=[f"{n}-3d={m}" for n, _, m, _ in KSPACE_CASES],
)
def test_kspace_conversion_elementwise(name, file_name, mode_3d):
    path = require_file(os.path.join(TEST_DATA, file_name))
    md = MRIData(path, acquisition_mode="3d" if mode_3d else "2d")
    got = KSpaceConverter.convert(md, mode_3d=mode_3d)
    reference = _reference_convert(md.processed_data, mode_3d)
    assert got.shape == reference.shape
    assert np.allclose(got, reference, rtol=RTOL, atol=ATOL), (
        f"kspace[{name}, mode_3d={mode_3d}]: max abs delta " f"{np.abs(got - reference).max():.3e}"
    )


def test_image_processor_identity_elementwise():
    """identity == plain min/max normalization (no floating-library involved)."""
    image = PROCESSOR_INPUT
    expected = (image - image.min()) / (image.max() - image.min())
    got = ImageProcessor().process(image)
    assert got.shape == expected.shape
    assert np.allclose(got, expected, rtol=RTOL, atol=ATOL)


@pytest.mark.parametrize(
    "label,data", [(c[0], c[1]) for c in RSS_CASES], ids=[c[0] for c in RSS_CASES]
)
def test_rss_combine_elementwise(label, data):
    from src.core import views

    combine = views.rss_combine if label == "rss_combine" else views.rss_combine_complex
    got = combine(data, axis=0)
    expected = data[0] if data.shape[0] == 1 else np.sqrt(np.sum(np.abs(data) ** 2, axis=0))
    assert got.shape == np.shape(expected)
    assert np.allclose(got, expected, rtol=RTOL, atol=ATOL)
