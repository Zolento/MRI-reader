"""
MRI Data Model - Handles loading and interpreting MRI data
Detects data type (image/k-space) and dimensionality (2D/3D) with user guidance

Geometry contract
-----------------
After normalization the internal volume is always ``(C, S, H, W)`` where ``S`` is
the slice axis, ``H`` the row axis and ``W`` the column axis.  All view/plane
semantics live in :mod:`src.core.views`; this module never re-implements them.

Lazy HDF5
---------
When an ``.h5``/``.hdf5`` file is opened by path the dataset is *not* read into
memory.  :attr:`MRIData.raw_data` and :attr:`MRIData.processed_data` are
properties that materialize the full array on first access (with exactly the
same dtype and values as the previous eager implementation), while
:meth:`MRIData.get_slice`, :meth:`MRIData.get_view` and
:meth:`MRIData.get_view_channels` read only the requested plane straight from
the file.  Accessing ``processed_data``/``raw_data`` therefore re-instates the
eager (whole-volume) behavior; use the plane accessors to keep memory bounded.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Sequence, Tuple

import numpy as np

from . import views


class DataType(Enum):
    """Type of MRI data"""

    IMAGE = "image"
    KSPACE = "k-space"


class DataDimension(Enum):
    """Dimensionality of MRI data"""

    DIM_2D = "2D"
    DIM_3D = "3D"


class _LazyH5Source:
    """
    Read-only lazy handle over a single HDF5 dataset.

    Only shape/dtype metadata is read at construction; pixel data is fetched on
    demand through :meth:`read`.  The file handle is kept open so repeated slice
    reads are cheap and is released by :meth:`close`.

    Once :meth:`close` has been called the source is permanently dead: a later
    :meth:`read` raises ``ValueError`` instead of silently reopening the file.
    No legitimate path needs a resurrected handle -- :meth:`MRIData.close`
    discards the source -- and failing loudly prevents an unnoticed descriptor
    from being held open after teardown.
    """

    def __init__(self, path: str, key: str):
        import h5py

        self.path = path
        self.key = key
        with h5py.File(path, "r") as f:
            ds = f[key]
            self.shape: Tuple[int, ...] = tuple(int(s) for s in ds.shape)
            self.stored_dtype = ds.dtype
            self.ndim = ds.ndim
        self._file = None
        self._closed = False

    def _open(self):
        import h5py

        if self._file is None:
            self._file = h5py.File(self.path, "r")
        return self._file

    def read(self, indexer):
        """Read a subset (an h5py-style index tuple) of the dataset."""
        if self._closed:
            raise ValueError(
                f"Cannot read from closed HDF5 source {self.path!r} " f"(dataset {self.key!r})"
            )
        return self._open()[self.key][indexer]

    def close(self) -> None:
        """Release the underlying file handle; the source cannot be reused."""
        self._closed = True
        if self._file is not None:
            try:
                self._file.close()
            finally:
                self._file = None


class MRIData:
    """
    MRI data container with user-guided shape and type detection

    Expected shapes:
    - 3D k-space (3D acquisition): (channels, slices, phase, freq)
    - 3D k-space (2D acquisition): (channels/slices, phase, freq) - IFFT per slice
    - 3D image: (channels, slices, height, width) or (slices, height, width)
    - 2D k-space: (phase, freq) or (1, phase, freq)
    - 2D image: (height, width) or (1, height, width)

    Args:
        file_path: Path to .npy file
        preloaded_data: Pre-loaded numpy array (e.g. from .mat file)
        acquisition_mode: "2d" for slice-by-slice acquisition (default),
                          "3d" for volume acquisition
        dim3_interpretation: For 3D raw data (X, H, W), how to interpret:
                             "coil_hw" = (Coil, H, W) - default
                             "slice_hw" = (Slice, H, W)
    """

    def __init__(
        self,
        file_path: str,
        preloaded_data: Optional[np.ndarray] = None,
        acquisition_mode: str = "2d",
        dim3_interpretation: str = "coil_hw",
        dim4_interpretation: str = "coil_slice_hw",
        h5_key: Optional[str] = None,
    ):
        self.file_path = file_path
        #: Explicit HDF5 dataset name; ``None`` auto-selects the first meaningful
        #: numeric 2D/3D/4D dataset.
        self.h5_key = h5_key
        self.data_type: Optional[DataType] = None
        self.dimension: Optional[DataDimension] = None
        self.num_slices: int = 1
        self.num_channels: int = 1
        self.height: int = 0
        self.width: int = 0

        # Lazy/eager backing fields (see the raw_data / processed_data properties)
        self._raw_data: Optional[np.ndarray] = None
        self._processed_data: Optional[np.ndarray] = None
        self._lazy: Optional[_LazyH5Source] = None
        self._raw_shape: Tuple[int, ...] = ()
        self._raw_dtype = None
        self._processed_shape: Tuple[int, int, int, int] = (1, 1, 0, 0)

        # User-provided hints for data interpretation
        self.acquisition_mode = acquisition_mode  # "2d" or "3d"
        self.dim3_interpretation = dim3_interpretation  # "coil_hw" or "slice_hw"
        self.dim4_interpretation = dim4_interpretation  # "coil_slice_hw" or "slice_coil_hw"

        # Load and analyze data
        if preloaded_data is not None:
            raw = preloaded_data
            if np.iscomplexobj(raw):
                raw = raw.astype(np.complex128)
            else:
                raw = raw.astype(np.float64)
            self._raw_data = raw
            self._raw_shape = tuple(raw.shape)
            self._raw_dtype = raw.dtype
            self._analyze_data()
        else:
            self._load_data()
            self._analyze_data()
            # If analysis had to materialize (no lazy source left), release the
            # file handle; a still-lazy instance keeps it for plane reads.
            if self._raw_data is not None:
                self._release_lazy()

    # ------------------------------------------------------------------ #
    # Public array views (lazy materialization)
    # ------------------------------------------------------------------ #
    @property
    def raw_data(self) -> np.ndarray:
        """Raw volume; materializes the HDF5 dataset on first access."""
        return self._materialize_raw()

    @raw_data.setter
    def raw_data(self, value) -> None:
        self._raw_data = value
        self._processed_data = None
        self._raw_shape = tuple(value.shape) if value is not None else ()
        self._raw_dtype = value.dtype if value is not None else None
        self._release_lazy()

    @property
    def processed_data(self) -> np.ndarray:
        """
        Shape-normalized ``(C, S, H, W)`` volume.

        For an HDF5-backed instance this materializes the dataset on first
        access, exactly like the previous eager implementation.
        """
        if self._processed_data is None:
            self._raw_data = self._materialize_raw()
            self._processed_data = self._build_processed(self._raw_data)
        return self._processed_data

    @property
    def processed_shape(self) -> Tuple[int, int, int, int]:
        """``(C, S, H, W)`` shape without materializing the volume."""
        return self._processed_shape

    def close(self) -> None:
        """Release the HDF5 file handle (no-op for in-memory data)."""
        self._release_lazy()

    # ------------------------------------------------------------------ #
    # Loading
    # ------------------------------------------------------------------ #
    def _release_lazy(self) -> None:
        if self._lazy is not None:
            self._lazy.close()
            self._lazy = None

    def _materialize_raw(self) -> np.ndarray:
        if self._raw_data is None:
            if self._lazy is None:
                raise ValueError(
                    f"No data available: {self.file_path!r} was closed or never " "held a dataset"
                )
            stored = self._lazy.read(())
            if np.iscomplexobj(stored):
                self._raw_data = stored.astype(np.complex128)
            else:
                self._raw_data = stored.astype(np.float64)
        return self._raw_data

    def _load_data(self):
        """Load data from .npy or .h5/.hdf5 file"""
        if self.file_path.endswith((".h5", ".hdf5")):
            self._load_h5_data()
        else:
            self._load_npy_data()

    def _load_npy_data(self):
        """Load data from .npy file"""
        try:
            raw = np.load(self.file_path)
        except Exception as e:
            raise ValueError(f"Failed to load file {self.file_path}: {e}") from e

        if np.iscomplexobj(raw):
            raw = raw.astype(np.complex128)
        else:
            raw = raw.astype(np.float64)
        self._raw_data = raw
        self._raw_shape = tuple(raw.shape)
        self._raw_dtype = raw.dtype

    def _select_h5_dataset(self, f, keys: Sequence[str]) -> str:
        """
        Pick the dataset to load from the top-level keys.

        Only :class:`h5py.Dataset` objects are considered (top-level groups are
        skipped, matching the app layer's ``ask_h5_key``/``peek_file_ndim``).
        Preference order:

        1. the first numeric 2D/3D/4D dataset -- this skips metadata such as the
           0-D object ``ismrmrd_header`` in ISMRMRD files;
        2. otherwise the first dataset of any rank, so an unsupported 0-D/1-D
           dataset reaches :meth:`_analyze_data` and fails there with the clean
           ``Unsupported data dimension`` error.

        Raises:
            ValueError: if the file contains no dataset at all (groups only).
        """
        import h5py

        datasets = [key for key in keys if isinstance(f.get(key), h5py.Dataset)]
        if not datasets:
            raise ValueError(f"No datasets found in {self.file_path}")

        for key in datasets:
            ds = f[key]
            if ds.ndim in (2, 3, 4) and ds.dtype.kind in "fiubc":
                return key
        return datasets[0]

    def _load_h5_data(self):
        """Open the first meaningful dataset in an .h5/.hdf5 file lazily"""
        import h5py

        with h5py.File(self.file_path, "r") as f:
            keys = list(f.keys())
            if not keys:
                raise ValueError(f"No datasets found in {self.file_path}")
            if self.h5_key is not None:
                if self.h5_key not in f:
                    raise ValueError(
                        f"Key '{self.h5_key}' not found in H5 file. " f"Available keys: {keys}"
                    )
                obj = f[self.h5_key]
                if not isinstance(obj, h5py.Dataset):
                    raise ValueError(
                        f"Key '{self.h5_key}' is not a dataset in H5 file. "
                        f"Available datasets: "
                        f"{[k for k in keys if isinstance(f.get(k), h5py.Dataset)]}"
                    )
                key = self.h5_key
            else:
                key = self._select_h5_dataset(f, keys)
            ds = f[key]
            self._raw_shape = tuple(int(s) for s in ds.shape)
            stored_dtype = ds.dtype

        self._raw_dtype = (
            np.complex128 if np.iscomplexobj(np.empty(0, dtype=stored_dtype)) else np.float64
        )
        self._lazy = _LazyH5Source(self.file_path, key)

    # ------------------------------------------------------------------ #
    # Shape normalization
    # ------------------------------------------------------------------ #
    def _build_processed(self, raw: np.ndarray) -> np.ndarray:
        """Normalize ``raw`` to ``(C, S, H, W)`` exactly as the eager path did."""
        shape = raw.shape
        ndim = len(shape)
        if ndim == 2:
            return raw.reshape(1, 1, shape[0], shape[1])
        if ndim == 3:
            if self.dim3_interpretation == "slice_hw":
                return raw.reshape(1, shape[0], shape[1], shape[2])
            return raw.reshape(shape[0], 1, shape[1], shape[2])
        if ndim == 4:
            if self.dim4_interpretation == "slice_coil_hw":
                return np.transpose(raw, (1, 0, 2, 3))
            return raw
        raise ValueError(f"Unsupported data dimension: {ndim}D, expected 2D, 3D, or 4D")

    def _analyze_data(self):
        """Analyze data shape and determine type and dimensionality"""
        shape = self._raw_shape
        ndim = len(shape)

        # Validate dimensionality *before* any type detection: 0-D/1-D data must
        # fail with the same clean ValueError for real and complex input, not
        # with an IndexError from the magnitude heuristic.
        if ndim not in (2, 3, 4):
            raise ValueError(f"Unsupported data dimension: {ndim}D, expected 2D, 3D, or 4D")

        # Heuristic to determine if data is k-space or image
        self.data_type = self._detect_data_type()

        # Normalize shape to 4D: (channels, slices, height, width)
        if ndim == 2:
            # (height, width) - single channel, single slice
            self.dimension = DataDimension.DIM_2D
            self.num_channels = 1
            self.num_slices = 1
            self.height = shape[0]
            self.width = shape[1]
        elif ndim == 3:
            # Could be (slices, height, width) or (channels, height, width)
            # Use user-provided dim3_interpretation instead of heuristics
            if self.dim3_interpretation == "slice_hw":
                # User says: (slices, height, width)
                self.dimension = DataDimension.DIM_3D
                self.num_channels = 1
                self.num_slices = shape[0]
                self.height = shape[1]
                self.width = shape[2]
            else:
                # Default: (channels, height, width)
                self.dimension = DataDimension.DIM_2D
                self.num_channels = shape[0]
                self.num_slices = 1
                self.height = shape[1]
                self.width = shape[2]
        else:  # ndim == 4
            self.dimension = DataDimension.DIM_3D

            if self.dim4_interpretation == "slice_coil_hw":
                self.num_channels = shape[1]
                self.num_slices = shape[0]
                self.height = shape[2]
                self.width = shape[3]
            else:
                self.num_channels = shape[0]
                self.num_slices = shape[1]
                self.height = shape[2]
                self.width = shape[3]

        self._processed_shape = (
            int(self.num_channels),
            int(self.num_slices),
            int(self.height),
            int(self.width),
        )

        # Eager backing only when the data is already in memory; otherwise the
        # processed volume is materialized on demand from the lazy source.
        if self._raw_data is not None:
            self._processed_data = self._build_processed(self._raw_data)

    def _detect_data_type(self) -> DataType:
        """
        Detect if data is k-space or image
        Heuristic: complex data or data with specific characteristics

        Never materializes a lazily opened dataset: complex data is recognized
        from the stored dtype, and real data is summarized with bounded-memory
        chunked reads (see :meth:`_stream_real_stats`).
        """
        # If data is complex, likely k-space (no read needed for lazy data)
        if np.issubdtype(np.dtype(self._raw_dtype), np.complexfloating):
            return DataType.KSPACE

        if self._lazy is not None:
            max_abs, mean_abs, center_peak, edge_mean = self._stream_real_stats()
        else:
            data_abs = np.abs(self.raw_data)
            max_abs = float(data_abs.max())
            mean_abs = float(data_abs.mean())
            center_peak, edge_mean = self._center_edge_stats(data_abs)

        # High dynamic range suggests k-space
        if mean_abs > 0 and max_abs > 100 * mean_abs:
            return DataType.KSPACE

        # A dominant central DC spike suggests k-space
        if edge_mean > 0 and center_peak > 100 * edge_mean:
            return DataType.KSPACE

        # Default to image
        return DataType.IMAGE

    @staticmethod
    def _center_edge_stats(abs_data: np.ndarray) -> Tuple[float, float]:
        """
        Return ``(center_peak, edge_mean)`` for an absolute-valued array.

        The edge region is everything outside the central block (10% margin per
        side along the last two axes); its mean is derived from sums so the edge
        is never materialized.
        """
        if abs_data.ndim < 2:
            return 0.0, 0.0
        h, w = abs_data.shape[-2:]
        if h <= 10 or w <= 10:
            return 0.0, 0.0
        mh, mw = h // 10, w // 10
        if mh == 0 or mw == 0:
            return 0.0, 0.0
        center = abs_data[..., mh:-mh, mw:-mw]
        edge_count = abs_data.size - center.size
        if edge_count <= 0:
            return float(center.max()), 0.0
        edge_mean = (float(abs_data.sum()) - float(center.sum())) / edge_count
        return float(center.max()), float(edge_mean)

    def _stream_real_stats(self) -> Tuple[float, float, float, float]:
        """
        Stream a real lazily-opened dataset and return
        ``(max_abs, mean_abs, center_peak, edge_mean)``.

        The dataset is read in bounded chunks along the first axis, so peak
        memory stays at roughly one chunk (a few tens of MB) regardless of the
        volume size.  The quantities match the eager heuristic exactly up to
        floating-point summation order.
        """
        shape = self._raw_shape
        h, w = shape[-2], shape[-1]
        mh, mw = h // 10, w // 10
        has_center = h > 10 and w > 10 and mh > 0 and mw > 0

        itemsize = max(1, int(np.dtype(self._lazy.stored_dtype).itemsize))
        trailing = int(np.prod(shape[1:])) if len(shape) > 1 else 1
        rows = max(1, (32 * 1024 * 1024) // max(1, itemsize * trailing))

        total_sum = 0.0
        total_count = 0
        global_max = 0.0
        center_sum = 0.0
        center_count = 0
        center_peak = 0.0

        n0 = shape[0] if shape else 0
        for start in range(0, n0, rows):
            chunk = np.abs(self._read_raw_subset((slice(start, min(start + rows, n0)),)))
            total_sum += float(chunk.sum())
            total_count += int(chunk.size)
            chunk_max = float(chunk.max())
            if chunk_max > global_max:
                global_max = chunk_max
            if has_center and chunk.ndim >= 2:
                center = chunk[..., mh:-mh, mw:-mw]
                center_sum += float(center.sum())
                center_count += int(center.size)
                center_max = float(center.max())
                if center_max > center_peak:
                    center_peak = center_max

        mean_abs = total_sum / total_count if total_count else 0.0
        edge_count = total_count - center_count
        if has_center and edge_count > 0:
            edge_mean = (total_sum - center_sum) / edge_count
        else:
            edge_mean = 0.0
        return global_max, mean_abs, center_peak, float(edge_mean)

    def _looks_like_kspace(self, data: np.ndarray) -> bool:
        """
        Check whether real-valued in-memory data has k-space characteristics.

        k-space is dominated by a single DC spike in the centre; the rest of the
        plane is small compared with that spike.  The comparison therefore uses
        the *true* edge region (everything outside the central block) against the
        central peak -- a smooth image, whose energy is broadly distributed, does
        not produce such a peak.
        """
        if data.ndim < 2:
            return False
        center_peak, edge_mean = self._center_edge_stats(np.abs(data))
        if edge_mean <= 0:
            return False
        return bool(center_peak > 100 * edge_mean)

    # ------------------------------------------------------------------ #
    # Lazy plane access
    # ------------------------------------------------------------------ #
    def _read_raw_subset(self, indexer) -> np.ndarray:
        """Read a raw subset from the lazy source, applying the eager dtype."""
        stored = self._lazy.read(indexer)
        if np.iscomplexobj(stored):
            return stored.astype(np.complex128)
        return stored.astype(np.float64)

    def _read_lazy_plane(self, channel: int, view: str, index: int) -> np.ndarray:
        """
        Return ``processed_data[channel]`` sliced by ``view``/``index``, reading
        only the requested plane from the HDF5 dataset (never the whole volume).

        ``view`` must already be normalized; the returned shape follows the
        canonical convention in :mod:`src.core.views` and matches
        ``views.extract_view(processed_data[channel], view, index)``.
        """
        shape = self._raw_shape
        ndim = len(shape)
        ch = int(channel)
        idx = int(index)

        if ndim == 4:
            if self.dim4_interpretation == "slice_coil_hw":
                if view == "axial":
                    return self._read_raw_subset((idx, ch))
                if view == "sagittal":
                    return self._read_raw_subset((slice(None), ch, slice(None), idx))
                return self._read_raw_subset((slice(None), ch, idx, slice(None)))
            if view == "axial":
                return self._read_raw_subset((ch, idx))
            if view == "sagittal":
                return self._read_raw_subset((ch, slice(None), slice(None), idx))
            return self._read_raw_subset((ch, slice(None), idx, slice(None)))

        if ndim == 3:
            if self.dim3_interpretation == "slice_hw":
                if view == "axial":
                    return self._read_raw_subset((idx,))
                if view == "sagittal":
                    return self._read_raw_subset((slice(None), slice(None), idx))
                return self._read_raw_subset((slice(None), idx, slice(None)))
            # (C, H, W): a single slice along S, so S has extent 1.
            if view == "axial":
                return self._read_raw_subset((ch,))
            if view == "sagittal":
                return self._read_raw_subset((ch, slice(None), idx)).reshape(1, shape[1])
            return self._read_raw_subset((ch, idx, slice(None))).reshape(1, shape[2])

        # ndim == 2: (H, W) with C = S = 1.
        if view == "axial":
            return self._read_raw_subset(())
        if view == "sagittal":
            return self._read_raw_subset((slice(None), idx)).reshape(1, shape[0])
        return self._read_raw_subset((idx, slice(None))).reshape(1, shape[1])

    def _read_lazy_slice(self, channel: int, slice_idx: int) -> np.ndarray:
        """Return ``processed_data[channel, slice_idx]`` from the lazy source."""
        shape = self._raw_shape
        ndim = len(shape)
        if ndim == 4:
            if self.dim4_interpretation == "slice_coil_hw":
                return self._read_raw_subset((int(slice_idx), int(channel)))
            return self._read_raw_subset((int(channel), int(slice_idx)))
        if ndim == 3:
            if self.dim3_interpretation == "slice_hw":
                return self._read_raw_subset(int(slice_idx))
            return self._read_raw_subset(int(channel))
        # ndim == 2
        return self._read_raw_subset(())

    def _check_view_index(self, view_type: str, index: int) -> int:
        view = views.normalize_view_type(view_type)
        axis = views.view_axis(view)
        size = self._processed_shape[axis + 1]
        idx = int(index)
        if not 0 <= idx < size:
            raise IndexError(f"{view} index {idx} out of range [0, {size})")
        return idx

    # ------------------------------------------------------------------ #
    # Public slice/view API
    # ------------------------------------------------------------------ #
    def get_slice(self, slice_idx: int, channel: int = 0) -> np.ndarray:
        """Get a specific slice from the data"""
        if slice_idx < 0 or slice_idx >= self.num_slices:
            raise ValueError(f"Slice index {slice_idx} out of range [0, {self.num_slices})")

        if channel < 0 or channel >= self.num_channels:
            raise ValueError(f"Channel index {channel} out of range [0, {self.num_channels})")

        if self._lazy is not None:
            return self._read_lazy_slice(int(channel), int(slice_idx))
        return self.processed_data[channel, slice_idx]

    def get_view(self, view_type: str, index: int, channel: int = 0) -> np.ndarray:
        """
        Get different view orientations for 3D data

        view_type: 'axial', 'sagittal', or 'coronal'
        index: slice index for the requested view
        """
        if self.dimension == DataDimension.DIM_2D:
            return self.get_slice(0, channel)

        if self._lazy is not None:
            view = views.normalize_view_type(view_type)
            idx = self._check_view_index(view, index)
            return self._read_lazy_plane(int(channel), view, idx)

        return views.extract_view(self.processed_data[channel], view_type, index)

    def get_view_max_index(self, view_type: str) -> int:
        """Largest valid index for ``view_type`` (delegates to views.max_index)."""
        return views.max_index(self._processed_shape, view_type)

    def get_view_channels(self, view_type: str, index: int) -> np.ndarray:
        """
        Extract a view plane for every coil without combining them.

        Returns ``(C, H, W)`` for axial, ``(C, S, H)`` for sagittal and
        ``(C, S, W)`` for coronal -- identical to
        ``views.extract_view_channels(processed_data, view_type, index)`` but
        without materializing the full volume for HDF5-backed data.
        """
        if self._lazy is None:
            return views.extract_view_channels(self.processed_data, view_type, index)

        view = views.normalize_view_type(view_type)
        idx = self._check_view_index(view, index)

        # Axial reads one raw plane that already holds all coils -- the
        # lowest-footprint path for the common (2D acquisition) display case.
        if views.view_axis(view) == 0 and len(self._raw_shape) == 4:
            if self.dim4_interpretation == "slice_coil_hw":
                return self._read_raw_subset((idx, slice(None)))
            return self._read_raw_subset((slice(None), idx))

        planes = [self._read_lazy_plane(ch, view, idx) for ch in range(self.num_channels)]
        return np.stack(planes, axis=0)

    def get_info(self) -> str:
        """Get human-readable data information"""
        info = []
        info.append(f"File: {self.file_path}")
        info.append(f"Type: {self.data_type.value}")
        info.append(f"Dimension: {self.dimension.value}")
        info.append(f"Shape: {tuple(self._raw_shape)}")
        info.append(f"Channels: {self.num_channels}")
        info.append(f"Slices: {self.num_slices}")
        info.append(f"Height: {self.height}")
        info.append(f"Width: {self.width}")
        info.append(f"Dtype: {np.dtype(self._raw_dtype)}")

        if np.issubdtype(np.dtype(self._raw_dtype), np.complexfloating):
            info.append("Is Complex: Yes")

        return "\n".join(info)
