"""Pure octave-domain Gaussian smoothing shared by fit and room preparation."""
import numpy as np


def smooth_segment(values, x, width):
    """Gaussian FWHM in octaves, renormalized at data ends (no extrapolation)."""
    if width == 0 or len(x) < 3:
        return values.copy()
    sigma = width / 2.355
    result = np.empty_like(values)
    for i, center in enumerate(x):
        ids = np.flatnonzero(abs(x - center) <= 3 * sigma)
        weights = np.exp(-.5 * ((x[ids] - center) / sigma)**2)
        result[i] = np.dot(values[ids], weights) / weights.sum()
    return result


def smooth_three_band(values, x, boundaries=(200., 2000.), widths=(1/12, 1/6, 1/3)):
    """Blend low/mid/high Gaussian curves across 1/3 octave with C1 weights."""
    if (len(boundaries) != 2 or len(widths) != 3
            or not np.isfinite([*boundaries, *widths]).all()
            or not 0 < boundaries[0] < boundaries[1]
            or any(not 0 <= width <= .5 for width in widths)):
        raise ValueError('Invalid three-band smoothing settings')
    low = np.clip((x-np.log2(boundaries[0])+1/6)/(1/3), 0, 1)
    high = np.clip((x-np.log2(boundaries[1])+1/6)/(1/3), 0, 1)
    low, high = low*low*(3-2*low), high*high*(3-2*high)
    weights = (1-low, low*(1-high), low*high)
    return sum(w*smooth_segment(values, x, width) for w, width in zip(weights, widths))
