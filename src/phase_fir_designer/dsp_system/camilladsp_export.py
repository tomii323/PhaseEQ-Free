"""Build CamillaDSP pipeline YAML from an already finalized DSP System."""
from __future__ import annotations

from collections import Counter

from ..iir import biquad_rows
from .export_names import _slug, _rate_label, _way_stem
from .output_pipeline import DSPSystemOutput, DSPWayOutput


def _unique_filter_stems(items: list[tuple[str, int]], fallback: str) -> dict[str, str]:
    counts = Counter(_slug(identity, fallback) for identity, _channel in items)
    reserved = set(counts)
    result: dict[str, str] = {}
    for identity, channel in items:
        stem = _slug(identity, fallback)
        if counts[stem] > 1:
            stem += f"_ch{channel}"
            while stem in reserved:
                stem += "_"
            reserved.add(stem)
        result[identity] = stem
    return result


def export_camilladsp_yaml(output: DSPSystemOutput, ways: list[DSPWayOutput], dsp_id: str, stamp: str) -> str:
    sample_rate = int(ways[0].sample_rate)
    relevant_routes = [route for route in output.routes if any(way.way_id == route.way_id for way in ways)]
    inputs = {item.id: item for item in output.inputs}
    active_routes = [
        route for route in relevant_routes
        if route.enabled and not route.muted
        and route.input_id in inputs and not inputs[route.input_id].muted
    ]
    bindings = {(item.input_id, item.dsp_id): item.input_channel for item in output.input_bindings}
    input_channels = [channel for (_input_id, device_id), channel in bindings.items() if device_id == dsp_id]
    use_matrix = bool(relevant_routes or output.inputs or output.input_bindings)
    mixer_name = f"phaseeq_input_matrix_{_slug(dsp_id, 'dsp')}"
    lines = ["# PhaseEQ CamillaDSP filter/pipeline snippet"]
    if use_matrix:
        lines.extend([
            "mixers:", f"  {mixer_name}:", "    channels:",
            f"      in: {max(input_channels, default=0) + 1}",
            f"      out: {max(way.output_channel for way in ways) + 1}",
            "    mapping:",
        ])
        for way in ways:
            sources = [route for route in active_routes if route.way_id == way.way_id]
            lines.extend([f"      - dest: {way.output_channel}", "        sources:" if sources else "        sources: []"])
            for route in sources:
                channel = bindings.get((route.input_id, dsp_id))
                if channel is None:
                    raise ValueError(f"CamillaDSP Routing export is missing an input binding for {route.input_id}")
                lines.extend([
                    f"          - channel: {channel}",
                    f"            gain: {float(route.gain_db) + float(inputs.get(route.input_id).gain_db if inputs.get(route.input_id) else 0.0):.16g}",
                    f"            inverted: {'true' if bool(inputs.get(route.input_id).polarity_invert if inputs.get(route.input_id) else False) else 'false'}",
                ])
    lines.append("filters:")
    input_stems = _unique_filter_stems([
        (item.id, bindings[(item.id, dsp_id)]) for item in output.inputs if (item.id, dsp_id) in bindings
    ], "input")
    way_stems = _unique_filter_stems([(way.way_id, way.output_channel) for way in ways], "way")
    input_chains: list[tuple[int, list[str]]] = []
    for input_item in output.inputs:
        channel = bindings.get((input_item.id, dsp_id))
        filters = tuple(item for item in input_item.iir_filters if item.enabled)
        if channel is None or not filters or input_item.muted:
            continue
        input_chain: list[str] = []
        input_name = f"phaseeq_input_{input_stems[input_item.id]}"
        for row in biquad_rows(filters, sample_rate):
            iir_name = f"{input_name}_iir_{row['section']}"
            input_chain.append(iir_name)
            lines.extend([
                f"  {iir_name}:", "    type: DiffEq", "    parameters:",
                f"      a: [1.0, {float(row['a1']):.16g}, {float(row['a2']):.16g}]",
                f"      b: [{float(row['b0']):.16g}, {float(row['b1']):.16g}, {float(row['b2']):.16g}]",
            ])
        input_chains.append((channel, input_chain))
    names: list[tuple[DSPWayOutput, list[str]]] = []
    for way in ways:
        name = f"phaseeq_{way_stems[way.way_id]}"
        chain: list[str] = []
        for row in biquad_rows(way.iir_filters, way.sample_rate):
            iir_name = f"{name}_iir_{row['section']}"
            chain.append(iir_name)
            lines.extend([
                f"  {iir_name}:", "    type: DiffEq", "    parameters:",
                f"      a: [1.0, {float(row['a1']):.16g}, {float(row['a2']):.16g}]",
                f"      b: [{float(row['b0']):.16g}, {float(row['b1']):.16g}, {float(row['b2']):.16g}]",
            ])
        if way.fir_enabled:
            chain.append(name)
            lines.extend([
                f"  {name}:", "    type: Conv", "    parameters:", "      type: Wav",
                f"      filename: fir/{_way_stem(way)}_FIR_{_rate_label(way.sample_rate)}_{stamp}.wav",
                "      channel: 0",
            ])
        output_gain_db = float(way.way_gain_db) + float(output.common_auto_gain_db)
        if abs(output_gain_db) > 1e-12 or way.polarity_invert:
            gain_name = f"{name}_output_gain"
            chain.append(gain_name)
            lines.extend([
                f"  {gain_name}:", "    type: Gain", "    parameters:",
                f"      gain: {output_gain_db:.16g}",
                f"      inverted: {'true' if way.polarity_invert else 'false'}",
                "      mute: false", "      scale: dB",
            ])
        if float(way.delay_ms) > 1e-12:
            delay_name = f"{name}_output_delay"
            chain.append(delay_name)
            lines.extend([
                f"  {delay_name}:", "    type: Delay", "    parameters:",
                f"      delay: {float(way.delay_ms):.16g}",
                "      unit: ms", "      subsample: false",
            ])
        if chain:
            names.append((way, chain))
    lines.append("pipeline:")
    for channel, chain in input_chains:
        lines.extend([
            "  - type: Filter",
            f"    channels: [{channel}]",
            f"    names: [{', '.join(chain)}]",
        ])
    if use_matrix:
        lines.extend(["  - type: Mixer", f"    name: {mixer_name}"])
    for way, chain in names:
        lines.extend(["  - type: Filter", f"    channels: [{way.output_channel}]", f"    names: [{', '.join(chain)}]"])
    return "\n".join(lines) + "\n"
