"""
Test Data Generator - Generate sample MRI data for testing
Creates both image and k-space data in 2D and 3D formats
"""

import numpy as np
import os

try:
    import h5py
    HAS_H5PY = True
except ImportError:
    HAS_H5PY = False


def generate_test_data():
    """Generate various test data files"""
    
    output_dir = "test_data"
    os.makedirs(output_dir, exist_ok=True)
    
    print("Generating test data...")
    
    # 1. 2D Image data (10 slices, 128x128)
    print("  - 2D image data (10 slices, 128x128)")
    image_2d = np.zeros((10, 128, 128), dtype=np.float64)
    for i in range(10):
        # Create simple circle patterns
        y, x = np.ogrid[:128, :128]
        center_x, center_y = 64, 64
        radius = 30 + i * 3
        mask = (x - center_x)**2 + (y - center_y)**2 <= radius**2
        image_2d[i][mask] = 1.0
        
        # Add some noise
        image_2d[i] += np.random.normal(0, 0.05, image_2d[i].shape)
        image_2d[i] = np.clip(image_2d[i], 0, 1)
    
    np.save(os.path.join(output_dir, "test_2d_image.npy"), image_2d)
    
    # 2. 3D Image data (2 channels, 16 slices, 64x64)
    print("  - 3D image data (2 channels, 16 slices, 64x64)")
    image_3d = np.zeros((2, 16, 64, 64), dtype=np.float64)
    for ch in range(2):
        for i in range(16):
            # Create simple patterns
            y, x = np.ogrid[:64, :64]
            center_x, center_y = 32, 32
            radius = 15 + i * 2 + ch * 5
            mask = (x - center_x)**2 + (y - center_y)**2 <= radius**2
            image_3d[ch, i][mask] = 1.0
            
            # Add noise
            image_3d[ch, i] += np.random.normal(0, 0.05, image_3d[ch, i].shape)
            image_3d[ch, i] = np.clip(image_3d[ch, i], 0, 1)
    
    np.save(os.path.join(output_dir, "test_3d_image.npy"), image_3d)
    
    # 3. 2D k-space data (single slice, 128x128)
    print("  - 2D k-space data (128x128)")
    # Create a simple image first
    y, x = np.ogrid[:128, :128]
    image = np.zeros((128, 128), dtype=np.float64)
    mask = (x - 64)**2 + (y - 64)**2 <= 30**2
    image[mask] = 1.0
    
    # Convert to k-space
    kspace_2d = np.fft.fft2(np.fft.ifftshift(image))
    np.save(os.path.join(output_dir, "test_2d_kspace.npy"), kspace_2d)
    
    # 4. 3D k-space data (1 channel, 16 slices, 64x64)
    print("  - 3D k-space data (1 channel, 16 slices, 64x64)")
    kspace_3d = np.zeros((1, 16, 64, 64), dtype=np.complex128)
    for i in range(16):
        # Create simple 3D pattern
        y, x = np.ogrid[:64, :64]
        image_slice = np.zeros((64, 64), dtype=np.float64)
        radius = 15 + i * 2
        mask = (x - 32)**2 + (y - 32)**2 <= radius**2
        image_slice[mask] = 1.0
        
        # Convert to k-space
        kspace_3d[0, i] = np.fft.fft2(np.fft.ifftshift(image_slice))
    
    np.save(os.path.join(output_dir, "test_3d_kspace.npy"), kspace_3d)
    
    # 5. 3D k-space with multiple channels (4, 32, 128, 128)
    print("  - 3D k-space data (4 channels, 32 slices, 128x128)")
    kspace_3d_multi = np.zeros((4, 32, 128, 128), dtype=np.complex128)
    for ch in range(4):
        for i in range(32):
            y, x = np.ogrid[:128, :128]
            image_slice = np.zeros((128, 128), dtype=np.float64)
            radius = 20 + i + ch * 5
            mask = (x - 64)**2 + (y - 64)**2 <= radius**2
            image_slice[mask] = 1.0
            
            kspace_3d_multi[ch, i] = np.fft.fft2(np.fft.ifftshift(image_slice))
    
    np.save(os.path.join(output_dir, "test_3d_kspace_multi.npy"), kspace_3d_multi)

    # 6. HDF5 2D image
    if HAS_H5PY:
        print("  - HDF5 2D image data (10 slices, 128x128)")
        with h5py.File(os.path.join(output_dir, "test_2d_image.h5"), 'w') as f:
            f.create_dataset('image', data=image_2d)

        print("  - HDF5 3D k-space data (4 channels, 32 slices, 128x128)")
        with h5py.File(os.path.join(output_dir, "test_3d_kspace.h5"), 'w') as f:
            f.create_dataset('kspace', data=kspace_3d_multi)
    else:
        print("  - HDF5 files skipped (h5py not available)")

    print(f"\n✅ Test data generated in '{output_dir}/' directory")
    print("Files created:")
    for f in os.listdir(output_dir):
        filepath = os.path.join(output_dir, f)
        size = os.path.getsize(filepath)
        print(f"  - {f} ({size / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    generate_test_data()
