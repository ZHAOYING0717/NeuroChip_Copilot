from pathlib import Path

import pytest

from scripts.build_drug_features import parse_condition


@pytest.mark.parametrize(
    ("name", "dose", "organoid"),
    [
        ("control_2950.mat", 0.0, "2950"),
        ("diazepam3uM_2953.mat", 3.0, "2953"),
        ("diazepam50uM_2957.mat", 50.0, "2957"),
    ],
)
def test_parse_condition(name, dose, organoid):
    assert parse_condition(Path(name)) == (dose, organoid)

