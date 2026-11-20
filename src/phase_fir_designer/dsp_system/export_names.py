"""Shared stable names for DSP export files and filter identifiers."""
from __future__ import annotations

import re

from .output_pipeline import DSPWayOutput


def _slug(value: str, fallback: str) -> str:
    clean = re.sub(r"[^0-9A-Za-z._-]+", "_", str(value).strip()).strip("._-")
    return clean or fallback


def _rate_label(sample_rate: int) -> str:
    rate = int(sample_rate)
    return f"{rate // 1000}k" if rate % 1000 == 0 else f"{rate}Hz"


def _way_stem(way: DSPWayOutput) -> str:
    return "_".join(
        [
            _slug(way.device_name, "DSP"),
            f"CH{way.output_channel + 1:02d}",
            _slug(way.way_name, "Way"),
        ]
    )
