"""
Hub-height wind speeds from the two heights we hold (10 m and 100 m).

Each hour's speed at hub height comes from a logarithmic profile fitted through
that hour's 10 m and 100 m speeds, so the shear varies with the weather (stable
nights are strongly sheared, mixed afternoons much less) instead of a single
fixed exponent. Where a file has no usable 10 m series the fixed power-law
exponent is used.

Profile: v(z) = A * ln(z / z0). The ratio r = v(H) / v(L) fixes z0, and then

    v(z) = v(H) * (u + ln(z / L)) / (u + ln(H / L)),    u = ln(H / L) / (r - 1)

which passes through both measured speeds and needs no roughness length.
"""

import math
from typing import List, Optional, Sequence, Tuple

import numpy as np

LOW_HEIGHT_M = 10.0
HIGH_HEIGHT_M = 100.0
FIXED_SHEAR_EXPONENT = 0.14

# Bound the 100 m / 10 m ratio. At or below ~1 the pair implies no (or negative) shear, which
# happens briefly under strong convective mixing; above 3 it implies an unphysical roughness.
RATIO_MIN = 1.02
RATIO_MAX = 3.0
# Below this the ratio of two tiny speeds is noise (and there is no generation anyway).
MIN_LOW_SPEED = 0.5


def hub_height_speeds(speed_high: Sequence[float], speed_low: Optional[Sequence[float]],
                      hub_height: float, *,
                      low_height: float = LOW_HEIGHT_M,
                      high_height: float = HIGH_HEIGHT_M,
                      fixed_shear: float = FIXED_SHEAR_EXPONENT) -> Tuple[List[float], str]:
    """
    Wind speed at `hub_height` for every hour.

    Args:
        speed_high: speeds at `high_height` (100 m), one per hour.
        speed_low: speeds at `low_height` (10 m), one per hour, or None.
        hub_height: turbine hub height in metres.

    Returns:
        (speeds at hub height, "profile" or "fixed shear" -- how they were derived)
    """
    v_high = np.asarray(speed_high, dtype=float)
    if speed_low is None or len(speed_low) != len(v_high):
        return (v_high * (hub_height / high_height) ** fixed_shear).tolist(), 'fixed shear'

    v_low = np.asarray(speed_low, dtype=float)
    hub = max(float(hub_height), low_height)      # the profile is undefined below the lower height
    span = math.log(high_height / low_height)
    ratio = np.clip(v_high / np.maximum(v_low, MIN_LOW_SPEED), RATIO_MIN, RATIO_MAX)
    u = span / (ratio - 1.0)
    factor = (u + math.log(hub / low_height)) / (u + span)
    return (v_high * factor).tolist(), 'profile'
