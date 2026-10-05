"""
Slice Navigator - UI component for navigating through 3D MRI slices
Provides slider, buttons, and keyboard shortcuts for slice navigation
"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class SliceNavigator(QWidget):
    """
    Widget for navigating through 3D MRI slices

    Features:
    - Horizontal slider for slice selection
    - Previous/Next buttons
    - Current slice display
    - Keyboard shortcut hints
    """

    # Signals
    slice_changed = pyqtSignal(int)
    view_changed = pyqtSignal(str)  # 'axial', 'sagittal', 'coronal'

    def __init__(self, parent=None):
        super().__init__(parent)
        self.num_slices = 1
        self.current_slice = 0
        self.current_view = "axial"
        self.is_3d_mode = False

        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI layout"""
        layout = QVBoxLayout(self)

        # View tabs for 3D mode
        self.view_tabs = QTabWidget()
        self.view_tabs.addTab(QWidget(), "横截面 (Axial)")
        self.view_tabs.addTab(QWidget(), "矢状面 (Sagittal)")
        self.view_tabs.addTab(QWidget(), "冠状面 (Coronal)")
        self.view_tabs.currentChanged.connect(self._on_view_changed)
        layout.addWidget(self.view_tabs)

        # Slice control group
        slice_layout = QVBoxLayout()

        # Current slice display
        info_layout = QHBoxLayout()
        self.slice_label = QLabel("切片: 0 / 0")
        self.slice_label.setAlignment(Qt.AlignCenter)
        self.slice_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        info_layout.addWidget(self.slice_label)
        slice_layout.addLayout(info_layout)

        # Slider
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(0)
        self.slider.setValue(0)
        self.slider.valueChanged.connect(self._on_slider_changed)
        slice_layout.addWidget(self.slider)

        # Navigation buttons
        btn_layout = QHBoxLayout()

        btn_first = QPushButton("|<")
        btn_first.clicked.connect(lambda: self._go_to_slice(0))
        btn_layout.addWidget(btn_first)

        btn_prev = QPushButton("<")
        btn_prev.clicked.connect(self._prev_slice)
        btn_layout.addWidget(btn_prev)

        btn_next = QPushButton(">")
        btn_next.clicked.connect(self._next_slice)
        btn_layout.addWidget(btn_next)

        btn_last = QPushButton(">|")
        btn_last.clicked.connect(self._go_to_last_slice)
        btn_layout.addWidget(btn_last)

        slice_layout.addLayout(btn_layout)

        # Keyboard hint
        hint_label = QLabel("提示: 使用方向键←→或鼠标滚轮切换切片")
        hint_label.setAlignment(Qt.AlignCenter)
        hint_label.setStyleSheet("color: gray; font-size: 11px;")
        slice_layout.addWidget(hint_label)

        layout.addLayout(slice_layout)

    def set_3d_mode(self, is_3d: bool, num_slices: int):
        """
        Set 3D mode and number of slices

        Args:
            is_3d: Whether data is 3D
            num_slices: Number of slices
        """
        self.is_3d_mode = is_3d
        self.set_range(num_slices - 1)
        self.slider.setValue(0)
        self._update_label()

        # Enable/disable view tabs
        self.view_tabs.setEnabled(is_3d)

    def set_range(self, max_index: int):
        """
        Set the valid slice index range to ``[0, max_index]``.

        Single entry point for range changes so the slider maximum,
        ``num_slices``, ``current_slice`` and the label stay in sync.

        Args:
            max_index: Highest selectable slice index (>= 0)
        """
        max_index = max(0, int(max_index))
        self.num_slices = max_index + 1

        # Qt clamps the slider value into the new range and emits
        # valueChanged, which routes through _on_slider_changed.
        self.slider.setMaximum(max_index)
        if self.slider.value() > max_index:
            self.slider.setValue(max_index)

        # The slider is the source of truth after a range change.
        self.current_slice = self.slider.value()
        self._update_label()

    def _on_slider_changed(self, value):
        """Handle slider value change"""
        self.current_slice = value
        self._update_label()
        self.slice_changed.emit(self.current_slice)

    def _on_view_changed(self, index):
        """Handle view tab change"""
        view_map = {0: "axial", 1: "sagittal", 2: "coronal"}
        self.current_view = view_map.get(index, "axial")
        self.view_changed.emit(self.current_view)

    def _prev_slice(self):
        """Go to previous slice"""
        if self.current_slice > 0:
            self._go_to_slice(self.current_slice - 1)

    def _next_slice(self):
        """Go to next slice"""
        if self.current_slice < self.num_slices - 1:
            self._go_to_slice(self.current_slice + 1)

    def _go_to_slice(self, slice_idx: int):
        """Go to specific slice"""
        if 0 <= slice_idx < self.num_slices:
            self.current_slice = slice_idx
            self.slider.setValue(slice_idx)
            self._update_label()
            self.slice_changed.emit(self.current_slice)

    def _go_to_last_slice(self):
        """Go to last slice"""
        self._go_to_slice(self.num_slices - 1)

    def _update_label(self):
        """Update slice display label"""
        self.slice_label.setText(f"切片: {self.current_slice} / {self.num_slices - 1}")

    def keyPressEvent(self, event):
        """Handle keyboard events"""
        if not self.is_3d_mode:
            # Not ours to handle: pass it on instead of swallowing the event.
            super().keyPressEvent(event)
            return

        if event.key() == Qt.Key_Left:
            self._prev_slice()
            event.accept()
        elif event.key() == Qt.Key_Right:
            self._next_slice()
            event.accept()
        elif event.key() == Qt.Key_Up:
            self._prev_slice()
            event.accept()
        elif event.key() == Qt.Key_Down:
            self._next_slice()
            event.accept()
        else:
            super().keyPressEvent(event)

    def reset(self):
        """Reset to first slice"""
        self._go_to_slice(0)
        self.view_tabs.setCurrentIndex(0)
