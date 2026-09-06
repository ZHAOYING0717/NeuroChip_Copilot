from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np

from neurochip.trujillo import read_trujillo_well, treatment_effect_class, treatment_for_well


def write_synthetic_trujillo(path: Path) -> None:
    with h5py.File(path, "w") as handle:
        handle.create_dataset("t_s", data=np.arange(0.0, 1.0, 0.01)[None, :])
        counts = np.zeros((64, 12), dtype=float)
        counts[0, 4] = 3
        handle.create_dataset("spike_cnt", data=counts)
        references = np.empty((64, 12), dtype=h5py.ref_dtype)
        empty = handle.create_dataset("empty", data=np.array([0.0, 0.0]))
        active = handle.create_dataset("active", data=np.array([[10.0, 20.0, 90.0]]))
        references[...] = empty.ref
        references[0, 4] = active.ref
        handle.create_dataset("spikes", data=references, dtype=h5py.ref_dtype)


def test_read_trujillo_well_converts_samples_and_windows(tmp_path: Path):
    source = tmp_path / "LFP_Sp_161217.mat"
    write_synthetic_trujillo(source)
    recording = read_trujillo_well(source, 5, start_s=0.1, duration_s=0.2)
    assert recording.n_channels == 64
    assert recording.n_spikes == 2
    assert np.allclose(recording.spike_times[0], [0.0, 0.1])
    assert np.isclose(recording.duration_s, 0.2)


def test_public_treatment_map_keeps_unknown_date_unlabeled():
    assert treatment_for_well("161217", 7) == "CNQX+AP5"
    assert treatment_for_well("170207", 6) == "baclofen"
    assert treatment_effect_class(treatment_for_well("170207", 5)) == "negative_control"
    assert treatment_for_well("170303", 5) == "unknown_pharmacology"
    assert treatment_effect_class("unknown_pharmacology") == "unlabeled"
