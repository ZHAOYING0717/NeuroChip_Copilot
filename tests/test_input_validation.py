from pathlib import Path

from neurochip.input_validation import validate_input_file


def test_csv_preflight_accepts_aliases_and_reports_summary(tmp_path: Path):
    source = tmp_path / "events.csv"
    source.write_text("channel,time_s,duration_s,well\nA,0.1,2,A1\nB,0.2,2,A1\n", encoding="utf-8")

    result = validate_input_file(source)

    assert result.valid
    assert result.summary["events"] == 2
    assert result.summary["channels"] == 2
    assert result.summary["wells"] == 1


def test_csv_preflight_blocks_invalid_time_values(tmp_path: Path):
    source = tmp_path / "invalid.csv"
    source.write_text("timestamp_s,channel_id\nnot-a-time,A\n-1,B\n", encoding="utf-8")

    result = validate_input_file(source)

    assert not result.valid
    assert any("时间" in error for error in result.errors)


def test_csv_preflight_warns_about_multiple_wells(tmp_path: Path):
    source = tmp_path / "multiwell.csv"
    source.write_text(
        "recording_id,timestamp_s,channel_id,well_id\n"
        "sample,0.1,A,A1\n"
        "sample,0.2,B,B1\n",
        encoding="utf-8",
    )

    result = validate_input_file(source)

    assert result.valid
    assert any("多个孔位" in warning for warning in result.warnings)
