"""
Final Verification - Test all components without GUI
"""

import sys
import os

print("=" * 60)
print("MRI Reader - Final Verification")
print("=" * 60)
print()

# Test 1: Import all modules
print("1. Testing module imports...")
try:
    from src.core.mri_data import MRIData, DataType, DataDimension
    from src.core.kspace_converter import KSpaceConverter
    from src.core.image_processor import ImageProcessor
    from src.ui.image_canvas import ImageCanvas
    from src.ui.enhancement_panel import EnhancementPanel
    from src.ui.slice_navigator import SliceNavigator
    from src.main_window import MainWindow
    print("   ✅ All modules imported successfully")
except Exception as e:
    print(f"   ❌ Import failed: {e}")
    sys.exit(1)

# Test 2: Load test data
print("\n2. Testing data loading...")
try:
    test_files = [
        ('test_data/test_2d_image.npy', {'dim3_interpretation': 'slice_hw'}),
        ('test_data/test_3d_image.npy', {}),
        ('test_data/test_2d_kspace.npy', {}),
        ('test_data/test_3d_kspace.npy', {}),
    ]

    for test_file, kwargs in test_files:
        if os.path.exists(test_file):
            mri = MRIData(test_file, **kwargs)
            print(f"   ✅ {test_file}: {mri.dimension.value}, {mri.data_type.value}, {mri.num_slices} slices")
        else:
            print(f"   ⚠️  {test_file}: Not found (run generate_test_data.py)")
except Exception as e:
    print(f"   ❌ Data loading failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: k-space conversion
print("\n3. Testing k-space conversion...")
try:
    mri_2d = MRIData('test_data/test_2d_kspace.npy')
    image_2d = KSpaceConverter.convert(mri_2d, mode_3d=False)
    print(f"   ✅ 2D k-space converted: {image_2d.shape}")

    mri_3d = MRIData('test_data/test_3d_kspace.npy')
    image_3d_2d_acq = KSpaceConverter.convert(mri_3d, mode_3d=False)
    print(f"   ✅ 3D k-space (2D acquisition) converted: {image_3d_2d_acq.shape}")

    mri_3d_3d = MRIData('test_data/test_3d_kspace.npy', acquisition_mode='3d')
    image_3d_3d_acq = KSpaceConverter.convert(mri_3d_3d, mode_3d=True)
    print(f"   ✅ 3D k-space (3D acquisition) converted: {image_3d_3d_acq.shape}")
except Exception as e:
    print(f"   ❌ Conversion failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Image processing
print("\n4. Testing image processing...")
try:
    import numpy as np
    processor = ImageProcessor()
    test_img = np.random.random((64, 64))
    
    processor.contrast = 1.5
    result = processor.process(test_img)
    print(f"   ✅ Contrast adjustment: {result.shape}")
    
    processor.reset()
    processor.use_log = True
    result = processor.process(test_img)
    print(f"   ✅ Log transform: {result.shape}")
    
    processor.reset()
    processor.rotation_angle = 45
    result = processor.process(test_img)
    print(f"   ✅ Rotation: {result.shape}")
except Exception as e:
    print(f"   ❌ Processing failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Multi-view extraction
print("\n5. Testing multi-view extraction...")
try:
    mri = MRIData('test_data/test_3d_image.npy')
    axial = mri.get_view('axial', 0)
    sagittal = mri.get_view('sagittal', 32)
    coronal = mri.get_view('coronal', 8)
    print(f"   ✅ Axial: {axial.shape}")
    print(f"   ✅ Sagittal: {sagittal.shape}")
    print(f"   ✅ Coronal: {coronal.shape}")
except Exception as e:
    print(f"   ❌ Multi-view failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 6: 3D data interpretation
print("\n6. Testing 3D data interpretation...")
try:
    # (Coil, H, W) interpretation
    coil_data = np.random.random((3, 64, 64))
    mri_coil = MRIData('test', preloaded_data=coil_data, dim3_interpretation='coil_hw')
    assert mri_coil.dimension == DataDimension.DIM_2D
    assert mri_coil.num_channels == 3
    print(f"   ✅ (Coil, H, W): {mri_coil.num_channels} channels, 2D")

    # (Slice, H, W) interpretation
    slice_data = np.random.random((10, 64, 64))
    mri_slice = MRIData('test', preloaded_data=slice_data, dim3_interpretation='slice_hw')
    assert mri_slice.dimension == DataDimension.DIM_3D
    assert mri_slice.num_slices == 10
    print(f"   ✅ (Slice, H, W): {mri_slice.num_slices} slices, 3D")
except Exception as e:
    print(f"   ❌ 3D interpretation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 7: PyQt5 availability
print("\n7. Testing PyQt5 availability...")
try:
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import Qt
    print("   ✅ PyQt5 is available and importable")
except Exception as e:
    print(f"   ❌ PyQt5 not available: {e}")
    sys.exit(1)

# Test 8: HDF5 loading
print("\n8. Testing HDF5 loading...")
try:
    import h5py
    h5_files = [
        ('test_data/test_2d_image.h5', {'dim3_interpretation': 'slice_hw'}),
        ('test_data/test_3d_kspace.h5', {}),
    ]
    for test_file, kwargs in h5_files:
        if os.path.exists(test_file):
            mri = MRIData(test_file, **kwargs)
            print(f"   ✅ {test_file}: {mri.dimension.value}, {mri.data_type.value}, {mri.num_slices} slices")
        else:
            print(f"   ⚠️  {test_file}: Not found (run generate_test_data.py)")
except Exception as e:
    print(f"   ❌ HDF5 loading failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("=" * 60)
print("✅ ALL VERIFICATIONS PASSED!")
print("=" * 60)
print()
print("The MRI Reader application is ready to use!")
print()
print("To run the application:")
print("  ./run.sh")
print("  or")
print("  uv run python -m src.main")
print()
