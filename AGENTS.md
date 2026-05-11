# Project Instructions

This file provides context for AI assistants working on this project.

## Project Type: Python

### Commands
- Install: `pip install -e .`
- Test: `pytest`
- Format: `black .`
- Lint: `ruff check .`

### Documentation
See README.md for project overview.

### Version Control
This project uses Git. See .gitignore for excluded files.


## Guidelines

- Follow existing code style and patterns
- Write tests for new functionality
- Keep changes focused and atomic
- Document public APIs

## Important Notes

### Project Summary

MRI Reader is a PyQt5-based desktop application for viewing and processing MRI data (.npy, .h5/.hdf5, .mat). It handles both image-domain and k-space (frequency-domain) data in 2D and 3D, with automatic type detection and user-guided dimensional interpretation.

**Key capabilities:**
- k-space → image conversion via 2D or 3D IFFT (user selects acquisition mode)
- Multi-planar 3D views (Axial, Sagittal, Coronal) with slice navigation
- Multi-channel coil data merging via Root Sum of Squares (RSS)
- Real-time image enhancement: contrast, brightness, log transform, rotation, zoom, flip

### Architecture

```
src/
├── main.py              # QApplication bootstrap, entry point
├── main_window.py       # MainWindow: coordinates all panels and menus
├── core/
│   ├── mri_data.py      # MRIData: load .npy/.h5/.mat, shape normalization to (C,S,H,W),
│   │                    #   auto-detect image vs k-space, slice/view extraction
│   ├── kspace_converter.py  # IFFT conversion: 2D per-slice or 3D volumetric
│   └── image_processor.py   # Enhancement ops: contrast, brightness, log, rotate, zoom, flip
└── ui/
    ├── image_canvas.py      # QGraphicsView-based image display with mouse/scroll handling
    ├── enhancement_panel.py # Right-side control panel with per-target (K-Space/Image) params
    └── slice_navigator.py   # Bottom slice slider, view tabs, navigation buttons
```

**Data flow:**
1. User opens file → `MRIData` loads raw array, normalizes to 4D `(channels, slices, H, W)`
2. If k-space → `KspaceConverter` applies IFFT (2D or 3D) to produce image-domain data
3. `ImageProcessor` applies enhancement pipeline (same processor used for both k-space and image display)
4. `ImageCanvas` renders the processed 2D slice as QImage via QGraphicsView
5. User interactions (sliders, mouse, keyboard) trigger re-processing and re-rendering

**Design decisions:**
- Data is always normalized to `(C, S, H, W)` internally regardless of input shape
- Enhancement parameters are stored independently for K-Space and Image display targets
- Auto-detection uses heuristics (complex dtype → k-space; high center energy → k-space) but user can override
- Supports both `.npy` (single array) and `.h5`/`.hdf5` (first dataset, for ISMRMRD-style files)
- 3D raw data interpretation (coil vs slice dimension) is user-specified, not guessed

### Dependencies

- **PyQt5** — GUI framework
- **NumPy** — array operations
- **SciPy** — image rotation/zoom (ndimage)
- **Pillow** — image save (JPG/PNG)
- **h5py** — HDF5 file support

### Development Notes

- Package installed in editable mode: `pip install -e .`
- Entry point: `python -m src.main` or `uv run python -m src.main`
- Test data generator: `generate_test_data.py` (produces .npy/.h5 files in `test_data/`)
- No test suite exists yet; `pytest` is configured but no tests written
- The `test_data/` directory contains generated test fixtures and a real brain MRI sample (`file_brain_AXT2_*.h5`)
