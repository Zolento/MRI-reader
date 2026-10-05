"""
Read-only lazy volume proxies for lazily opened HDF5 data.

``MRIData.processed_data`` materializes the whole ``(C, S, H, W)`` volume on
first access (1485 MB of ``complex128`` for the 778 MB brain k-space file), so
the display path must never touch it.  Instead the window holds one of these
proxies for ``current_image`` / ``kspace_data`` and asks for a *single plane*:

* ``view_channels(view, index)`` returns the ``(C, plane)`` block for one view
  without materializing the volume.
* ``shape`` / ``ndim`` / ``dtype`` / ``__len__`` come from metadata only.
* ``__getitem__`` / ``__array__`` materialize the full volume on demand, so
  legacy code that expects an ndarray still gets correct values.

Hybrid strategy (this is a "quick-look" tool for DL work):

* **axial** - the default and most common view - stays fully lazy: one plane
  read / one per-coil IFFT, ~280 MB peak, instant.
* **sagittal / coronal** need every slice converted, which costs ~5 s of IFFT
  work; that work is identical for *every* oblique index.  So the first oblique
  request **materializes the converted image volume once** (~742 MB ``float64``),
  and every later oblique index is a cheap in-memory slice.  A user who never
  leaves axial never pays for it.

Only the genuinely lazy (HDF5-backed) source uses these objects; eager data
(``.npy`` / ``.mat`` / small preloaded arrays) keeps returning real ndarrays.
"""

from __future__ import annotations

import numpy as np

from ..core import views
from ..core.kspace_converter import KSpaceConverter


def is_lazy(mri_data) -> bool:
    """True when ``mri_data`` is backed by an on-disk HDF5 source.

    ``MRIData`` does not expose a public "is lazy" flag, so this probes the
    documented backing field first and falls back to "known shape but neither
    backing array allocated", which is only true for an unmaterialized lazy
    source.  Any mismatch or failure degrades to the eager path, which is
    always correct (just less memory-efficient).  Suggest core expose
    ``is_lazy`` so the app can drop this probe (see task notes).
    """
    if mri_data is None:
        return False
    try:
        if getattr(mri_data, "_lazy", None) is not None:
            return True
        if getattr(mri_data, "processed_shape", None) is None:
            return False
        return (
            getattr(mri_data, "_raw_data", None) is None
            and getattr(mri_data, "_processed_data", None) is None
        )
    except Exception:
        return False


def supports_convert_slice() -> bool:
    """True when the core provides the bounded-memory per-slice IFFT."""
    return callable(getattr(KSpaceConverter, "convert_slice", None))


class _LazyVolume:
    """Common metadata / materialization behaviour for lazy volumes."""

    def __init__(self, mri_data, dtype):
        self._mri = mri_data
        self._dtype = np.dtype(dtype)

    # -- metadata (no I/O) ------------------------------------------------
    @property
    def shape(self):
        return tuple(self._mri.processed_shape)

    @property
    def ndim(self) -> int:
        return len(self.shape)

    @property
    def dtype(self):
        return self._dtype

    def __len__(self) -> int:
        return self.shape[0]

    # -- optional bounded-memory plane access -----------------------------
    def view_channels(self, view_type: str, index: int) -> np.ndarray:
        raise NotImplementedError

    # -- full materialization (legacy / escape hatch) ---------------------
    def _materialize(self) -> np.ndarray:
        raise NotImplementedError

    def release(self) -> None:
        """Drop any cached full-volume array held by this proxy."""
        return None

    def __array__(self, dtype=None, copy=None) -> np.ndarray:
        """NumPy 2 array protocol (``dtype`` and ``copy`` keywords).

        The proxy materializes on demand, so the returned array is always an
        independent object owned by this call (or the proxy's own cache).
        ``copy=True`` forces a genuinely independent copy, while ``copy=False``
        does not copy again - returning the materialized array directly is the
        best possible behaviour for a proxy that must build it anyway.  That
        matches NumPy's intent of "do not copy the result" and avoids the
        ``copy=False`` error NumPy raises when ``__array__`` lacks the keyword.
        """
        arr = self._materialize()
        if dtype is not None:
            return arr.astype(dtype, copy=True if copy else False)
        if copy:
            return arr.copy()
        return arr

    def __getitem__(self, indexer):
        return self.__array__()[indexer]


class ImageVolumeProxy(_LazyVolume):
    """Image-domain ``(C, S, H, W)`` volume backed by a lazy source.

    ``converted=False`` reads an image-domain HDF5 dataset; ``converted=True``
    wraps 2D-acquired k-space whose image domain is produced by the per-slice
    IFFT in :meth:`KSpaceConverter.convert_slice`.
    """

    def __init__(self, mri_data, converted: bool):
        if converted:
            dtype = np.dtype(np.float64)
        else:
            dtype = np.dtype(getattr(mri_data, "_raw_dtype", np.float64))
        super().__init__(mri_data, dtype)
        self._converted = bool(converted)
        #: Converted image volume, materialized on the first oblique request.
        self._converted_cache = None

    # ------------------------------------------------------------------
    # Materialization
    # ------------------------------------------------------------------
    def _materialize(self) -> np.ndarray:
        if self._converted:
            return self.materialize_converted()
        return self._mri.processed_data

    def materialize_converted(self) -> np.ndarray:
        """Build and cache the converted ``(C, S, H, W)`` ``float64`` volume.

        Fills a preallocated output slice by slice via the core's
        ``convert_slice``, so the raw ``complex128`` k-space volume is never
        materialized and peak memory is just the output volume.  The values are
        bit-identical to the eager ``convert(mode_3d=False)``.
        """
        if self._converted_cache is not None:
            return self._converted_cache

        md = self._mri
        if not supports_convert_slice():
            # Defensive fallback for a core without the per-slice converter.
            self._converted_cache = KSpaceConverter.convert(md, mode_3d=False)
            return self._converted_cache

        num_channels, num_slices, height, width = (int(n) for n in md.processed_shape)
        converted = np.empty((num_channels, num_slices, height, width), dtype=np.float64)
        for ch in range(num_channels):
            for sl in range(num_slices):
                converted[ch, sl] = KSpaceConverter.convert_slice(md, ch, sl)
        self._converted_cache = converted
        return converted

    def release(self) -> None:
        self._converted_cache = None

    # ------------------------------------------------------------------
    # Plane access
    # ------------------------------------------------------------------
    def view_channels(self, view_type: str, index: int) -> np.ndarray:
        if not self._converted:
            return self._mri.get_view_channels(view_type, index)

        view = views.normalize_view_type(view_type)
        # Axial stays lazy until an oblique view forces the upgrade.
        if views.view_axis(view) != 0 or self._converted_cache is not None:
            return views.extract_view_channels(self.materialize_converted(), view, int(index))
        return self._converted_view_channels(view, int(index))

    def _converted_view_channels(self, view_type: str, index: int) -> np.ndarray:
        """Lazy axial plane: one 2D IFFT per coil, no volume materialization.

        Each pixel comes from the core's own ``convert_slice``, so the numbers
        are identical to the eager ``convert(mode_3d=False)`` while the
        transient arrays stay plane-sized.
        """
        md = self._mri
        view = views.normalize_view_type(view_type)
        axis = views.view_axis(view)  # 0 -> S, 1 -> H, 2 -> W

        if axis == 0:
            planes = [
                KSpaceConverter.convert_slice(md, ch, int(index)) for ch in range(md.num_channels)
            ]
            return np.stack(planes, axis=0)

        # Only reachable through the (defensive) no-convert_slice path.
        num_slices = md.num_slices
        per_channel = []
        for ch in range(md.num_channels):
            rows = []
            for sl in range(num_slices):
                plane = KSpaceConverter.convert_slice(md, ch, sl)  # (H, W)
                rows.append(plane[:, index] if axis == 2 else plane[index, :])
            per_channel.append(np.stack(rows, axis=0))  # (S, H) or (S, W)
        return np.stack(per_channel, axis=0)  # (C, S, H) or (C, S, W)


class KSpaceVolumeProxy(_LazyVolume):
    """Raw ``(C, S, H, W)`` k-space volume backed by a lazy source."""

    def __init__(self, mri_data):
        super().__init__(mri_data, np.dtype(getattr(mri_data, "_raw_dtype", np.complex128)))

    def _materialize(self) -> np.ndarray:
        return self._mri.processed_data

    def view_channels(self, view_type: str, index: int) -> np.ndarray:
        return self._mri.get_view_channels(view_type, index)
