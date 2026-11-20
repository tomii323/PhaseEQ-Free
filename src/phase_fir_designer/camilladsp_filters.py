"""CamillaDSP parameter import and coefficient export, independent of UI state."""
from __future__ import annotations

from dataclasses import replace
import math
from typing import Iterable

import yaml

from .config import IIRFilter
from .rew_filters import import_rew_filters


class _FilterLoader(yaml.SafeLoader):
    """Reject aliases and duplicate keys rather than changing filter meaning."""

    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            raise ValueError("CamillaDSP: YAML aliases are not supported")
        return super().compose_node(parent, index)

    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise ValueError("CamillaDSP: string keys must be unique")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def _mapping(value, allowed: set[str]) -> dict:
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError(f"CamillaDSP: expected fields {', '.join(sorted(allowed))}")
    return value


def _number(parameters: dict, key: str) -> float:
    value = parameters.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"CamillaDSP: finite numeric {key} required")
    return float(value)


def _convert(definition: dict, sample_rate: int) -> IIRFilter:
    definition = _mapping(definition, {"type", "parameters"})
    parameters = definition.get("parameters")
    if not isinstance(parameters, dict):
        raise ValueError("CamillaDSP: parameters required")
    kind = parameters.get("type")
    fc = _number(parameters, "freq")
    if definition.get("type") == "BiquadCombo":
        combos = {"ButterworthHighpass": ("high_pass", "butterworth"),
                  "ButterworthLowpass": ("low_pass", "butterworth"),
                  "LinkwitzRileyHighpass": ("high_pass", "linkwitz_riley"),
                  "LinkwitzRileyLowpass": ("low_pass", "linkwitz_riley")}
        if not isinstance(kind, str) or kind not in combos:
            raise ValueError(f"CamillaDSP: unsupported BiquadCombo {kind}")
        _mapping(parameters, {"type", "freq", "order"})
        order = parameters.get("order")
        target, family = combos[kind]
        orders = (2, 4, 6, 8) if family == "linkwitz_riley" else (1, 2, 3, 4, 6, 8)
        if type(order) is not int or order not in orders:
            raise ValueError(f"CamillaDSP: supported orders {orders}")
        base = import_rew_filters(f"Filter 1: ON HP1 Fc {fc} Hz", sample_rate)[0]
        return replace(base, kind=target, family=family, order=order)
    codes = {"Peaking": "PK", "Lowshelf": "LS Q", "Highshelf": "HS Q",
             "Highpass": "HP Q", "Lowpass": "LP Q", "HighpassFO": "HP1",
             "LowpassFO": "LP1", "Allpass": "AP", "AllpassFO": "AP"}
    if definition.get("type") != "Biquad" or not isinstance(kind, str) or kind not in codes:
        raise ValueError(f"CamillaDSP: unsupported filter {definition.get('type')}/{kind}")
    fields = {"type", "freq"}
    row = f"Filter 1: ON {codes[kind]} Fc {fc} Hz"
    if kind in {"Peaking", "Lowshelf", "Highshelf"}:
        fields.add("gain")
        row += f" Gain {_number(parameters, 'gain')} dB"
    if not kind.endswith("FO"):
        fields.add("q")
        row += f" Q {_number(parameters, 'q')}"
    elif kind == "AllpassFO":
        row += " Q 0.7"
    _mapping(parameters, fields)
    item = import_rew_filters(row, sample_rate)[0]
    # CamillaDSP AllpassFO has DC +1 and Nyquist -1, matching manual AP1.
    return replace(item, order=1) if kind == "AllpassFO" else item


def import_camilladsp_filters(text: str, sample_rate: int) -> list[IIRFilter]:
    """Validate the whole file before returning filters in pipeline order.

    Device/routing configurations are deliberately excluded: a PhaseEQ IIR
    list represents one channel, not a CamillaDSP processing graph.
    """
    if len(text) > 1_048_576:
        raise ValueError("CamillaDSP: file exceeds 1 MiB")
    try:
        data = yaml.load(text.lstrip('\ufeff'), Loader=_FilterLoader)
    except (yaml.YAMLError, RecursionError) as exc:
        raise ValueError("CamillaDSP: invalid YAML") from exc
    data = _mapping(data, {"filters", "pipeline"})
    definitions = data.get("filters")
    if not isinstance(definitions, dict) or not definitions or len(definitions) > 128:
        raise ValueError("CamillaDSP: 1–128 filter definitions required")
    names = list(definitions)
    if "pipeline" in data:
        pipeline = data["pipeline"]
        if not isinstance(pipeline, list) or len(pipeline) != 1:
            raise ValueError("CamillaDSP: one Filter pipeline step required")
        step = _mapping(pipeline[0], {"type", "channel", "channels", "names"})
        if step.get("type") != "Filter" or ("channel" in step) == ("channels" in step):
            raise ValueError("CamillaDSP: one Filter channel required")
        channels = [step["channel"]] if "channel" in step else step["channels"]
        if not isinstance(channels, list) or len(channels) != 1 or type(channels[0]) is not int or channels[0] < 0:
            raise ValueError("CamillaDSP: one non-negative channel required")
        names = step.get("names")
        if not isinstance(names, list) or not names or len(names) > 128 or any(not isinstance(n, str) for n in names):
            raise ValueError("CamillaDSP: pipeline filter names required")
        if len(set(names)) != len(names) or set(names) != set(definitions):
            raise ValueError("CamillaDSP: each filter must occur once in pipeline")
    result = []
    for name in names:
        try:
            result.append(_convert(definitions[name], sample_rate))
        except ValueError as exc:
            raise ValueError(f"{name}: {exc}") from exc
    return result


def export_camilladsp_biquads(filters: Iterable[IIRFilter], sample_rate: int, *, extra_sos=()) -> str:
    """Return CamillaDSP filter definitions using normalized DiffEq sections."""
    from .iir import biquad_rows

    lines = ["# PhaseEQ CamillaDSP IIR filter snippet", "filters:"]
    names: list[str] = []
    for row in biquad_rows(filters, sample_rate, extra_sos=extra_sos):
        name = f"phaseeq_iir_{int(row['section'])}"
        names.append(name)
        lines.extend(
            [
                f"  {name}:",
                "    type: DiffEq",
                "    parameters:",
                f"      a: [1.0, {float(row['a1']):.16g}, {float(row['a2']):.16g}]",
                f"      b: [{float(row['b0']):.16g}, {float(row['b1']):.16g}, {float(row['b2']):.16g}]",
            ]
        )
    lines.extend(["# Apply in this order:", f"# names: [{', '.join(names)}]"])
    return "\n".join(lines) + "\n"
