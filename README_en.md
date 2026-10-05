# MRI Reader

[English](README_en.md) | [中文](README.md)

A lightweight MRI data inspector. In a deep-learning data pipeline, use it to quickly open
`.npy` / `.h5` / `.mat`, confirm shapes and dimension meaning, take a look at the image or
k-space, and reconstruct with the correct IFFT mode when needed.

> It is not a clinical viewer and does no quantitative analysis. It exists to answer
> "let me just look at this data and make sure it is fine".

## What it solves

While debugging MRI models you keep having to answer:

- Is this data in the **image domain** or in **k-space**?
- In `(C, S, H, W)`, which axis is coil and which is slice? Is 4D data `(Coil, Slice)` or `(Slice, Coil)`?
- What does the k-space look like after IFFT? Should it be reconstructed as **2D slice-by-slice** or **3D volumetric** acquisition?
- Does the multi-coil data look right after RSS combination? Is one slice broken?

MRI Reader is built for exactly those "take a look" moments: drop the file in, answer two
questions, page through slices with the arrow keys.

## Quick start

```bash
pip install -e ".[dev]"      # install (includes pytest / ruff / black)
python -m src.main           # or ./run.sh, or the installed `mri-reader` command
```

Dropping a file onto the window also works.

## Supported input

| Format | Notes |
|--------|-------|
| `.npy` | a single array, read directly |
| `.h5` / `.hdf5` | pick a dataset (e.g. `kspace` / `reconstruction_rss` in ISMRMRD-style files) |
| `.mat` | pick a variable key |

After opening, you confirm three things:

1. **Data type**: `Image` (image domain) or `K-Space` (frequency domain)
2. **Acquisition mode** (k-space only): `2D` (slice-by-slice 2D IFFT, default) or `3D` (volume 3D IFFT)
3. **Dimension interpretation**: whether 4D data is `(Coil, Slice, H, W)` or `(Slice, Coil, H, W)`,
   and whether the first axis of 3D data is coil or slice

Internally everything is normalized to `(C, S, H, W)`:

| Axis | Meaning |
|------|---------|
| C | coil channel |
| S | slice (superior–inferior) |
| H | rows (anterior–posterior) |
| W | columns (left–right) |

| Raw shape | Your interpretation | Internal shape | Dimension |
|---|---|---|---|
| `(H, W)` | — | `(1, 1, H, W)` | 2D |
| `(X, H, W)` | `(Coil, H, W)` | `(X, 1, H, W)` | 2D |
| `(X, H, W)` | `(Slice, H, W)` | `(1, X, H, W)` | 3D |
| `(C, S, H, W)` | `(Coil, Slice, H, W)` | unchanged | 3D |
| `(S, C, H, W)` | `(Slice, Coil, H, W)` | transposed to `(C, S, H, W)` | 3D |

Each view fixes one axis (`src/core/views.py` is the single source of truth):

| View | Fixed axis | Plane shape | Index range |
|---|---|---|---|
| Axial | S | `(H, W)` | `0 .. S-1` |
| Sagittal | W | `(S, H)` | `0 .. W-1` |
| Coronal | H | `(S, W)` | `0 .. H-1` |

## k-space reconstruction

| Acquisition mode | Granularity | IFFT axes |
|---|---|---|
| 2D (default) | per `(coil, slice)` | last two `(phase, freq)` |
| 3D | per `coil` | last three `(slice, phase, freq)` |

The difference is whether the slice direction carries phase encoding: with 2D slice-by-slice
acquisition it does not participate in the IFFT; with 3D volumetric acquisition it does.
Magnitude is taken afterwards, and coils are combined with root-sum-of-squares (RSS).

## Interface and controls

```
+------------------+------------------+------------+
|   K-Space view   |    Image view    | Enhance    |
+------------------+------------------+            |
+-------------------------------------+------------+
|        Slice / view navigator (bottom)            |
+--------------------------------------------------+
```

- **Open**: `Ctrl+O`, or drag a file onto the window
- **Save current image**: `Ctrl+S` (JPG / PNG)
- **Page slices**: arrow keys, bottom slider, mouse wheel, click on the image
- **Switch view**: the Axial / Sagittal / Coronal tabs at the bottom
- **Zoom**: `Ctrl+wheel`, `Ctrl++` / `Ctrl+-` / `Ctrl+0`
- **Enhance**: right panel; pick `K-Space` or `Image` at the top — the two parameter sets are independent
  - contrast `0.1x–5.0x`, brightness `-1.0–+1.0`
  - **Log transform**: almost always on for k-space, otherwise the huge dynamic range hides everything but the bright center
  - arbitrary-angle rotation, 90° shortcuts, zoom, horizontal/vertical flip
- **Reset current target**: `Ctrl+R`

## Large files and memory

`.h5` is read lazily: opening a 778 MB k-space dataset does not pull the whole thing into memory.

| Scenario | Peak memory |
|---|---|
| Open + axial (default view) inspection | ~280 MB |
| First switch to sagittal / coronal | one-time volume build: memory rises, takes a few seconds |
| Subsequent sagittal / coronal switching | instant |

`.npy` / `.mat` are loaded whole by NumPy / SciPy and do not get this optimization.

## Tests and development

```bash
python -m pytest -q            # full test suite (headless Qt)
python test_core.py            # legacy core smoke test (kept)
python verify.py               # legacy end-to-end verification (kept)
ruff check . && black --check .
```

Set `QT_QPA_PLATFORM=offscreen` when there is no display. CI lives in `.github/workflows/test.yml`.

## Project layout

```
src/
├── main.py                  # entry point (QApplication bootstrap)
├── main_window.py           # main window: layout / menus / signal wiring (thin coordinator)
├── app/                     # application layer: wires core and ui together
│   ├── file_loader.py       #   file dialogs and loading (.npy / .h5 / .mat)
│   ├── display.py           #   view extraction, RSS, rendering, display cache
│   ├── enhancement.py       #   the two processors and parameter sync
│   └── lazy.py              #   lazy read-only proxy for large HDF5
├── core/                    # pure computation, no Qt dependency
│   ├── views.py             #   ★ single source of truth for view/index semantics
│   ├── mri_data.py          #   loading, shape normalization, lazy reads
│   ├── kspace_converter.py  #   2D / 3D IFFT
│   └── image_processor.py   #   contrast / brightness / log / rotate / zoom / flip
└── ui/                      # pure widget layer
    ├── image_canvas.py      #   image canvas
    ├── enhancement_panel.py #   enhancement panel
    └── slice_navigator.py   #   slice / view navigator
```

Layering rule: `core` does not import Qt (so it is unit-testable without a GUI), `ui` holds no
numerical logic, and `app` does the assembly.

## Tech stack

PyQt5, NumPy, SciPy (`ndimage` rotation/zoom, `.mat` reading), h5py, Pillow.

## Known limitations

- View semantics are fixed: axial fixes S, sagittal fixes W, coronal fixes H. No arbitrary oblique reformatting.
- Automatic k-space detection is a heuristic; the GUI selection always wins.
- HDF5: a single dataset is used; the ISMRMRD header is not parsed.
- `.npy` / `.mat` do not benefit from lazy loading.
- No quantitative analysis, no registration, no DICOM writing.

## License

This project is for learning and research use only.
