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
    """Test 2D image loading"""
    print("Testing 2D image loading...")
    mri = MRIData('test_data/test_2d_image.npy')
    
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
    assert image_data.max() <= 1.0
    
    print("  ✅ 2D k-space test passed")
    return True


def test_3d_kspace():
    """Test 3D k-space conversion"""
    print("Testing 3D k-space conversion...")
    mri = MRIData('test_data/test_3d_kspace.npy')
    
    assert mri.data_type == DataType.KSPACE
    assert mri.dimension == DataDimension.DIM_3D
    
    # Convert k-space to image (both 2D and 3D modes)
    image_2d = KSpaceConverter.convert(mri, mode_3d=False)
    image_3d = KSpaceConverter.convert(mri, mode_3d=True)
    
    assert image_2d.shape == mri.processed_data.shape
    assert image_3d.shape == mri.processed_data.shape
    
    # Both should be normalized
    assert image_2d.max() <= 1.0
    assert image_3d.max() <= 1.0
    
    print("  ✅ 3D k-space test passed")
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
