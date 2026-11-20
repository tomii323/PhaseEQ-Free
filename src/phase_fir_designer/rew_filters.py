"""REW Generic text conversion, independent of UI, files and session state."""
from __future__ import annotations

from dataclasses import dataclass, replace
import csv
import io
import math
import re
from typing import Iterable

import numpy as np
from scipy import signal

from .config import IIRFilter, quantize_iir_q


_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_ROW = re.compile(r"Filter\s+(\d+)\s*:\s*(ON|OFF)\s+(.+)", re.I)
_BODY = re.compile(
    rf"(PK|LS\s*Q|HS\s*Q|LS|HS|HP\s*Q|LP\s*Q|HP1|LP1|HP|LP|AP|All\s+pass)"
    rf"\s+Fc\s+({_NUMBER})\s*Hz(?:\s+Gain\s+({_NUMBER})\s*dB)?"
    rf"(?:\s+Q\s+({_NUMBER}))?", re.I,
)
_KINDS = {"PK": "peq", "LS": "low_shelf", "LSQ": "low_shelf",
          "HS": "high_shelf", "HSQ": "high_shelf", "AP": "allpass",
          "HP": "high_pass", "HP1": "high_pass", "HPQ": "high_pass",
          "LP": "low_pass", "LP1": "low_pass", "LPQ": "low_pass"}


def _validate(item: IIRFilter, sample_rate: int | None = None) -> None:
    if not all(math.isfinite(v) for v in (item.fc, item.q, item.gain_db)) or item.fc <= 0 or item.q <= 0:
        raise ValueError("REW: finite Fc/Gain/Q and positive Fc/Q required")
    if sample_rate is not None and not 1 <= item.fc <= sample_rate / 2 - 1:
        raise ValueError(f"REW: Fc 1–{sample_rate / 2 - 1:g} Hz")


def import_rew_filters(text: str, sample_rate: int) -> list[IIRFilter]:
    """Validate the entire file, then return manual IIR items for preview."""
    if not math.isfinite(sample_rate) or sample_rate < 4:
        raise ValueError("REW: invalid sample rate")
    result: list[IIRFilter] = []
    seen: set[int] = set()
    for line_number, raw in enumerate(text.lstrip('\ufeff').splitlines(), 1):
        line = raw.strip()
        if line.lower().startswith("equaliser:") and line.split(':', 1)[1].strip().lower() != "generic":
            raise ValueError("REW Equaliser: Generic")
        if not re.match(r"Filter\b", line, re.I) or line.lower() == "filter settings file":
            continue
        row = _ROW.fullmatch(line)
        if row is None or int(row[1]) < 1:
            raise ValueError(f"Line {line_number}: invalid Filter row")
        index, state, body = row.groups()
        # Separate unused crossover slots repeat the regular filter numbers.
        if body.lower() == "none":
            continue
        match = _BODY.fullmatch(body)
        if match is None:
            raise ValueError(f"Line {line_number}: unsupported REW filter: {body}")
        if int(index) in seen:
            raise ValueError(f"Line {line_number}: duplicate Filter {index}")
        seen.add(int(index))
        code, fc, gain, q = match.groups()
        code = re.sub(r"\s+", "", code).upper().replace("ALLPASS", "AP")
        needs_gain = code in {"PK", "LS", "HS", "LSQ", "HSQ"}
        needs_q = code in {"PK", "LSQ", "HSQ", "HPQ", "LPQ", "AP"}
        if (gain is not None) != needs_gain or (q is not None) != needs_q:
            raise ValueError(f"Line {line_number}: invalid Gain/Q fields for {code}")
        kind = _KINDS[code]
        q_value = float(q) if q is not None else math.sqrt(0.5)
        q_max = 5 if kind == "peq" else 1 if "shelf" in kind else 100
        q_min = 0.01 if code in {"HPQ", "LPQ"} else 0.1
        if not q_min <= q_value <= q_max:
            raise ValueError(f"Line {line_number}: Q {q_min:g}–{q_max:g}")
        gain_value = float(gain) if gain is not None else 0.
        if not -30 <= gain_value <= 20:
            raise ValueError(f"Line {line_number}: Gain -30–20 dB")
        item = IIRFilter(kind=kind, fc=float(fc), gain_db=gain_value,
                         q=q_value if kind in {"high_pass", "low_pass"} else quantize_iir_q(kind, q_value),
                         family="variable_q" if code in {"HPQ", "LPQ"} else "butterworth",
                         order=1 if code in {"HP1", "LP1"} else 2,
                         enabled=state.upper() == "ON", origin="manual")
        _validate(item, sample_rate)
        result.append(item)
    if not result:
        raise ValueError("REW Generic: no supported IIR filters")
    return result


def _sections(item: IIRFilter, sample_rate: int | None) -> list[IIRFilter]:
    """Expand compound prototypes through the existing coefficient owner."""
    if item.kind == "biquad":
        raise ValueError("Biquad係数はREWパラメータ形式の対象外です。Biquad出力を使用してください。")
    if item.kind not in {"high_pass", "low_pass", "allpass"}:
        return [item]
    if item.kind == "allpass":
        if item.allpass_preset in {"lr2_lo", "lr2_hi"} or (item.allpass_preset == "manual" and item.order != 2):
            raise ValueError("1次All PassはREW Generic形式の対象外です。Biquad出力を使用してください。")
        if item.allpass_preset == "manual":
            return [item]
    if item.kind != "allpass" and item.family == "variable_q":
        if item.order != 2:
            raise ValueError("REW: Variable-Q HP/LP requires order 2")
        return [item]
    if item.kind != "allpass" and item.family == "butterworth" and item.order in {1, 2}:
        return [replace(item, q=math.sqrt(0.5))]
    if sample_rate is None:
        raise ValueError("REW: sample rate required for compound filters")
    if item.kind != "allpass" and item.family not in {"butterworth", "bessel", "linkwitz_riley"}:
        raise ValueError(f"{item.family}のHP／LPはREW形式の対象外です。Biquad出力を使用してください。")
    from .iir import design_iir_sos
    original = design_iir_sos(replace(item, enabled=True), sample_rate)
    sections = []
    for sos in original:
        _, poles, _ = signal.sos2zpk(sos[None, :])
        # SciPy pads odd-order sections with a pole at zero.
        poles = poles[np.abs(poles) > 1e-12]
        analog = 2 * sample_rate * (poles - 1) / (poles + 1)
        if len(analog) == 1:
            order, omega, q = 1, -analog[0].real, math.sqrt(0.5)
        else:
            order = 2
            omega = float(np.sqrt(np.prod(analog).real))
            q = float(omega / -np.sum(analog).real)
        sections.append(replace(item, fc=float(sample_rate / np.pi * np.arctan(omega / (2 * sample_rate))),
                                q=q, order=order, family="butterworth" if order == 1 else "variable_q",
                                allpass_preset="manual"))
    # A representable denominator alone is insufficient: check the full response.
    probe = np.geomspace(1, sample_rate / 2 - 1, 256)
    rebuilt = np.vstack([design_iir_sos(replace(s, enabled=True), sample_rate) for s in sections])
    if not np.allclose(signal.sosfreqz(original, worN=probe, fs=sample_rate)[1],
                       signal.sosfreqz(rebuilt, worN=probe, fs=sample_rate)[1], rtol=1e-7, atol=1e-8):
        raise ValueError("REWの段構成で応答を保持できません。Biquad出力を使用してください。")
    return sections


def export_rew_filters(filters: Iterable[IIRFilter], sample_rate: int | None = None) -> str:
    """Serialize all items or raise; never silently drop unsupported items."""
    lines = ["Filter Settings file", "", "Notes: PhaseEQ IIR filters", "", "Equaliser: Generic", ""]
    index = 0
    for item in filters:
        _validate(item, sample_rate)
        for section in _sections(item, sample_rate):
            _validate(section, sample_rate)
            kind = section.kind
            if kind in {"peq", "low_shelf", "high_shelf"}:
                code = {"peq": "PK", "low_shelf": "LS Q", "high_shelf": "HS Q"}[kind]
            elif kind in {"high_pass", "low_pass"}:
                code = ("HP" if kind == "high_pass" else "LP") + ("1" if section.order == 1 else " Q")
            elif kind == "allpass" and section.order == 2:
                code = "All pass"
            else:
                raise ValueError(f"REW: unsupported filter {kind}/{section.order}")
            index += 1
            row = f"Filter {index}: {'ON' if section.enabled else 'OFF'} {code} Fc {_number(section.fc)} Hz"
            if kind in {"peq", "low_shelf", "high_shelf"}:
                row += f" Gain {_number(section.gain_db)} dB"
            if code not in {"HP1", "LP1"}:
                row += f" Q {_number(section.q)}"
            lines.append(row)
    return '\n'.join(lines) + '\n'


def _number(value: float) -> str:
    return f"{float(value):.10f}".rstrip('0').rstrip('.')


@dataclass(frozen=True)
class RewExportEntry:
    source_index: int
    item: IIRFilter
    filter_numbers: tuple[int, ...]
    error: str = ""


@dataclass(frozen=True)
class RewExportResult:
    text: str
    entries: tuple[RewExportEntry, ...]

    @property
    def exported_count(self) -> int:
        return sum(not entry.error for entry in self.entries)

    @property
    def section_count(self) -> int:
        return sum(len(entry.filter_numbers) for entry in self.entries)


def build_rew_export(filters: Iterable[IIRFilter], sample_rate: int) -> RewExportResult:
    """Export each complete source item atomically and retain every outcome."""
    lines = export_rew_filters([], sample_rate).splitlines()
    entries = []
    next_number = 1
    for index, item in enumerate(filters, 1):
        try:
            text = export_rew_filters([item], sample_rate)
        except ValueError as exc:
            entries.append(RewExportEntry(index, item, (), str(exc)))
            continue
        rows = [line for line in text.splitlines() if _ROW.fullmatch(line)]
        numbers = tuple(range(next_number, next_number + len(rows)))
        for number, row in zip(numbers, rows):
            lines.append(re.sub(r"^Filter\s+\d+:", f"Filter {number}:", row))
        entries.append(RewExportEntry(index, item, numbers))
        next_number += len(rows)
    return RewExportResult('\n'.join(lines) + '\n', tuple(entries))


def export_rew_result_csv(result: RewExportResult) -> str:
    """Return a separate, spreadsheet-readable ledger, including errors."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator='\n')
    writer.writerow(['元IIR番号', '種類', 'ON/OFF', '周波数Hz', 'ゲインdB', 'Q',
                     'Family', '次数', 'All Pass preset', '結果', '出力Filter番号', 'エラー'])
    labels = {'peq': 'PEQ', 'low_shelf': 'Low Shelf', 'high_shelf': 'High Shelf',
              'high_pass': 'HP', 'low_pass': 'LP', 'allpass': 'All Pass', 'biquad': 'Biquad係数'}
    for entry in result.entries:
        item = entry.item
        writer.writerow([entry.source_index, labels.get(item.kind, item.kind),
                         'ON' if item.enabled else 'OFF',
                         *([''] * 6 if item.kind == 'biquad' else
                           [item.fc, item.gain_db, item.q, item.family, item.order, item.allpass_preset]),
                         'エラー・出力対象外' if entry.error else '出力',
                         ';'.join(map(str, entry.filter_numbers)), entry.error])
    return '\ufeff' + output.getvalue()


def import_rew_peq(text: str, sample_rate: int) -> list[IIRFilter]:
    """Keep the original PEQ-only API for existing callers."""
    items = import_rew_filters(text, sample_rate)
    if any(item.kind != "peq" for item in items):
        raise ValueError("REW PEQ import accepts peaking filters only")
    return items


def export_rew_peq(filters: Iterable[IIRFilter]) -> str:
    """Keep the original PEQ-only API for existing callers."""
    items = list(filters)
    if any(item.kind != "peq" for item in items):
        raise ValueError("REW PEQ export accepts peaking filters only")
    return export_rew_filters(items)
