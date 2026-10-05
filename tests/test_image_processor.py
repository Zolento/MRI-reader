"""ImageProcessor enhancement pipeline contract.

Every op must keep the 2D shape, stay finite and land in ``[0, 1]``; degenerate
inputs must never produce NaN.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.core.image_processor import ImageProcessor

SHAPE = (48, 48)

OPS = [
    ("identity", {}),
    ("contrast", {"contrast": 2.5}),
    ("brightness", {"brightness": 0.25}),
    ("contrast_brightness", {"contrast": 1.7, "brightness": -0.3}),
    ("log", {"use_log": True}),
    ("rotate45", {"rotation_angle": 45.0}),
    ("rotate_neg30", {"rotation_angle": -30.0}),
    ("zoom_in", {"zoom_factor": 1.5}),
    ("zoom_out", {"zoom_factor": 0.6}),
    ("rot90", {"rotation_90_times": 1}),
    ("rot180", {"rotation_90_times": 2}),
    ("flip_h", {"flip_h": True}),
    ("flip_v", {"flip_v": True}),
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
    ),
]


def make_processor(**params):
    processor = ImageProcessor()
    for key, value in params.items():
        setattr(processor, key, value)
    return processor


def test_defaults_and_reset():
    processor = ImageProcessor()
    for attr, value in (
        ("contrast", 1.0),
        ("brightness", 0.0),
        ("use_log", False),
        ("rotation_angle", 0.0),
        ("rotation_90_times", 0),
        ("zoom_factor", 1.0),
        ("flip_h", False),
        ("flip_v", False),
    ):
        assert getattr(processor, attr) == value

    for key, value in OPS[-1][1].items():
        setattr(processor, key, value)
    processor.reset()
    assert processor.contrast == 1.0
    assert processor.use_log is False
    assert processor.zoom_factor == 1.0


@pytest.mark.parametrize("label,params", OPS, ids=[label for label, _ in OPS])
def test_process_keeps_shape_and_range(label, params):
    rng = np.random.RandomState(0)
    image = rng.rand(*SHAPE)
    out = make_processor(**params).process(image)
    assert out.shape == image.shape
    assert out.dtype == np.float64
    assert np.isfinite(out).all()
    assert out.min() >= 0.0
    assert out.max() <= 1.0


@pytest.mark.parametrize("value", [0.0, 1e-12, 2.5, 100.0])
def test_constant_input_yields_finite_zeros(value):
    image = np.full(SHAPE, value, dtype=np.float64)
    out = ImageProcessor().process(image)
    assert np.isfinite(out).all()
    assert np.all(out == 0.0)


@pytest.mark.parametrize("use_log", [False, True])
def test_constant_input_with_every_op_never_nans(use_log):
    image = np.zeros(SHAPE, dtype=np.float64)
    out = make_processor(use_log=use_log, contrast=3.0, brightness=0.5).process(image)
    assert np.isfinite(out).all()
    assert out.min() >= 0.0 and out.max() <= 1.0


def test_nan_and_inf_are_cleaned():
    rng = np.random.RandomState(1)
    image = rng.rand(*SHAPE)
    image[0, 0] = np.nan
    image[1, 1] = np.inf
    image[2, 2] = -np.inf
    out = ImageProcessor().process(image)
    assert np.isfinite(out).all()
    assert out.min() >= 0.0 and out.max() <= 1.0


def test_complex_input_uses_magnitude():
    rng = np.random.RandomState(2)
    real = rng.rand(*SHAPE)
    out = ImageProcessor().process(real + 1j * real)
    expected = ImageProcessor().process(np.abs(real + 1j * real))
    assert np.allclose(out, expected)


def test_rotate_90_swaps_non_square_shape():
    image = np.random.RandomState(3).rand(20, 30)
    processor = make_processor(rotation_90_times=1)
    assert processor.rotate_90(image, 1).shape == (30, 20)
    # rotate/zoom keep the shape even for non-square input
    assert make_processor(rotation_angle=30.0).process(image).shape == (20, 30)
    assert make_processor(zoom_factor=1.4).process(image).shape == (20, 30)


def test_flips_match_numpy():
    image = np.random.RandomState(4).rand(*SHAPE)
    base = ImageProcessor().process(image)
    assert np.allclose(make_processor(flip_h=True).process(image), np.fliplr(base))
    assert np.allclose(make_processor(flip_v=True).process(image), np.flipud(base))


def test_normalize_image_contract():
    image = np.array([[0.0, 5.0], [10.0, 20.0]])
    normalized = ImageProcessor.normalize_image(image)
    assert normalized.min() == 0.0
    assert normalized.max() == 1.0

    constant = ImageProcessor.normalize_image(np.full((4, 4), 3.0))
    assert np.all(constant == 0.0)


def test_convert_to_8bit_contract():
    out = ImageProcessor.convert_to_8bit(np.array([[-1.0, 0.0, 0.5, 1.0, 2.0]]))
    assert out.dtype == np.uint8
    assert out.min() == 0
    assert out.max() == 255
    assert list(out.reshape(-1)) == [0, 0, 127, 255, 255]
