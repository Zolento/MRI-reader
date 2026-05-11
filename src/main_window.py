"""
Main Window - Main application window integrating all components
"""

import sys
import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QSplitter, QFileDialog, QMessageBox, QLabel, QScrollArea
)
from PyQt5.QtCore import Qt
import numpy as np

from .core.mri_data import MRIData, DataType, DataDimension
from .core.kspace_converter import KSpaceConverter
from .core.image_processor import ImageProcessor
from .ui.image_canvas import ImageCanvas
from .ui.enhancement_panel import EnhancementPanel
from .ui.slice_navigator import SliceNavigator


class MainWindow(QMainWindow):
    """
    Main application window
    
    Layout:
    - Menu bar and toolbar at top
    - Central area with image canvas
    - Right panel with enhancement controls
    - Bottom panel with slice navigator (for 3D data)
    """
    
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
        file_menu = menubar.addMenu('文件')
        
        open_action = file_menu.addAction('打开')
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self._open_file)
        
        save_action = file_menu.addAction('保存为JPG')
        save_action.setShortcut('Ctrl+S')
        save_action.triggered.connect(self._save_image)
        
        file_menu.addSeparator()
        
        exit_action = file_menu.addAction('退出')
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        
        # Edit menu
        edit_menu = menubar.addMenu('编辑')
        
        reset_action = edit_menu.addAction('重置所有设置')
        reset_action.setShortcut('Ctrl+R')
        reset_action.triggered.connect(self._on_reset)
        
        # View menu
        view_menu = menubar.addMenu('视图')
        
        view_menu.addSeparator()
        
        zoom_in_action = view_menu.addAction('放大')
        zoom_in_action.setShortcut('Ctrl+=')
        zoom_in_action.triggered.connect(lambda: self._set_zoom(1.2))
        
        zoom_out_action = view_menu.addAction('缩小')
        zoom_out_action.setShortcut('Ctrl+-')
        zoom_out_action.triggered.connect(lambda: self._set_zoom(0.8))
        
        fit_action = view_menu.addAction('适应窗口')
        fit_action.setShortcut('Ctrl+0')
        fit_action.triggered.connect(lambda: self._set_zoom(1.0))
        
        # Help menu
        help_menu = menubar.addMenu('帮助')
        
        about_action = help_menu.addAction('关于')
        about_action.triggered.connect(self._show_about)
    
    def _create_toolbar(self):
        """Create toolbar with common actions"""
        toolbar = self.addToolBar('主工具栏')
        toolbar.setMovable(False)
        
        # Open file
        open_action = toolbar.addAction('Open')
        open_action.triggered.connect(self._open_file)

        # Save image
        save_action = toolbar.addAction('Save')
        save_action.triggered.connect(self._save_image)

        toolbar.addSeparator()

        # Reset
        reset_action = toolbar.addAction('Reset')
        reset_action.triggered.connect(self._on_reset)
    
    def _open_file(self):
        """Open file dialog and load MRI data"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "打开MRI文件",
            "",
            "MRI Files (*.npy *.mat *.h5 *.hdf5);;NumPy Files (*.npy);;MAT Files (*.mat);;HDF5 Files (*.h5 *.hdf5);;All Files (*)"
        )

        if not file_path:
            return

        self._open_file_path(file_path)

    def _open_file_path(self, file_path: str):
        """Load MRI data from a given file path (used by both dialog and drag&drop)"""
        data_type_result = self._ask_data_type_with_options(file_path)
        if data_type_result is None:
            return

        is_kspace, acquisition_mode, dim3_interpretation, dim4_interpretation = data_type_result

        selected_key = None
        if file_path.endswith('.mat'):
            selected_key = self._ask_mat_key(file_path)
            if selected_key is None:
                return
        elif file_path.endswith(('.h5', '.hdf5')):
            selected_key = self._ask_h5_key(file_path)
            if selected_key is None:
                return

        try:
            self._load_file(file_path, is_kspace=is_kspace, mat_key=selected_key,
                           acquisition_mode=acquisition_mode,
                           dim3_interpretation=dim3_interpretation,
                           dim4_interpretation=dim4_interpretation)
        except Exception as e:
            QMessageBox.critical(
                self,
                "错误",
                f"加载文件失败:\n{str(e)}"
            )

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
    
    def _peek_file_ndim(self, file_path: str) -> int:
        """Peek at a file's ndim without loading it into MRIData."""
        if file_path.endswith(('.h5', '.hdf5')):
            import h5py
            with h5py.File(file_path, 'r') as f:
                for key in f.keys():
                    ndim = f[key].ndim
                    if ndim >= 2:
                        return ndim
                keys = list(f.keys())
                return f[keys[0]].ndim if keys else 0
        if file_path.endswith('.mat'):
            from scipy import io
            mat_data = io.loadmat(file_path)
            valid_keys = [k for k in mat_data if not k.startswith('__')]
            if not valid_keys:
                return 0
            return mat_data[valid_keys[0]].ndim
        if file_path.endswith('.npy'):
            return np.load(file_path).ndim
        return 0

    def _ask_data_type_with_options(self, file_path: str):
        """
        Ask user to select data type, acquisition mode, 3D interpretation, and 4D order

        Returns:
            Tuple of (is_kspace, acquisition_mode, dim3_interpretation, dim4_interpretation) or None if cancelled
        """
        from PyQt5.QtWidgets import (
            QDialog, QRadioButton, QVBoxLayout, QHBoxLayout,
            QPushButton, QLabel, QGroupBox, QButtonGroup
        )

        file_ndim = self._peek_file_ndim(file_path)

        dialog = QDialog(self)
        dialog.setWindowTitle("选择数据选项")
        dialog.setMinimumWidth(480)

        layout = QVBoxLayout(dialog)

        # File info
        filename = file_path.split('/')[-1]
        layout.addWidget(QLabel(f"文件: {filename}"))

        # === Group 1: Data type ===
        type_group = QGroupBox("数据类型")
        type_layout = QVBoxLayout(type_group)

        radio_kspace = QRadioButton("K-Space (频域数据)")
        radio_kspace.setChecked(True)
        radio_image = QRadioButton("Image (图像数据)")

        type_layout.addWidget(radio_kspace)
        type_layout.addWidget(radio_image)
        layout.addWidget(type_group)

        # === Group 2: Acquisition mode (for k-space only) ===
        acq_group = QGroupBox("采集方式")
        acq_layout = QVBoxLayout(acq_group)

        radio_2d_acq = QRadioButton("2D 采集（逐层采集，2D IFFT）")
        radio_2d_acq.setChecked(True)
        radio_3d_acq = QRadioButton("3D 采集（体积采集，3D IFFT）")

        acq_layout.addWidget(radio_2d_acq)
        acq_layout.addWidget(radio_3d_acq)
        layout.addWidget(acq_group)

        # === Group 3: 3D shape interpretation ===
        dim3_group = QGroupBox("三维数据解释")
        dim3_layout = QVBoxLayout(dim3_group)
        dim3_desc = QLabel("当原始数据有3个维度 (X, H, W) 时:")
        dim3_desc.setStyleSheet("color: gray; font-size: 11px;")
        dim3_layout.addWidget(dim3_desc)

        radio_coil_hw = QRadioButton("(Coil, H, W) — 第一维是线圈通道")
        radio_coil_hw.setChecked(True)
        radio_slice_hw = QRadioButton("(Slice, H, W) — 第一维是切片数")

        dim3_layout.addWidget(radio_coil_hw)
        dim3_layout.addWidget(radio_slice_hw)
        layout.addWidget(dim3_group)

        # === Group 4: 4D dimension order (visible only for 4D files) ===
        dim4_group = QGroupBox("四维数据维度顺序")
        dim4_layout = QVBoxLayout(dim4_group)
        dim4_desc = QLabel("当原始数据有4个维度时 (dim0, dim1, H, W):")
        dim4_desc.setStyleSheet("color: gray; font-size: 11px;")
        dim4_layout.addWidget(dim4_desc)

        radio_coil_slice_hw = QRadioButton("(Coil, Slice, H, W) — dim0线圈, dim1切片")
        radio_coil_slice_hw.setChecked(True)
        radio_slice_coil_hw = QRadioButton("(Slice, Coil, H, W) — dim0切片, dim1线圈")

        dim4_layout.addWidget(radio_coil_slice_hw)
        dim4_layout.addWidget(radio_slice_coil_hw)
        layout.addWidget(dim4_group)

        # Update group availability based on selection
        def update_availability():
            is_ks = radio_kspace.isChecked()
            acq_group.setEnabled(is_ks)
            dim4_group.setVisible(True)

        radio_kspace.toggled.connect(update_availability)
        radio_image.toggled.connect(update_availability)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("确定")
        btn_cancel = QPushButton("取消")
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        result = [None]

        def on_ok():
            is_kspace = radio_kspace.isChecked()
            acquisition_mode = "2d" if radio_2d_acq.isChecked() else "3d"
            dim3_interp = "coil_hw" if radio_coil_hw.isChecked() else "slice_hw"
            dim4_interp = "coil_slice_hw" if radio_coil_slice_hw.isChecked() else "slice_coil_hw"
            result[0] = (is_kspace, acquisition_mode, dim3_interp, dim4_interp)
            dialog.accept()

        def on_cancel():
            result[0] = None
            dialog.reject()

        btn_ok.clicked.connect(on_ok)
        btn_cancel.clicked.connect(on_cancel)
        update_availability()

        if dialog.exec_() == QDialog.Accepted:
            return result[0]
        return None
    
    def _ask_mat_key(self, file_path: str) -> str:
        """
        Ask user to select a key from MAT file
        
        Returns:
            Selected key string, or None if cancelled
        """
        from PyQt5.QtWidgets import (
            QDialog, QComboBox, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
        )
        from scipy import io
        
        # Load mat file to get keys
        mat_data = io.loadmat(file_path)
        
        # Filter out scipy internal keys
        valid_keys = [k for k in mat_data.keys() if not k.startswith('__')]
        
        if not valid_keys:
            QMessageBox.warning(self, "警告", "MAT文件中没有有效的数据键")
            return None
        
        dialog = QDialog(self)
        dialog.setWindowTitle("选择MAT数据键")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(dialog)
        
        # File info
        filename = file_path.split('/')[-1]
        layout.addWidget(QLabel(f"文件: {filename}"))
        layout.addWidget(QLabel("请选择数据键:"))
        
        # Combobox for keys
        key_combo = QComboBox()
        for key in valid_keys:
            shape = mat_data[key].shape
            key_combo.addItem(f"{key} (shape: {shape})")
        layout.addWidget(key_combo)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("确定")
        btn_cancel = QPushButton("取消")
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        result = [None]
        
        def on_ok():
            selected = key_combo.currentText().split(' (')[0]
            result[0] = selected
            dialog.accept()
        
        def on_cancel():
            result[0] = None
            dialog.reject()
        
        btn_ok.clicked.connect(on_ok)
        btn_cancel.clicked.connect(on_cancel)
        
        if dialog.exec_() == QDialog.Accepted:
            return result[0]
        return None
    
    def _load_file(self, file_path: str, is_kspace: bool = True, mat_key: str = None,
                   acquisition_mode: str = "2d", dim3_interpretation: str = "coil_hw",
                   dim4_interpretation: str = "coil_slice_hw"):
        """Load and process MRI file

        Args:
            file_path: Path to the .npy, .mat, or .h5 file
            is_kspace: True if k-space data, False if image data
            mat_key: Key to use for .mat / .h5 files (None for .npy)
            acquisition_mode: "2d" for slice-by-slice, "3d" for volume acquisition
            dim3_interpretation: "coil_hw" or "slice_hw" for 3D raw data
            dim4_interpretation: "coil_slice_hw" or "slice_coil_hw" for 4D raw data
        """
        if file_path.endswith('.mat'):
            self._load_mat_file(file_path, mat_key,
                               acquisition_mode=acquisition_mode,
                               dim3_interpretation=dim3_interpretation,
                               dim4_interpretation=dim4_interpretation)
        elif file_path.endswith(('.h5', '.hdf5')):
            self._load_h5_file(file_path, mat_key,
                              acquisition_mode=acquisition_mode,
                              dim3_interpretation=dim3_interpretation,
                              dim4_interpretation=dim4_interpretation)
        else:
            self._load_npy_file(file_path,
                               acquisition_mode=acquisition_mode,
                               dim3_interpretation=dim3_interpretation,
                               dim4_interpretation=dim4_interpretation)

        # Use user's selection instead of auto-detection
        self.is_kspace = is_kspace

        # Convert k-space if needed
        if self.is_kspace:
            self._convert_kspace()
        else:
            # Use processed data directly
            self.current_image = self.mri_data.processed_data.copy()

        # No extra normalization - canvas handles display normalization

        # Setup UI based on data
        self._setup_for_data()

        # Display first slice
        self._display_current_slice()

        # Update info
        self.info_label.setText(self.mri_data.get_info())
        self.info_label.setToolTip(self.mri_data.get_info())
    
    def _load_processor_params_to_ui(self, processor: ImageProcessor):
        """Load processor parameters to UI controls"""
        params = {
            'contrast': processor.contrast,
            'brightness': processor.brightness,
            'use_log': processor.use_log,
            'rotation': processor.rotation_angle,
            'zoom': processor.zoom_factor,
        }
        self.enhancement_panel.blockSignals(True)
        self.enhancement_panel.set_params(params)
        self.enhancement_panel.blockSignals(False)
    
    def _load_npy_file(self, file_path: str, acquisition_mode: str = "2d",
                        dim3_interpretation: str = "coil_hw",
                        dim4_interpretation: str = "coil_slice_hw"):
        """Load .npy file"""
        self.mri_data = MRIData(file_path, acquisition_mode=acquisition_mode,
                                dim3_interpretation=dim3_interpretation,
                                dim4_interpretation=dim4_interpretation)
    
    def _load_mat_file(self, file_path: str, key: str, acquisition_mode: str = "2d",
                        dim3_interpretation: str = "coil_hw",
                        dim4_interpretation: str = "coil_slice_hw"):
        """Load .mat file with specified key"""
        from scipy import io

        mat_data = io.loadmat(file_path)

        if key not in mat_data:
            available = [k for k in mat_data.keys() if not k.startswith('__')]
            raise ValueError(f"Key '{key}' not found in MAT file. Available keys: {available}")

        # Extract data
        raw_data = mat_data[key]

        # Convert to numpy array if needed (MAT files often load as matrix type)
        if hasattr(raw_data, 'A'):
            raw_data = raw_data.A

        # Squeeze single dimensions (MAT files may add extra dims)
        raw_data = np.squeeze(raw_data)

        # Create MRIData with preloaded data and user options
        self.mri_data = MRIData(file_path, preloaded_data=raw_data,
                                acquisition_mode=acquisition_mode,
                                dim3_interpretation=dim3_interpretation,
                                dim4_interpretation=dim4_interpretation)

    def _load_h5_file(self, file_path: str, key: str, acquisition_mode: str = "2d",
                      dim3_interpretation: str = "coil_hw",
                      dim4_interpretation: str = "coil_slice_hw"):
        """Load .h5/.hdf5 file with specified key"""
        import h5py

        with h5py.File(file_path, 'r') as f:
            if key not in f:
                available = list(f.keys())
                raise ValueError(f"Key '{key}' not found in H5 file. Available keys: {available}")
            ds = f[key]
            raw_data = ds[()]

        if hasattr(raw_data, 'A'):
            raw_data = raw_data.A
        raw_data = np.squeeze(raw_data)

        self.mri_data = MRIData(file_path, preloaded_data=raw_data,
                                acquisition_mode=acquisition_mode,
                                dim3_interpretation=dim3_interpretation,
                                dim4_interpretation=dim4_interpretation)

    def _ask_h5_key(self, file_path: str) -> str:
        """Ask user to select a key from HDF5 file"""
        from PyQt5.QtWidgets import (
            QDialog, QComboBox, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
        )
        import h5py

        with h5py.File(file_path, 'r') as f:
            keys = list(f.keys())

        if not keys:
            QMessageBox.warning(self, "警告", "H5文件中没有有效的数据集")
            return None

        dialog = QDialog(self)
        dialog.setWindowTitle("选择H5数据集")
        dialog.setMinimumWidth(400)

        layout = QVBoxLayout(dialog)
        filename = file_path.split('/')[-1]
        layout.addWidget(QLabel(f"文件: {filename}"))
        layout.addWidget(QLabel("请选择数据集:"))

        key_combo = QComboBox()
        with h5py.File(file_path, 'r') as f:
            for key in keys:
                shape = f[key].shape
                key_combo.addItem(f"{key} (shape: {shape})")
        layout.addWidget(key_combo)

        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("确定")
        btn_cancel = QPushButton("取消")
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        result = [None]

        def on_ok():
            selected = key_combo.currentText().split(' (')[0]
            result[0] = selected
            dialog.accept()

        def on_cancel():
            result[0] = None
            dialog.reject()

        btn_ok.clicked.connect(on_ok)
        btn_cancel.clicked.connect(on_cancel)

        if dialog.exec_() == QDialog.Accepted:
            return result[0]
        return None

    def _convert_kspace(self):
        """Convert k-space to image using user-selected acquisition mode"""
        # Store original k-space for display
        self.kspace_data = self.mri_data.processed_data.copy()
        
        # Use user-selected acquisition mode from the dialog
        use_3d = (self.mri_data.acquisition_mode == "3d")

        self.current_image = KSpaceConverter.convert(self.mri_data, mode_3d=use_3d)
    
    def _normalize_data(self):
        """Normalize data to 0-1 range"""
        if self.current_image is None:
            return
        
        # Normalize each slice independently
        for ch in range(self.current_image.shape[0]):
            for sl in range(self.current_image.shape[1]):
                slice_data = self.current_image[ch, sl]
                if slice_data.max() > slice_data.min():
                    self.current_image[ch, sl] = (slice_data - slice_data.min()) / \
                                                (slice_data.max() - slice_data.min())
                else:
                    self.current_image[ch, sl] = np.zeros_like(slice_data)
    
    def _setup_for_data(self):
        """Setup UI components based on loaded data"""
        is_3d = (self.mri_data.dimension == DataDimension.DIM_3D and
                self.mri_data.num_slices > 1)

        # Setup canvases
        self.canvas.set_3d_mode(is_3d, self.mri_data.num_slices)
        self.kspace_canvas.set_3d_mode(is_3d, self.mri_data.num_slices)

        # Setup slice navigator
        self.slice_navigator.set_3d_mode(is_3d, self.mri_data.num_slices)

        # Reset processors
        self.kspace_processor.reset()
        self.image_processor.reset()
        
        # K-space default: enable log transform for better visibility
        if self.is_kspace:
            self.kspace_processor.use_log = True
        
        # Set default target to Image
        self.enhancement_target = "Image"
        self.processor = self.image_processor
        self.enhancement_panel.set_target("Image")
        
        # Load Image processor params to UI
        self._load_processor_params_to_ui(self.image_processor)
        
        # Set initial navigator range for axial view
        if is_3d:
            self._update_navigator_range('axial')
    
    def _display_current_slice(self):
        """Display the current slice with all enhancements"""
        if self.current_image is None or self.mri_data is None:
            return

        slice_idx = self.slice_navigator.current_slice
        view_type = self.slice_navigator.current_view

        # Clamp slice index to valid range for current view
        max_idx = self._get_max_index_for_view(view_type)
        slice_idx = max(0, min(slice_idx, max_idx))

        # === Display K-Space (left canvas) - always use kspace_processor ===
        if self.kspace_data is not None:
            kspace = self._get_kspace_slice(slice_idx, view_type)
            # Apply k-space processor (handles complex->magnitude, log, contrast, etc.)
            kspace_enhanced = self.kspace_processor.process(kspace)
            self.kspace_canvas.set_image(kspace_enhanced)
            self.kspace_info_label.setText(f"K-Space ({view_type}, idx {slice_idx})")
        else:
            # Not k-space data - show blank or message
            self.kspace_canvas.clear()
            self.kspace_info_label.setText("非K-Space数据")

        # === Display Image (middle canvas) - always use image_processor ===
        if self.mri_data.dimension == DataDimension.DIM_3D and self.mri_data.num_slices > 1:
            # For 3D data, get the appropriate view
            if view_type == 'axial':
                # Get all channels for this slice
                slice_data = self.current_image[:, slice_idx]  # (channels, height, width)
                image = self._combine_channels(slice_data)
            elif view_type == 'sagittal':
                # Sagittal: index along width dimension -> (slices, height)
                image = self._get_sagittal_view(slice_idx)
            elif view_type == 'coronal':
                # Coronal: index along height dimension -> (slices, width)
                image = self._get_coronal_view(slice_idx)
            else:
                slice_data = self.current_image[:, slice_idx]
                image = self._combine_channels(slice_data)
        else:
            # 2D data - combine all channels if multi-channel
            slice_data = self.current_image[:, 0]  # (channels, height, width)
            image = self._combine_channels(slice_data)

        # Apply image processor
        enhanced = self.image_processor.process(image)

        # Display
        self.canvas.set_image(enhanced)
        self.image_info_label.setText(f"Image ({view_type}, idx {slice_idx})")
    
    def _get_max_index_for_view(self, view_type: str) -> int:
        """Get the maximum valid index for the current view type"""
        if self.mri_data.dimension != DataDimension.DIM_3D or self.mri_data.num_slices <= 1:
            return 0
        
        if view_type == 'axial':
            return self.mri_data.num_slices - 1
        elif view_type == 'sagittal':
            return self.mri_data.width - 1
        elif view_type == 'coronal':
            return self.mri_data.height - 1
        return 0
    
    def _get_sagittal_view(self, height_idx: int) -> np.ndarray:
        """
        Get sagittal view at specified height index
        data shape: (slices, height, width)
        Slice at height_idx → (slices, width)
        """
        views_per_channel = []
        for ch in range(self.current_image.shape[0]):
            data = self.current_image[ch]  # (slices, height, width)
            views_per_channel.append(data[:, height_idx, :])
        
        if len(views_per_channel) == 1:
            return views_per_channel[0]
        
        views_stacked = np.stack(views_per_channel, axis=0)
        return self._combine_channels(views_stacked)
    
    def _get_coronal_view(self, width_idx: int) -> np.ndarray:
        """
        Get coronal view at specified width index
        data shape: (slices, height, width)
        Slice at width_idx → (slices, height)
        """
        views_per_channel = []
        for ch in range(self.current_image.shape[0]):
            data = self.current_image[ch]  # (slices, height, width)
            views_per_channel.append(data[:, :, width_idx])
        
        if len(views_per_channel) == 1:
            return views_per_channel[0]
        
        views_stacked = np.stack(views_per_channel, axis=0)
        return self._combine_channels(views_stacked)
    
    def _get_kspace_slice(self, slice_idx: int, view_type: str) -> np.ndarray:
        """
        Get k-space slice for display with RSS combination if multi-channel

        Args:
            slice_idx: slice index (meaning depends on view_type)
            view_type: 'axial', 'sagittal', or 'coronal'

        Returns:
            2D k-space data (complex)
        """
        if self.mri_data.dimension == DataDimension.DIM_3D and self.mri_data.num_slices > 1:
            if view_type == 'axial':
                # Get all channels for this slice
                kspace_slice = self.kspace_data[:, slice_idx]  # (channels, height, width)
                # RSS combine channels
                return self._combine_channels_complex(kspace_slice)
            elif view_type == 'sagittal':
                return self._get_kspace_sagittal(slice_idx)
            elif view_type == 'coronal':
                return self._get_kspace_coronal(slice_idx)
            else:
                kspace_slice = self.kspace_data[:, slice_idx]
                return self._combine_channels_complex(kspace_slice)
        else:
            # 2D data
            kspace_slice = self.kspace_data[:, 0]
            return self._combine_channels_complex(kspace_slice)
    
    def _get_kspace_sagittal(self, height_idx: int) -> np.ndarray:
        """Get sagittal view from k-space data with RSS combination"""
        views_per_channel = []
        for ch in range(self.kspace_data.shape[0]):
            data = self.kspace_data[ch]  # (slices, height, width)
            views_per_channel.append(data[:, height_idx, :])

        views_stacked = np.stack(views_per_channel, axis=0)
        return self._combine_channels_complex(views_stacked)

    def _get_kspace_coronal(self, width_idx: int) -> np.ndarray:
        """Get coronal view from k-space data with RSS combination"""
        views_per_channel = []
        for ch in range(self.kspace_data.shape[0]):
            data = self.kspace_data[ch]  # (slices, height, width)
            views_per_channel.append(data[:, :, width_idx])

        views_stacked = np.stack(views_per_channel, axis=0)
        return self._combine_channels_complex(views_stacked)
    
    def _combine_channels_complex(self, data: np.ndarray) -> np.ndarray:
        """
        Combine multiple coil channels for k-space data using RSS
        Works with complex data
        """
        if data.shape[0] == 1:
            return data[0]
        else:
            return np.sqrt(np.sum(np.abs(data)**2, axis=0))
    
    def _get_current_processor(self) -> ImageProcessor:
        """Get the processor for the current target"""
        if self.enhancement_target == "K-Space":
            return self.kspace_processor
        return self.image_processor
    
    def _on_target_changed(self, target: str):
        """Handle enhancement target change"""
        # Save current UI parameters to current processor
        current_params = self.enhancement_panel.get_params()
        if self.enhancement_target == "K-Space":
            self.kspace_processor.contrast = current_params['contrast']
            self.kspace_processor.brightness = current_params['brightness']
            self.kspace_processor.use_log = current_params['use_log']
            self.kspace_processor.rotation_angle = current_params['rotation']
            self.kspace_processor.zoom_factor = current_params['zoom']
        else:
            self.image_processor.contrast = current_params['contrast']
            self.image_processor.brightness = current_params['brightness']
            self.image_processor.use_log = current_params['use_log']
            self.image_processor.rotation_angle = current_params['rotation']
            self.image_processor.zoom_factor = current_params['zoom']
        
        # Switch target
        self.enhancement_target = target
        self.processor = self._get_current_processor()
        
        # Load parameters for new target to UI
        if target == "K-Space":
            self._load_processor_params_to_ui(self.kspace_processor)
        else:
            self._load_processor_params_to_ui(self.image_processor)
        
        # Refresh display (both canvases always use their respective processors)
        self._display_current_slice()
    
    def _combine_channels(self, slice_data: np.ndarray) -> np.ndarray:
        """
        Combine multiple coil channels using Root Sum of Squares (RSS)
        
        Args:
            slice_data: numpy array of shape (channels, height, width)
            
        Returns:
            Combined 2D image of shape (height, width)
        """
        if slice_data.shape[0] == 1:
            # Single channel - no combination needed
            return slice_data[0]
        else:
            # Multi-channel - RSS combination
            # RSS = sqrt(sum(|channel_i|^2))
            return np.sqrt(np.sum(np.abs(slice_data)**2, axis=0))
    
    def _on_slice_changed(self, slice_idx):
        """Handle slice change from navigator"""
        self._display_current_slice()
    
    def _on_view_changed(self, view_type):
        """Handle view change from navigator"""
        # Update slice navigator range for the new view type
        self._update_navigator_range(view_type)
        self._display_current_slice()
    
    def _update_navigator_range(self, view_type: str):
        """Update slice navigator slider range based on current view type"""
        if self.mri_data is None:
            return
        
        if self.mri_data.dimension != DataDimension.DIM_3D or self.mri_data.num_slices <= 1:
            return
        
        if view_type == 'axial':
            max_idx = self.mri_data.num_slices - 1
        elif view_type == 'sagittal':
            max_idx = self.mri_data.height - 1
        elif view_type == 'coronal':
            max_idx = self.mri_data.width - 1
        else:
            max_idx = 0
        
        # Update navigator
        self.slice_navigator.slider.setMaximum(max(0, max_idx))
        self.slice_navigator.num_slices = max_idx + 1
        
        # Clamp current slice to new range
        if self.slice_navigator.current_slice > max_idx:
            self.slice_navigator.current_slice = max_idx
            self.slice_navigator.slider.setValue(max_idx)
        
        self.slice_navigator._update_label()
    
    def _on_canvas_slice_changed(self, slice_idx):
        """Handle slice change from canvas click"""
        self.slice_navigator._go_to_slice(slice_idx)
    
    def _on_contrast_changed(self, value):
        """Handle contrast change"""
        self.processor.contrast = value
        self._display_current_slice()
    
    def _on_brightness_changed(self, value):
        """Handle brightness change"""
        self.processor.brightness = value
        self._display_current_slice()
    
    def _on_log_toggled(self, enabled):
        """Handle log transform toggle"""
        self.processor.use_log = enabled
        self._display_current_slice()
    
    def _on_rotation_changed(self, angle):
        """Handle rotation change"""
        self.processor.rotation_angle = angle
        self._display_current_slice()
    
    def _on_zoom_changed(self, factor):
        """Handle zoom change"""
        self.processor.zoom_factor = factor
        self._display_current_slice()
    
    def _on_rotate_90(self, times):
        """Handle 90-degree rotation button"""
        if self.current_image is None:
            return
        
        # Add to current rotation (cumulative)
        self.processor.rotation_90_times = (self.processor.rotation_90_times + times) % 4
        self._display_current_slice()
    
    def _on_flip_horizontal(self):
        """Toggle horizontal flip"""
        if self.current_image is None:
            return
        
        self.processor.flip_h = not self.processor.flip_h
        self._display_current_slice()
    
    def _on_flip_vertical(self):
        """Toggle vertical flip"""
        if self.current_image is None:
            return
        
        self.processor.flip_v = not self.processor.flip_v
        self._display_current_slice()
    
    def _on_reset(self):
        """Reset all enhancements for current target"""
        # Reset current processor only
        self.processor.reset()

        # Reset UI controls (blocks signals to prevent recursion)
        self.enhancement_panel.reset_all(block_signals=True)

        # Refresh display
        self._display_current_slice()
    
    def _set_zoom(self, factor):
        """Set zoom level"""
        self.processor.zoom_factor = factor
        self.enhancement_panel.set_zoom(factor)
        self._display_current_slice()
    
    def _save_image(self):
        """Save current image as JPG"""
        if self.current_image is None:
            QMessageBox.warning(self, "警告", "没有可保存的图像")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存图像",
            "",
            "JPEG Image (*.jpg);;PNG Image (*.png);;All Files (*)"
        )

        if file_path:
            try:
                # Get current displayed slice with same logic as _display_current_slice
                slice_idx = self.slice_navigator.current_slice
                view_type = self.slice_navigator.current_view

                if self.mri_data.dimension == DataDimension.DIM_3D and self.mri_data.num_slices > 1:
                    if view_type == 'axial':
                        slice_data = self.current_image[:, slice_idx]
                        image = self._combine_channels(slice_data)
                    elif view_type == 'sagittal':
                        image = self._get_sagittal_view(slice_idx)
                    elif view_type == 'coronal':
                        image = self._get_coronal_view(slice_idx)
                    else:
                        slice_data = self.current_image[:, slice_idx]
                        image = self._combine_channels(slice_data)
                else:
                    slice_data = self.current_image[:, 0]
                    image = self._combine_channels(slice_data)

                # Apply image processor (not current target processor)
                enhanced = self.image_processor.process(image)

                # Convert to 8-bit
                image_8bit = ImageProcessor.convert_to_8bit(enhanced)

                # Save using PIL if available, otherwise save as numpy
                try:
                    from PIL import Image
                    img = Image.fromarray(image_8bit)
                    img.save(file_path)
                except ImportError:
                    # Save as numpy array
                    np.save(file_path.replace('.jpg', '.npy').replace('.png', '.npy'), image_8bit)
                    QMessageBox.information(
                        self,
                        "提示",
                        "未安装PIL,已保存为npy格式"
                    )
                    return

                QMessageBox.information(
                    self,
                    "成功",
                    f"图像已保存到:\n{file_path}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "错误",
                    f"保存失败:\n{str(e)}"
                )
    
    def _show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "关于 MRI Reader",
            "<h3>MRI Reader v0.1.0</h3>"
            "<p>一个基于Qt和Python的MRI图像阅读工具</p>"
            "<p><b>功能:</b></p>"
            "<ul>"
            "<li>支持2D/3D MRI图像和k-space数据</li>"
            "<li>自动数据类型检测</li>"
            "<li>k-space到图像的FFT转换</li>"
            "<li>对比度、亮度、旋转、缩放等增强操作</li>"
            "<li>3D数据多视角显示(横截面/矢状面/冠状面)</li>"
            "</ul>"
            "<p><b>技术栈:</b> PyQt5, NumPy, SciPy</p>"
        )
    
    def keyPressEvent(self, event):
        """Handle global keyboard events"""
        # Pass key events to slice navigator
        if self.slice_navigator.is_3d_mode:
            self.slice_navigator.keyPressEvent(event)
        else:
            super().keyPressEvent(event)
