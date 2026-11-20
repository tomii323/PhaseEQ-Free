"""Build DSP System miniDSP coefficient files without UI or package state."""
from __future__ import annotations

from .output_pipeline import DSPWayOutput
from .export_names import _rate_label, _way_stem
from ..iir import export_minidsp_biquads
from .export_codecs import _bin_bytes, _coefficient_text


def build_minidsp_files(ways: list[DSPWayOutput], adapter_root: str, stamp: str) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for way in ways:
        stem = _way_stem(way)
        if way.fir_enabled:
            files[f"{adapter_root}/fir/{stem}_FIR_F32LE_{_rate_label(way.sample_rate)}_{stamp}.bin"] = _bin_bytes(way.coefficients)
            files[f"{adapter_root}/fir/{stem}_FIR_Paste_{_rate_label(way.sample_rate)}_{stamp}.txt"] = _coefficient_text(way.coefficients)
        if way.iir_filters:
            files[f"{adapter_root}/iir/{stem}_IIR_miniDSP_{_rate_label(way.sample_rate)}_{stamp}.txt"] = export_minidsp_biquads(way.iir_filters, way.sample_rate).encode()
    return files
