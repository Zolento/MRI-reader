"""
Image Canvas - Custom widget for displaying MRI images
Supports mouse interactions for slice selection and zoom
"""

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QPainter, QImage, QPixmap
import numpy as np


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
            return
        
        # Normalize image to 0-255
        image_normalized = self.image.copy()
        if image_normalized.max() > image_normalized.min():
            image_normalized = (image_normalized - image_normalized.min()) / \
                             (image_normalized.max() - image_normalized.min())
        
        # Convert to 8-bit
        image_8bit = (image_normalized * 255).astype(np.uint8)
        
        # Create QImage
        height, width = image_8bit.shape
        bytes_per_line = width
        self.qimage = QImage(image_8bit.data, width, height, bytes_per_line, QImage.Format_Grayscale8)
        
        # Convert to QPixmap
        self.pixmap = QPixmap.fromImage(self.qimage)
    
    def paintEvent(self, event):
        """Paint the image"""
        super().paintEvent(event)
        
        if self.pixmap is None:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # Calculate scaled size maintaining aspect ratio
        available_size = self.size()
        pixmap_size = self.pixmap.size()
        
        # Apply zoom
        scaled_width = int(pixmap_size.width() * self.zoom_level)
        scaled_height = int(pixmap_size.height() * self.zoom_level)
        
        # Scale to fit widget while maintaining aspect ratio
        scaled_pixmap = self.pixmap.scaled(
            available_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        
        # Center the pixmap
        x = (available_size.width() - scaled_pixmap.width()) // 2
        y = (available_size.height() - scaled_pixmap.height()) // 2
        
        painter.drawPixmap(x, y, scaled_pixmap)
        painter.end()
    
    def mousePressEvent(self, event):
        """Handle mouse press events"""
        if event.button() == Qt.LeftButton and self.is_3d_mode:
            # Calculate which slice was clicked based on y position
            # This is a simple heuristic - could be improved
            pos = event.pos()
            y_ratio = pos.y() / self.height()
            new_slice = int(y_ratio * self.num_slices)
            new_slice = max(0, min(new_slice, self.num_slices - 1))
            
            if new_slice != self.current_slice:
                self.current_slice = new_slice
                self.slice_changed.emit(self.current_slice)
    
    def wheelEvent(self, event):
        """Handle mouse wheel for zoom"""
        # Zoom in/out with Ctrl+wheel
        if event.modifiers() & Qt.ControlModifier:
            zoom_delta = 0.1
            if event.angleDelta().y() > 0:
                self.zoom_level *= (1 + zoom_delta)
            else:
                self.zoom_level /= (1 + zoom_delta)
            
            # Limit zoom range
            self.zoom_level = max(0.1, min(self.zoom_level, 5.0))
            
            self.zoom_changed.emit(self.zoom_level)
            event.accept()
        else:
            # In 3D mode, use wheel to navigate slices
            if self.is_3d_mode:
                if event.angleDelta().y() > 0:
                    new_slice = self.current_slice + 1
                else:
                    new_slice = self.current_slice - 1
                
                new_slice = max(0, min(new_slice, self.num_slices - 1))
                
                if new_slice != self.current_slice:
                    self.current_slice = new_slice
                    self.slice_changed.emit(self.current_slice)
                
                event.accept()
    
    def reset_zoom(self):
        """Reset zoom level"""
        self.zoom_level = 1.0
        self.update()
    
    def clear(self):
        """Clear the canvas"""
        self.image = None
        self.pixmap = None
        self.update()
