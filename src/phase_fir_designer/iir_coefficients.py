"""Validate immutable, sample-rate-bound biquad coefficients without UI state."""
from __future__ import annotations

import math
import numpy as np


def normalized_biquad(values) -> tuple[float, ...]:
    if not isinstance(values, (tuple, list)) or len(values) != 6:
        raise ValueError("Biquad: six SOS coefficients required")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in values):
        raise ValueError("Biquad: finite numeric coefficients required")
    try:
        b0, b1, b2, a0, a1, a2 = map(float, values)
    except OverflowError as exc:
        raise ValueError("Biquad: finite numeric coefficients required") from exc
    if not all(math.isfinite(v) for v in (b0, b1, b2, a0, a1, a2)):
        raise ValueError("Biquad: finite numeric coefficients required")
    if a0 == 0:
        raise ValueError("Biquad: a0 must not be zero")
    row = tuple(v / a0 for v in (b0, b1, b2, a0, a1, a2))
    if not all(math.isfinite(v) for v in row):
        raise ValueError("Biquad: normalization overflow")
    if np.any(np.abs(np.roots([1.0, row[4], row[5]])) >= 1.0):
        raise ValueError("Biquad: poles must be strictly inside the unit circle")
    return row


def coefficient_sos(values, stored_rate: int, sample_rate: int) -> np.ndarray:
    if type(stored_rate) is not int or stored_rate < 4:
        raise ValueError("Biquad: valid coefficient sample rate required")
    if stored_rate != sample_rate:
        raise ValueError(f"Biquad: coefficients require {stored_rate} Hz; disable or re-import at the source rate")
    return np.asarray([normalized_biquad(values)], dtype=float)


def camilladsp_coefficient_row(definition: dict) -> tuple[float, ...]:
    parameters = definition.get("parameters")
    if not isinstance(parameters, dict):
        raise ValueError("CamillaDSP: coefficient parameters required")
    if definition.get("type") == "DiffEq":
        if set(parameters) - {"a", "b"}:
            raise ValueError("CamillaDSP DiffEq: only a/b coefficients supported")
        vectors = []
        for key in ("b", "a"):
            vector = parameters.get(key, [1.0])
            if not isinstance(vector, list) or not 1 <= len(vector) <= 3:
                raise ValueError("CamillaDSP DiffEq: only orders 0–2 supported per section")
            vectors.extend(vector + [0.0] * (3 - len(vector)))
        return normalized_biquad(vectors)
    if definition.get("type") == "Biquad" and parameters.get("type") == "Free":
        fields = {"type", "b0", "b1", "b2", "a1", "a2"}
        if set(parameters) != fields:
            raise ValueError("CamillaDSP Free: b0/b1/b2/a1/a2 required")
        return normalized_biquad([parameters["b0"], parameters["b1"], parameters["b2"], 1.0,
                                 parameters["a1"], parameters["a2"]])
    raise ValueError("CamillaDSP: unsupported coefficient definition")
