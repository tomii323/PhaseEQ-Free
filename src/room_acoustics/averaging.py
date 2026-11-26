"""Log-frequency smoothing and spatial averaging without file/UI side effects."""
from dataclasses import dataclass

import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import savgol_filter
from frequency_smoothing import smooth_three_band


@dataclass(frozen=True)
class Response:
    frequency: np.ndarray
    gain_db: np.ndarray
    phase_deg: np.ndarray | None = None
    name: str = ""

    def __post_init__(self):
        f, g = np.array(self.frequency, float, copy=True), np.array(self.gain_db, float, copy=True)
        if (f.ndim != 1 or len(f) < 2 or g.shape != f.shape
                or not np.isfinite(f).all() or not np.isfinite(g).all()
                or np.any(f <= 0) or np.any(np.diff(f) <= 0)):
            raise ValueError("Response requires finite gains and increasing positive frequencies")
        p = None if self.phase_deg is None else np.array(self.phase_deg, float, copy=True)
        if p is not None and (p.shape != f.shape or not np.isfinite(p).all()):
            raise ValueError("Phase must be finite and match frequency")
        for values in (f, g, p):
            if values is not None:
                values.setflags(write=False)
        object.__setattr__(self, "frequency", f)
        object.__setattr__(self, "gain_db", g)
        object.__setattr__(self, "phase_deg", p)


@dataclass(frozen=True)
class AverageResult:
    response: Response
    aligned_gain_db: np.ndarray
    level_offsets_db: np.ndarray
    weights: np.ndarray
    phase_coherence: np.ndarray | None
    metadata: dict


def _positive_grid(responses, points_per_octave):
    if not responses:
        raise ValueError("At least one response is required")
    if not isinstance(points_per_octave, int) or not 24 <= points_per_octave <= 768:
        raise ValueError("points_per_octave must be an integer from 24 to 768")
    low = max(r.frequency[0] for r in responses)
    high = min(r.frequency[-1] for r in responses)
    if low >= high:
        raise ValueError("Responses have no common frequency interval")
    count = int(np.ceil(np.log2(high / low) * points_per_octave)) + 1
    if count > 32769:
        raise ValueError("Common grid is too large")
    return np.geomspace(low, high, count)


def _band_mask(frequency, band):
    if len(band) != 2 or not np.isfinite(band).all() or not 0 < band[0] < band[1]:
        raise ValueError("Level band must have two increasing positive bounds")
    if band[0] < frequency[0] or band[1] > frequency[-1]:
        raise ValueError("Level band must be inside the common interval")
    mask = (frequency >= band[0]) & (frequency <= band[1])
    if mask.sum() < 3:
        raise ValueError("Level band needs at least three grid points")
    return mask


def smooth_db(frequency, gain_db, *, method="moving_average", bandwidth_oct=1 / 3, polyorder=3,
              boundaries=(200., 2000.), widths=(1/12, 1/6, 1/3)):
    """Smooth dB on a uniform log2 grid; reflected edges preserve a constant.

    This is a specified octave-domain filter, not REW's proprietary smoothing.
    """
    f, g = np.asarray(frequency, float), np.asarray(gain_db, float)
    Response(f, g)
    steps = np.diff(np.log2(f))
    if not np.allclose(steps, steps[0], rtol=1e-6, atol=1e-10):
        raise ValueError("Smoothing requires a uniform log-frequency grid")
    if method not in ("none", "moving_average", "savgol", "three_band"):
        raise ValueError("Unknown smoothing method")
    if not np.isfinite(bandwidth_oct) or not 0 <= bandwidth_oct <= 2:
        raise ValueError("Smoothing width must be 0 to 2 octaves")
    if not isinstance(polyorder, int) or not 1 <= polyorder <= 7:
        raise ValueError("Polynomial order must be 1 to 7")
    if method == "three_band":
        return smooth_three_band(g, np.log2(f), boundaries, widths)
    if method == "none" or bandwidth_oct == 0:
        return g.copy()
    window = max(3, int(round(bandwidth_oct / steps[0])))
    if window % 2 == 0:
        window += 1
    if window > len(f):
        raise ValueError("Smoothing window exceeds the available interval")
    if method == "savgol":
        if window <= polyorder:
            raise ValueError("Smoothing window must exceed the polynomial order")
        return savgol_filter(g, window, polyorder, mode="mirror")
    return uniform_filter1d(g, size=window, mode="reflect")


def _mean_db(values, weights, mode):
    if mode == "db":
        return weights @ values
    if mode == "trimmed_power":
        if len(values) < 5:
            raise ValueError("Trimmed power average requires at least five active responses")
        # Trimming changes the represented seat population; callers opt in.
        trim = max(1, int(len(values) * .2))
        indices = np.argsort(values, axis=0, kind="stable")[trim:-trim]
        selected = np.take_along_axis(values, indices, axis=0)
        local_weights = weights[indices]
        local_weights /= local_weights.sum(axis=0)
        peak = selected.max(axis=0)
        return peak + 10*np.log10(np.sum(local_weights * 10**((selected-peak)/10), axis=0))
    if mode not in ("power", "amplitude"):
        raise ValueError("Unknown magnitude average mode")
    divisor = 10 if mode == "power" else 20
    # Referencing the largest value avoids overflow even for absolute SPL input.
    peak = values.max(axis=0)
    return peak + divisor * np.log10(weights @ (10 ** ((values - peak) / divisor)))


def average_responses(responses, *, weights=None, average_mode="power", level_band=None,
                      smoothing="three_band", bandwidth_oct=1 / 3, polyorder=3,
                      points_per_octave=96, phase_mode="none", phase_reference=0,
                      phase_estimator=None, boundaries=(200., 2000.), widths=(1/12, 1/6, 1/3)):
    """Align levels, average magnitudes, then smooth the resulting dB curve.

    Phase modes are opt-in for time-referenced future uses. A supplied estimator
    implements minimum-phase difference adjustment; it never runs in Room EQ.
    """
    responses = tuple(responses)
    if not responses:
        raise ValueError("At least one response is required")
    w = np.ones(len(responses)) if weights is None else np.asarray(weights, float).copy()
    if (w.shape != (len(responses),) or not np.isfinite(w).all()
            or np.any(w < 0) or not np.any(w > 0)):
        raise ValueError("Weights must be finite, nonnegative and have a positive sum")
    # Zero-weight inputs must not constrain either the grid or phase requirements.
    active = w > 0
    if not active.all():
        return average_responses(tuple(r for r, use in zip(responses, active) if use),
            weights=w[active], average_mode=average_mode, level_band=level_band,
            smoothing=smoothing, bandwidth_oct=bandwidth_oct, polyorder=polyorder,
            points_per_octave=points_per_octave, phase_mode=phase_mode,
            phase_reference=_active_reference(active, phase_reference), phase_estimator=phase_estimator,
            boundaries=boundaries, widths=widths)
    f = _positive_grid(responses, points_per_octave)
    w /= w.max()
    w /= w.sum()
    if not isinstance(phase_reference, int) or not 0 <= phase_reference < len(responses):
        raise ValueError("Invalid phase reference")
    gains = np.stack([np.interp(np.log2(f), np.log2(r.frequency), r.gain_db) for r in responses])
    offsets = np.zeros(len(responses))
    if level_band is not None:
        mask = _band_mask(f, level_band)
        levels = gains[:, mask].mean(axis=1)
        offsets = levels[phase_reference] - levels
        gains = gains + offsets[:, None]
    mean = _mean_db(gains, w, average_mode)
    result_gain = smooth_db(f, mean, method=smoothing, bandwidth_oct=bandwidth_oct, polyorder=polyorder,
                            boundaries=boundaries, widths=widths)
    phase, coherence = _average_phase(responses, f, gains, result_gain, w, phase_mode,
                                      phase_reference, phase_estimator)
    return AverageResult(Response(f, result_gain, phase), gains.copy(), offsets.copy(), w.copy(),
                         coherence, {"version": 1, "average_mode": average_mode,
                         "smoothing_order": "average_then_smooth_db", "smoothing": smoothing,
                         "bandwidth_oct": bandwidth_oct, "phase_mode": phase_mode,
                         "boundaries_hz": list(boundaries), "widths_oct": list(widths),
                         "level_band": level_band, "names": [r.name for r in responses]})


def _active_reference(active, reference):
    if not isinstance(reference, int) or not 0 <= reference < len(active) or not active[reference]:
        raise ValueError("Reference must have a positive weight")
    return int(np.count_nonzero(active[:reference]))


def _average_phase(responses, f, gains, output_gain, weights, mode, reference, estimator):
    if mode == "none":
        return None, None
    if mode not in ("reference", "circular", "minimum_phase_delta"):
        raise ValueError("Unknown phase mode")
    selected = (responses[reference],) if mode == "reference" else responses
    if any(r.phase_deg is None for r in selected):
        raise ValueError("Requested phase mode requires measured phase")
    # Unwrap before interpolation; callers must provide adequate sampling for delay.
    phases = np.stack([np.interp(np.log2(f), np.log2(r.frequency),
                                np.unwrap(np.deg2rad(r.phase_deg))) for r in selected])
    if mode == "reference":
        return np.rad2deg(phases[0]), np.ones_like(f)
    if mode == "minimum_phase_delta":
        if estimator is None:
            raise ValueError("Minimum-phase delta requires an explicit phase estimator")
        after = _estimated_phase(estimator, f, output_gain)
        phases += np.stack([after - _estimated_phase(estimator, f, g) for g in gains])
    mean = weights @ np.exp(1j * phases)
    coherence = np.abs(mean)
    # An undefined circular mean must not silently become a plausible 0 degree phase.
    if np.any(coherence < 1e-6):
        raise ValueError("Circular phase mean is undefined due to cancellation")
    return np.rad2deg(np.angle(mean)), coherence


def _estimated_phase(estimator, frequency, gain):
    phase = np.asarray(estimator(frequency.copy(), gain.copy()), float)
    if phase.shape != frequency.shape or not np.isfinite(phase).all():
        raise ValueError("Phase estimator returned invalid data")
    return np.deg2rad(phase)
