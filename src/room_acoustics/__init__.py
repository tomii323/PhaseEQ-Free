"""Offline room-response preparation, independent of UI and DSP state.

Experimental: adoption requires per-seat and measured-room validation.
"""
from .averaging import Response, AverageResult, average_responses, smooth_db
from .correction import CorrectionResult, generate_correction

__all__ = ["Response", "AverageResult", "average_responses", "smooth_db",
           "CorrectionResult", "generate_correction"]
