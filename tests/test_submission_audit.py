from scripts.audit_submission import contains_private_content


def test_private_path_scan_catches_json_escaped_windows_path():
    assert contains_private_content('"model_path": "D:\\\\codex-workspace\\\\NeuroChip_Copilot\\\\models"')


def test_private_path_scan_does_not_reject_relative_repository_path():
    assert not contains_private_content('"model_path": "models/drug_response_model.joblib"')
