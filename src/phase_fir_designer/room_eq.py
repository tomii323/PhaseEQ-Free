"""Independent room-target gain delta; never changes source phase or timing."""
from copy import deepcopy
import json

import numpy as np

from .config import SpeakerResponse
from .speaker import load_speaker_response_text
from .response_support import inherit_support


FORMAT = "phaseeq-room-eq"


def normalize_room_eq(value=None):
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ValueError("Room EQ must be an object")
    operation = value.get("operation", "add")
    if operation not in ("add", "subtract"):
        raise ValueError("Room EQ operation must be add or subtract")
    enabled = value.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ValueError("Room EQ enabled must be boolean")
    response = value.get("response")
    if response is not None:
        if not isinstance(response, dict):
            raise ValueError("Room EQ response must be an object")
        f = np.asarray(response.get("frequency", []), dtype=float)
        g = np.asarray(response.get("gain_db", []), dtype=float)
        if (f.ndim != 1 or g.shape != f.shape or len(f) < 2
                or not np.all(np.isfinite(f)) or not np.all(np.isfinite(g))
                or np.any(f <= 0) or np.any(np.diff(f) <= 0)):
            raise ValueError("Room EQ requires finite gain and increasing positive frequencies")
        response = {"frequency": f.tolist(), "gain_db": g.tolist()}
    elif enabled:
        raise ValueError("Room EQ data is required when enabled")
    return {"enabled": enabled, "operation": operation,
            "name": str(value.get("name", "")), "response": response}


def load_room_eq(data: bytes, filename: str):
    text = data.decode("utf-8-sig")
    if filename.lower().endswith(".json"):
        package = json.loads(text)
        if not isinstance(package, dict) or package.get("format") != FORMAT or package.get("format_version") != 1:
            raise ValueError("Unsupported Room EQ file format or version")
        if not isinstance(package.get("room_eq"), dict):
            raise ValueError("Room EQ settings are required")
        return normalize_room_eq(package["room_eq"])
    source = load_speaker_response_text(text)
    return normalize_room_eq({"name": filename, "response": {
        "frequency": source.frequency, "gain_db": source.gain_db}})


def room_eq_bytes(value):
    return json.dumps({"format": FORMAT, "format_version": 1,
                       "room_eq": normalize_room_eq(value)}, ensure_ascii=False, indent=2).encode("utf-8")


def apply_room_eq(target: SpeakerResponse, value=None):
    room = normalize_room_eq(value)
    if not room["enabled"]:
        return target
    curve = room["response"]
    frequency = np.asarray(target.frequency, dtype=float)
    delta = np.zeros_like(frequency)
    positive = frequency > 0
    delta[positive] = np.interp(np.log(frequency[positive]), np.log(curve["frequency"]),
                                curve["gain_db"], left=0., right=0.)
    if room["operation"] == "subtract":
        delta = -delta
    return inherit_support(SpeakerResponse(
        list(target.frequency), (np.asarray(target.gain_db)+delta).tolist(),
        deepcopy(target.phase_deg)), target)
