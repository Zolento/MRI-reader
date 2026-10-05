# Project Instructions

This file provides context for AI assistants working on this project.

## Project Type: Python (PyQt5 desktop app)

### Commands
- Install (with dev tools): `pip install -e ".[dev]"`
- Test: `python -m pytest -q` (headless Qt: set `QT_QPA_PLATFORM=offscreen`)
- Legacy smoke tests: `python test_core.py`, `python verify.py`
- Format: `black .`
- Lint: `ruff check .`
- Test data: `python generate_test_data.py` (writes fixtures into `test_data/`, which is git-ignored)
- Run: `python -m src.main` / `./run.sh` / `mri-reader`

### Documentation
See README.md for the project overview.

### Version Control
This project uses Git. See .gitignore for excluded files.

## Guidelines

- Follow existing code style and patterns (black + ruff, line length 100, target py3.9)
- Write tests for new functionality (add them under `tests/`)
- Keep changes focused and atomic
- Document public APIs
- **Never re-implement view/index semantics outside `src/core/views.py`.** It is the single
  source of truth. The Qt and app layers must import from it.

## Important Notes

### Project Summary

MRI Reader is a lightweight PyQt5 tool for **inspecting MRI data quickly in deep-learning
pipelines**. It opens `.npy`, `.h5`/`.hdf5` and `.mat` files and handles both image-domain and
k-space (frequency-domain) data, with user-guided dimensional interpretation.

**Key capabilities:**
- k-space → image conversion via 2D or 3D IFFT (user selects acquisition mode)
- Multi-planar views (Axial, Sagittal, Coronal) with slice navigation
- Multi-coil merging via Root Sum of Squares (RSS)
- Real-time enhancement: contrast, brightness, log transform, rotation, zoom, flip
- Lazy HDF5 reads so that inspecting a large dataset stays memory-bounded

### Architecture

```
src/
├── main.py                 # QApplication bootstrap, entry point
├── main_window.py          # MainWindow: layout / menus / signal wiring (thin coordinator)
├── app/                    # application layer, wires core and ui together
│   ├── file_loader.py      #   file dialogs, .npy/.h5/.mat loading
│   ├── display.py          #   view extraction, RSS, rendering, LRU display cache
│   ├── enhancement.py      #   the two processors and target/parameter sync
│   └── lazy.py             #   lazy read-only proxies for large HDF5 volumes
├── core/                   # pure computation — MUST NOT import Qt
│   ├── views.py            #   ★ single source of truth for view/index semantics
│   ├── mri_data.py         #   MRIData: loading, shape normalization to (C,S,H,W), lazy reads
│   ├── kspace_converter.py #   IFFT conversion: 2D per-slice or 3D volumetric
│   └── image_processor.py  #   contrast, brightness, log, rotate, zoom, flip
└── ui/                     # pure widgets — MUST NOT hold numerical logic
    ├── image_canvas.py     #   QWidget canvas, zoom + slice interaction
    ├── enhancement_panel.py#   right-side controls, per-target (K-Space/Image) params
    └── slice_navigator.py  #   bottom slice slider, view tabs, navigation buttons
```

**Canonical geometry** (see the `src/core/views.py` docstring): data is always normalized to
`(C, S, H, W)`. A view fixes one axis:

| view | fixed axis | plane shape | max index |
|------|-----------|-------------|-----------|
| axial | S | `(H, W)` | `S - 1` |
| sagittal | W | `(S, H)` | `W - 1` |
| coronal | H | `(S, W)` | `H - 1` |

**Data flow:**
1. User opens a file → `MRIData` normalizes the array to 4D `(C, S, H, W)`
2. If k-space → `KSpaceConverter` applies IFFT (2D per `(coil, slice)`, or 3D per coil)
3. The app layer extracts the requested plane (`views.extract_view_channels`) and combines coils
   (`views.rss_combine`)
4. `ImageProcessor` applies the enhancement pipeline (one processor per display target)
5. `ImageCanvas` renders the 2D result as a grayscale `QImage`
6. Interactions (slider, mouse, keyboard) re-render via a bounded plane cache

**Design decisions:**
- Data is always normalized to `(C, S, H, W)` regardless of input shape
- Enhancement parameters are stored independently for the K-Space and Image targets
- Auto-detection is only a heuristic; the user's dialog choice always wins
- 3D/4D raw-data interpretation (coil vs slice, and the 4D order) is user-specified, not guessed
- Large `.h5` volumes load lazily; `.npy`/`.mat` are read eagerly by NumPy/SciPy
- The GUI is testable headless: the dialog seams on `MainWindow` are class-patchable

### Testing

- `tests/` holds the pytest suite: `test_views.py`, `test_mri_data.py`, `test_kspace_converter.py`,
  `test_image_processor.py`, `test_io_formats.py`, `test_characterization.py`,
  `test_gui_smoke.py`, `test_regression_axis.py`, `test_perf_budget.py`.
- GUI tests need `QT_QPA_PLATFORM=offscreen`. `tests/conftest.py` provides a session `QApplication`.
- `test_characterization.py` locks numerical behaviour; if you intentionally change numerics,
  update it deliberately rather than deleting assertions.
- `test_data/` is git-ignored, so tests must `skip` (not fail) when fixtures are missing.

### Dependencies

Runtime: **PyQt5**, **NumPy**, **SciPy**, **Pillow**, **h5py**.
Dev extras (`.[dev]`): **pytest**, **ruff**, **black**.

### Development Notes

- Package installed in editable mode: `pip install -e ".[dev]"`
- Entry points: `python -m src.main`, `./run.sh`, or the `mri-reader` console script
- Test data generator: `generate_test_data.py` (produces `.npy`/`.h5` fixtures in `test_data/`)
- `test_data/` also contains a real brain MRI sample (`file_brain_AXT2_*.h5`, ~778 MB) with
  `kspace` (16, 20, 768, 396) and `reconstruction_rss` (16, 384, 384)
- CI runs lint, format check and pytest on Python 3.9 and 3.11: `.github/workflows/test.yml`
