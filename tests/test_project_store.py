from __future__ import annotations

import json

from neurochip.project_store import ProjectStore


def test_project_store_registers_samples_and_analysis(tmp_path):
    source = tmp_path / "sample.csv"
    source.write_text("channel,time_s\nA,0.1\n", encoding="utf-8")
    store = ProjectStore(tmp_path / "projects.sqlite3")
    project_id = store.create_project("Drug screening 2026", "pilot")
    sample_id = store.add_sample(project_id, "Organoid001", source, "control", {"batch": "B1"})
    store.record_analysis(sample_id, {"quality_score": 95.0})
    projects = store.list_projects()
    samples = store.list_samples(project_id)
    assert projects.loc[0, "name"] == "Drug screening 2026"
    assert samples.loc[0, "sample_name"] == "Organoid001"
    assert json.loads(samples.loc[0, "latest_analysis_json"])["quality_score"] == 95.0
