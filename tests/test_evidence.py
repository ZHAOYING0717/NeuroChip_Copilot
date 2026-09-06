from pathlib import Path

from neurochip.evidence import load_evidence_ladder


ROOT = Path(__file__).resolve().parents[1]


def test_evidence_ladder_is_bounded_and_result_backed():
    rows = load_evidence_ladder(ROOT)
    assert [row["验证层级"].split()[0] for row in rows] == ["1", "2", "3", "4", "5"]
    assert "0.858" in rows[1]["主要结果"]
    assert "0.952" in rows[3]["主要结果"]
    assert "不能支持" in rows[4]
