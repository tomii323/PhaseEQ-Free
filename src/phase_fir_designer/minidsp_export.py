"""Format miniDSP Advanced Biquad files without UI or persistence state."""
from __future__ import annotations

from typing import Iterable

from .config import IIRFilter


def export_minidsp_biquads(filters: Iterable[IIRFilter], sample_rate: int, *, extra_sos=()) -> str:
    from .iir import biquad_rows

    lines: list[str] = []
    for row in biquad_rows(filters, sample_rate, extra_sos=extra_sos):
        lines.extend(
            [
                f"biquad{row['section']},",
                f"b0={float(row['b0']):.16g},",
                f"b1={float(row['b1']):.16g},",
                f"b2={float(row['b2']):.16g},",
                f"a1={-float(row['a1']):.16g},",
                f"a2={-float(row['a2']):.16g}",
            ]
        )
    return "\n".join(lines) + ("\n" if lines else "")
