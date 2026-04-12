"""
K-space Converter - Converts k-space data to MRI images
Supports both 2D and 3D k-space data
"""

import numpy as np
from typing import Optional
from .mri_data import MRIData, DataType


class KSpaceConverter:
    """
    Converts k-space data to MRI images using Inverse FFT

    For 2D data: performs 2D IFFT slice by slice
    For 3D data: performs 3D IFFT across slice, phase, and frequency dimensions
    """

    @staticmethod
    def ifft_np(data: np.ndarray) -> np.ndarray:
        """
        IFFT for complex k-space data
        
        Assumes DC component is already centered in the input data.
        Steps:
        1. ifftshift to move DC to corner
        2. ifftn with ortho normalization
        3. fftshift to move image center to center
        
        Only operates on the last two dimensions (phase, frequency).
        """
        data = np.fft.ifftshift(data, axes=[-2, -1])
        data = np.fft.ifftn(data, axes=[-2, -1], norm='ortho')
        data = np.fft.fftshift(data, axes=[-2, -1])
        return data

    @staticmethod
    def convert(mri_data: MRIData, mode_3d: bool = None) -> np.ndarray:
        """
        Convert k-space data to image data
        
        Args:
            mri_data: MRIData object containing k-space data
            mode_3d: Force 3D or 2D mode. If None, auto-detect from data.
            
        Returns:
            Converted image data as numpy array
        """
        if mri_data.data_type != DataType.KSPACE:
            raise ValueError("Data is not k-space type")
        
        # Auto-detect mode if not specified
        if mode_3d is None:
            mode_3d = (mri_data.num_slices > 1)
        
        if mode_3d:
            return KSpaceConverter._convert_3d(mri_data)
        else:
            return KSpaceConverter._convert_2d(mri_data)
    
    @staticmethod
    def _convert_2d(mri_data: MRIData) -> np.ndarray:
        """
        Convert 2D k-space data to image
        Process each slice independently with 2D IFFT
        """
        converted = np.zeros_like(mri_data.processed_data, dtype=np.float64)

        for ch in range(mri_data.num_channels):
            for sl in range(mri_data.num_slices):
                kspace_slice = mri_data.processed_data[ch, sl]

                # Apply IFFT (assumes DC already centered)
                image_slice = KSpaceConverter.ifft_np(kspace_slice)

                # Take magnitude (no normalization - let display handle it)
                converted[ch, sl] = np.abs(image_slice)

        return converted

    @staticmethod
    def _convert_3d(mri_data: MRIData) -> np.ndarray:
        """
        Convert 3D k-space data to image
        Perform IFFT on each slice (last two dimensions only)
        """
        converted = np.zeros_like(mri_data.processed_data, dtype=np.float64)

        for ch in range(mri_data.num_channels):
            # Get 3D k-space data for this channel: (slices, phase, freq)
            kspace_3d = mri_data.processed_data[ch]

            # Apply IFFT on last two dimensions (phase, freq)
            image_3d = KSpaceConverter.ifft_np(kspace_3d)

            # Take magnitude (no normalization - let display handle it)
            converted[ch] = np.abs(image_3d)

        return converted

    @staticmethod
    def convert_slice_by_slice(mri_data: MRIData) -> np.ndarray:
        """
        Alternative conversion method: always process slice by slice
        Useful for debugging or when 3D IFFT produces artifacts
        """
        converted = np.zeros_like(mri_data.processed_data, dtype=np.float64)

        for ch in range(mri_data.num_channels):
            for sl in range(mri_data.num_slices):
                kspace_slice = mri_data.processed_data[ch, sl]

                # Apply IFFT
                image_slice = KSpaceConverter.ifft_np(kspace_slice)
                converted[ch, sl] = np.abs(image_slice)

        return converted
