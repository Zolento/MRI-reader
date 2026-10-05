"""Main Window - thin coordinator: widget tree, menus, state, signal wiring.

Loading, rendering and enhancement bookkeeping live in :mod:`src.app`.  The
delegating methods below are frozen seams for the offscreen GUI gate.
"""

import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .app.display import DisplayController
from .app.enhancement import EnhancementController
from .app.file_loader import FileLoader
from .core import views
from .core.image_processor import ImageProcessor
from .ui.enhancement_panel import EnhancementPanel
from .ui.image_canvas import ImageCanvas
from .ui.slice_navigator import SliceNavigator


class MainWindow(QMainWindow):
    """Main window: menu bar + toolbar, two canvases, panel and navigator."""

    def __init__(self):
        super().__init__()

        # Data
        self.mri_data = None
        self.current_image = None
        self.kspace_data = None  # Store original k-space for display
        self.is_kspace = False

        # Processors - separate for k-space and image
        self.kspace_processor = ImageProcessor()
        self.image_processor = ImageProcessor()
        self.enhancement_target = "Image"  # Default target

        # Current processor alias (will be updated based on target selection)
        self.processor = self.image_processor

        # Application-layer collaborators (logic lives in src/app)
        self.file_loader = FileLoader(self)
        self.display = DisplayController(self)
        self.enhancement = EnhancementController(self)

        # Setup UI
        self._setup_ui()

        # Set window properties
        self.setWindowTitle("MRI Reader")
        self.resize(1200, 800)
        self.setAcceptDrops(True)

    def _setup_ui(self):
        """Setup the user interface"""
        # Create menu bar
        self._create_menu_bar()

        # Create toolbar
        self._create_toolbar()

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout (vertical: top area + bottom navigator)
        main_layout = QVBoxLayout(central_widget)

        # Top area: horizontal splitter for canvases and enhancement panel
        top_splitter = QSplitter(Qt.Horizontal)

        # === Left: K-Space display area ===
        kspace_container = QWidget()
        kspace_layout = QVBoxLayout(kspace_container)

        # K-space canvas
        self.kspace_canvas = ImageCanvas()
        self.kspace_canvas.slice_changed.connect(self._on_canvas_slice_changed)
        kspace_layout.addWidget(self.kspace_canvas)

        # K-space info label
        self.kspace_info_label = QLabel("K-Space")
        self.kspace_info_label.setAlignment(Qt.AlignCenter)
        self.kspace_info_label.setStyleSheet("padding: 3px; color: gray; font-size: 11px;")
        kspace_layout.addWidget(self.kspace_info_label)

        top_splitter.addWidget(kspace_container)

        # === Middle: Image display area ===
        image_container = QWidget()
        image_layout = QVBoxLayout(image_container)

        # Image canvas
        self.canvas = ImageCanvas()
        self.canvas.slice_changed.connect(self._on_canvas_slice_changed)
        image_layout.addWidget(self.canvas)

        # Image info label
        self.image_info_label = QLabel("Image")
        self.image_info_label.setAlignment(Qt.AlignCenter)
        self.image_info_label.setStyleSheet("padding: 3px; color: gray; font-size: 11px;")
        image_layout.addWidget(self.image_info_label)

        top_splitter.addWidget(image_container)

        # === Right: Enhancement panel ===
        self.enhancement_panel = EnhancementPanel()
        self.enhancement_panel.target_changed.connect(self._on_target_changed)
        self.enhancement_panel.contrast_changed.connect(self._on_contrast_changed)
        self.enhancement_panel.brightness_changed.connect(self._on_brightness_changed)
        self.enhancement_panel.log_toggled.connect(self._on_log_toggled)
        self.enhancement_panel.rotation_changed.connect(self._on_rotation_changed)
        self.enhancement_panel.zoom_changed.connect(self._on_zoom_changed)
        self.enhancement_panel.rotate_90_clicked.connect(self._on_rotate_90)
        self.enhancement_panel.flip_horizontal_clicked.connect(self._on_flip_horizontal)
        self.enhancement_panel.flip_vertical_clicked.connect(self._on_flip_vertical)
        self.enhancement_panel.reset_clicked.connect(self._on_reset)

        # Add enhancement panel to scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumWidth(350)
        scroll_area.setWidget(self.enhancement_panel)

        top_splitter.addWidget(scroll_area)

        # Set initial splitter sizes
        top_splitter.setSizes([400, 400, 350])

        main_layout.addWidget(top_splitter, stretch=1)

        # === Bottom: Slice navigator ===
        self.slice_navigator = SliceNavigator()
        self.slice_navigator.slice_changed.connect(self._on_slice_changed)
        self.slice_navigator.view_changed.connect(self._on_view_changed)
        main_layout.addWidget(self.slice_navigator)

        # Info label at very bottom
        self.info_label = QLabel("未加载文件")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet("padding: 5px; color: gray;")
        main_layout.addWidget(self.info_label)

    def _create_menu_bar(self):
        """Create menu bar"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("文件")

        open_action = file_menu.addAction("打开")
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_file)

        save_action = file_menu.addAction("保存为JPG")
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_image)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("退出")
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)

        # Edit menu
        edit_menu = menubar.addMenu("编辑")

        reset_action = edit_menu.addAction("重置所有设置")
        reset_action.setShortcut("Ctrl+R")
        reset_action.triggered.connect(self._on_reset)

        # View menu
        view_menu = menubar.addMenu("视图")

        view_menu.addSeparator()

        zoom_in_action = view_menu.addAction("放大")
        zoom_in_action.setShortcut("Ctrl+=")
        zoom_in_action.triggered.connect(lambda: self._set_zoom(1.2))

        zoom_out_action = view_menu.addAction("缩小")
        zoom_out_action.setShortcut("Ctrl+-")
        zoom_out_action.triggered.connect(lambda: self._set_zoom(0.8))

        fit_action = view_menu.addAction("适应窗口")
        fit_action.setShortcut("Ctrl+0")
        fit_action.triggered.connect(lambda: self._set_zoom(1.0))

        # Help menu
        help_menu = menubar.addMenu("帮助")

        about_action = help_menu.addAction("关于")
        about_action.triggered.connect(self._show_about)

    def _create_toolbar(self):
        """Create toolbar with common actions"""
        toolbar = self.addToolBar("主工具栏")
        toolbar.setMovable(False)

        # Open file
        open_action = toolbar.addAction("Open")
        open_action.triggered.connect(self._open_file)

        # Save image
        save_action = toolbar.addAction("Save")
        save_action.triggered.connect(self._save_image)

        toolbar.addSeparator()

        # Reset
        reset_action = toolbar.addAction("Reset")
        reset_action.triggered.connect(self._on_reset)

    def _open_file(self):
        """Open file dialog and load MRI data"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "打开MRI文件",
            "",
            "MRI Files (*.npy *.mat *.h5 *.hdf5);;NumPy Files (*.npy);;MAT Files (*.mat);;"
            "HDF5 Files (*.h5 *.hdf5);;All Files (*)",
        )

        if not file_path:
            return

        self._open_file_path(file_path)

    def dragEnterEvent(self, event):
        """接受拖入的文件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """处理拖入的文件"""
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.isfile(file_path):
                self._open_file_path(file_path)
                break  # 只处理第一个文件

    # Frozen compatibility seams (names/behaviour preserved; now delegates)
    def _open_file_path(self, file_path: str):
        """Load MRI data from a given file path (used by both dialog and drag&drop)"""
        return self.file_loader.open_file_path(file_path)

    def _load_file(
        self,
        file_path: str,
        is_kspace: bool = True,
        mat_key: str = None,
        acquisition_mode: str = "2d",
        dim3_interpretation: str = "coil_hw",
        dim4_interpretation: str = "coil_slice_hw",
    ):
        """Load and process MRI file (delegates to the file loader)"""
        return self.file_loader.load_file(
            file_path,
            is_kspace=is_kspace,
            mat_key=mat_key,
            acquisition_mode=acquisition_mode,
            dim3_interpretation=dim3_interpretation,
            dim4_interpretation=dim4_interpretation,
        )

    def _peek_file_ndim(self, file_path: str) -> int:
        """Peek at a file's ndim without loading it into MRIData."""
        return self.file_loader.peek_file_ndim(file_path)

    def _ask_data_type_with_options(self, file_path: str):
        """Ask for data type / acquisition mode / dimension interpretation."""
        return self.file_loader.ask_data_type_with_options(file_path)

    def _ask_mat_key(self, file_path: str) -> str:
        """Ask user to select a key from MAT file"""
        return self.file_loader.ask_mat_key(file_path)

    def _ask_h5_key(self, file_path: str) -> str:
        """Ask user to select a key from HDF5 file"""
        return self.file_loader.ask_h5_key(file_path)

    def _combine_channels(self, slice_data):
        """RSS coil combination - thin delegate to the core authority."""
        return views.rss_combine(slice_data)

    def _combine_channels_complex(self, data):
        """RSS coil combination for complex data - delegate to core."""
        return views.rss_combine_complex(data)

    def _display_current_slice(self):
        """Display the current slice with all enhancements"""
        return self.display.display_current_slice()

    def _setup_for_data(self):
        """Setup UI components based on loaded data"""
        return self.display.setup_for_data()

    def _on_target_changed(self, target: str):
        """Handle enhancement target change"""
        return self.enhancement.on_target_changed(target)

    def _on_reset(self):
        """Reset all enhancements for current target"""
        return self.enhancement.on_reset()

    # Signal handlers
    def _on_slice_changed(self, slice_idx):
        """Handle slice change from navigator (slider, keys, buttons, canvas)"""
        self.display.sync_canvas_slice()
        self._display_current_slice()

    def _on_view_changed(self, view_type):
        """Handle view change from navigator"""
        # Update navigator + both canvases to this view's canonical range.
        self.display.apply_view_range(view_type)
        self._display_current_slice()

    def _on_canvas_slice_changed(self, slice_idx):
        """Handle slice change from canvas click"""
        self.slice_navigator._go_to_slice(slice_idx)

    def _on_contrast_changed(self, value):
        """Handle contrast change"""
        self.enhancement.set_param("contrast", value)

    def _on_brightness_changed(self, value):
        """Handle brightness change"""
        self.enhancement.set_param("brightness", value)

    def _on_log_toggled(self, enabled):
        """Handle log transform toggle"""
        self.enhancement.set_param("use_log", enabled)

    def _on_rotation_changed(self, angle):
        """Handle rotation change"""
        self.enhancement.set_param("rotation_angle", angle)

    def _on_zoom_changed(self, factor):
        """Handle zoom change"""
        self.enhancement.set_param("zoom_factor", factor)

    def _on_rotate_90(self, times):
        """Handle 90-degree rotation button"""
        self.enhancement.rotate_90(times)

    def _on_flip_horizontal(self):
        """Toggle horizontal flip"""
        self.enhancement.flip_horizontal()

    def _on_flip_vertical(self):
        """Toggle vertical flip"""
        self.enhancement.flip_vertical()

    def _set_zoom(self, factor):
        """Set zoom level"""
        self.enhancement.set_zoom(factor)

    def _save_image(self):
        """Save current image as JPG"""
        self.display.save_image()

    def _show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "关于 MRI Reader",
            f"<h3>MRI Reader v{__version__}</h3>"
            "<p>一个基于Qt和Python的MRI图像阅读工具</p>"
            "<p><b>功能:</b></p>"
            "<ul>"
            "<li>支持2D/3D MRI图像和k-space数据</li>"
            "<li>自动数据类型检测</li>"
            "<li>k-space到图像的FFT转换</li>"
            "<li>对比度、亮度、旋转、缩放等增强操作</li>"
            "<li>3D数据多视角显示(横截面/矢状面/冠状面)</li>"
            "</ul>"
            "<p><b>技术栈:</b> PyQt5, NumPy, SciPy</p>",
        )

    def keyPressEvent(self, event):
        """Handle global keyboard events"""
        # Pass key events to slice navigator
        if self.slice_navigator.is_3d_mode:
            self.slice_navigator.keyPressEvent(event)
        else:
            super().keyPressEvent(event)
