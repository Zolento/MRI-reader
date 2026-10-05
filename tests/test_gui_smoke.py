"""Offscreen GUI smoke tests driven through the frozen ``MainWindow`` seams.

The core regression is the axis check: on an *asymmetric* volume every view has
a different max index and plane shape, so a sagittal/coronal axis swap cannot
hide.  All expectations match the frozen ``.artifacts/gui_smoke.py`` gate (also
cross-checked by ``tests/test_regression_axis.py``).
"""

from __future__ import annotations

import numpy as np
import pytest

pytestmark = pytest.mark.gui

# Modal dialogs must never appear: they would block a headless run forever.
_MODAL_EVENTS: list = []


@pytest.fixture(scope="session", autouse=True)
def _modal_safety_net(qapp):
    from PyQt5.QtCore import QTimer
    from PyQt5.QtWidgets import QApplication

    def close_modals():
        for widget in QApplication.topLevelWidgets():
            if widget.isVisible() and widget.isModal():
                _MODAL_EVENTS.append(type(widget).__name__)
                widget.close()

    timer = QTimer(qapp)
    timer.timeout.connect(close_modals)
    timer.start(200)
    yield
    timer.stop()


@pytest.fixture
def main_window(qapp, monkeypatch):
    from _helpers import stub_mainwindow_dialogs

    from src.main_window import MainWindow

    _MODAL_EVENTS.clear()
    stub_mainwindow_dialogs(monkeypatch, is_kspace=False)
    window = MainWindow()
    window.resize(640, 480)
    try:
        yield window
    finally:
        window.close()
        qapp.processEvents()
        assert _MODAL_EVENTS == [], f"unexpected modal dialogs: {_MODAL_EVENTS}"


@pytest.fixture
def asym_path(tmp_path):
    from _helpers import save_asymmetric_volume

    return save_asymmetric_volume(tmp_path / "asym.npy")


def _load(window, monkeypatch, path, **kwargs):
    from _helpers import stub_mainwindow_dialogs

    stub_mainwindow_dialogs(monkeypatch, **kwargs)
    window._open_file_path(path)


# --------------------------------------------------------------------------- #
# Axis regression: max index + plane shape per view
# --------------------------------------------------------------------------- #
def test_asymmetric_view_axis_regression(main_window, monkeypatch, asym_path):
    from _helpers import ASYMMETRIC_SHAPE, AXIS_EXPECTATIONS

    _load(main_window, monkeypatch, asym_path, is_kspace=False)
    md = main_window.mri_data
    assert md is not None
    assert md.processed_shape == ASYMMETRIC_SHAPE

    for tab, view, want_max, want_shape in AXIS_EXPECTATIONS:
        main_window.slice_navigator.view_tabs.setCurrentIndex(tab)
        assert main_window.slice_navigator.current_view == view
        assert main_window.slice_navigator.slider.maximum() == want_max, (
            f"{view}: navigator max {main_window.slice_navigator.slider.maximum()} "
            f"!= canonical {want_max} (axis swap / wrong index axis)"
        )
        for index in range(want_max + 1):
            main_window.slice_navigator.slider.setValue(index)
            image = main_window.canvas.image
            assert image is not None, f"{view}[{index}]: nothing displayed"
            assert tuple(np.shape(image)) == want_shape, (
                f"{view}[{index}]: plane {tuple(np.shape(image))} != canonical " f"{want_shape}"
            )
            pixmap = main_window.canvas.pixmap
            assert pixmap is not None and not pixmap.isNull() and pixmap.width() > 0


def test_axial_display_matches_canonical_core_math(main_window, monkeypatch, asym_path):
    from src.core import views
    from src.core.image_processor import ImageProcessor

    _load(main_window, monkeypatch, asym_path, is_kspace=False)
    main_window.slice_navigator.view_tabs.setCurrentIndex(0)
    volume = np.asarray(main_window.mri_data.processed_data)
    for index in (0, 3, 7):
        main_window.slice_navigator.slider.setValue(index)
        want = ImageProcessor().process(
            views.rss_combine(views.extract_view_channels(volume, "axial", index))
        )
        got = np.asarray(main_window.canvas.image)
        assert np.allclose(got, want, rtol=1e-9, atol=1e-12), (
            f"axial[{index}]: GUI display differs from canonical core math "
            f"(max abs delta {np.abs(got - want).max():.3e})"
        )


def test_image_only_load_leaves_kspace_canvas_blank(main_window, monkeypatch, asym_path):
    _load(main_window, monkeypatch, asym_path, is_kspace=False)
    assert main_window.is_kspace is False
    assert main_window.kspace_data is None
    assert main_window.kspace_canvas.pixmap is None


# --------------------------------------------------------------------------- #
# k-space path: both canvases render for every slice
# --------------------------------------------------------------------------- #
def test_kspace_path_renders_both_canvases(main_window, monkeypatch):
    import os

    from _helpers import TEST_DATA, require_file

    path = require_file(os.path.join(TEST_DATA, "test_3d_kspace.npy"))
    _load(main_window, monkeypatch, path, is_kspace=True, acquisition_mode="2d")
    assert main_window.is_kspace is True
    assert main_window.kspace_data is not None
    assert main_window.current_image is not None

    main_window.slice_navigator.view_tabs.setCurrentIndex(0)
    for index in range(main_window.slice_navigator.slider.maximum() + 1):
        main_window.slice_navigator.slider.setValue(index)
        assert main_window.kspace_canvas.pixmap is not None, f"kspace canvas blank at {index}"
        assert main_window.canvas.pixmap is not None, f"image canvas blank at {index}"


def test_enhancement_target_switch_and_reset(main_window, monkeypatch):
    import os

    from _helpers import TEST_DATA, require_file

    path = require_file(os.path.join(TEST_DATA, "test_3d_kspace.npy"))
    _load(main_window, monkeypatch, path, is_kspace=True)
    for target in ("Image", "K-Space"):
        main_window.enhancement_panel.set_target(target)
        assert main_window.canvas.pixmap is not None
        assert main_window.kspace_canvas.pixmap is not None

    main_window.enhancement_panel.set_contrast(1.8)
    main_window.enhancement_panel.set_brightness(-0.2)
    main_window.enhancement_panel.set_log_enabled(True)
    main_window.enhancement_panel.set_rotation(35)
    main_window.enhancement_panel.set_zoom(1.4)
    main_window._on_rotate_90(1)
    main_window._on_flip_horizontal()
    main_window._on_flip_vertical()
    assert main_window.canvas.pixmap is not None
    assert main_window.kspace_canvas.pixmap is not None

    main_window.enhancement_panel.set_target("Image")
    main_window._on_reset()
    assert main_window.canvas.pixmap is not None
    assert main_window.kspace_canvas.pixmap is not None


def test_every_view_renders_with_enhancements(main_window, monkeypatch):
    import os

    from _helpers import TEST_DATA, require_file

    path = require_file(os.path.join(TEST_DATA, "test_3d_kspace.npy"))
    _load(main_window, monkeypatch, path, is_kspace=True)
    for tab in (0, 1, 2):
        main_window.slice_navigator.view_tabs.setCurrentIndex(tab)
        main_window.slice_navigator.slider.setValue(
            main_window.slice_navigator.slider.maximum() // 2
        )
        main_window.enhancement_panel.set_target("K-Space")
        assert main_window.canvas.pixmap is not None
        assert main_window.kspace_canvas.pixmap is not None


# --------------------------------------------------------------------------- #
# Saving
# --------------------------------------------------------------------------- #
def test_save_png_to_tmp_path(main_window, monkeypatch, tmp_path, asym_path):
    Image = pytest.importorskip("PIL.Image")
    from src.app import display as display_mod

    _load(main_window, monkeypatch, asym_path, is_kspace=False)
    main_window.slice_navigator.view_tabs.setCurrentIndex(0)
    main_window.slice_navigator.slider.setValue(3)

    out = tmp_path / "slice.png"
    monkeypatch.setattr(
        display_mod.QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(out), "PNG Image (*.png)"),
    )
    monkeypatch.setattr(display_mod.QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(display_mod.QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(display_mod.QMessageBox, "critical", lambda *a, **k: None)

    main_window._save_image()
    assert out.exists() and out.stat().st_size > 0
    with Image.open(out) as saved:
        assert saved.size == (30, 20)  # (W, H) of the axial plane


# --------------------------------------------------------------------------- #
# Canvas zoom must affect rendering (QPixmap/GDI-independent check)
# --------------------------------------------------------------------------- #
def test_canvas_zoom_changes_render(main_window, monkeypatch, asym_path):
    from PyQt5.QtCore import QPoint, Qt
    from PyQt5.QtGui import QPixmap, QWheelEvent

    _load(main_window, monkeypatch, asym_path, is_kspace=False)
    canvas = main_window.canvas
    canvas.resize(320, 320)
    canvas.reset_zoom()
    assert canvas.zoom_level == 1.0

    event = QWheelEvent(
        QPoint(160, 160),
        QPoint(160, 160),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.NoButton,
        Qt.ControlModifier,
        Qt.NoScrollPhase,
        False,
    )
    canvas.wheelEvent(event)
    assert canvas.zoom_level > 1.0, "Ctrl+wheel up did not increase zoom_level"

    canvas.zoom_level = 1.0
    at_1x = QPixmap(canvas.size())
    canvas.render(at_1x)
    canvas.zoom_level = 3.0
    at_3x = QPixmap(canvas.size())
    canvas.render(at_3x)
    assert (
        at_1x.toImage() != at_3x.toImage()
    ), "paintEvent ignores zoom_level: rendering at 1x and 3x is byte-identical"
    canvas.reset_zoom()


def test_signal_contract(qapp):
    from src.ui.image_canvas import ImageCanvas
    from src.ui.slice_navigator import SliceNavigator

    canvas = ImageCanvas()
    seen = []
    canvas.slice_changed.connect(lambda value: seen.append(("slice", value)))
    canvas.zoom_changed.connect(lambda value: seen.append(("zoom", value)))
    canvas.slice_changed.emit(3)
    canvas.zoom_changed.emit(1.5)
    assert seen == [("slice", 3), ("zoom", 1.5)]

    navigator = SliceNavigator()
    navigator_events = []
    navigator.slice_changed.connect(lambda value: navigator_events.append(("slice", value)))
    navigator.view_changed.connect(lambda value: navigator_events.append(("view", value)))
    navigator.set_3d_mode(True, 8)
    navigator._go_to_slice(2)
    navigator.view_tabs.setCurrentIndex(2)
    assert ("slice", 2) in navigator_events
    assert ("view", "coronal") in navigator_events


# --------------------------------------------------------------------------- #
# D1 regression: the *canvases* must get the oblique slice range too
# --------------------------------------------------------------------------- #
def _wheel(canvas, times, up=True):
    """Send ``times`` non-Ctrl wheel steps to ``canvas`` (slice navigation)."""
    from PyQt5.QtCore import QPoint, Qt
    from PyQt5.QtGui import QWheelEvent

    delta = 120 if up else -120
    for _ in range(times):
        event = QWheelEvent(
            QPoint(50, 50),
            QPoint(50, 50),
            QPoint(0, 0),
            QPoint(0, delta),
            Qt.NoButton,
            Qt.NoModifier,
            Qt.NoScrollPhase,
            False,
        )
        canvas.wheelEvent(event)


def _make_kspace_file(tmp_path, name, shape=(1, 6, 8, 10), seed=0):
    rng = np.random.RandomState(seed)
    data = (rng.rand(*shape) + 1j * rng.rand(*shape)).astype(np.complex128)
    path = tmp_path / name
    np.save(path, data)
    return str(path)


def test_view_range_syncs_navigator_and_both_canvases(main_window, monkeypatch, asym_path):
    """D1: every view gives navigator *and* both canvases ``max_idx + 1``."""
    from _helpers import AXIS_EXPECTATIONS

    _load(main_window, monkeypatch, asym_path, is_kspace=False)
    for tab, view, want_max, _shape in AXIS_EXPECTATIONS:
        main_window.slice_navigator.view_tabs.setCurrentIndex(tab)
        assert main_window.slice_navigator.current_view == view
        assert main_window.slice_navigator.slider.maximum() == want_max
        assert main_window.slice_navigator.num_slices == want_max + 1
        assert main_window.canvas.num_slices == want_max + 1, (
            f"{view}: image canvas num_slices {main_window.canvas.num_slices} "
            f"!= {want_max + 1} (canvas cannot navigate past S-1)"
        )
        assert main_window.kspace_canvas.num_slices == want_max + 1, (
            f"{view}: k-space canvas num_slices {main_window.kspace_canvas.num_slices} "
            f"!= {want_max + 1}"
        )


@pytest.mark.parametrize(
    "tab,view,want_max,plane_shape",
    [(0, "axial", 7, (20, 30)), (1, "sagittal", 29, (8, 20)), (2, "coronal", 19, (8, 30))],
    ids=["axial", "sagittal", "coronal"],
)
def test_canvas_wheel_reaches_oblique_last_index(
    main_window, monkeypatch, asym_path, tab, view, want_max, plane_shape
):
    """D1 symptom: canvas wheel navigation must actually reach the last index."""
    _load(main_window, monkeypatch, asym_path, is_kspace=False)
    main_window.slice_navigator.view_tabs.setCurrentIndex(tab)
    main_window.slice_navigator.slider.setValue(0)
    canvas = main_window.canvas
    canvas.current_slice = 0

    _wheel(canvas, want_max + 3)

    assert canvas.current_slice == want_max, (
        f"{view}: wheel stopped at {canvas.current_slice}, expected {want_max} "
        "(canvas still clamped to the slice axis)"
    )
    assert (
        main_window.slice_navigator.current_slice == want_max
    ), f"{view}: navigator did not follow the canvas to {want_max}"
    assert (
        tuple(np.shape(canvas.image)) == plane_shape
    ), f"{view}[{want_max}]: wrong plane {tuple(np.shape(canvas.image))}"


def test_kspace_canvas_wheel_reaches_oblique_last_index(main_window, monkeypatch, tmp_path):
    """D1: the k-space canvas is covered by the same range sync."""
    path = _make_kspace_file(tmp_path, "oblique_kspace.npy", shape=(2, 8, 20, 30), seed=3)
    _load(main_window, monkeypatch, path, is_kspace=True)
    main_window.slice_navigator.view_tabs.setCurrentIndex(1)  # sagittal
    main_window.slice_navigator.slider.setValue(0)
    canvas = main_window.kspace_canvas
    canvas.current_slice = 0

    _wheel(canvas, 29 + 3)

    assert canvas.current_slice == 29
    assert main_window.slice_navigator.current_slice == 29
    assert tuple(np.shape(canvas.image)) == (8, 20)


@pytest.mark.parametrize(
    "shape,tab,max_idx",
    [
        ((2, 8, 20, 1), 1, 0),  # W = 1 -> sagittal has a single index
        ((2, 8, 1, 30), 2, 0),  # H = 1 -> coronal has a single index
        ((2, 1, 20, 30), 0, 0),  # S = 1 -> no navigable volume at all
    ],
    ids=["W=1", "H=1", "S=1"],
)
def test_degenerate_singleton_axis_does_not_crash(
    main_window, monkeypatch, tmp_path, shape, tab, max_idx
):
    """D1: degenerate axes must clamp to 0 without crashing the range sync."""
    path = tmp_path / "degenerate.npy"
    np.save(path, np.random.RandomState(4).rand(*shape))
    _load(main_window, monkeypatch, str(path), is_kspace=False)

    main_window.slice_navigator.view_tabs.setCurrentIndex(tab)
    canvas = main_window.canvas
    _wheel(canvas, 3)

    assert canvas.num_slices >= 1
    assert canvas.current_slice >= 0
    assert main_window.slice_navigator.slider.maximum() >= 0
    if main_window.mri_data.num_slices > 1:
        assert canvas.num_slices == max_idx + 1


# --------------------------------------------------------------------------- #
# D2 regression: reloading a file must not leak the previous target's params
# --------------------------------------------------------------------------- #
def _assert_load_time_defaults(window, expect_log: bool):
    panel_params = window.enhancement_panel.get_params()
    assert panel_params["contrast"] == pytest.approx(1.0)
    assert panel_params["brightness"] == pytest.approx(0.0)
    assert panel_params["use_log"] is False
    assert panel_params["rotation"] == 0
    assert panel_params["zoom"] == pytest.approx(1.0)

    assert window.enhancement_target == "Image"
    assert window.processor is window.image_processor
    assert window.image_processor.contrast == pytest.approx(1.0)
    assert window.image_processor.brightness == pytest.approx(0.0)
    assert window.image_processor.use_log is False

    assert window.kspace_processor.contrast == pytest.approx(1.0)
    assert window.kspace_processor.brightness == pytest.approx(0.0)
    assert window.kspace_processor.use_log is expect_log


def test_reload_while_on_kspace_target_does_not_pollute_image_params(
    main_window, monkeypatch, tmp_path
):
    """D2: stale K-Space panel values must not be written into image_processor."""
    path_a = _make_kspace_file(tmp_path, "a.npy", seed=1)
    path_b = _make_kspace_file(tmp_path, "b.npy", seed=2)

    _load(main_window, monkeypatch, path_a, is_kspace=True)
    assert main_window.kspace_processor.use_log is True

    main_window.enhancement_panel.set_target("K-Space")
    assert main_window.enhancement_target == "K-Space"
    main_window.enhancement_panel.set_contrast(2.0)
    main_window.enhancement_panel.set_brightness(0.5)
    assert main_window.kspace_processor.contrast == pytest.approx(2.0)
    assert main_window.kspace_processor.brightness == pytest.approx(0.5)

    _load(main_window, monkeypatch, path_b, is_kspace=True)

    _assert_load_time_defaults(main_window, expect_log=True)
    # The specific D2 symptom: contrast 2.0 must NOT survive into image_processor.
    assert main_window.image_processor.contrast == pytest.approx(1.0)
    assert main_window.image_processor.brightness == pytest.approx(0.0)


def test_reload_while_on_image_target_also_resets(main_window, monkeypatch, tmp_path):
    """D2 control group: leaving on the Image target resets identically."""
    path_a = _make_kspace_file(tmp_path, "a2.npy", seed=5)
    path_b = _make_kspace_file(tmp_path, "b2.npy", seed=6)

    _load(main_window, monkeypatch, path_a, is_kspace=True)
    assert main_window.enhancement_target == "Image"
    main_window.enhancement_panel.set_contrast(2.0)
    main_window.enhancement_panel.set_brightness(0.5)
    assert main_window.image_processor.contrast == pytest.approx(2.0)

    _load(main_window, monkeypatch, path_b, is_kspace=True)

    _assert_load_time_defaults(main_window, expect_log=True)


def test_target_switch_keeps_processor_params_independent(main_window, monkeypatch, tmp_path):
    """D2 guard: within one file, per-target parameters stay independent."""
    path = _make_kspace_file(tmp_path, "c.npy", seed=7)
    _load(main_window, monkeypatch, path, is_kspace=True)
    panel = main_window.enhancement_panel

    panel.set_target("Image")
    panel.set_contrast(1.5)
    assert main_window.image_processor.contrast == pytest.approx(1.5)

    panel.set_target("K-Space")
    assert panel.get_params()["contrast"] == pytest.approx(1.0)  # k-space default
    assert main_window.kspace_processor.contrast == pytest.approx(1.0)
    panel.set_contrast(0.7)
    assert main_window.kspace_processor.contrast == pytest.approx(0.7)

    panel.set_target("Image")
    assert panel.get_params()["contrast"] == pytest.approx(1.5)
    assert main_window.image_processor.contrast == pytest.approx(1.5)
    assert main_window.kspace_processor.contrast == pytest.approx(0.7)


# --------------------------------------------------------------------------- #
# D5 regression: slider <-> canvas slice sync (no stale canvas index)
# --------------------------------------------------------------------------- #
def test_slider_to_canvas_sync_and_wheel_boundary(main_window, monkeypatch, asym_path):
    """D5: slider moves must update both canvases; wheel steps from there."""
    _load(main_window, monkeypatch, asym_path, is_kspace=False)
    navigator = main_window.slice_navigator
    navigator.view_tabs.setCurrentIndex(0)  # axial, max = 7
    slider = navigator.slider
    assert slider.maximum() == 7

    slider.setValue(7)
    assert main_window.canvas.current_slice == 7
    assert main_window.kspace_canvas.current_slice == 7

    # At the upper boundary a wheel step must stay at 7, not restart from a stale 0.
    _wheel(main_window.canvas, 1)
    assert navigator.current_slice == 7, "wheel at the boundary jumped the navigator"
    assert main_window.canvas.current_slice == 7

    slider.setValue(3)
    assert main_window.canvas.current_slice == 3
    assert main_window.kspace_canvas.current_slice == 3
    _wheel(main_window.canvas, 1)
    assert main_window.canvas.current_slice == 4
    assert navigator.current_slice == 4, "wheel step did not propagate to the navigator"
    assert tuple(np.shape(main_window.canvas.image)) == (20, 30)

    # Same contract for an oblique view (sagittal max = 29).
    navigator.view_tabs.setCurrentIndex(1)
    slider = navigator.slider
    slider.setValue(29)
    assert main_window.canvas.current_slice == 29
    assert main_window.kspace_canvas.current_slice == 29
    _wheel(main_window.canvas, 1)
    assert navigator.current_slice == 29
    assert main_window.canvas.current_slice == 29


def test_arrow_keys_advance_and_sync_canvases(main_window, monkeypatch, asym_path):
    """D5: navigator key steps keep both canvases on the same index."""
    from PyQt5.QtCore import QEvent, Qt
    from PyQt5.QtGui import QKeyEvent

    _load(main_window, monkeypatch, asym_path, is_kspace=False)
    navigator = main_window.slice_navigator
    navigator.view_tabs.setCurrentIndex(0)
    navigator.slider.setValue(2)

    def press(key):
        navigator.keyPressEvent(QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier))

    press(Qt.Key_Right)
    assert navigator.current_slice == 3
    assert main_window.canvas.current_slice == 3
    assert main_window.kspace_canvas.current_slice == 3

    press(Qt.Key_Left)
    assert navigator.current_slice == 2
    assert main_window.canvas.current_slice == 2
    assert main_window.kspace_canvas.current_slice == 2

    navigator.slider.setValue(navigator.slider.maximum())
    press(Qt.Key_Right)  # boundary: stays put and stays in sync
    assert navigator.current_slice == navigator.slider.maximum()
    assert main_window.canvas.current_slice == navigator.slider.maximum()
    assert main_window.kspace_canvas.current_slice == navigator.slider.maximum()


# --------------------------------------------------------------------------- #
# D-MAT regression through the frozen open-file seam
# --------------------------------------------------------------------------- #
def test_mat_4d_singleton_coil_axis_via_open_file_path(main_window, monkeypatch, tmp_path):
    """D-MAT end-to-end: a (1,5,7,11) .mat must load as C=1, S=5.

    Goes through ``_open_file_path`` with the class-level dialog seams stubbed,
    so the real file-loader path (not just ``load_mat_file``) is exercised.
    """
    io = pytest.importorskip("scipy.io")
    from _helpers import stub_mainwindow_dialogs

    from src.main_window import MainWindow

    array = np.arange(1 * 5 * 7 * 11, dtype=float).reshape(1, 5, 7, 11)
    path = tmp_path / "single_coil.mat"
    io.savemat(str(path), {"vol": array})

    stub_mainwindow_dialogs(monkeypatch, is_kspace=False, dim4_interpretation="coil_slice_hw")
    monkeypatch.setattr(MainWindow, "_ask_mat_key", lambda self, p: "vol")

    main_window._open_file_path(str(path))

    md = main_window.mri_data
    assert md.raw_data.shape == (1, 5, 7, 11)
    assert (md.num_channels, md.num_slices) == (1, 5)
    assert md.processed_shape == (1, 5, 7, 11)

    # Every slice of the single coil must be displayable.
    for index in range(5):
        main_window.slice_navigator.slider.setValue(index)
        assert main_window.canvas.pixmap is not None, f"slice {index} did not render"
