"""Final verification entry point for the MRI Reader.

Runs a quick import smoke check and then the full pytest suite (offscreen GUI
included, performance budget skipped).  ``python verify.py`` must exit non-zero
on any failure; README/AGENTS reference it.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def import_smoke_check() -> bool:
    print("1. Testing module imports...")
    try:
        from src.core.image_processor import ImageProcessor  # noqa: F401
        from src.core.kspace_converter import KSpaceConverter  # noqa: F401
        from src.core.mri_data import DataDimension, DataType, MRIData  # noqa: F401
        from src.core.views import VIEW_TYPES  # noqa: F401
        from src.main_window import MainWindow  # noqa: F401
        from src.ui.enhancement_panel import EnhancementPanel  # noqa: F401
        from src.ui.image_canvas import ImageCanvas  # noqa: F401
        from src.ui.slice_navigator import SliceNavigator  # noqa: F401
    except Exception as exc:  # pragma: no cover - failure path
        print(f"   ❌ Import failed: {exc}")
        return False
    print("   ✅ All modules imported successfully")
    return True


def main() -> int:
    print("=" * 60)
    print("MRI Reader - Final Verification")
    print("=" * 60)
    if not import_smoke_check():
        return 1

    import pytest

    print("\n2. Running the full test suite (performance budget excluded)...")
    args = [
        "-q",
        "-p",
        "no:cacheprovider",
        "-c",
        os.path.join(ROOT, "pyproject.toml"),
        "--rootdir",
        ROOT,
        "-m",
        "not perf",
        os.path.join(ROOT, "tests"),
    ]
    code = int(pytest.main(args))

    print()
    print("=" * 60)
    if code == 0:
        print("✅ ALL VERIFICATIONS PASSED!")
    else:
        print("❌ VERIFICATION FAILED")
    print("=" * 60)
    return code


if __name__ == "__main__":
    sys.exit(main())
