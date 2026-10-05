"""
View extraction and coil-combination utilities.

Canonical internal geometry
---------------------------
After :class:`~src.core.mri_data.MRIData` normalization, volumetric data has
shape ``(channels, slices, height, width)`` = ``(C, S, H, W)``::

    C  coil channel            (dim -4)
    S  slice axis              (dim -3)   superior <-> inferior
    H  rows                    (dim -2)   anterior <-> posterior
    W  columns                 (dim -1)   left <-> right

A *view* fixes one spatial axis and displays the plane it spans:

    ==========  ============  =======================  ===========
    view        fixed axis    plane shape (per coil)   max index
    ==========  ============  =======================  ===========
    axial       S             (H, W)                   S - 1
    sagittal    W             (S, H)                   W - 1
    coronal     H             (S, W)                   H - 1
    ==========  ============  =======================  ===========

This module is the **single source of truth** for that convention.  Neither the
Qt layer nor :mod:`src.core.mri_data` may re-implement it.

All functions accept either a 3D ``(S, H, W)`` array (single volume) or a 4D
``(C, S, H, W)`` array, matching the layout produced by ``MRIData``.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

__all__ = [
    "VIEW_TYPES",
    "normalize_view_type",
    "view_axis",
    "max_index",
    "extract_view",
    "extract_view_channels",
    "rss_combine",
    "rss_combine_complex",
]

#: Supported view names, in tab order.
VIEW_TYPES: tuple[str, ...] = ("axial", "sagittal", "coronal")

#: Spatial axis (inside the trailing ``(S, H, W)`` block) indexed by each view.
_VIEW_AXIS: dict[str, int] = {"axial": 0, "sagittal": 2, "coronal": 1}


def normalize_view_type(view_type: str) -> str:
    """Validate a view name and return its canonical lower-case form."""
    try:
        key = view_type.lower()
    except AttributeError as exc:  # non-str input
        raise ValueError(f"view_type must be a string, got {view_type!r}") from exc
    if key not in _VIEW_AXIS:
        raise ValueError(f"Unknown view type: {view_type!r}; expected one of {VIEW_TYPES}")
    return key


def view_axis(view_type: str) -> int:
    """Return the ``(S, H, W)`` axis that ``view_type`` indexes."""
    return _VIEW_AXIS[normalize_view_type(view_type)]


def _spatial_shape(shape: Sequence[int], ndim: int) -> tuple[int, int, int]:
    if ndim not in (3, 4):
        raise ValueError(
            f"Expected a 3D (S,H,W) or 4D (C,S,H,W) array, got {ndim}D shape {tuple(shape)}"
        )
    return tuple(int(n) for n in tuple(shape)[-3:])  # type: ignore[return-value]


def max_index(shape: Sequence[int], view_type: str) -> int:
    """
    Largest valid index for ``view_type``.

    Args:
        shape: shape of an ``(S, H, W)`` or ``(C, S, H, W)`` array.
        view_type: ``"axial"``, ``"sagittal"`` or ``"coronal"``.

    Returns:
        The maximum index (never negative; a size-0 axis yields ``0``).
    """
    hsw = _spatial_shape(shape, len(shape))
    return max(0, hsw[view_axis(view_type)] - 1)


def _check_index(index: int, size: int, view_type: str) -> int:
    idx = int(index)
    if not 0 <= idx < size:
        raise IndexError(f"{view_type} index {idx} out of range [0, {size})")
    return idx


def extract_view(volume: np.ndarray, view_type: str, index: int) -> np.ndarray:
    """Extract a 2D plane from a single ``(S, H, W)`` volume."""
    arr = np.asarray(volume)
    if arr.ndim != 3:
        raise ValueError(f"Expected a 3D (S,H,W) volume, got {arr.ndim}D")
    view = normalize_view_type(view_type)
    axis = _VIEW_AXIS[view]
    _check_index(index, arr.shape[axis], view)
    return np.take(arr, int(index), axis=axis)


def extract_view_channels(data: np.ndarray, view_type: str, index: int) -> np.ndarray:
    """
    Extract a plane from a 4D ``(C, S, H, W)`` volume, keeping coils separate.

    Returns:
        ``(C, H, W)`` for axial, ``(C, S, H)`` for sagittal,
        ``(C, S, W)`` for coronal.
    """
    arr = np.asarray(data)
    if arr.ndim != 4:
        raise ValueError(f"Expected a 4D (C,S,H,W) array, got {arr.ndim}D")
    view = normalize_view_type(view_type)
    axis = _VIEW_AXIS[view] + 1  # skip the channel axis
    _check_index(index, arr.shape[axis], view)
    return np.take(arr, int(index), axis=axis)


def rss_combine(data: np.ndarray, axis: int = 0) -> np.ndarray:
    """
    Root-sum-of-squares coil combination, ``sqrt(sum(|x|^2))``.

    A single coil is returned unchanged (no magnitude is taken), so signed
    image data keeps its sign.  Multi-coil input always yields a magnitude
    image (``float64`` for real input, ``float64`` magnitude for complex).
    """
    arr = np.asarray(data)
    if arr.shape[axis] == 1:
        return np.take(arr, 0, axis=axis)
    return np.sqrt(np.sum(np.abs(arr) ** 2, axis=axis))


#: Backwards-compatible alias used by the k-space display path.  The formula is
#: identical; the name only documents intent (complex input is accepted).
rss_combine_complex = rss_combine
