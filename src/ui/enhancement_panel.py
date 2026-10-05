"""
Enhancement Panel - UI panel for image enhancement operations
Provides controls for contrast, brightness, log transform, rotation, and zoom
"""

from PyQt5.QtCore import QSignalBlocker, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

# Defaults shared by the controls and by ImageProcessor.reset(), so a UI reset
# and a processor reset always describe the same state.
DEFAULT_CONTRAST = 1.0
DEFAULT_BRIGHTNESS = 0.0
DEFAULT_LOG_ENABLED = False
DEFAULT_ROTATION = 0
DEFAULT_ZOOM = 1.0


class EnhancementPanel(QWidget):
    """
    Panel with controls for image enhancement

    Features:
    - Target selector (K-Space / Image)
    - Contrast adjustment (slider + spinbox)
    - Brightness adjustment (slider + spinbox)
    - Log transform toggle
    - Rotation controls
    - Zoom controls
    - Reset button
    """

    # Signals
    target_changed = pyqtSignal(str)  # "K-Space" or "Image"
    contrast_changed = pyqtSignal(float)
    brightness_changed = pyqtSignal(float)
    log_toggled = pyqtSignal(bool)
    rotation_changed = pyqtSignal(float)
    zoom_changed = pyqtSignal(float)
    rotate_90_clicked = pyqtSignal(int)  # times parameter
    flip_horizontal_clicked = pyqtSignal()
    flip_vertical_clicked = pyqtSignal()
    reset_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI layout"""
        layout = QVBoxLayout(self)

        # Target selector
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("增强目标:"))
        self.target_combo = QComboBox()
        self.target_combo.addItems(["K-Space", "Image"])
        self.target_combo.currentTextChanged.connect(lambda t: self.target_changed.emit(t))
        target_layout.addWidget(self.target_combo)
        target_layout.addStretch()
        layout.addLayout(target_layout)

        # Contrast control
        self.contrast_group = self._create_contrast_group()
        layout.addWidget(self.contrast_group)

        # Brightness control
        self.brightness_group = self._create_brightness_group()
        layout.addWidget(self.brightness_group)

        # Log transform
        self.log_group = self._create_log_group()
        layout.addWidget(self.log_group)

        # Rotation controls
        self.rotation_group = self._create_rotation_group()
        layout.addWidget(self.rotation_group)

        # Zoom control
        self.zoom_group = self._create_zoom_group()
        layout.addWidget(self.zoom_group)

        # Flip controls
        self.flip_group = self._create_flip_group()
        layout.addWidget(self.flip_group)

        # Reset button
        self.reset_btn = QPushButton("重置所有")
        self.reset_btn.clicked.connect(lambda: self.reset_clicked.emit())
        layout.addWidget(self.reset_btn)

        # Add stretch to push everything to top
        layout.addStretch()

    def _create_contrast_group(self) -> QGroupBox:
        """Create contrast control group"""
        group = QGroupBox("对比度")
        layout = QHBoxLayout()

        # Slider
        self.contrast_slider = QSlider(Qt.Horizontal)
        self.contrast_slider.setMinimum(10)  # 0.1
        self.contrast_slider.setMaximum(500)  # 5.0
        self.contrast_slider.setValue(100)  # 1.0
        self.contrast_slider.valueChanged.connect(self._on_contrast_slider_changed)
        layout.addWidget(self.contrast_slider)

        # Spinbox
        self.contrast_spin = QDoubleSpinBox()
        self.contrast_spin.setMinimum(0.1)
        self.contrast_spin.setMaximum(5.0)
        self.contrast_spin.setValue(1.0)
        self.contrast_spin.setSingleStep(0.1)
        self.contrast_spin.setDecimals(2)
        self.contrast_spin.valueChanged.connect(self._on_contrast_spin_changed)
        layout.addWidget(self.contrast_spin)

        group.setLayout(layout)
        return group

    def _create_brightness_group(self) -> QGroupBox:
        """Create brightness control group"""
        group = QGroupBox("亮度")
        layout = QHBoxLayout()

        # Slider
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setMinimum(-100)
        self.brightness_slider.setMaximum(100)
        self.brightness_slider.setValue(0)
        self.brightness_slider.valueChanged.connect(self._on_brightness_slider_changed)
        layout.addWidget(self.brightness_slider)

        # Spinbox
        self.brightness_spin = QDoubleSpinBox()
        self.brightness_spin.setMinimum(-1.0)
        self.brightness_spin.setMaximum(1.0)
        self.brightness_spin.setValue(0.0)
        self.brightness_spin.setSingleStep(0.05)
        self.brightness_spin.setDecimals(2)
        self.brightness_spin.valueChanged.connect(self._on_brightness_spin_changed)
        layout.addWidget(self.brightness_spin)

        group.setLayout(layout)
        return group

    def _create_log_group(self) -> QGroupBox:
        """Create log transform control"""
        group = QGroupBox("Log变换")
        layout = QHBoxLayout()

        self.log_checkbox = QCheckBox("启用Log变换 (用于查看k-space)")
        self.log_checkbox.stateChanged.connect(
            lambda state: self.log_toggled.emit(state == Qt.Checked)
        )
        layout.addWidget(self.log_checkbox)

        group.setLayout(layout)
        return group

    def _create_rotation_group(self) -> QGroupBox:
        """Create rotation control group"""
        group = QGroupBox("旋转")
        layout = QVBoxLayout()

        # Angle control
        angle_layout = QHBoxLayout()
        angle_layout.addWidget(QLabel("角度:"))

        self.rotation_spin = QSpinBox()
        self.rotation_spin.setMinimum(-180)
        self.rotation_spin.setMaximum(180)
        self.rotation_spin.setValue(0)
        self.rotation_spin.setSingleStep(1)
        self.rotation_spin.valueChanged.connect(self._on_rotation_changed)
        angle_layout.addWidget(self.rotation_spin)
        angle_layout.addWidget(QLabel("°"))
        angle_layout.addStretch()

        layout.addLayout(angle_layout)

        # Quick rotation buttons
        quick_btn_layout = QHBoxLayout()
        btn_90 = QPushButton("90°")
        btn_90.clicked.connect(lambda: self.rotate_90_clicked.emit(1))
        quick_btn_layout.addWidget(btn_90)

        btn_180 = QPushButton("180°")
        btn_180.clicked.connect(lambda: self.rotate_90_clicked.emit(2))
        quick_btn_layout.addWidget(btn_180)

        btn_270 = QPushButton("270°")
        btn_270.clicked.connect(lambda: self.rotate_90_clicked.emit(3))
        quick_btn_layout.addWidget(btn_270)

        layout.addLayout(quick_btn_layout)

        group.setLayout(layout)
        return group

    def _create_zoom_group(self) -> QGroupBox:
        """Create zoom control group"""
        group = QGroupBox("缩放")
        layout = QHBoxLayout()

        # Slider
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setMinimum(10)  # 0.1x
        self.zoom_slider.setMaximum(500)  # 5.0x
        self.zoom_slider.setValue(100)  # 1.0x
        self.zoom_slider.valueChanged.connect(self._on_zoom_slider_changed)
        layout.addWidget(self.zoom_slider)

        # Spinbox
        self.zoom_spin = QDoubleSpinBox()
        self.zoom_spin.setMinimum(0.1)
        self.zoom_spin.setMaximum(5.0)
        self.zoom_spin.setValue(1.0)
        self.zoom_spin.setSingleStep(0.1)
        self.zoom_spin.setDecimals(2)
        self.zoom_spin.valueChanged.connect(self._on_zoom_spin_changed)
        layout.addWidget(self.zoom_spin)

        group.setLayout(layout)
        return group

    def _create_flip_group(self) -> QGroupBox:
        """Create flip control group"""
        group = QGroupBox("翻转")
        layout = QHBoxLayout()

        btn_h = QPushButton("水平翻转")
        btn_h.clicked.connect(lambda: self.flip_horizontal_clicked.emit())
        layout.addWidget(btn_h)

        btn_v = QPushButton("垂直翻转")
        btn_v.clicked.connect(lambda: self.flip_vertical_clicked.emit())
        layout.addWidget(btn_v)

        group.setLayout(layout)
        return group

    @staticmethod
    def _sync_silently(widget, value):
        """Update a paired widget without re-entering its change handler."""
        was_blocked = widget.blockSignals(True)
        try:
            widget.setValue(value)
        finally:
            widget.blockSignals(was_blocked)

    def _on_contrast_slider_changed(self, value):
        """Handle contrast slider change"""
        contrast = value / 100.0
        self._sync_silently(self.contrast_spin, contrast)
        self.contrast_changed.emit(contrast)

    def _on_contrast_spin_changed(self, value):
        """Handle contrast spinbox change"""
        self._sync_silently(self.contrast_slider, int(value * 100))
        self.contrast_changed.emit(value)

    def _on_brightness_slider_changed(self, value):
        """Handle brightness slider change"""
        brightness = value / 100.0
        self._sync_silently(self.brightness_spin, brightness)
        self.brightness_changed.emit(brightness)

    def _on_brightness_spin_changed(self, value):
        """Handle brightness spinbox change"""
        self._sync_silently(self.brightness_slider, int(value * 100))
        self.brightness_changed.emit(value)

    def _on_rotation_changed(self, value):
        """Handle rotation change"""
        self.rotation_changed.emit(value)

    def _on_zoom_slider_changed(self, value):
        """Handle zoom slider change"""
        zoom = value / 100.0
        self._sync_silently(self.zoom_spin, zoom)
        self.zoom_changed.emit(zoom)

    def _on_zoom_spin_changed(self, value):
        """Handle zoom spinbox change"""
        self._sync_silently(self.zoom_slider, int(value * 100))
        self.zoom_changed.emit(value)

    def set_contrast(self, value: float):
        """Set contrast value programmatically"""
        self.contrast_slider.setValue(int(value * 100))
        self.contrast_spin.setValue(value)

    def set_brightness(self, value: float):
        """Set brightness value programmatically"""
        self.brightness_slider.setValue(int(value * 100))
        self.brightness_spin.setValue(value)

    def set_log_enabled(self, enabled: bool):
        """Set log transform enabled"""
        self.log_checkbox.setChecked(enabled)

    def set_rotation(self, angle: int):
        """Set rotation angle"""
        self.rotation_spin.setValue(angle)

    def set_zoom(self, factor: float):
        """Set zoom factor"""
        self.zoom_slider.setValue(int(factor * 100))
        self.zoom_spin.setValue(factor)

    def reset_all(self, block_signals=True):
        """
        Reset all controls to default values

        Args:
            block_signals: If True, block signals during reset to prevent recursion
        """
        controls = (
            self.contrast_slider,
            self.contrast_spin,
            self.brightness_slider,
            self.brightness_spin,
            self.log_checkbox,
            self.rotation_spin,
            self.zoom_slider,
            self.zoom_spin,
        )

        # Block both the panel's own signals and every child control, so the
        # reset cannot recursively re-enter the enhancement pipeline.
        blockers = []
        if block_signals:
            blockers = [QSignalBlocker(self)]
            blockers.extend(QSignalBlocker(control) for control in controls)

        try:
            self.set_contrast(DEFAULT_CONTRAST)
            self.set_brightness(DEFAULT_BRIGHTNESS)
            self.set_log_enabled(DEFAULT_LOG_ENABLED)
            self.set_rotation(DEFAULT_ROTATION)
            self.set_zoom(DEFAULT_ZOOM)
        finally:
            # Dropping the blockers restores the previous signal states.
            blockers.clear()

        # Only emit signal if not blocking
        if not block_signals:
            self.reset_clicked.emit()

    def get_params(self) -> dict:
        """Get current parameter values"""
        return {
            "contrast": self.contrast_spin.value(),
            "brightness": self.brightness_spin.value(),
            "use_log": self.log_checkbox.isChecked(),
            "rotation": int(self.rotation_spin.value()),
            "zoom": self.zoom_spin.value(),
        }

    def set_params(self, params: dict):
        """Set parameter values"""
        self.set_contrast(params.get("contrast", 1.0))
        self.set_brightness(params.get("brightness", 0.0))
        self.set_log_enabled(params.get("use_log", False))
        self.set_rotation(int(params.get("rotation", 0)))
        self.set_zoom(params.get("zoom", 1.0))

    def set_target(self, target: str):
        """Set the target selector value"""
        idx = self.target_combo.findText(target)
        if idx >= 0:
            self.target_combo.setCurrentIndex(idx)
