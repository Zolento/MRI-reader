"""
MRI Data Model - Handles loading and interpreting MRI data
Detects data type (image/k-space) and dimensionality (2D/3D) with user guidance
"""

import numpy as np
from enum import Enum
from typing import Tuple, Optional


class DataType(Enum):
    """Type of MRI data"""
    IMAGE = "image"
    KSPACE = "k-space"


class DataDimension(Enum):
    """Dimensionality of MRI data"""
    DIM_2D = "2D"
    DIM_3D = "3D"


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

    def __init__(self, file_path: str, preloaded_data: Optional[np.ndarray] = None,
                 acquisition_mode: str = "2d", dim3_interpretation: str = "coil_hw"):
        self.file_path = file_path
        self.raw_data: Optional[np.ndarray] = None
        self.data_type: Optional[DataType] = None
        self.dimension: Optional[DataDimension] = None
        self.processed_data: Optional[np.ndarray] = None
        self.num_slices: int = 1
        self.num_channels: int = 1
        self.height: int = 0
        self.width: int = 0

        # User-provided hints for data interpretation
        self.acquisition_mode = acquisition_mode  # "2d" or "3d"
        self.dim3_interpretation = dim3_interpretation  # "coil_hw" or "slice_hw"

        # Load and analyze data
        if preloaded_data is not None:
            self.raw_data = preloaded_data
            # Convert type if needed
            if np.iscomplexobj(self.raw_data):
                self.raw_data = self.raw_data.astype(np.complex128)
            else:
                self.raw_data = self.raw_data.astype(np.float64)
            self._analyze_data()
        else:
            self._load_data()
            self._analyze_data()
    
    def _load_data(self):
        """Load data from .npy file"""
        try:
            self.raw_data = np.load(self.file_path)
        except Exception as e:
            raise ValueError(f"Failed to load file {self.file_path}: {e}")
        
        # Convert to float64 for processing
        if np.iscomplexobj(self.raw_data):
            self.raw_data = self.raw_data.astype(np.complex128)
        else:
            self.raw_data = self.raw_data.astype(np.float64)
    
    def _analyze_data(self):
        """Analyze data shape and determine type and dimensionality"""
        shape = self.raw_data.shape
        ndim = len(shape)

        # Heuristic to determine if data is k-space or image
        # k-space typically has complex values or specific magnitude characteristics
        self.data_type = self._detect_data_type()

        # Normalize shape to 4D: (channels, slices, height, width)
        if ndim == 2:
            # (height, width) - single channel, single slice
            self.dimension = DataDimension.DIM_2D
            self.num_channels = 1
            self.num_slices = 1
            self.height = shape[0]
            self.width = shape[1]
            self.processed_data = self.raw_data.reshape(1, 1, shape[0], shape[1])

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
                self.processed_data = self.raw_data.reshape(1, shape[0], shape[1], shape[2])
            else:
                # Default: (channels, height, width)
                self.dimension = DataDimension.DIM_2D
                self.num_channels = shape[0]
                self.num_slices = 1
                self.height = shape[1]
                self.width = shape[2]
                self.processed_data = self.raw_data.reshape(shape[0], 1, shape[1], shape[2])

        elif ndim == 4:
            # (channels, slices, height, width)
            # Use heuristics to identify dimension roles
            self.dimension = DataDimension.DIM_3D

            # Try to identify which dimension is channels
            # Channels are typically small (<16)
            if shape[0] <= 16:
                self.num_channels = shape[0]
                self.num_slices = shape[1]
                self.height = shape[2]
                self.width = shape[3]
                self.processed_data = self.raw_data
            elif shape[1] <= 16:
                # (slices, channels, height, width) - need to transpose
                self.num_channels = shape[1]
                self.num_slices = shape[0]
                self.height = shape[2]
                self.width = shape[3]
                self.processed_data = np.transpose(self.raw_data, (1, 0, 2, 3))
            else:
                # Assume standard (channels, slices, height, width) with single channel
                self.num_channels = 1
                self.num_slices = shape[0]
                self.height = shape[1]
                self.width = shape[2]
                self.processed_data = self.raw_data.reshape(1, shape[0], shape[1], shape[2])
        else:
            raise ValueError(f"Unsupported data dimension: {ndim}D, expected 2D, 3D, or 4D")
    
    def _detect_data_type(self) -> DataType:
        """
        Detect if data is k-space or image
        Heuristic: complex data or data with specific characteristics
        """
        # If data is complex, likely k-space
        if np.iscomplexobj(self.raw_data):
            # Complex data is very likely to be k-space
            return DataType.KSPACE
        
        # For real data, check magnitude distribution
        # k-space often has very large dynamic range
        data_max = np.abs(self.raw_data).max()
        data_mean = np.abs(self.raw_data).mean()
        
        # High dynamic range suggests k-space
        if data_mean > 0 and data_max > 100 * data_mean:
            return DataType.KSPACE
        
        # Check if data has k-space characteristics
        if self._looks_like_kspace(self.raw_data):
            return DataType.KSPACE
        
        # Default to image
        return DataType.IMAGE
    
    def _looks_like_kspace(self, data: np.ndarray) -> bool:
        """
        Check if data has k-space characteristics
        k-space typically has:
        - High energy in center (DC component)
        - Symmetric pattern
        """
        # Get center region (10% of size)
        if len(data.shape) >= 2:
            if data.shape[-2] > 10 and data.shape[-1] > 10:
                h, w = data.shape[-2:]
                ch, cw = h // 10, w // 10
                
                # Center region energy
                center_region = np.abs(data[..., ch:-ch, cw:-cw])
                edge_region = np.abs(data)
                
                center_energy = center_region.mean()
                edge_energy = edge_region.mean()
                
                # k-space has much higher energy in center
                if center_energy > 5 * edge_energy:
                    return True
        
        return False
    
    def get_slice(self, slice_idx: int, channel: int = 0) -> np.ndarray:
        """Get a specific slice from the data"""
        if slice_idx < 0 or slice_idx >= self.num_slices:
            raise ValueError(f"Slice index {slice_idx} out of range [0, {self.num_slices})")
        
        if channel < 0 or channel >= self.num_channels:
            raise ValueError(f"Channel index {channel} out of range [0, {self.num_channels})")
        
        return self.processed_data[channel, slice_idx]
    
    def get_view(self, view_type: str, index: int, channel: int = 0) -> np.ndarray:
        """
        Get different view orientations for 3D data
        
        view_type: 'axial', 'sagittal', or 'coronal'
        index: slice index for the requested view
        """
        if self.dimension == DataDimension.DIM_2D:
            return self.get_slice(0, channel)
        
        data = self.processed_data[channel]  # (slices, height, width)
        
        if view_type == 'axial':
            # Transverse plane (default view) - horizontal slice
            return data[index]
            
        elif view_type == 'sagittal':
            # Side view - slice through width dimension (left-right)
            # data shape: (slices, height, width)
            # Take index along width dimension -> (slices, height)
            return data[:, :, index]
            
        elif view_type == 'coronal':
            # Front view - slice through height dimension (anterior-posterior)
            # data shape: (slices, height, width)
            # Take index along height dimension -> (slices, width)
            return data[:, index, :]
        
        else:
            raise ValueError(f"Unknown view type: {view_type}")
    
    def get_info(self) -> str:
        """Get human-readable data information"""
        info = []
        info.append(f"File: {self.file_path}")
        info.append(f"Type: {self.data_type.value}")
        info.append(f"Dimension: {self.dimension.value}")
        info.append(f"Shape: {self.raw_data.shape}")
        info.append(f"Channels: {self.num_channels}")
        info.append(f"Slices: {self.num_slices}")
        info.append(f"Height: {self.height}")
        info.append(f"Width: {self.width}")
        info.append(f"Dtype: {self.raw_data.dtype}")
        
        if np.iscomplexobj(self.raw_data):
            info.append(f"Is Complex: Yes")
        
        return "\n".join(info)
