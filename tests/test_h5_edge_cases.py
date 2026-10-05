"""D-H5-EDGE / S-3 regression: clean errors for degenerate HDF5 layouts.

* 0-D/1-D datasets, groups-only files and explicit group keys must fail with a
  precise ``ValueError`` (never ``IndexError``/``AttributeError``).
* A brain-like file (0-D metadata + 4-D k-space) must still open.
* Once a lazy source is closed it stays closed: reads raise ``ValueError`` and
  the file descriptor is released exactly once (double close is idempotent).
"""

from __future__ import annotations

import os

import numpy as np
import pytest
from _helpers import BRAIN_H5, require_file  # noqa: E402

from src.core.mri_data import DataType, MRIData


def _write(path, datasets=(), groups=()):
    h5py = pytest.importorskip("h5py")
    with h5py.File(path, "w") as handle:
        for name in groups:
            handle.create_group(name)
        for name, data in datasets:
            handle.create_dataset(name, data=data)
    return str(path)


# --------------------------------------------------------------------------- #
# Unsupported ranks
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "data",
    [np.array(5.0), np.array(5.0 + 1j), np.arange(5.0), np.arange(5.0) + 1j],
    ids=["0d-real", "0d-complex", "1d-real", "1d-complex"],
)
def test_unsupported_rank_raises_clear_value_error(tmp_path, data):
    path = _write(tmp_path / "degenerate.h5", [("meta", data)])

    with pytest.raises(ValueError, match="Unsupported data dimension") as excinfo:
        MRIData(path)
    # pytest.raises(ValueError) already excludes IndexError/AttributeError;
    # assert the type explicitly for the regression record.
    assert type(excinfo.value) is ValueError
    assert not isinstance(excinfo.value, (IndexError, AttributeError))


# --------------------------------------------------------------------------- #
# Groups
# --------------------------------------------------------------------------- #
def test_groups_only_file_raises_no_datasets_value_error(tmp_path):
    path = _write(tmp_path / "groups_only.h5", groups=("meta", "header"))

    with pytest.raises(ValueError, match="No datasets found") as excinfo:
        MRIData(path)
    assert type(excinfo.value) is ValueError
    assert not isinstance(excinfo.value, (IndexError, AttributeError))


def test_explicit_group_key_raises_value_error(tmp_path):
    path = _write(
        tmp_path / "group_key.h5",
        [("kspace", np.zeros((2, 3, 4)))],
        groups=("meta",),
    )

    with pytest.raises(ValueError, match="not a dataset") as excinfo:
        MRIData(path, h5_key="meta")
    assert type(excinfo.value) is ValueError
    assert not isinstance(excinfo.value, (IndexError, AttributeError))


def test_group_selection_never_touches_group_shape(tmp_path):
    """A Group that sorts first must be skipped, not queried for ``.shape``."""
    path = _write(
        tmp_path / "group_first.h5",
        [("kspace", np.zeros((2, 3, 4)))],
        groups=("aaa_meta",),
    )
    md = MRIData(path)
    assert md.processed_shape == (2, 1, 3, 4)


# --------------------------------------------------------------------------- #
# Brain-like file still opens
# --------------------------------------------------------------------------- #
def test_brain_like_metadata_plus_kspace_opens(tmp_path):
    h5py = pytest.importorskip("h5py")
    path = tmp_path / "brain_like.h5"
    with h5py.File(path, "w") as handle:
        handle.create_dataset("ismrmrd_header", data=np.float64(1.0))  # 0-D metadata
        handle.create_dataset("kspace", data=np.zeros((2, 3, 4, 5), dtype=np.complex64))

    md = MRIData(str(path))
    assert md.data_type == DataType.KSPACE
    assert md.processed_shape == (2, 3, 4, 5)
    md.close()


def test_real_brain_h5_opens_lazily():
    path = require_file(BRAIN_H5)
    md = MRIData(path)
    try:
        assert md.data_type == DataType.KSPACE
        assert md.processed_shape == (16, 20, 768, 396)
    finally:
        md.close()


# --------------------------------------------------------------------------- #
# S-3: a closed lazy source stays closed and releases its descriptor
# --------------------------------------------------------------------------- #
def _fd_count():
    return len(os.listdir("/proc/self/fd"))


def test_lazy_source_close_is_permanent_and_idempotent(tmp_path):
    h5py = pytest.importorskip("h5py")
    value = np.arange(2 * 3 * 4 * 5, dtype=np.float32).reshape(2, 3, 4, 5)
    path = tmp_path / "lazy.h5"
    with h5py.File(path, "w") as handle:
        handle.create_dataset("kspace", data=value)

    md = MRIData(str(path))
    lazy = getattr(md, "_lazy", None)
    if lazy is None:
        pytest.skip("MRIData no longer exposes a lazy source handle")
    assert getattr(md, "_raw_data", None) is None, "opening must stay lazy"

    # A first plane read opens the file handle.
    assert np.array_equal(md.get_slice(0, 0), value[0, 0])

    md.close()
    md.close()  # idempotent: must not raise

    with pytest.raises(ValueError, match="Cannot read from closed HDF5 source"):
        lazy.read(())
    with pytest.raises(ValueError):
        md.get_slice(0, 0)
    with pytest.raises(ValueError):
        _ = md.processed_data


@pytest.mark.skipif(not os.path.isdir("/proc/self/fd"), reason="descriptor accounting needs /proc")
def test_lazy_close_releases_descriptor(tmp_path):
    h5py = pytest.importorskip("h5py")
    path = tmp_path / "fd.h5"
    with h5py.File(path, "w") as handle:
        handle.create_dataset("kspace", data=np.zeros((2, 3, 4, 5), dtype=np.complex64))

    md = MRIData(str(path))
    baseline = _fd_count()
    md.get_slice(0, 0)  # opens exactly one descriptor
    opened = _fd_count()
    assert opened == baseline + 1, f"expected one extra fd, got {opened - baseline}"

    md.close()
    assert _fd_count() == baseline
    md.close()  # second close must not change the descriptor count
    assert _fd_count() == baseline
