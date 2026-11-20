"""Encode DSP coefficient payloads without routing or UI dependencies."""
from __future__ import annotations

import io
import numpy as np

from ..export import export_bin, export_wav


def _wav_bytes(coefficients: np.ndarray, sample_rate: int) -> bytes:
    output = io.BytesIO()
    export_wav(output, np.asarray(coefficients, dtype=float), int(sample_rate))
    return output.getvalue()


def _bin_bytes(coefficients: np.ndarray) -> bytes:
    output = io.BytesIO()
    export_bin(output, np.asarray(coefficients, dtype=float))
    return output.getvalue()


def _coefficient_text(coefficients: np.ndarray) -> bytes:
    return ("\n".join(f"{float(value):.16g}" for value in coefficients) + "\n").encode()
