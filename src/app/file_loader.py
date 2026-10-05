"""
File loading and open-file dialogs for the MRI Reader main window.

Everything here is *host-driven*: the dialogs and the ``_ask_*`` seams are
looked up on the window instance at call time (``window._ask_data_type_with_options``
etc.).  That is deliberate - the offscreen GUI gate patches those names on the
``MainWindow`` class, and a call through the host keeps the patch effective.
"""

from __future__ import annotations

import inspect

import numpy as np
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from ..core.mri_data import MRIData


class FileLoader:
    """Owns the open-file dialogs and the ``MRIData`` construction helpers."""

    def __init__(self, window):
        self.window = window

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------
    def open_file_path(self, file_path: str):
        """Load MRI data from a given file path (used by dialog and drag&drop)"""
        w = self.window
        data_type_result = w._ask_data_type_with_options(file_path)
        if data_type_result is None:
            return

        is_kspace, acquisition_mode, dim3_interpretation, dim4_interpretation = data_type_result

        selected_key = None
        if file_path.endswith(".mat"):
            selected_key = w._ask_mat_key(file_path)
            if selected_key is None:
                return
        elif file_path.endswith((".h5", ".hdf5")):
            selected_key = w._ask_h5_key(file_path)
            if selected_key is None:
                return

        try:
            w._load_file(
                file_path,
                is_kspace=is_kspace,
                mat_key=selected_key,
                acquisition_mode=acquisition_mode,
                dim3_interpretation=dim3_interpretation,
                dim4_interpretation=dim4_interpretation,
            )
        except Exception as e:
            from PyQt5.QtWidgets import QMessageBox

            QMessageBox.critical(w, "错误", f"加载文件失败:\n{str(e)}")

    def load_file(
        self,
        file_path: str,
        is_kspace: bool = True,
        mat_key: str = None,
        acquisition_mode: str = "2d",
        dim3_interpretation: str = "coil_hw",
        dim4_interpretation: str = "coil_slice_hw",
    ):
        """Load and process an MRI file.

        Args:
            file_path: Path to the .npy, .mat, or .h5 file
            is_kspace: True if k-space data, False if image data
            mat_key: Key to use for .mat / .h5 files (None for .npy)
            acquisition_mode: "2d" for slice-by-slice, "3d" for volume acquisition
            dim3_interpretation: "coil_hw" or "slice_hw" for 3D raw data
            dim4_interpretation: "coil_slice_hw" or "slice_coil_hw" for 4D raw data
        """
        w = self.window
        if file_path.endswith(".mat"):
            self.load_mat_file(
                file_path,
                mat_key,
                acquisition_mode=acquisition_mode,
                dim3_interpretation=dim3_interpretation,
                dim4_interpretation=dim4_interpretation,
            )
        elif file_path.endswith((".h5", ".hdf5")):
            self.load_h5_file(
                file_path,
                mat_key,
                acquisition_mode=acquisition_mode,
                dim3_interpretation=dim3_interpretation,
                dim4_interpretation=dim4_interpretation,
            )
        else:
            self.load_npy_file(
                file_path,
                acquisition_mode=acquisition_mode,
                dim3_interpretation=dim3_interpretation,
                dim4_interpretation=dim4_interpretation,
            )

        # Use the user's selection instead of auto-detection
        w.is_kspace = is_kspace

        # Materialize the display sources (k-space original + image domain).
        w.display.load_sources()

        # Setup UI based on data
        w._setup_for_data()

        # Display first slice
        w._display_current_slice()

        # Update info
        w.info_label.setText(w.mri_data.get_info())
        w.info_label.setToolTip(w.mri_data.get_info())

    # ------------------------------------------------------------------
    # Per-format loaders
    # ------------------------------------------------------------------
    def _install(self, new_data) -> None:
        """Adopt ``new_data`` as the window's MRIData, releasing the old one."""
        old = self.window.mri_data
        self.window.mri_data = new_data
        if old is not None and old is not new_data:
            close = getattr(old, "close", None)
            if callable(close):
                close()

    def load_npy_file(
        self,
        file_path: str,
        acquisition_mode: str = "2d",
        dim3_interpretation: str = "coil_hw",
        dim4_interpretation: str = "coil_slice_hw",
    ):
        """Load .npy file"""
        self._install(
            MRIData(
                file_path,
                acquisition_mode=acquisition_mode,
                dim3_interpretation=dim3_interpretation,
                dim4_interpretation=dim4_interpretation,
            )
        )

    def load_mat_file(
        self,
        file_path: str,
        key: str,
        acquisition_mode: str = "2d",
        dim3_interpretation: str = "coil_hw",
        dim4_interpretation: str = "coil_slice_hw",
    ):
        """Load .mat file with specified key"""
        from scipy import io

        mat_data = io.loadmat(file_path)

        if key not in mat_data:
            available = [k for k in mat_data.keys() if not k.startswith("__")]
            raise ValueError(f"Key '{key}' not found in MAT file. Available keys: {available}")

        # Extract data
        raw_data = mat_data[key]

        # Convert to numpy array if needed (MAT files often load as matrix type)
        if hasattr(raw_data, "A"):
            raw_data = raw_data.A

        # Squeeze single dimensions (MAT files may add extra dims)
        raw_data = np.squeeze(raw_data)

        # Create MRIData with preloaded data and user options
        self._install(
            MRIData(
                file_path,
                preloaded_data=raw_data,
                acquisition_mode=acquisition_mode,
                dim3_interpretation=dim3_interpretation,
                dim4_interpretation=dim4_interpretation,
            )
        )

    def load_h5_file(
        self,
        file_path: str,
        key: str,
        acquisition_mode: str = "2d",
        dim3_interpretation: str = "coil_hw",
        dim4_interpretation: str = "coil_slice_hw",
    ):
        """Load .h5/.hdf5 file with specified key.

        Prefers the core's lazy HDF5 path (``h5_key=``): the dataset is not read
        into memory here, and plane accessors stream only the displayed slice.
        Falls back to the historical eager preload if the installed core has no
        ``h5_key`` support.
        """
        import h5py

        with h5py.File(file_path, "r") as f:
            if key not in f:
                available = list(f.keys())
                raise ValueError(f"Key '{key}' not found in H5 file. Available keys: {available}")

        kwargs = dict(
            acquisition_mode=acquisition_mode,
            dim3_interpretation=dim3_interpretation,
            dim4_interpretation=dim4_interpretation,
        )

        if "h5_key" in inspect.signature(MRIData.__init__).parameters:
            self._install(MRIData(file_path, h5_key=key, **kwargs))
            return

        with h5py.File(file_path, "r") as f:
            raw_data = f[key][()]
        if hasattr(raw_data, "A"):
            raw_data = raw_data.A
        raw_data = np.squeeze(raw_data)
        self._install(MRIData(file_path, preloaded_data=raw_data, **kwargs))

    # ------------------------------------------------------------------
    # Dialogs
    # ------------------------------------------------------------------
    def peek_file_ndim(self, file_path: str) -> int:
        """Peek at a file's ndim without materializing its data.

        The dialog only needs the dimensionality, so nothing here may read the
        array body: a large ``.npy`` must cost a few header bytes, not its full
        size (an h5 ``Group`` must not crash the peek either).
        """
        if file_path.endswith((".h5", ".hdf5")):
            return self._peek_h5_ndim(file_path)
        if file_path.endswith(".mat"):
            return self._peek_mat_ndim(file_path)
        if file_path.endswith(".npy"):
            return self._peek_npy_ndim(file_path)
        return 0

    @staticmethod
    def _peek_h5_ndim(file_path: str) -> int:
        """First 2D+ Dataset's ndim, else the first Dataset's, else 0.

        Only top-level Datasets are considered; Groups (metadata containers,
        common in NIfTI/ISMRMRD-style files) are skipped rather than recursed
        into, so the result stays simple and predictable.
        """
        import h5py

        try:
            with h5py.File(file_path, "r") as f:
                datasets = [f[key] for key in f.keys() if isinstance(f[key], h5py.Dataset)]
                if not datasets:
                    return 0
                for dataset in datasets:
                    if dataset.ndim >= 2:
                        return int(dataset.ndim)
                return int(datasets[0].ndim)
        except Exception:
            return 0

    @staticmethod
    def _peek_npy_ndim(file_path: str) -> int:
        """Read only the ``.npy`` header (magic + shape), never the body."""
        import numpy.lib.format as npformat

        try:
            with open(file_path, "rb") as f:
                version = npformat.read_magic(f)
                reader = getattr(npformat, f"read_array_header_{version[0]}_{version[1]}", None)
                if reader is None:
                    return 0
                shape, _fortran_order, _dtype = reader(f)
            return len(shape)
        except Exception:
            # Not a valid .npy (or an unsupported header version): degrade to
            # "unknown" instead of crashing the dialog.
            return 0

    @staticmethod
    def _peek_mat_ndim(file_path: str) -> int:
        """First variable's ndim.

        ``scipy.io.loadmat`` has no header-only mode - the MAT container must be
        parsed as a whole - so this branch keeps that unavoidable cost and only
        guards against malformed content.
        """
        try:
            from scipy import io

            mat_data = io.loadmat(file_path)
            valid_keys = [k for k in mat_data if not k.startswith("__")]
            if not valid_keys:
                return 0
            return int(mat_data[valid_keys[0]].ndim)
        except Exception:
            return 0

    def ask_data_type_with_options(self, file_path: str):
        """
        Ask user to select data type, acquisition mode, 3D interpretation, and 4D order

        Returns:
            Tuple of (is_kspace, acquisition_mode, dim3_interpretation, dim4_interpretation)
            or None if cancelled
        """
        w = self.window
        # Kept for parity with the original dialog: it peeks the file's ndim.
        w._peek_file_ndim(file_path)

        dialog = QDialog(w)
        dialog.setWindowTitle("选择数据选项")
        dialog.setMinimumWidth(480)

        layout = QVBoxLayout(dialog)

        # File info
        filename = file_path.split("/")[-1]
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

    def ask_mat_key(self, file_path: str) -> str:
        """
        Ask user to select a key from MAT file

        Returns:
            Selected key string, or None if cancelled
        """
        from PyQt5.QtWidgets import QMessageBox
        from scipy import io

        # Load mat file to get keys
        mat_data = io.loadmat(file_path)

        # Filter out scipy internal keys
        valid_keys = [k for k in mat_data.keys() if not k.startswith("__")]

        if not valid_keys:
            QMessageBox.warning(self.window, "警告", "MAT文件中没有有效的数据键")
            return None

        dialog = QDialog(self.window)
        dialog.setWindowTitle("选择MAT数据键")
        dialog.setMinimumWidth(400)

        layout = QVBoxLayout(dialog)

        # File info
        filename = file_path.split("/")[-1]
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
            selected = key_combo.currentText().split(" (")[0]
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

    def ask_h5_key(self, file_path: str) -> str:
        """Ask user to select a dataset from an HDF5 file.

        Only top-level ``h5py.Dataset`` objects are offered: Groups carry no
        shape and cannot be loaded, and listing them would crash the dialog
        (``'Group' object has no attribute 'shape'``).
        """
        import h5py
        from PyQt5.QtWidgets import QMessageBox

        with h5py.File(file_path, "r") as f:
            datasets = [(key, f[key].shape) for key in f.keys() if isinstance(f[key], h5py.Dataset)]

        if not datasets:
            QMessageBox.warning(self.window, "警告", "H5文件中没有有效的数据集")
            return None

        dialog = QDialog(self.window)
        dialog.setWindowTitle("选择H5数据集")
        dialog.setMinimumWidth(400)

        layout = QVBoxLayout(dialog)
        filename = file_path.split("/")[-1]
        layout.addWidget(QLabel(f"文件: {filename}"))
        layout.addWidget(QLabel("请选择数据集:"))

        key_combo = QComboBox()
        for key, shape in datasets:
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
            selected = key_combo.currentText().split(" (")[0]
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
