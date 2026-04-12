# MRI Reader

[English](README_en.md) | [中文](README.md)

MRI image viewing and processing tool based on Qt and Python, supporting 2D/3D images and k-space data.

## Features

### Core Features
- Intelligent data detection: automatically identifies 2D/3D, manually identifies image/k-space data types
- k-space conversion: supports 2D slice-by-slice IFFT and 3D full IFFT conversion
- Multi-format support: reads .npy files, saves as .jpg/.png format
- Multi-view display: 3D data supports Axial, Sagittal, and Coronal views
- RSS coil combination: automatically combines multi-channel data using Root Sum of Squares

### Image Enhancement Operations
- Contrast adjustment: 0.1x - 5.0x range with slider + spinbox control
- Brightness adjustment: -1.0 - +1.0 range with real-time preview
- Log transform: specifically for viewing k-space data
- Rotation: arbitrary angle (-180 to 180 degrees) and quick 90-degree multiples
- Zoom: 0.1x - 5.0x, supports mouse wheel zoom
- Flip: horizontal and vertical flip

### 3D Navigation
- Slider: intuitive slice position selection
- Button navigation: previous/next/first/last slice quick buttons
- Keyboard support: arrow keys for quick slice switching
- Mouse wheel: switch slices in 3D mode
- Click selection: click on image to select slice

## System Requirements

- OS: Linux (primary), Windows, macOS
- Python: >= 3.9
- Package manager: uv (recommended) or pip

## Quick Start

### 1. Install uv (if not installed)

```bash
# Linux/macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# or via pip
pip install uv
```

### 2. Setup Environment

```bash
# Enter project directory
cd mri-reader

# Run environment setup script
./setup.sh
```

### 3. Run the Program

```bash
# Method 1: Use uv directly
uv run python -m src.main

# Method 2: Quick start script
./run.sh
```

### 4. Generate Test Data (Optional)

```bash
# Generate test data to verify features
uv run python generate_test_data.py
```

This will generate test files in the `test_data/` directory, including 2D/3D images and k-space data.

## Usage

### Interface Layout

```
+----------------+----------------+-----------+
|   K-Space View |    Image View   | Enhance   |
|    (Left)      |    (Center)     |  (Right)  |
+----------------+----------------+           |
+----------------------------------+-----------+
|        Slice/View Navigator (Bottom)         |
+----------------------------------------------+
```

### Open File
1. Click menu `File` -> `Open` or press `Ctrl+O`
2. Select `.npy` MRI data file
3. Program automatically detects data type and displays

### Save Image
1. Click menu `File` -> `Save as JPG` or press `Ctrl+S`
2. Choose save path and format (JPG/PNG)
3. Currently displayed image will be saved

### Enhancement Operations
1. Select enhancement target at top of right panel: K-Space or Image
2. Adjust parameters (each target's parameters saved independently):
   - Drag sliders or input values to adjust contrast/brightness
   - Check Log transform to view k-space
   - Set rotation angle or use quick buttons
3. Click "Reset All" to restore current target's default settings

### 3D Data Navigation
- Use bottom slider to select slice
- Click tabs to switch views (Axial/Sagittal/Coronal)
- Use arrow keys to quickly browse slices
- Mouse wheel to switch slices (hold Ctrl to zoom)

## Keyboard Shortcuts

| Shortcut | Function |
|----------|----------|
| Ctrl+O | Open file |
| Ctrl+S | Save image |
| Ctrl+R | Reset current target settings |
| Ctrl+0 | Fit to window |
| Ctrl++ | Zoom in |
| Ctrl+- | Zoom out |
| Arrow Keys | Switch slice (3D mode) |
| Ctrl+Mouse Wheel | Zoom image |

## Project Structure

```
mri-reader/
├── pyproject.toml              # Project config and dependencies
├── setup.sh                    # Environment setup script
├── run.sh                      # Quick start script
├── generate_test_data.py       # Test data generator
├── README.md                   # Chinese documentation
├── README_en.md                # English documentation
├── src/
│   ├── main.py                 # Entry point
│   ├── main_window.py          # Main window
│   ├── core/
│   │   ├── mri_data.py         # MRI data model and auto-detection
│   │   ├── kspace_converter.py # k-space FFT conversion
│   │   └── image_processor.py  # Image enhancement processing
│   └── ui/
│       ├── image_canvas.py     # Image display canvas
│       ├── enhancement_panel.py # Enhancement operation panel
│       └── slice_navigator.py  # Slice navigator
└── test_data/                  # Test data directory (git ignored)
```

## Data Format Specification

### Supported Input Formats

Supports the following file formats:

- **NumPy (.npy)**: Direct reading of .npy files
- **MAT (.mat)**: Reading MATLAB .mat files with multi-key selection

Program automatically detects following data shapes:

1. 2D image: (height, width) or (slices, height, width)
2. 3D image: (channels, slices, height, width)
3. 2D k-space: (phase, freq) (complex data)
4. 3D k-space: (channels, slices, phase, freq) (complex data)

### Loading Process

1. Select .npy or .mat file
2. Select data type: K-Space (frequency domain) / Image (image data)
3. If .mat file, select data key
4. Auto-process and display

### K-Space Conversion

- 2D mode: slice-by-slice 2D IFFT
- 3D mode: IFFT on phase and frequency dimensions (ortho normalization)

## Tech Stack

- GUI Framework: PyQt5 - mature cross-platform GUI library
- Numerical Computing: NumPy - array operations and math
- Scientific Computing: SciPy - image rotation and scaling
- Image Processing: Pillow - image saving support

## Development Guide

### Add New Dependencies

```bash
uv pip install package_name
# and update pyproject.toml
```

### Extend Features

1. Add new image enhancement: add method to `ImageProcessor` class
2. Add new UI components: create components in corresponding `ui/` module
3. Support new data formats: extend `MRIData` class detection method

## License

This project is for learning and research use only.
