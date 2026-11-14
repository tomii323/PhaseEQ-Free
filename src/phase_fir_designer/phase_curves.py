from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
from response_math import interpolate_values, interpolate_phase

from .auto_eq import (
    apply_auto_edge_smooth as _apply_auto_edge_smooth,
    apply_auto_edge_smooth_octave as _apply_auto_edge_smooth_octave,
    auto_boundary_oct as _auto_boundary_oct,
    auto_effective_range as _auto_effective_range,
    auto_eq_sections as _auto_eq_sections,
    auto_gain_eq_sections as _auto_gain_eq_sections,
    auto_phase_eq_sections as _auto_phase_eq_sections,
    auto_section_edge_taper_oct as _auto_section_edge_taper_oct,
    combine_auto_eq_sections as _combine_auto_eq_sections,
    nearest_equivalent_phase as _nearest_equivalent_phase,
    boundary_smootherstep_weight as _boundary_smootherstep_weight,
)
from .config import (
    AutoEQSection,
    DesignConfig,
    GainLinearFilter,
    GainPEQ,
    GainShelf,
    GainTilt,
    PhaseAllPass,
    PhasePEQ,
    PhaseShelf,
    PhaseTilt,
)
from .correction_planner import (
    GainCorrectionPlan,
    PhaseCorrectionPlan,
    replace_gain_correction_values,
    replace_phase_correction_values,
)
from .linear_fir_eq_mask import apply_linear_fir_eq_mask as _apply_linear_fir_eq_mask
from .linear_fir_eq_mask import linear_fir_eq_mask as _linear_fir_eq_mask
from .fir_input import FIRInputTransfer, fir_input_transfer
from .response_axis import finite_unwrapped_phase_samples
from .edition import require_fir_auto_eq_for, require_pro_auto_eq

AUTO_EQ_EDGE_TAPER_WITH_LINEAR_FIR_MASK_STRENGTH = 0.5


@dataclass
class _AxisResponseCache:
    """Shared response projections for one config and frequency axis."""

    fir_input: FIRInputTransfer | None = None
    speaker_complex: dict[str, np.ndarray] = field(default_factory=dict)
    speaker_phase: dict[str, np.ndarray] = field(default_factory=dict)
    target_gain: np.ndarray | None = None
    target_phase: np.ndarray | None = None


def frequency_axis(sample_rate: int, taps: int) -> np.ndarray:
    return np.fft.rfftfreq(taps, d=1.0 / sample_rate)


def multiway_kaiser_taps(sample_rate: float, fc: float, cycles: float) -> int:
    """Return the APPY Multiway FIR Studio compatible Kaiser tap count."""
    estimate = int(np.floor(float(sample_rate) / max(float(fc), 1.0) * float(cycles)))
    taps = estimate + 1 + (estimate % 2)
    return max(3, int(taps))


def multiway_clip_cutoff_hz(fc: float, sample_rate: float) -> float:
    """Clip FIR cutoff like APPY Multiway FIR Studio."""
    nyquist = float(sample_rate) / 2.0
    return float(min(max(float(fc), 1.0), nyquist - 1.0))


def wrapped_phase_deg(phase_deg: np.ndarray) -> np.ndarray:
    return (phase_deg + 180.0) % 360.0 - 180.0


def phase_error_deg(
    target_unwrapped: np.ndarray,
    realized_unwrapped: np.ndarray,
    reference_gain_db: np.ndarray | None = None,
) -> np.ndarray:
    target = np.asarray(target_unwrapped, dtype=float)
    realized = np.asarray(realized_unwrapped, dtype=float)
    error = realized - target
    centered = error - 360.0 * np.round(error / 360.0)
    reference = _phase_error_zero_reference_deg(centered, reference_gain_db)
    if reference == 0.0:
        return centered
    return (centered - reference) - 360.0 * np.round((centered - reference) / 360.0)


def _phase_error_zero_reference_deg(
    phase_error: np.ndarray,
    reference_gain_db: np.ndarray | None,
) -> float:
    if reference_gain_db is None:
        return 0.0
    phase = np.asarray(phase_error, dtype=float).ravel()
    gain = np.asarray(reference_gain_db, dtype=float).ravel()
    length = min(phase.size, gain.size)
    if length <= 0:
        return 0.0
    phase = phase[:length]
    gain = gain[:length]
    finite = np.isfinite(phase) & np.isfinite(gain)
    if not np.any(finite):
        return 0.0
    finite_gain = gain[finite]
    max_gain = float(np.nanmax(finite_gain))
    passband = finite & (gain >= max_gain - 6.0)
    if not np.any(passband):
        passband = finite
    candidates = np.flatnonzero(passband)
    if candidates.size == 0:
        return 0.0
    anchor_idx = int(candidates[np.nanargmin(np.abs(phase[candidates]))])
    reference = float(phase[anchor_idx])
    if not np.isfinite(reference) or abs(reference) >= 90.0:
        return 0.0
    return reference


def smootherstep_weight(t: np.ndarray | float) -> np.ndarray:
    values = np.clip(np.asarray(t, dtype=float), 0.0, 1.0)
    return values * values * values * (values * (values * 6.0 - 15.0) + 10.0)


def build_target_curves(config: DesignConfig, frequency: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Build target gain and phase while sharing axis projections and IIR response."""

    require_fir_auto_eq_for(config)
    response_cache = _AxisResponseCache()
    gain = build_target_gain_db(config, frequency, _response_cache=response_cache)
    phase = build_target_phase_deg(config, frequency, _response_cache=response_cache)
    return gain, phase


def build_target_phase_deg(
    config: DesignConfig,
    frequency: np.ndarray,
    *,
    _response_cache: _AxisResponseCache | None = None,
) -> np.ndarray:
    response_cache = _response_cache or _AxisResponseCache()
    base_phase = _direct_target_phase_for_correction(config, frequency, response_cache=response_cache)
    manual_phase = manual_phase_eq_deg(
        config,
        frequency,
        apply_linear_fir_mask=True,
    )
    gain_phase = auto_gain_phase_eq_deg(config, frequency, apply_linear_fir_mask=True)
    auto_phase = auto_phase_eq_deg(
        config,
        frequency,
        manual_phase_deg=base_phase + manual_phase + gain_phase,
        apply_linear_fir_mask=True,
        _response_cache=response_cache,
    )
    return base_phase + manual_phase + gain_phase + auto_phase


def manual_phase_eq_deg(
    config: DesignConfig,
    frequency: np.ndarray,
    *,
    apply_linear_fir_mask: bool = False,
) -> np.ndarray:
    phase = np.zeros_like(frequency, dtype=float)
    from .gain_crossover import gain_crossover_response
    for item in config.gain_linear_filters:
        if item.enabled:
            response = gain_crossover_response(frequency, item, config.sample_rate)
            phase += _maybe_apply_linear_fir_eq_mask(
                config, frequency, np.rad2deg(np.unwrap(np.angle(response))),
                mode="gain", enabled=apply_linear_fir_mask,
            )
    for item in config.peq_filters:
        if item.enabled:
            phase += _maybe_apply_linear_fir_eq_mask(
                config,
                frequency,
                peq_phase_deg(frequency, item),
                mode="phase",
                enabled=apply_linear_fir_mask,
            )
    for item in config.shelf_filters:
        if item.enabled:
            phase += _maybe_apply_linear_fir_eq_mask(
                config,
                frequency,
                shelf_phase_deg(frequency, item),
                mode="phase",
                enabled=apply_linear_fir_mask,
            )
    phase += _total_phase_tilt_deg(
        config,
        frequency,
        apply_linear_fir_mask=apply_linear_fir_mask,
    )
    for item in config.allpass_filters:
        if item.enabled:
            phase += _maybe_apply_linear_fir_eq_mask(
                config,
                frequency,
                allpass_phase_deg(frequency, item),
                mode="phase",
                enabled=apply_linear_fir_mask,
            )
    return phase


def build_target_gain_db(
    config: DesignConfig,
    frequency: np.ndarray,
    *,
    _response_cache: _AxisResponseCache | None = None,
) -> np.ndarray:
    response_cache = _response_cache or _AxisResponseCache()
    base_gain = _direct_target_gain_for_correction(config, frequency, response_cache=response_cache)
    manual_gain = manual_gain_eq_db(
        config,
        frequency,
        apply_linear_fir_mask=True,
    )
    auto_gain = auto_gain_eq_db(
        config,
        frequency,
        manual_gain_db=base_gain + manual_gain,
        apply_linear_fir_mask=True,
        _response_cache=response_cache,
    )
    return base_gain + manual_gain + auto_gain


def _direct_target_gain_for_correction(
    config: DesignConfig,
    frequency: np.ndarray,
    *,
    response_cache: _AxisResponseCache | None = None,
) -> np.ndarray:
    from .acoustic_target import enabled as acoustic_target_enabled
    # Acoustic goals are measurement references, never standalone FIR stages.
    if (acoustic_target_enabled(config) or config.target_response is None
            or config.speaker_response is not None or _auto_gain_eq_sections(config.auto_eq)):
        return np.zeros_like(frequency, dtype=float)
    return _target_gain_on_axis(config, frequency, response_cache=response_cache)


def _direct_target_phase_for_correction(
    config: DesignConfig,
    frequency: np.ndarray,
    *,
    response_cache: _AxisResponseCache | None = None,
) -> np.ndarray:
    from .acoustic_target import enabled as acoustic_target_enabled
    if (acoustic_target_enabled(config) or config.target_response is None
            or config.speaker_response is not None or _auto_phase_eq_sections(config.auto_eq)):
        return np.zeros_like(frequency, dtype=float)
    return _target_phase_on_axis(config, frequency, response_cache=response_cache)


def manual_gain_eq_db(
    config: DesignConfig,
    frequency: np.ndarray,
    *,
    apply_linear_fir_mask: bool = False,
) -> np.ndarray:
    gain = np.zeros_like(frequency, dtype=float)
    for item in config.gain_peq_filters:
        if item.enabled:
            gain += _maybe_apply_linear_fir_eq_mask(
                config,
                frequency,
                gain_peq_db(frequency, item),
                mode="gain",
                enabled=apply_linear_fir_mask,
            )
    for item in config.gain_shelf_filters:
        if item.enabled:
            gain += _maybe_apply_linear_fir_eq_mask(
                config,
                frequency,
                gain_shelf_db(frequency, item),
                mode="gain",
                enabled=apply_linear_fir_mask,
            )
    for item in config.gain_linear_filters:
        if item.enabled:
            gain += _maybe_apply_linear_fir_eq_mask(
                config,
                frequency,
                gain_linear_eq_filter_db(frequency, item, sample_rate=config.sample_rate),
                mode="gain",
                enabled=apply_linear_fir_mask,
            )
    gain += _total_gain_tilt_db(
        config,
        frequency,
        apply_linear_fir_mask=apply_linear_fir_mask,
    )
    return gain


def _total_phase_tilt_deg(
    config: DesignConfig,
    frequency: np.ndarray,
    *,
    apply_linear_fir_mask: bool,
) -> np.ndarray:
    total = np.zeros_like(frequency, dtype=float)
    has_enabled = False
    for item in config.tilt_filters:
        if item.enabled:
            has_enabled = True
            total += tilt_phase_deg(
                frequency,
                replace(item, edge_smooth_oct=0.0, edge_smooth_percent=0.0),
            )
    if not has_enabled:
        return total
    total = _maybe_apply_linear_fir_eq_mask(
        config,
        frequency,
        total,
        mode="phase",
        enabled=apply_linear_fir_mask,
    )
    open_high = any(
        item.enabled and _tilt_reaches_nyquist(item.f_end, frequency)
        for item in config.tilt_filters
    )
    return smooth_total_tilt_curve(
        total,
        frequency,
        config.phase_tilt_smoothing_oct,
        open_high=open_high,
    )


def _total_gain_tilt_db(
    config: DesignConfig,
    frequency: np.ndarray,
    *,
    apply_linear_fir_mask: bool,
) -> np.ndarray:
    combined = np.zeros_like(frequency, dtype=float)
    for mode in ("high", "low"):
        total = np.zeros_like(frequency, dtype=float)
        has_enabled = False
        for item in config.gain_tilt_filters:
            if item.enabled and getattr(item, "mode", "high") == mode:
                has_enabled = True
                total += gain_tilt_db(
                    frequency,
                    replace(item, edge_smooth_oct=0.0, edge_smooth_percent=0.0),
                )
        if not has_enabled:
            continue
        total = _maybe_apply_linear_fir_eq_mask(
            config,
            frequency,
            total,
            mode="gain",
            enabled=apply_linear_fir_mask,
        )
        open_high = mode == "high" and any(
            item.enabled
            and getattr(item, "mode", "high") == mode
            and _tilt_reaches_nyquist(item.f_end, frequency)
            for item in config.gain_tilt_filters
        )
        combined += smooth_total_tilt_curve(
            total,
            frequency,
            config.gain_tilt_smoothing_oct,
            open_high=open_high,
        )
    return combined


def _maybe_apply_linear_fir_eq_mask(
    config: DesignConfig,
    frequency: np.ndarray,
    values: np.ndarray,
    *,
    mode: str,
    enabled: bool,
) -> np.ndarray:
    if not enabled:
        return values
    # The mask limits the FIR EQ correction only.  The output-band split FIR is
    # convolved later at full length and is never modified by this operation.
    return _apply_linear_fir_eq_mask(config, frequency, values, mode=mode)


def smooth_total_tilt_curve(
    values: np.ndarray,
    frequency: np.ndarray,
    smoothing_oct: float,
    *,
    open_high: bool = False,
) -> np.ndarray:
    smoothing_oct = float(smoothing_oct)
    if smoothing_oct <= 0:
        return values
    finite_values = np.asarray(values, dtype=float)
    finite_values = finite_values[np.isfinite(finite_values)]
    if finite_values.size == 0 or np.allclose(finite_values, finite_values[0]):
        return values.copy()
    smoothing_fraction = 1.0 / smoothing_oct
    if open_high:
        finite_frequency = np.asarray(frequency, dtype=float)
        finite_frequency = finite_frequency[np.isfinite(finite_frequency)]
        if finite_frequency.size:
            return _smooth_open_high_source_values(
                frequency,
                values,
                float(np.min(finite_frequency)),
                float(np.max(finite_frequency)),
                smoothing_fraction,
                float(np.max(finite_frequency)),
                slope_axis="log",
            )
    return fractional_octave_smooth(frequency, values, smoothing_fraction)


def _tilt_reaches_nyquist(f_end: float, frequency: np.ndarray) -> bool:
    finite = np.asarray(frequency, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return False
    return float(f_end) == 0.0 or np.isclose(float(f_end), float(np.max(finite)))


def peq_phase_deg(frequency: np.ndarray, item: PhasePEQ) -> np.ndarray:
    center = max(item.fc, 1e-9)
    q = max(item.q, 1e-9)
    log_ratio = np.log2(np.maximum(frequency, 1e-9) / center)
    sigma = 1.0 / q
    return item.phase_deg * np.exp(-0.5 * (log_ratio / sigma) ** 2)


def shelf_phase_deg(frequency: np.ndarray, item: PhaseShelf) -> np.ndarray:
    center = max(item.fc, 1e-9)
    q = max(item.q, 1e-9)
    freq = np.asarray(frequency, dtype=float)
    x = q * np.log2(np.maximum(freq, 1e-9) / center)
    transition = 0.5 * (1.0 + np.tanh(x))
    if item.mode == "low":
        shape = 1.0 - transition
    else:
        shape = transition
    phase = item.phase_deg * shape
    if item.mode == "low":
        phase = _fade_low_frequency_phase_boundary(freq, phase, center)
    return phase


def _fade_low_frequency_phase_boundary(
    frequency: np.ndarray,
    phase_deg: np.ndarray,
    center_frequency: float,
) -> np.ndarray:
    phase_magnitude = float(np.nanmax(np.abs(phase_deg))) if np.size(phase_deg) else 0.0
    phase_ratio = np.clip(phase_magnitude / 180.0, 0.0, 1.0)
    fade_end = max(float(center_frequency) * (0.25 + 0.25 * phase_ratio), 1e-9)
    fade_start = max(fade_end * 0.25, 1e-9)
    if fade_end <= fade_start:
        return phase_deg

    freq = np.asarray(frequency, dtype=float)
    phase = np.asarray(phase_deg, dtype=float).copy()
    mask = freq < fade_end
    if not np.any(mask):
        return phase

    distance_oct = np.log2(np.maximum(freq[mask], 1e-9) / fade_start)
    width_oct = np.log2(fade_end / fade_start)
    weight = smootherstep_weight(np.clip(distance_oct / max(width_oct, 1e-9), 0.0, 1.0))
    phase[mask] *= weight
    return phase


def tilt_phase_deg(frequency: np.ndarray, item: PhaseTilt) -> np.ndarray:
    f_start = _effective_tilt_start(item.f_start, frequency)
    f_end = _effective_tilt_end(item.f_end, frequency)
    f_end = max(f_end, f_start + 1e-9)

    clipped_f = np.clip(np.maximum(frequency, 1e-9), f_start, f_end)
    phase = item.slope_deg_per_oct * np.log2(clipped_f / f_start)

    end_phase = item.slope_deg_per_oct * np.log2(f_end / f_start)
    if item.edge_smooth_oct > 0:
        return _smooth_tilt_edges_octave(
            phase,
            frequency,
            f_start,
            f_end,
            item.edge_smooth_oct,
            end_phase,
        )

    smooth = item.edge_smooth_percent / 100.0
    if smooth <= 0:
        return phase

    span = f_end - f_start
    fade_width = span * smooth
    if fade_width <= 0:
        return phase

    start_phase = 0.0
    smoothed = phase.copy()

    start_mask = (frequency >= f_start) & (frequency < f_start + fade_width)
    if np.any(start_mask):
        t = (frequency[start_mask] - f_start) / fade_width
        w = smootherstep_weight(t)
        smoothed[start_mask] = start_phase + w * (phase[start_mask] - start_phase)

    end_mask = (frequency > f_end - fade_width) & (frequency <= f_end)
    if np.any(end_mask):
        t = (f_end - frequency[end_mask]) / fade_width
        w = smootherstep_weight(t)
        smoothed[end_mask] = end_phase + w * (phase[end_mask] - end_phase)

    return smoothed


def allpass_phase_deg(frequency: np.ndarray, item: PhaseAllPass) -> np.ndarray:
    center = max(item.fc, 1e-9)
    q = max(item.q, 1e-9)
    ratio = np.maximum(frequency, 1e-9) / center
    phase = 2.0 * np.rad2deg(np.arctan2(ratio / q, 1.0 - ratio**2))
    if item.polarity == "negative":
        phase = -phase
    phase = np.where(frequency <= 0, 0.0, phase)
    return phase


def _smooth_tilt_edges_octave(
    values: np.ndarray,
    frequency: np.ndarray,
    f_start: float,
    f_end: float,
    edge_smooth_oct: float,
    end_value: float,
) -> np.ndarray:
    edge_width = float(edge_smooth_oct)
    if edge_width <= 0:
        return values

    freq = np.maximum(np.asarray(frequency, dtype=float), 1e-9)
    smoothed = values.copy()
    start_value = 0.0

    start_distance_oct = np.log2(freq / f_start)
    start_mask = (freq >= f_start) & (start_distance_oct < edge_width)
    if np.any(start_mask):
        t = np.clip(start_distance_oct[start_mask] / edge_width, 0.0, 1.0)
        w = smootherstep_weight(t)
        smoothed[start_mask] = start_value + w * (values[start_mask] - start_value)

    end_distance_oct = np.log2(f_end / freq)
    end_mask = (freq <= f_end) & (end_distance_oct < edge_width)
    if np.any(end_mask):
        t = np.clip(end_distance_oct[end_mask] / edge_width, 0.0, 1.0)
        w = smootherstep_weight(t)
        smoothed[end_mask] = end_value + w * (values[end_mask] - end_value)

    return smoothed


def gain_peq_db(frequency: np.ndarray, item: GainPEQ) -> np.ndarray:
    center = max(item.fc, 1e-9)
    q = max(item.q, 1e-9)
    log_ratio = np.log2(np.maximum(frequency, 1e-9) / center)
    sigma = 1.0 / q
    return item.gain_db * np.exp(-0.5 * (log_ratio / sigma) ** 2)


def gain_shelf_db(frequency: np.ndarray, item: GainShelf) -> np.ndarray:
    center = max(item.fc, 1e-9)
    q = max(item.q, 1e-9)
    x = q * np.log2(np.maximum(frequency, 1e-9) / center)
    transition = 0.5 * (1.0 + np.tanh(x))
    if item.mode == "low":
        shape = 1.0 - transition
    else:
        shape = transition
    return item.gain_db * shape


def gain_linear_filter_db(frequency: np.ndarray, item: GainLinearFilter) -> np.ndarray:
    magnitude = _linkwitz_riley_magnitude(frequency, item)
    return 20.0 * np.log10(np.clip(magnitude, 1e-9, 1.0))


def _linkwitz_riley_magnitude(frequency: np.ndarray, item: GainLinearFilter) -> np.ndarray:
    fc = max(float(item.fc), 1e-9)
    ratio = np.maximum(np.asarray(frequency, dtype=float), 0.0) / fc
    magnitude = 1.0 / (1.0 + ratio**2)
    if item.mode == "hp":
        return 1.0 - magnitude
    return magnitude


def gain_linear_eq_filter_db(frequency: np.ndarray, item: GainLinearFilter, *, sample_rate: int = 48000) -> np.ndarray:
    from .gain_crossover import gain_crossover_response
    magnitude = np.abs(gain_crossover_response(frequency, item, sample_rate))
    return 20.0 * np.log10(np.clip(magnitude, 1e-9, 1.0))


def _sample_rate_from_frequency_axis(frequency: np.ndarray) -> float:
    freq = np.asarray(frequency, dtype=float)
    finite = freq[np.isfinite(freq)]
    if finite.size == 0:
        return 48_000.0
    max_freq = max(float(np.nanmax(finite)), 1.0)
    return max(max_freq * 2.0, 2.0)


def gain_tilt_db(frequency: np.ndarray, item: GainTilt) -> np.ndarray:
    f_start = _effective_tilt_start(item.f_start, frequency)
    f_end = _effective_tilt_end(item.f_end, frequency)
    f_end = max(f_end, f_start + 1e-9)

    clipped_f = np.clip(np.maximum(frequency, 1e-9), f_start, f_end)
    if str(getattr(item, "mode", "high")) == "low":
        gain = item.slope_db_per_oct * np.log2(f_end / clipped_f)
    else:
        gain = item.slope_db_per_oct * np.log2(clipped_f / f_start)

    end_gain = item.slope_db_per_oct * np.log2(f_end / f_start)
    if item.edge_smooth_oct > 0:
        return _smooth_tilt_edges_octave(
            gain,
            frequency,
            f_start,
            f_end,
            item.edge_smooth_oct,
            0.0 if str(getattr(item, "mode", "high")) == "low" else end_gain,
        )

    smooth = item.edge_smooth_percent / 100.0
    if smooth <= 0:
        return gain

    span = f_end - f_start
    fade_width = span * smooth
    if fade_width <= 0:
        return gain

    start_gain = 0.0
    smoothed = gain.copy()

    start_mask = (frequency >= f_start) & (frequency < f_start + fade_width)
    if np.any(start_mask):
        t = (frequency[start_mask] - f_start) / fade_width
        w = smootherstep_weight(t)
        smoothed[start_mask] = start_gain + w * (gain[start_mask] - start_gain)

    end_mask = (frequency > f_end - fade_width) & (frequency <= f_end)
    if np.any(end_mask):
        t = (f_end - frequency[end_mask]) / fade_width
        w = smootherstep_weight(t)
        smoothed[end_mask] = end_gain + w * (gain[end_mask] - end_gain)

    return smoothed


def _effective_tilt_end(f_end: float, frequency: np.ndarray) -> float:
    if float(f_end) == 0.0:
        finite = np.asarray(frequency, dtype=float)
        finite = finite[np.isfinite(finite)]
        if finite.size:
            return float(np.max(finite))
    return float(f_end)


def _effective_tilt_start(f_start: float, frequency: np.ndarray) -> float:
    if float(f_start) <= 0.0:
        return 1.0
    return max(float(f_start), 1e-9)


def auto_gain_eq_db(
    config: DesignConfig,
    frequency: np.ndarray,
    manual_gain_db: np.ndarray | None = None,
    *,
    apply_linear_fir_mask: bool = False,
    _response_cache: _AxisResponseCache | None = None,
) -> np.ndarray:
    from .acoustic_target import correction_config
    config = correction_config(config)
    sections, section_plans = _auto_gain_section_plans(
        config,
        frequency,
        manual_gain_db=manual_gain_db,
        response_cache=_response_cache,
        apply_linear_fir_mask=apply_linear_fir_mask,
    )
    if not sections:
        return np.zeros_like(frequency, dtype=float)
    edge_taper_strength = _auto_eq_edge_taper_strength(config, frequency)
    result = _combine_auto_eq_sections(
        frequency,
        sections,
        [
            _maybe_apply_linear_fir_eq_mask(
                config,
                frequency,
                plan.correction_db,
                mode="gain",
                enabled=apply_linear_fir_mask,
            )
            for plan in section_plans
        ],
        taper_edges=False,
        edge_taper_strength=edge_taper_strength,
        boundary_smoothing_method=config.auto_eq.gain_boundary_smoothing_method,
    )

    from .acoustic_target import enabled as acoustic_enabled, continue_boundary_gain_correction
    result = continue_boundary_gain_correction(config, frequency, result, manual_gain_db)
    return np.clip(result, -120.0, 6.0) if acoustic_enabled(config) and config.acoustic_correction_enabled else result


def auto_gain_phase_eq_deg(
    config: DesignConfig,
    frequency: np.ndarray,
    *,
    apply_linear_fir_mask: bool = False,
) -> np.ndarray:
    """Minimum phase of the selected Auto Gain contributions, before Auto Phase.

    Use a complete, analysis-independent FFT grid. Lin sections remain in the
    boundary layout with zero log magnitude, so mixed modes retain the existing
    shared-boundary processing. Never window or convert the final combined FIR.
    """
    from fir_design_common import generation_fft_size, generation_frequency_axis
    from .acoustic_target import correction_config
    from .speaker import _minimum_phase_spectrum_from_magnitude

    config = correction_config(config)
    sections = _auto_gain_eq_sections(config.auto_eq)
    if not any(section.gain_phase_mode == "min" for section in sections):
        return np.zeros_like(frequency, dtype=float)
    require_pro_auto_eq()
    n_fft = max(32768, generation_fft_size(config.sample_rate, config.taps))
    axis = generation_frequency_axis(config.sample_rate, n_fft)
    manual_gain = _direct_target_gain_for_correction(config, axis) + manual_gain_eq_db(
        config, axis, apply_linear_fir_mask=apply_linear_fir_mask,
    )
    if all(section.gain_phase_mode == "min" for section in sections):
        gain = auto_gain_eq_db(
            config, axis, manual_gain, apply_linear_fir_mask=apply_linear_fir_mask,
        )
    else:
        sections, plans = _auto_gain_section_plans(config, axis, manual_gain,
            apply_linear_fir_mask=apply_linear_fir_mask)
        gain = _combine_auto_eq_sections(
            axis, sections,
            [
                _maybe_apply_linear_fir_eq_mask(
                    config, axis, plan.correction_db, mode="gain",
                    enabled=apply_linear_fir_mask,
                ) if section.gain_phase_mode == "min" else np.zeros_like(axis)
                for section, plan in zip(sections, plans)
            ],
            taper_edges=False,
            edge_taper_strength=_auto_eq_edge_taper_strength(config, axis),
            boundary_smoothing_method=config.auto_eq.gain_boundary_smoothing_method,
        )
    spectrum = _minimum_phase_spectrum_from_magnitude(10.0 ** (gain / 20.0), n_fft)
    phase = np.rad2deg(np.unwrap(np.angle(spectrum)))
    return np.interp(frequency, axis, phase)


def auto_gain_candidate_plans(
    config: DesignConfig,
    frequency: np.ndarray,
    *,
    apply_linear_fir_mask: bool = False,
) -> list[GainCorrectionPlan]:
    from .acoustic_target import correction_config
    config = correction_config(config)
    manual_gain = _direct_target_gain_for_correction(config, frequency) + manual_gain_eq_db(
        config,
        frequency,
        apply_linear_fir_mask=apply_linear_fir_mask,
    )
    _sections, plans = _auto_gain_section_plans(config, frequency, manual_gain_db=manual_gain,
        apply_linear_fir_mask=apply_linear_fir_mask)
    if not apply_linear_fir_mask:
        return plans
    return [
        replace_gain_correction_values(
            plan,
            frequency,
            _maybe_apply_linear_fir_eq_mask(
                config,
                frequency,
                plan.correction_db,
                mode="gain",
                enabled=True,
            ),
        )
        for plan in plans
    ]


def auto_gain_shaped_speaker_response(config: DesignConfig, *, apply_linear_fir_mask: bool = True):
    """Shared calculation input after all IIR and manual FIR Gain EQ."""
    from .auto_iir_input_shaping import prepare_speaker_input, speaker_input_with_gain
    from .acoustic_target import effective_target
    from .config import SpeakerResponse

    speaker = config.speaker_response
    if speaker is None or not config.auto_gain_input_shaping.enabled:
        return None
    source_f = np.asarray(speaker.frequency, dtype=float)
    positive = np.isfinite(source_f) & (source_f > 0) & (source_f <= config.sample_rate / 2)
    if np.count_nonzero(positive) < 3:
        return None
    # Preserve native measurement detail; an output FFT axis may miss narrow dips.
    f = source_f[positive]
    gain = np.asarray(speaker.gain_db, dtype=float)[positive].copy()
    if config.iir_filters:
        gain = fir_input_transfer(config.iir_filters, config.sample_rate, f).gain_db(gain)
    from .response_support import inherit_support
    source = inherit_support(SpeakerResponse(f.tolist(), gain.tolist(), None), speaker)
    if not config.legacy_input_shaping_order:
        source = speaker_input_with_gain(source, manual_gain_eq_db(
            config, f, apply_linear_fir_mask=apply_linear_fir_mask))
    target = effective_target(config)
    if target is None:
        target = SpeakerResponse(f.tolist(), np.zeros_like(f).tolist(), None)
    target_f = np.asarray(target.frequency, dtype=float)
    common = target_f[np.isfinite(target_f) & (target_f > 0)]
    if common.size < 2 or min(f[-1], common[-1]) <= max(f[0], common[0]):
        return None
    shaped, _ = prepare_speaker_input(source, target, config.sample_rate,
        config.auto_gain_input_shaping, require_complete=False)
    return source, shaped


def _auto_gain_section_plans(
    config: DesignConfig,
    frequency: np.ndarray,
    manual_gain_db: np.ndarray | None = None,
    *,
    response_cache: _AxisResponseCache | None = None,
    apply_linear_fir_mask: bool = False,
) -> tuple[list[AutoEQSection], list[GainCorrectionPlan]]:
    sections = _auto_gain_eq_sections(config.auto_eq)
    if not sections:
        return [], []
    return require_pro_auto_eq()._auto_gain_section_plans(
        config, sections, frequency, manual_gain_db, response_cache=response_cache, apply_linear_fir_mask=apply_linear_fir_mask,
    )


def auto_phase_eq_deg(
    config: DesignConfig,
    frequency: np.ndarray,
    manual_phase_deg: np.ndarray | None = None,
    *,
    apply_linear_fir_mask: bool = False,
    _response_cache: _AxisResponseCache | None = None,
) -> np.ndarray:
    from .acoustic_target import correction_config
    config = correction_config(config)
    sections = _auto_phase_eq_sections(config.auto_eq)
    if not sections:
        return np.zeros_like(frequency, dtype=float)
    if manual_phase_deg is None:
        manual_phase_deg = auto_gain_phase_eq_deg(
            config, frequency, apply_linear_fir_mask=apply_linear_fir_mask,
        )
    edge_taper_strength = _auto_eq_edge_taper_strength(config, frequency)
    return _combine_auto_eq_sections(
        frequency,
        sections,
        [
            _maybe_apply_linear_fir_eq_mask(
                config,
                frequency,
                plan.correction_deg,
                mode="phase",
                enabled=apply_linear_fir_mask,
            )
            for plan in _auto_phase_section_plans(
                config,
                frequency,
                manual_phase_deg=manual_phase_deg,
                response_cache=_response_cache,
            )[1]
        ],
        phase_boundary_nearest=True,
        edge_taper_strength=edge_taper_strength,
        boundary_smoothing_method="smooth_connect",
        correction_mode="phase",
    )


def auto_phase_candidate_plans(
    config: DesignConfig,
    frequency: np.ndarray,
    *,
    apply_linear_fir_mask: bool = False,
) -> list[PhaseCorrectionPlan]:
    from .acoustic_target import correction_config
    config = correction_config(config)
    manual_phase = _direct_target_phase_for_correction(config, frequency) + manual_phase_eq_deg(
        config,
        frequency,
        apply_linear_fir_mask=apply_linear_fir_mask,
    )
    manual_phase = manual_phase + auto_gain_phase_eq_deg(
        config, frequency, apply_linear_fir_mask=apply_linear_fir_mask,
    )
    _sections, plans = _auto_phase_section_plans(config, frequency, manual_phase_deg=manual_phase)
    if not apply_linear_fir_mask:
        return plans
    return [
        replace_phase_correction_values(
            plan,
            frequency,
            _maybe_apply_linear_fir_eq_mask(
                config,
                frequency,
                plan.correction_deg,
                mode="phase",
                enabled=True,
            ),
        )
        for plan in plans
    ]


def _auto_phase_section_plans(
    config: DesignConfig,
    frequency: np.ndarray,
    manual_phase_deg: np.ndarray | None = None,
    *,
    response_cache: _AxisResponseCache | None = None,
) -> tuple[list[AutoEQSection], list[PhaseCorrectionPlan]]:
    sections = _auto_phase_eq_sections(config.auto_eq)
    if not sections:
        return [], []
    return require_pro_auto_eq()._auto_phase_section_plans(
        config, sections, frequency, manual_phase_deg, response_cache=response_cache,
    )


def _smooth_open_high_source_values(
    frequency: np.ndarray,
    values: np.ndarray,
    f_min: float,
    f_max: float,
    smoothing_fraction: float,
    nyquist: float,
    *,
    slope_axis: str,
) -> np.ndarray:
    """Apply optional smoothing after extending an open Nyquist high side."""
    freq = np.asarray(frequency, dtype=float)
    output = np.asarray(values, dtype=float).copy()
    open_high = (
        freq.size >= 2
        and output.size == freq.size
        and np.isclose(float(freq[-1]), nyquist)
        and np.isclose(float(f_max), nyquist)
    )
    if not open_high:
        return _smooth_auto_eq_source_values(freq, output, f_min, f_max, smoothing_fraction)

    source_mask = (
        np.isfinite(freq)
        & np.isfinite(output)
        & (freq >= float(f_min))
        & (freq < nyquist)
    )
    source_freq = freq[source_mask]
    source_values = output[source_mask]
    if source_freq.size < 2:
        return _smooth_auto_eq_source_values(freq, output, f_min, f_max, smoothing_fraction)

    fit_width_oct = max(1.0 / 24.0, 0.5 / float(smoothing_fraction)) if smoothing_fraction > 0 else 1.0 / 12.0
    fit_mask = source_freq >= source_freq[-1] / (2.0**fit_width_oct)
    fit_indices = np.flatnonzero(fit_mask)
    if fit_indices.size < 2:
        fit_indices = np.arange(source_freq.size - 2, source_freq.size)
    fit_freq = source_freq[fit_indices]
    fit_values = source_values[fit_indices]
    fit_axis = np.log2(np.maximum(fit_freq, 1e-12)) if slope_axis == "log" else fit_freq
    center = float(np.mean(fit_axis))
    slope, intercept = np.polyfit(fit_axis - center, fit_values, 1)

    step_candidates = np.diff(source_freq)
    step_candidates = step_candidates[np.isfinite(step_candidates) & (step_candidates > 0)]
    step_hz = float(np.median(step_candidates)) if step_candidates.size else max(nyquist - source_freq[-1], 1.0)
    extension_stop = nyquist
    if smoothing_fraction > 0:
        extension_stop = nyquist * 2.0 ** (0.5 / float(smoothing_fraction))
    virtual_freq = np.arange(nyquist, extension_stop + step_hz * 0.5, step_hz, dtype=float)
    if virtual_freq.size == 0 or not np.isclose(virtual_freq[0], nyquist):
        virtual_freq = np.insert(virtual_freq, 0, nyquist)
    virtual_axis = np.log2(np.maximum(virtual_freq, 1e-12)) if slope_axis == "log" else virtual_freq
    virtual_values = slope * (virtual_axis - center) + intercept
    extended_freq = np.concatenate([source_freq, virtual_freq])
    extended_values = np.concatenate([source_values, virtual_values])
    smoothed_extended = (
        fractional_octave_smooth(extended_freq, extended_values, smoothing_fraction)
        if smoothing_fraction > 0
        else extended_values
    )

    output_mask = np.isfinite(freq) & (freq >= float(f_min)) & (freq <= nyquist)
    output[output_mask] = np.interp(freq[output_mask], extended_freq, smoothed_extended)
    return output


def _smooth_auto_eq_source_values(
    frequency: np.ndarray,
    values: np.ndarray,
    f_min: float,
    f_max: float,
    smoothing_fraction: float,
) -> np.ndarray:
    """Smooth Auto EQ source data before section correction is generated."""

    result = np.asarray(values, dtype=float).copy()
    if smoothing_fraction <= 0:
        return result

    freq = np.asarray(frequency, dtype=float)
    in_range = np.isfinite(freq) & np.isfinite(result) & (freq >= float(f_min)) & (freq <= float(f_max))
    if np.count_nonzero(in_range) < 2:
        return result

    result[in_range] = fractional_octave_smooth(
        freq[in_range],
        result[in_range],
        smoothing_fraction,
    )
    return result



def _linear_fir_eq_mask_is_active(config: DesignConfig, frequency: np.ndarray) -> bool:
    return _linear_fir_eq_mask(config, frequency) is not None


def _auto_eq_edge_taper_strength(config: DesignConfig, frequency: np.ndarray) -> float:
    if _linear_fir_eq_mask_is_active(config, frequency):
        return AUTO_EQ_EDGE_TAPER_WITH_LINEAR_FIR_MASK_STRENGTH
    return 1.0


def _reference_phase_in_range(
    frequency: np.ndarray,
    phase: np.ndarray,
    mask: np.ndarray,
    f_min: float,
    f_max: float,
) -> float:
    reference_freq = np.sqrt(max(f_min, 1e-9) * max(f_max, 1e-9))
    return float(
        np.interp(
            np.log10(reference_freq),
            np.log10(np.maximum(frequency[mask], 1e-9)),
            phase[mask],
        )
    )


def fractional_octave_smooth(
    frequency: np.ndarray,
    values: np.ndarray,
    smoothing_fraction: float,
) -> np.ndarray:
    if smoothing_fraction <= 0:
        return values.copy()
    smoothed = values.astype(float, copy=True)
    positive = frequency > 0
    if not np.any(positive):
        return smoothed
    positive_indices = np.flatnonzero(positive)
    log_freq = np.log2(frequency[positive])
    source_values = np.asarray(values[positive], dtype=float)
    half_width_oct = 0.5 / smoothing_fraction
    order = np.argsort(log_freq)
    sorted_log = log_freq[order]
    sorted_values = source_values[order]
    cumulative = np.concatenate([[0.0], np.cumsum(sorted_values)])
    left = np.searchsorted(sorted_log, sorted_log - half_width_oct, side="left")
    right = np.searchsorted(sorted_log, sorted_log + half_width_oct, side="right")
    counts = np.maximum(right - left, 1)
    sorted_smoothed = (cumulative[right] - cumulative[left]) / counts
    smoothed[positive_indices[order]] = sorted_smoothed
    return smoothed


def _auto_range_mask(f_min: float, f_max: float, frequency: np.ndarray) -> np.ndarray:
    return (frequency >= f_min) & (frequency <= f_max)


def _fir_input_on_axis(
    config: DesignConfig,
    frequency: np.ndarray,
    *,
    response_cache: _AxisResponseCache | None = None,
) -> FIRInputTransfer:
    if response_cache is not None and response_cache.fir_input is not None:
        return response_cache.fir_input
    stage = fir_input_transfer(config.iir_filters, config.sample_rate, frequency)
    if response_cache is not None:
        response_cache.fir_input = stage
    return stage


def _speaker_gain_on_axis(
    config: DesignConfig,
    frequency: np.ndarray,
    *,
    out_of_range: str = "neutral",
    response_cache: _AxisResponseCache | None = None,
) -> np.ndarray:
    response = _speaker_complex_on_axis(
        config,
        frequency,
        out_of_range=out_of_range,
        response_cache=response_cache,
    )
    return 20.0 * np.log10(np.maximum(np.abs(response), 1e-12))


def _speaker_phase_on_axis(
    config: DesignConfig,
    frequency: np.ndarray,
    *,
    out_of_range: str = "neutral",
    response_cache: _AxisResponseCache | None = None,
) -> np.ndarray:
    if response_cache is not None and out_of_range in response_cache.speaker_phase:
        return response_cache.speaker_phase[out_of_range]
    speaker = config.speaker_response
    frequency = np.asarray(frequency, dtype=float)
    if speaker is None or speaker.phase_deg is None or frequency.size == 0:
        return np.zeros_like(frequency, dtype=float)

    source_freq = np.asarray(speaker.frequency, dtype=float)
    source_phase_raw = np.asarray(speaker.phase_deg, dtype=float)
    valid = np.isfinite(source_freq) & np.isfinite(source_phase_raw) & (source_freq > 0)
    if not np.any(valid):
        return np.zeros_like(frequency, dtype=float)

    source_freq = source_freq[valid]
    source_phase_raw = source_phase_raw[valid]
    order = np.argsort(source_freq)
    source_freq = source_freq[order]
    source_phase = np.rad2deg(np.unwrap(np.deg2rad(source_phase_raw[order])))
    unique_freq, unique_indices = np.unique(source_freq, return_index=True)
    source_freq = unique_freq
    source_phase = source_phase[unique_indices]
    phase = interpolate_phase(source_freq, source_phase, frequency)

    if out_of_range == "hold":
        if config.iir_filters:
            phase = _fir_input_on_axis(config, frequency, response_cache=response_cache).phase_deg(phase)
        if response_cache is not None:
            response_cache.speaker_phase[out_of_range] = phase
        return phase

    f_min = float(source_freq[0])
    f_max = float(source_freq[-1])
    f_axis_max = float(np.nanmax(frequency)) if frequency.size else f_max
    low_mask = frequency < f_min
    high_mask = frequency > f_max
    if np.any(low_mask) and f_min > 0:
        t = np.clip(frequency[low_mask] / f_min, 0.0, 1.0)
        weight = smootherstep_weight(t)
        phase[low_mask] *= weight
    if np.any(high_mask) and f_axis_max > f_max:
        t = np.clip((frequency[high_mask] - f_max) / (f_axis_max - f_max), 0.0, 1.0)
        weight = smootherstep_weight(t)
        phase[high_mask] *= 1.0 - weight
    if config.iir_filters:
        phase = _fir_input_on_axis(config, frequency, response_cache=response_cache).phase_deg(phase)
    if response_cache is not None:
        response_cache.speaker_phase[out_of_range] = phase
    return phase


def _speaker_complex_on_axis(
    config: DesignConfig,
    frequency: np.ndarray,
    *,
    out_of_range: str = "neutral",
    response_cache: _AxisResponseCache | None = None,
) -> np.ndarray:
    if response_cache is not None and out_of_range in response_cache.speaker_complex:
        return response_cache.speaker_complex[out_of_range]
    speaker = config.speaker_response
    frequency = np.asarray(frequency, dtype=float)
    neutral = np.ones_like(frequency, dtype=complex)
    if speaker is None or frequency.size == 0:
        return neutral

    source_freq = np.asarray(speaker.frequency, dtype=float)
    source_gain = np.asarray(speaker.gain_db, dtype=float)
    valid = np.isfinite(source_freq) & np.isfinite(source_gain) & (source_freq > 0)
    if speaker.phase_deg is not None:
        source_phase_raw = np.asarray(speaker.phase_deg, dtype=float)
        valid &= np.isfinite(source_phase_raw)
    if not np.any(valid):
        return neutral

    source_freq = source_freq[valid]
    source_gain = source_gain[valid]
    order = np.argsort(source_freq)
    source_freq = source_freq[order]
    source_gain = source_gain[order]
    unique_freq, unique_indices = np.unique(source_freq, return_index=True)
    source_freq = unique_freq
    source_gain = source_gain[unique_indices]
    if speaker.phase_deg is None:
        source_phase = np.zeros_like(source_freq)
    else:
        phase_ordered = np.rad2deg(np.unwrap(np.deg2rad(source_phase_raw[valid][order])))
        source_phase = phase_ordered[unique_indices]

    if source_freq.size == 1:
        edge_response = 10.0 ** (source_gain[0] / 20.0) * np.exp(1j * np.deg2rad(source_phase[0]))
        response = np.full_like(frequency, edge_response, dtype=complex)
    else:
        target_frequency = np.maximum(frequency, 1e-9)
        gain = interpolate_values(source_freq, source_gain, target_frequency, axis="log10", frequency_floor=np.finfo(float).tiny)
        phase = interpolate_phase(source_freq, source_phase, frequency)
        response = 10.0 ** (gain / 20.0) * np.exp(1j * np.deg2rad(phase))

    f_min = float(source_freq[0])
    f_max = float(source_freq[-1])
    f_axis_max = float(np.nanmax(frequency)) if frequency.size else f_max

    low_mask = frequency < f_min
    high_mask = frequency > f_max
    low_edge = response[np.argmin(np.abs(frequency - f_min))]
    high_edge = response[np.argmin(np.abs(frequency - f_max))]

    if out_of_range == "hold":
        response[low_mask] = low_edge
        response[high_mask] = high_edge
    else:
        if np.any(low_mask) and f_min > 0:
            t = np.clip(frequency[low_mask] / f_min, 0.0, 1.0)
            weight = smootherstep_weight(t)
            response[low_mask] = (1.0 - weight) * 1.0 + weight * low_edge

        if np.any(high_mask) and f_axis_max > f_max:
            t = np.clip((frequency[high_mask] - f_max) / (f_axis_max - f_max), 0.0, 1.0)
            weight = smootherstep_weight(t)
            response[high_mask] = (1.0 - weight) * high_edge + weight * 1.0

    if config.iir_filters:
        response = _fir_input_on_axis(config, frequency, response_cache=response_cache).complex_response(response)
    if response.size and out_of_range != "hold":
        response[0] = np.real(response[0]) + 0.0j
        if np.isclose(float(frequency[-1]), float(config.sample_rate) / 2.0):
            response[-1] = np.real(response[-1]) + 0.0j
    if response_cache is not None:
        response_cache.speaker_complex[out_of_range] = response
    return response


def _target_gain_on_axis(
    config: DesignConfig,
    frequency: np.ndarray,
    *,
    response_cache: _AxisResponseCache | None = None,
) -> np.ndarray:
    if response_cache is not None and response_cache.target_gain is not None:
        return response_cache.target_gain
    from .acoustic_target import effective_target
    target = effective_target(config)
    if target is None:
        return np.zeros_like(frequency, dtype=float)
    source_freq = np.asarray(target.frequency, dtype=float)
    source_gain = np.asarray(target.gain_db, dtype=float)
    source_freq, source_gain = _limit_source_to_below_nyquist(
        source_freq,
        source_gain,
        config.sample_rate,
    )
    from response_completion import complete_response
    if source_freq.size >= 2:
        result, _, _ = complete_response(source_freq, source_gain, None, frequency, gain_axis="log10")
        # Design works in finite dB; the shared physical DC zero uses -inf.
        result = np.maximum(result, -240.0)
    else:
        result = _interp_log_frequency(source_freq, source_gain, frequency)
    if response_cache is not None:
        response_cache.target_gain = result
    return result


def _target_phase_on_axis(
    config: DesignConfig,
    frequency: np.ndarray,
    *,
    response_cache: _AxisResponseCache | None = None,
) -> np.ndarray:
    if response_cache is not None and response_cache.target_phase is not None:
        return response_cache.target_phase
    from .acoustic_target import effective_target
    target = effective_target(config)
    if target is None or target.phase_deg is None:
        return np.zeros_like(frequency, dtype=float)
    source_freq, source_phase = finite_unwrapped_phase_samples(
        target.frequency,
        target.phase_deg,
        min_frequency=np.nextafter(0.0, 1.0),
        max_frequency=float(config.sample_rate) / 2.0,
    )
    if source_freq.size >= 2:
        from response_completion import complete_response
        _, result, _ = complete_response(source_freq, np.zeros_like(source_freq),
            source_phase, frequency, phase_is_continuous=True)
    else:
        result = (interpolate_phase(source_freq, source_phase, frequency)
                  if source_freq.size else np.zeros_like(frequency, dtype=float))
    if response_cache is not None:
        response_cache.target_phase = result
    return result


def _limit_source_to_below_nyquist(
    source_freq: np.ndarray,
    source_value: np.ndarray,
    sample_rate: int,
) -> tuple[np.ndarray, np.ndarray]:
    nyquist = float(sample_rate) / 2.0
    valid = np.asarray(source_freq, dtype=float) <= nyquist
    if np.any(valid):
        return source_freq[valid], source_value[valid]
    return source_freq, source_value


def _interp_log_frequency(source_freq: np.ndarray, source_value: np.ndarray, target_freq: np.ndarray) -> np.ndarray:
    valid = np.isfinite(source_freq) & np.isfinite(source_value) & (source_freq > 0)
    if not np.any(valid):
        return np.zeros_like(target_freq, dtype=float)
    source_freq = source_freq[valid]
    source_value = source_value[valid]
    order = np.argsort(source_freq)
    source_freq = source_freq[order]
    source_value = source_value[order]
    return interpolate_values(source_freq, source_value, target_freq, axis="log10", frequency_floor=source_freq[0])
