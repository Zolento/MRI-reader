"""
K-space Converter - Converts k-space data to MRI images
Supports both 2D and 3D acquisition modes

2D acquisition: each slice is acquired independently
  - Shape: (channels, slices, phase, freq) or (channels/slices, phase, freq)
  - IFFT: 2D IFFT on (phase, freq) for each slice

3D acquisition: volume acquisition with phase encoding in all 3 dimensions
  - Shape: (channels, slices, phase, freq)
  - IFFT: 3D IFFT on (slices, phase, freq) for each channel
"""

import numpy as np
from typing import Optional
from .mri_data import MRIData, DataType


class KSpaceConverter:
    """
    Converts k-space data to MRI images using Inverse FFT

    For 2D acquisition: performs 2D IFFT on (phase, freq) slice by slice
    For 3D acquisition: performs 3D IFFT on (slices, phase, freq) for each channel
    """

    @staticmethod
    def ifft_2d(data: np.ndarray) -> np.ndarray:
        """
        2D IFFT for complex k-space data (phase, freq dimensions)

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
    def ifft_3d(data: np.ndarray) -> np.ndarray:
        """
        3D IFFT for complex k-space data (slices, phase, freq dimensions)

        Assumes DC component is already centered in the input data.
        Steps:
        1. ifftshift to move DC to corner
        2. ifftn with ortho normalization on all 3 dimensions
        3. fftshift to move image center to center
        """
        data = np.fft.ifftshift(data, axes=[-3, -2, -1])
        data = np.fft.ifftn(data, axes=[-3, -2, -1], norm='ortho')
        data = np.fft.fftshift(data, axes=[-3, -2, -1])
        return data

    @staticmethod
    def convert(mri_data: MRIData, mode_3d: bool = None) -> np.ndarray:
        """
        Convert k-space data to image data

        Args:
            mri_data: MRIData object containing k-space data
            mode_3d: Force 3D or 2D acquisition mode.
                     If None, auto-detect from mri_data.acquisition_mode.

        Returns:
            Converted image data as numpy array
        """
        if mri_data.data_type != DataType.KSPACE:
            raise ValueError("Data is not k-space type")

        # Auto-detect mode if not specified
        if mode_3d is None:
            mode_3d = (mri_data.acquisition_mode == "3d")

        if mode_3d:
            return KSpaceConverter._convert_3d_acquired(mri_data)
        else:
            return KSpaceConverter._convert_2d_acquired(mri_data)

    @staticmethod
    def _convert_2d_acquired(mri_data: MRIData) -> np.ndarray:
        """
        Convert 2D-acquired k-space data to image
        Each slice was acquired independently, so we do 2D IFFT per slice

        Shape: (channels, slices, phase, freq) or collapsed variants
        """
        converted = np.zeros_like(mri_data.processed_data, dtype=np.float64)

        for ch in range(mri_data.num_channels):
            for sl in range(mri_data.num_slices):
                kspace_slice = mri_data.processed_data[ch, sl]

                # Apply 2D IFFT (phase, freq)
                image_slice = KSpaceConverter.ifft_2d(kspace_slice)

                # Take magnitude
                converted[ch, sl] = np.abs(image_slice)

        return converted

    @staticmethod
    def _convert_3d_acquired(mri_data: MRIData) -> np.ndarray:
        """
        Convert 3D-acquired k-space data to image
        Volume acquisition with phase encoding in all 3 spatial dimensions

        Shape: (channels, slices, phase, freq)
        For each channel: 3D IFFT on (slices, phase, freq)
        """
        converted = np.zeros_like(mri_data.processed_data, dtype=np.float64)

        for ch in range(mri_data.num_channels):
            # Get 3D k-space data for this channel: (slices, phase, freq)
            kspace_3d = mri_data.processed_data[ch]

            # Apply 3D IFFT on all spatial dimensions
            image_3d = KSpaceConverter.ifft_3d(kspace_3d)

            # Take magnitude
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

                # Apply 2D IFFT
                image_slice = KSpaceConverter.ifft_2d(kspace_slice)
                converted[ch, sl] = np.abs(image_slice)

        return converted
