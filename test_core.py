"""
Test Script - Verify core functionality without GUI
"""

import numpy as np
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from core.mri_data import MRIData, DataType, DataDimension
from core.kspace_converter import KSpaceConverter
from core.image_processor import ImageProcessor


def test_2d_image():
    """Test 2D image loading (multi-slice, stored as 3D array)"""
    print("Testing 2D image loading...")
    # Shape: (10, 128, 128) — interpret as (slices, H, W)
    mri = MRIData('test_data/test_2d_image.npy', dim3_interpretation='slice_hw')

    assert mri.data_type == DataType.IMAGE
    assert mri.dimension == DataDimension.DIM_3D  # 10 slices is 3D
    assert mri.num_slices == 10
    assert mri.num_channels == 1
    assert mri.height == 128
    assert mri.width == 128

    # Test slice extraction
    slice_0 = mri.get_slice(0)
    assert slice_0.shape == (128, 128)

    print("  ✅ 2D image test passed")
    return True


def test_3d_image():
    """Test 3D image loading"""
    print("Testing 3D image loading...")
    mri = MRIData('test_data/test_3d_image.npy')
    
    assert mri.data_type == DataType.IMAGE
    assert mri.dimension == DataDimension.DIM_3D
    assert mri.num_slices == 16
    assert mri.num_channels == 2
    
    # Test different views
    axial = mri.get_view('axial', 0)
    sagittal = mri.get_view('sagittal', 32)  # index=32 along width
    coronal = mri.get_view('coronal', 8)  # index=8 along height
    
    assert axial.shape == (64, 64)
    # Sagittal shows all slices at a specific width position: (slices, height)
    assert sagittal.shape == (16, 64)
    # Coronal shows all slices at a specific height position: (slices, width)
    assert coronal.shape == (16, 64)
    
    print("  ✅ 3D image test passed")
    return True


def test_2d_kspace():
    """Test 2D k-space conversion"""
    print("Testing 2D k-space conversion...")
    mri = MRIData('test_data/test_2d_kspace.npy')

    assert mri.data_type == DataType.KSPACE

    # Convert k-space to image
    image_data = KSpaceConverter.convert(mri, mode_3d=False)

    assert image_data.shape == mri.processed_data.shape
    assert image_data.dtype == np.float64
    assert image_data.min() >= 0
    # Note: max value depends on IFFT normalization, just check it's finite
    assert np.isfinite(image_data.max())

    print("  ✅ 2D k-space test passed")
    return True


def test_3d_kspace():
    """Test 3D k-space conversion (2D acquisition, 4D data)"""
    print("Testing 3D k-space conversion (2D acquisition)...")
    mri = MRIData('test_data/test_3d_kspace.npy')

    assert mri.data_type == DataType.KSPACE
    assert mri.dimension == DataDimension.DIM_3D  # 4D data -> 3D

    # Convert with 2D acquisition mode (default): 2D IFFT per slice
    image_2d = KSpaceConverter.convert(mri, mode_3d=False)

    assert image_2d.shape == mri.processed_data.shape
    assert image_2d.dtype == np.float64
    assert np.isfinite(image_2d.max())

    print("  ✅ 3D k-space (2D acquisition) test passed")
    return True


def test_3d_kspace_3d_acquisition():
    """Test 3D k-space conversion with 3D acquisition mode"""
    print("Testing 3D k-space conversion (3D acquisition)...")
    mri = MRIData('test_data/test_3d_kspace.npy', acquisition_mode='3d')

    assert mri.data_type == DataType.KSPACE
    assert mri.dimension == DataDimension.DIM_3D

    # Convert with 3D acquisition mode: 3D IFFT
    image_3d = KSpaceConverter.convert(mri, mode_3d=True)

    assert image_3d.shape == mri.processed_data.shape
    assert image_3d.dtype == np.float64

    print("  ✅ 3D k-space (3D acquisition) test passed")
    return True


def test_3d_coil_hw_interpretation():
    """Test 3D data interpreted as (Coil, H, W)"""
    print("Testing 3D data as (Coil, H, W)...")
    # Create test data: (3 coils, 64H, 64W)
    test_data = np.random.random((3, 64, 64))
    mri = MRIData('test', preloaded_data=test_data, dim3_interpretation='coil_hw')

    assert mri.dimension == DataDimension.DIM_2D
    assert mri.num_channels == 3
    assert mri.num_slices == 1
    assert mri.height == 64
    assert mri.width == 64

    print("  ✅ 3D (Coil, H, W) interpretation test passed")
    return True


def test_3d_slice_hw_interpretation():
    """Test 3D data interpreted as (Slice, H, W)"""
    print("Testing 3D data as (Slice, H, W)...")
    # Create test data: (10 slices, 64H, 64W)
    test_data = np.random.random((10, 64, 64))
    mri = MRIData('test', preloaded_data=test_data, dim3_interpretation='slice_hw')

    assert mri.dimension == DataDimension.DIM_3D
    assert mri.num_channels == 1
    assert mri.num_slices == 10
    assert mri.height == 64
    assert mri.width == 64

    print("  ✅ 3D (Slice, H, W) interpretation test passed")
    return True


def test_4d_coil_slice_hw_interpretation():
    """Test 4D data interpreted as (Coil, Slice, H, W)"""
    print("Testing 4D data as (Coil, Slice, H, W)...")
    test_data = np.random.random((3, 5, 64, 64))
    mri = MRIData('test', preloaded_data=test_data, dim4_interpretation='coil_slice_hw')

    assert mri.dimension == DataDimension.DIM_3D
    assert mri.num_channels == 3
    assert mri.num_slices == 5
    assert mri.height == 64
    assert mri.width == 64

    print("  ✅ 4D (Coil, Slice, H, W) interpretation test passed")
    return True


def test_4d_slice_coil_hw_interpretation():
    """Test 4D data interpreted as (Slice, Coil, H, W)"""
    print("Testing 4D data as (Slice, Coil, H, W)...")
    test_data = np.random.random((5, 3, 64, 64))
    mri = MRIData('test', preloaded_data=test_data, dim4_interpretation='slice_coil_hw')

    assert mri.dimension == DataDimension.DIM_3D
    assert mri.num_channels == 3
    assert mri.num_slices == 5
    assert mri.height == 64
    assert mri.width == 64

    print("  ✅ 4D (Slice, Coil, H, W) interpretation test passed")
    return True


def test_image_processor():
    """Test image processing functions"""
    print("Testing image processor...")
    processor = ImageProcessor()
    
    # Create test image
    test_image = np.random.random((64, 64))
    
    # Test contrast
    processor.contrast = 2.0
    result = processor.process(test_image)
    assert result.shape == test_image.shape
    
    # Test brightness
    processor.brightness = 0.1
    result = processor.process(test_image)
    assert result.shape == test_image.shape
    
    # Test log transform
    processor.use_log = True
    result = processor.process(test_image)
    assert result.shape == test_image.shape
    
    # Test rotation
    processor.reset()
    processor.rotation_angle = 45
    result = processor.process(test_image)
    assert result.shape == test_image.shape
    
    # Test zoom
    processor.reset()
    processor.zoom_factor = 1.5
    result = processor.process(test_image)
    assert result.shape == test_image.shape
    
    # Test normalize and convert to 8-bit
    normalized = ImageProcessor.normalize_image(test_image)
    assert normalized.min() >= 0
    assert normalized.max() <= 1
    
    image_8bit = ImageProcessor.convert_to_8bit(normalized)
    assert image_8bit.dtype == np.uint8
    assert image_8bit.min() >= 0
    assert image_8bit.max() <= 255
    
    print("  ✅ Image processor test passed")
    return True


def main():
    """Run all tests"""
    print("=" * 50)
    print("MRI Reader - Core Functionality Tests")
    print("=" * 50)
    print()
    
    tests = [
        test_2d_image,
        test_3d_image,
        test_2d_kspace,
        test_3d_kspace,
        test_3d_kspace_3d_acquisition,
        test_3d_coil_hw_interpretation,
        test_3d_slice_hw_interpretation,
        test_4d_coil_slice_hw_interpretation,
        test_4d_slice_coil_hw_interpretation,
        test_image_processor,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"  ❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print()
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)
    
    return failed == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
