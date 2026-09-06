import pickle
from pathlib import Path

from neurochip.cache_payload import recording_from_cache_payload, recording_to_cache_payload
from neurochip.public_samples import discover_public_pairs, discover_public_samples, load_public_sample


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_demo_bundle_contains_all_sources_and_two_runnable_public_pairs():
    groups = discover_public_samples(PROJECT_ROOT, demo_only=True)

    assert list(groups) == [
        "前脑类器官参考",
        "脑类器官地西泮",
        "GIN二维神经网络",
        "Trujillo皮层类器官",
    ]
    assert [len(samples) for samples in groups.values()] == [1, 2, 1, 2]

    for samples in groups.values():
        for sample in samples:
            recording = load_public_sample(sample)
            assert recording.n_channels > 0
            assert recording.n_spikes > 0
            assert recording.duration_s > 0

    pairs = discover_public_pairs(groups)
    assert [pair.baseline.dataset_id for pair in pairs] == [
        "diazepam_organoid",
        "trujillo_cortical_organoid",
    ]
    for pair in pairs:
        assert load_public_sample(pair.baseline).n_spikes > 0
        assert load_public_sample(pair.treatment).n_spikes > 0


def test_every_public_loader_produces_a_streamlit_cache_safe_payload():
    groups = discover_public_samples(PROJECT_ROOT, demo_only=False)

    assert len(groups) == 4
    for samples in groups.values():
        recording = load_public_sample(samples[0])
        serialized = pickle.dumps(recording_to_cache_payload(recording))
        restored = recording_from_cache_payload(pickle.loads(serialized))

        assert restored.recording_id == recording.recording_id
        assert restored.n_channels == recording.n_channels
        assert restored.n_spikes == recording.n_spikes
        assert restored.duration_s == recording.duration_s


def test_full_install_discovers_matched_pairs_from_both_organoid_datasets():
    pairs = discover_public_pairs(discover_public_samples(PROJECT_ROOT, demo_only=False))

    assert len(pairs) >= 2
    assert {pair.baseline.dataset_id for pair in pairs} == {
        "diazepam_organoid",
        "trujillo_cortical_organoid",
    }
    assert all(pair.baseline.key != pair.treatment.key for pair in pairs)
