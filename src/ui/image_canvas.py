"""
Image Canvas - Custom widget for displaying MRI images
Supports mouse interactions for slice selection and zoom
"""

import numpy as np
from PyQt5.QtCore import QRect, Qt, pyqtSignal
from PyQt5.QtGui import QImage, QPainter, QPixmap
from PyQt5.QtWidgets import QWidget

# Zoom bounds shared by wheelEvent/reset_zoom so they cannot drift apart.
MIN_ZOOM = 0.1
MAX_ZOOM = 5.0
WHEEL_ZOOM_STEP = 0.1


class ImageCanvas(QWidget):
    """
    Custom widget for displaying MRI images

    Features:
    - Display 2D images with proper scaling
    - Mouse click to select slice (3D mode)
    - Mouse wheel for zoom
    - Maintains aspect ratio
    """

    # Signals
    slice_changed = pyqtSignal(int)  # Emitted when user clicks to change slice
    zoom_changed = pyqtSignal(float)  # Emitted when user zooms with mouse wheel

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = None
        self.pixmap = None
        self.zoom_level = 1.0
        self.is_3d_mode = False
        self.current_slice = 0
        self.num_slices = 1

        # QImage wraps the numpy buffer without copying it, so the buffer must
        # outlive the QImage.  Keep both references alive on the instance.
        self.qimage = None
        self._buffer = None

        # Set minimum size
        self.setMinimumSize(400, 400)
        self.setStyleSheet("background-color: black;")

    def set_image(self, image: np.ndarray):
        """
        Set the image to display

        Args:
            image: 2D numpy array (normalized 0-1 or any range)
        """
        if image is None:
            self.image = None
            self.pixmap = None
            self.qimage = None
            self._buffer = None
            self.update()
            return

        # Ensure image is 2D
        if len(image.shape) != 2:
            raise ValueError(f"Expected 2D image, got {len(image.shape)}D")

        self.image = image.copy()
        self._update_pixmap()
        self.update()

    def set_3d_mode(self, is_3d: bool, num_slices: int):
        """Enable/disable 3D mode"""
        self.is_3d_mode = is_3d
        self.num_slices = num_slices
        self.current_slice = 0

    def _update_pixmap(self):
        """Convert numpy array to QPixmap for display"""
        if self.image is None:
            self.pixmap = None
            self.qimage = None
            self._buffer = None
            return

        # Normalize image to 0-255
        image_normalized = self.image.copy()
        if image_normalized.max() > image_normalized.min():
            image_normalized = (image_normalized - image_normalized.min()) / (
                image_normalized.max() - image_normalized.min()
            )

        # Convert to 8-bit; ascontiguousarray guarantees the byte layout QImage expects.
        image_8bit = np.ascontiguousarray((image_normalized * 255).astype(np.uint8))

        height, width = image_8bit.shape
        if width <= 0 or height <= 0:
            self.pixmap = None
            self.qimage = None
            self._buffer = None
            return

        bytes_per_line = width
        # Keep the numpy buffer alive for as long as the QImage references it.
        self._buffer = image_8bit
        self.qimage = QImage(
            self._buffer.data, width, height, bytes_per_line, QImage.Format_Grayscale8
        )

        # Convert to QPixmap (this copies the pixels, but the buffer stays held).
        self.pixmap = QPixmap.fromImage(self.qimage)

    def paintEvent(self, event):
        """Paint the image, respecting the current zoom level."""
        super().paintEvent(event)

        if self.pixmap is None or self.pixmap.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        try:
            available_size = self.size()
            pixmap_size = self.pixmap.size()
            if available_size.width() <= 0 or available_size.height() <= 0:
                return
            if pixmap_size.width() <= 0 or pixmap_size.height() <= 0:
                return

            # Base scale fits the whole image inside the widget (aspect preserved).
            # 1x therefore means "fit to view", exactly like the previous behavior.
            fit_scale = min(
                available_size.width() / pixmap_size.width(),
                available_size.height() / pixmap_size.height(),
            )

            # User zoom multiplies the fit scale; >1x overflows the widget and
            # is clipped by the painter.
            scale = fit_scale * self.zoom_level
            scaled_width = max(1, int(round(pixmap_size.width() * scale)))
            scaled_height = max(1, int(round(pixmap_size.height() * scale)))

            # Center the scaled image in the widget.
            x = (available_size.width() - scaled_width) // 2
            y = (available_size.height() - scaled_height) // 2

            painter.drawPixmap(QRect(x, y, scaled_width, scaled_height), self.pixmap)
        finally:
            painter.end()

    def mousePressEvent(self, event):
        """Handle mouse press events"""
        if event.button() == Qt.LeftButton and self.is_3d_mode and self.num_slices > 0:
            # Calculate which slice was clicked based on y position
            # This is a simple heuristic - could be improved
            pos = event.pos()
            height = self.height()
            y_ratio = pos.y() / height if height > 0 else 0.0
            y_ratio = max(0.0, min(1.0, y_ratio))
            new_slice = int(y_ratio * self.num_slices)
            new_slice = max(0, min(new_slice, self.num_slices - 1))

            if new_slice != self.current_slice:
                self.current_slice = new_slice
                self.slice_changed.emit(self.current_slice)

    def wheelEvent(self, event):
        """Handle mouse wheel for zoom"""
        # Zoom in/out with Ctrl+wheel
        if event.modifiers() & Qt.ControlModifier:
            zoom_delta = WHEEL_ZOOM_STEP
            if event.angleDelta().y() > 0:
                self.zoom_level *= 1 + zoom_delta
            else:
                self.zoom_level /= 1 + zoom_delta

            # Limit zoom range
            self.zoom_level = max(MIN_ZOOM, min(self.zoom_level, MAX_ZOOM))

            self.zoom_changed.emit(self.zoom_level)
            event.accept()
        elif self.is_3d_mode:
            # In 3D mode, use wheel to navigate slices
            if event.angleDelta().y() > 0:
                new_slice = self.current_slice + 1
            else:
                new_slice = self.current_slice - 1

            new_slice = max(0, min(new_slice, self.num_slices - 1))

            if new_slice != self.current_slice:
                self.current_slice = new_slice
                self.slice_changed.emit(self.current_slice)

            event.accept()
        else:
            super().wheelEvent(event)

    def reset_zoom(self):
        """Reset zoom level"""
        self.zoom_level = 1.0
        self.update()

    def clear(self):
        """Clear the canvas"""
        self.image = None
        self.pixmap = None
        self.qimage = None
        self._buffer = None
        self.update()
