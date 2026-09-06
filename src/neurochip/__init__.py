"""NeuroChip Copilot analysis package."""

from .features import extract_features
from .functional_effect import FunctionalEffectEvaluation, evaluate_functional_effect
from .drug_response import DrugResponseModel, fit_drug_response_model
from .evidence import load_evidence_ladder
from .io import read_recording
from .qc import assess_event_quality, assess_raw_voltage_quality, recording_stability
from .schema import SpikeRecording
from .standard import convert_axion_csv, recording_to_event_table
from .trujillo import read_trujillo_well

__all__ = [
    "DrugResponseModel",
    "FunctionalEffectEvaluation",
    "SpikeRecording",
    "assess_event_quality",
    "assess_raw_voltage_quality",
    "extract_features",
    "evaluate_functional_effect",
    "fit_drug_response_model",
    "load_evidence_ladder",
    "read_recording",
    "recording_stability",
    "convert_axion_csv",
    "recording_to_event_table",
    "read_trujillo_well",
]
__version__ = "0.4.0"
