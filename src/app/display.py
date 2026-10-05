"""
View extraction, coil combination and rendering for the MRI Reader window.

Geometry (which axis each view fixes, and therefore each plane's shape and max
index) is **never** computed here: it comes from :mod:`src.core.views`, the
single source of truth.  This module only asks for a plane and combines coils.

The controller owns a bounded LRU cache of *combined pre-enhancement planes*
keyed by ``(generation, source, view, index)``.  Switching slice/view/target or
reloading does not invalidate the enhancer pipeline itself; only a new data
source bumps the generation and drops the cache.
"""

from __future__ import annotations

from collections import OrderedDict

import numpy as np
from PyQt5.QtWidgets import QFileDialog, QMessageBox

from ..core import views
from ..core.image_processor import ImageProcessor
from ..core.kspace_converter import KSpaceConverter
from ..core.mri_data import DataDimension
from . import lazy


class _LruCache:
    """Minimal bounded LRU cache (``OrderedDict`` based, no threads)."""

    def __init__(self, maxsize: int = 32):
        self.maxsize = max(1, int(maxsize))
        self._items: "OrderedDict[tuple, np.ndarray]" = OrderedDict()

    def get(self, key):
        try:
            value = self._items.pop(key)
        except KeyError:
            return None
        self._items[key] = value  # mark as most recently used
        return value

    def put(self, key, value) -> None:
        self._items.pop(key, None)
        self._items[key] = value
        while len(self._items) > self.maxsize:
            self._items.popitem(last=False)

    def clear(self) -> None:
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)


class DisplayController:
    """Extract view planes and render them onto the two canvases."""

    def __init__(self, window, cache_size: int = 32):
        self.window = window
        self._cache = _LruCache(cache_size)
        self._generation = 0

    # ------------------------------------------------------------------
    # Source lifecycle / cache invalidation
    # ------------------------------------------------------------------
    def invalidate(self) -> None:
        """Drop every cached plane and any materialized proxy volume.

        Called whenever the data source is (re)resolved, so a reload or a change
        of acquisition mode / dimension interpretation never reuses stale bytes.
        """
        self._generation += 1
        self._cache.clear()
        # Release on-demand volumes held by the outgoing proxies (~742 MB for
        # the large HDF5 case) before the new sources are installed.
        for attr in ("current_image", "kspace_data"):
            source = getattr(self.window, attr, None)
            release = getattr(source, "release", None)
            if callable(release):
                release()

    def load_sources(self) -> None:
        """Resolve the display sources from ``window.mri_data``.

        Eager data keeps the historical real-ndarray sources.  For lazily
        opened HDF5 data the sources are read-only proxies that materialize a
        volume only if a legacy caller asks for one; the display path itself
        always goes through bounded-memory single-plane access.
        """
        w = self.window
        md = w.mri_data
        self.invalidate()

        if lazy.is_lazy(md):
            self._load_lazy_sources(md)
        else:
            self._load_eager_sources(md)

    def _load_eager_sources(self, md) -> None:
        """In-memory sources: exactly the pre-optimization behaviour."""
        w = self.window
        if w.is_kspace:
            w.kspace_data = md.processed_data.copy()
            use_3d = md.acquisition_mode == "3d"
            w.current_image = KSpaceConverter.convert(md, mode_3d=use_3d)
        else:
            # Non-k-space data: the left canvas must stay blank (no stale source).
            w.kspace_data = None
            w.current_image = md.processed_data.copy()

    def _load_lazy_sources(self, md) -> None:
        """HDF5-backed sources: bound memory by never reading the full volume."""
        w = self.window
        if w.is_kspace:
            w.kspace_data = lazy.KSpaceVolumeProxy(md)
            use_3d = md.acquisition_mode == "3d"
            if use_3d or not lazy.supports_convert_slice():
                # 3D acquisition mixes slices in one IFFT, so per-slice
                # conversion would change the numbers: convert the volume once.
                w.current_image = KSpaceConverter.convert(md, mode_3d=use_3d)
            else:
                w.current_image = lazy.ImageVolumeProxy(md, converted=True)
        else:
            w.kspace_data = None
            w.current_image = lazy.ImageVolumeProxy(md, converted=False)

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------
    def is_3d_volume(self) -> bool:
        """True when the loaded data has more than one slice to navigate."""
        md = self.window.mri_data
        return md is not None and md.dimension == DataDimension.DIM_3D and md.num_slices > 1

    def volume_shape(self):
        """Shape of the active volume, without forcing lazy materialization."""
        w = self.window
        md = w.mri_data
        if md is not None:
            shape = getattr(md, "processed_shape", None)
            if shape is not None:
                return tuple(shape)
            arr = getattr(md, "processed_data", None)
            if arr is not None:
                return tuple(arr.shape)
        if w.current_image is not None:
            return tuple(np.shape(w.current_image))
        if w.kspace_data is not None:
            return tuple(np.shape(w.kspace_data))
        return None

    def max_index_for_view(self, view_type: str) -> int:
        """Largest valid index for ``view_type`` (canonical geometry)."""
        if self.window.mri_data is None or not self.is_3d_volume():
            # 2D data has a single axial plane.
            return 0
        # Prefer the core accessor so a lazy HDF5 volume is never materialized.
        getter = getattr(self.window.mri_data, "get_view_max_index", None)
        if callable(getter):
            try:
                return int(getter(view_type))
            except (ValueError, KeyError):
                return 0
        shape = self.volume_shape()
        if shape is None:
            return 0
        try:
            return views.max_index(shape, view_type)
        except ValueError:
            return 0

    @staticmethod
    def _normalize_view(view_type: str) -> str:
        """Fall back to axial for unknown view names (legacy behaviour)."""
        if view_type in views.VIEW_TYPES:
            return view_type
        return "axial"

    # ------------------------------------------------------------------
    # Plane extraction
    # ------------------------------------------------------------------
    def _extract_channels(self, source, view_type: str, index: int) -> np.ndarray:
        """Return ``(C, plane_2d)`` for ``source`` without coil combination.

        The lazy proxies expose ``view_channels``, which reads only the plane -
        never call ``np.asarray`` on them here, because that would materialize
        the full volume.
        """
        if self.is_3d_volume():
            view = self._normalize_view(view_type)
        else:
            view = "axial"
            index = 0

        # Lazy proxy: bounded-memory single-plane accessor.
        getter = getattr(source, "view_channels", None)
        if callable(getter):
            return np.asarray(getter(view, index))

        # Eager ndarray (np.asarray is a no-copy view for ndarray input).
        return views.extract_view_channels(np.asarray(source), view, index)

    def image_plane(self, view_type: str, index: int) -> np.ndarray:
        """Combined image-domain plane for ``view_type``/``index`` (cached)."""
        if self.is_3d_volume():
            view = self._normalize_view(view_type)
            idx = int(index)
        else:
            view, idx = "axial", 0

        key = (self._generation, "image", view, idx)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        channels = self._extract_channels(self.window.current_image, view, idx)
        plane = views.rss_combine(channels)
        self._cache.put(key, plane)
        return plane

    def kspace_plane(self, view_type: str, index: int) -> np.ndarray:
        """Combined raw k-space plane for ``view_type``/``index`` (cached)."""
        w = self.window
        if w.kspace_data is None:
            return None

        if self.is_3d_volume():
            view = self._normalize_view(view_type)
            idx = int(index)
        else:
            view, idx = "axial", 0

        key = (self._generation, "kspace", view, idx)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        channels = self._extract_channels(w.kspace_data, view, idx)
        plane = views.rss_combine_complex(channels)
        self._cache.put(key, plane)
        return plane

    def _combine_view(self, source_kind: str, view_type: str, index: int) -> np.ndarray:
        """Combined plane for a named source (compat helper)."""
        if source_kind == "kspace":
            return self.kspace_plane(view_type, index)
        return self.image_plane(view_type, index)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def display_current_slice(self) -> None:
        """Display the current slice with all enhancements"""
        w = self.window
        if w.current_image is None or w.mri_data is None:
            return

        slice_idx = w.slice_navigator.current_slice
        view_type = w.slice_navigator.current_view

        # Clamp slice index to valid range for current view
        max_idx = self.max_index_for_view(view_type)
        slice_idx = max(0, min(slice_idx, max_idx))

        # === Display K-Space (left canvas) - always use kspace_processor ===
        if w.kspace_data is not None:
            kspace = self.kspace_plane(view_type, slice_idx)
            # Apply k-space processor (handles complex->magnitude, log, contrast, etc.)
            kspace_enhanced = w.kspace_processor.process(kspace)
            w.kspace_canvas.set_image(kspace_enhanced)
            w.kspace_info_label.setText(f"K-Space ({view_type}, idx {slice_idx})")
        else:
            # Not k-space data - show blank or message
            w.kspace_canvas.clear()
            w.kspace_info_label.setText("非K-Space数据")

        # === Display Image (middle canvas) - always use image_processor ===
        image = self.image_plane(view_type, slice_idx)
        enhanced = w.image_processor.process(image)

        # Display
        w.canvas.set_image(enhanced)
        w.image_info_label.setText(f"Image ({view_type}, idx {slice_idx})")

    def sync_canvas_slice(self) -> None:
        """Mirror the navigator's authoritative slice index into both canvases.

        The canvases navigate relative to ``current_slice`` (wheel / click), so
        a slider or keyboard jump that only re-rendered used to leave them on a
        stale coordinate and the next wheel step landed on the wrong slice.
        Assigning the attribute emits nothing, so this cannot loop.
        """
        w = self.window
        slice_idx = w.slice_navigator.current_slice
        w.canvas.current_slice = slice_idx
        w.kspace_canvas.current_slice = slice_idx

    def apply_view_range(self, view_type: str) -> None:
        """Single entry point for the slice range of the active view.

        Keeps the navigator slider **and both canvases** in sync with the
        canonical geometry (``views.max_index``): axial -> S, sagittal -> W,
        coronal -> H.  The canvases clamp wheel/click navigation with their own
        ``num_slices``, so leaving them at the slice count would make oblique
        navigation stop at ``S - 1``.
        """
        w = self.window
        if w.mri_data is None:
            return

        if not self.is_3d_volume():
            return

        max_idx = self.max_index_for_view(view_type)

        # Navigator (slider maximum, num_slices, current_slice and label).
        w.slice_navigator.set_range(max_idx)

        # Both canvases must know how many indices this view actually has.
        num_slices = max_idx + 1
        for canvas in (w.canvas, w.kspace_canvas):
            canvas.set_3d_mode(True, num_slices)
            # set_3d_mode resets current_slice; keep it consistent with the
            # slider so a wheel step moves relative to what is displayed.
            canvas.current_slice = w.slice_navigator.current_slice

    def update_navigator_range(self, view_type: str) -> None:
        """Backwards-compatible alias for :meth:`apply_view_range`."""
        return self.apply_view_range(view_type)

    def setup_for_data(self) -> None:
        """Setup UI components based on loaded data"""
        w = self.window
        is_3d = self.is_3d_volume()

        # Baseline interaction state; the canonical range is applied below via
        # the single entry point so navigator and canvases cannot diverge.
        w.canvas.set_3d_mode(is_3d, 1)
        w.kspace_canvas.set_3d_mode(is_3d, 1)
        w.slice_navigator.set_3d_mode(is_3d, 1)

        # Reset both processors, the target and the panel to load-time defaults
        # without letting the panel's stale values leak into the processors.
        w.enhancement.reset_defaults()

        # Apply the range for the view that is currently selected (default axial).
        if is_3d:
            self.apply_view_range(w.slice_navigator.current_view)

    # ------------------------------------------------------------------
    # Saving
    # ------------------------------------------------------------------
    def save_image(self) -> None:
        """Save current image as JPG"""
        w = self.window
        if w.current_image is None:
            QMessageBox.warning(w, "警告", "没有可保存的图像")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            w,
            "保存图像",
            "",
            "JPEG Image (*.jpg);;PNG Image (*.png);;All Files (*)",
        )

        if not file_path:
            return

        try:
            # Same plane logic as display_current_slice, but always the image
            # processor (not the current target processor).
            slice_idx = w.slice_navigator.current_slice
            view_type = w.slice_navigator.current_view
            enhanced = w.image_processor.process(self.image_plane(view_type, slice_idx))

            # Convert to 8-bit
            image_8bit = ImageProcessor.convert_to_8bit(enhanced)

            # Save using PIL if available, otherwise save as numpy
            try:
                from PIL import Image

                Image.fromarray(image_8bit).save(file_path)
            except ImportError:
                # Save as numpy array
                np.save(file_path.replace(".jpg", ".npy").replace(".png", ".npy"), image_8bit)
                QMessageBox.information(w, "提示", "未安装PIL,已保存为npy格式")
                return

            QMessageBox.information(w, "成功", f"图像已保存到:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(w, "错误", f"保存失败:\n{str(e)}")
