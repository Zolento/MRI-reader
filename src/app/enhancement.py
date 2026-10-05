"""
Enhancement state for the MRI Reader window.

The window keeps two independent :class:`~src.core.image_processor.ImageProcessor`
instances (image-domain and k-space) and an ``enhancement_target`` string.  This
controller owns the parameter synchronisation between the two processors and
the UI panel, and every mutation triggers a re-render through the window's
frozen ``_display_current_slice`` seam.
"""

from __future__ import annotations

from PyQt5.QtCore import QSignalBlocker


class EnhancementController:
    """Two processors, targeted UI parameter sync, reset/rotate/flip/zoom."""

    def __init__(self, window):
        self.window = window

    # ------------------------------------------------------------------
    # Processor / UI sync
    # ------------------------------------------------------------------
    def load_params_to_ui(self, processor) -> None:
        """Load processor parameters to UI controls"""
        params = {
            "contrast": processor.contrast,
            "brightness": processor.brightness,
            "use_log": processor.use_log,
            "rotation": processor.rotation_angle,
            "zoom": processor.zoom_factor,
        }
        # QSignalBlocker composes with an outer blocker (a manual
        # blockSignals(False) would unblock early).
        blocker = QSignalBlocker(self.window.enhancement_panel)
        try:
            self.window.enhancement_panel.set_params(params)
        finally:
            del blocker

    def reset_defaults(self) -> None:
        """Reset both processors, the target and the panel to load-time defaults.

        Reconfiguring the panel fires ``target_changed``; if that reached
        ``on_target_changed`` after ``enhancement_target`` had already been set
        to ``"Image"``, the *previous* target's panel values would be written
        into the freshly reset image processor.  Blocking the panel for the
        whole reconfiguration prevents that stale write.
        """
        w = self.window
        w.kspace_processor.reset()
        w.image_processor.reset()

        # K-space default: enable log transform for better visibility.
        if w.is_kspace:
            w.kspace_processor.use_log = True

        blocker = QSignalBlocker(w.enhancement_panel)
        try:
            w.enhancement_target = "Image"
            w.processor = w.image_processor
            w.enhancement_panel.set_target("Image")
            self.load_params_to_ui(w.image_processor)
        finally:
            del blocker

    def current_processor(self):
        """Processor for the current target"""
        if self.window.enhancement_target == "K-Space":
            return self.window.kspace_processor
        return self.window.image_processor

    def _store_ui_params(self) -> None:
        """Persist the panel's current values into the active processor."""
        processor = self.current_processor()
        params = self.window.enhancement_panel.get_params()
        processor.contrast = params["contrast"]
        processor.brightness = params["brightness"]
        processor.use_log = params["use_log"]
        processor.rotation_angle = params["rotation"]
        processor.zoom_factor = params["zoom"]

    def on_target_changed(self, target: str) -> None:
        """Handle enhancement target change"""
        w = self.window
        # Save current UI parameters to current processor
        self._store_ui_params()

        # Switch target
        w.enhancement_target = target
        w.processor = self.current_processor()

        # Load parameters for new target to UI
        self.load_params_to_ui(w.processor)

        # Refresh display (both canvases always use their respective processors)
        w._display_current_slice()

    # ------------------------------------------------------------------
    # Live parameter edits
    # ------------------------------------------------------------------
    def set_param(self, name: str, value) -> None:
        """Apply a single processor parameter and re-render."""
        setattr(self.window.processor, name, value)
        self.window._display_current_slice()

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def rotate_90(self, times: int) -> None:
        """Handle 90-degree rotation button"""
        w = self.window
        if w.current_image is None:
            return

        # Add to current rotation (cumulative)
        w.processor.rotation_90_times = (w.processor.rotation_90_times + times) % 4
        w._display_current_slice()

    def flip_horizontal(self) -> None:
        """Toggle horizontal flip"""
        w = self.window
        if w.current_image is None:
            return

        w.processor.flip_h = not w.processor.flip_h
        w._display_current_slice()

    def flip_vertical(self) -> None:
        """Toggle vertical flip"""
        w = self.window
        if w.current_image is None:
            return

        w.processor.flip_v = not w.processor.flip_v
        w._display_current_slice()

    def on_reset(self) -> None:
        """Reset all enhancements for current target"""
        w = self.window
        # Reset current processor only
        w.processor.reset()

        # Reset UI controls (blocks signals to prevent recursion)
        w.enhancement_panel.reset_all(block_signals=True)

        # Refresh display
        w._display_current_slice()

    def set_zoom(self, factor: float) -> None:
        """Set zoom level"""
        w = self.window
        w.processor.zoom_factor = factor
        w.enhancement_panel.set_zoom(factor)
        w._display_current_slice()
