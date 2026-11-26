"""Generate bounded additive target corrections from reference/seat responses."""
from dataclasses import dataclass

import numpy as np

from .averaging import Response, AverageResult, average_responses, smooth_db, _band_mask


@dataclass(frozen=True)
class CorrectionResult:
    correction: Response
    spatial_average: AverageResult
    reference_gain_db: np.ndarray
    raw_correction_db: np.ndarray
    metadata: dict

    def room_eq(self, name="generated-room-correction"):
        """Existing format adapter: generated data is additive and initially OFF."""
        return {"enabled": False, "operation": "add", "name": name,
                "response": {"frequency": self.correction.frequency.tolist(),
                             "gain_db": self.correction.gain_db.tolist()}}


def generate_correction(reference, seats, *, correction_band, level_band=None, weights=None,
                        average_mode="power", smoothing="three_band", bandwidth_oct=1 / 3,
                        max_boost_db=0., max_cut_db=6., taper_oct=1 / 3, points_per_octave=96,
                        max_seat_worsening_db=1., boundaries=(200., 2000.), widths=(1/12, 1/6, 1/3)):
    """Reference minus spatial mean in dB, bounded then cosine-tapered to zero.

    Phase is intentionally omitted. Output has no DSP coefficients and changing
    a target still requires the existing EQ design/output flow.
    """
    if (not np.isfinite([max_boost_db, max_cut_db, taper_oct]).all()
            or not 0 <= max_boost_db <= 24 or not 0 <= max_cut_db <= 24 or not 0 < taper_oct <= 2):
        raise ValueError("Invalid boost/cut limits or edge taper")
    seats = tuple(seats)
    if not seats:
        raise ValueError("At least one seat is required")
    if weights is not None:
        weights = np.asarray(weights, float)
        if (weights.shape != (len(seats),) or not np.isfinite(weights).all()
                or np.any(weights < 0) or not np.any(weights > 0)):
            raise ValueError("Invalid seat weights")
        seats = tuple(r for r, w in zip(seats, weights) if w > 0)
        weights = weights[weights > 0]
    low = max(reference.frequency[0], *(r.frequency[0] for r in seats))
    high = min(reference.frequency[-1], *(r.frequency[-1] for r in seats))
    if low >= high:
        raise ValueError("Reference and seats have no common interval")
    # Clip to the intersection without extrapolating endpoint values.
    clipped = []
    for r in seats:
        f = np.unique(np.r_[low, r.frequency[(r.frequency > low) & (r.frequency < high)], high])
        clipped.append(Response(f, np.interp(np.log2(f), np.log2(r.frequency), r.gain_db), name=r.name))
    average = average_responses(clipped, weights=weights, average_mode=average_mode,
        level_band=level_band, smoothing=smoothing, bandwidth_oct=bandwidth_oct,
        points_per_octave=points_per_octave, phase_mode="none", boundaries=boundaries, widths=widths)
    f = average.response.frequency
    reference_db = np.interp(np.log2(f), np.log2(reference.frequency), reference.gain_db)
    # Use the same frequency smoothing on the reference and the seat mean.
    reference_db = smooth_db(f, reference_db, method=smoothing, bandwidth_oct=bandwidth_oct,
                             boundaries=boundaries, widths=widths)
    mean_db = average.response.gain_db.copy()
    level_offset = 0.
    if level_band is not None:
        mask = _band_mask(f, level_band)
        level_offset = float((reference_db[mask] - mean_db[mask]).mean())
        mean_db += level_offset
    _band_mask(f, correction_band)
    if np.log2(correction_band[1] / correction_band[0]) < 2 * taper_oct:
        raise ValueError("Correction band must accommodate both edge tapers")
    raw = reference_db - mean_db
    limited = np.clip(raw, -max_cut_db, max_boost_db)
    left = np.clip(np.log2(f / correction_band[0]) / taper_oct, 0., 1.)
    right = np.clip(np.log2(correction_band[1] / f) / taper_oct, 0., 1.)
    envelope = .5 * (1 - np.cos(np.pi * left)) * .5 * (1 - np.cos(np.pi * right))
    curve = limited * envelope
    if max_seat_worsening_db is not None:
        if not np.isfinite(max_seat_worsening_db) or not 0 <= max_seat_worsening_db <= 6:
            raise ValueError("Seat worsening tolerance must be 0 to 6 dB")
        # Limit absolute error relative to the reference at every measured seat.
        # All intervals include zero, so this cannot force a nonzero correction.
        errors = average.aligned_gain_db + level_offset - reference_db
        allowance = np.abs(errors) + max_seat_worsening_db
        lower = np.max(-allowance - errors, axis=0)
        upper = np.min(allowance - errors, axis=0)
        curve = np.clip(curve, lower, upper)
    if not np.isfinite(curve).all():
        raise ValueError("Correction generation produced invalid values")
    return CorrectionResult(Response(f, curve), average, reference_db, raw,
        {"version": 1, "operation": "add", "correction_band": list(correction_band),
         "max_boost_db": max_boost_db, "max_cut_db": max_cut_db, "taper_oct": taper_oct,
         "max_seat_worsening_db": max_seat_worsening_db,
         "average_to_reference_offset_db": level_offset,
         "definition": "smoothed reference minus level-aligned smoothed seat mean",
         "phase": "omitted", "level_band": level_band})
