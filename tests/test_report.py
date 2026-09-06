from __future__ import annotations

from io import BytesIO

import numpy as np
import pandas as pd
from pypdf import PdfReader

from neurochip.features import extract_features
from neurochip.qc import assess_event_quality
from neurochip.report import build_pdf_report
from neurochip.schema import SpikeRecording


def test_pdf_report_contains_expected_sections():
    base = np.arange(0.1, 10.0, 0.25)
    recording = SpikeRecording("pdf-sample", [base, base + 0.003], 10.0)
    features = extract_features(recording)
    quality, _ = assess_event_quality(recording)
    explanation = pd.DataFrame(
        {"feature": ["firing_rate_mean_hz"], "anomaly_shap_value": [0.01], "scaled_value": [0.5]}
    )
    payload = build_pdf_report(recording, features, quality, explanation=explanation)
    assert payload.startswith(b"%PDF")
    text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(payload)).pages)
    assert "Recording and quality control" in text
    assert "Interpretation boundary" in text

