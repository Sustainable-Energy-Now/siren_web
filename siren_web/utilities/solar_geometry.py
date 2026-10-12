"""
Sun position and irradiance splitting shared by the weather-file builders.

Every SAM weather CSV this project writes holds UTC rows, one per hour, each row
labelled by the START of the hour its irradiance averages. The sun position for a row
is therefore taken at the middle of that hour (start + 30 min), in UTC, at the site's
own longitude -- never at a clock hour treated as local solar time.
"""

from typing import Tuple

import numpy as np
import pandas as pd

# Above this zenith the sun is so low that dividing horizontal beam by cos(zenith)
# amplifies noise into absurd DNI; treat the hour as all diffuse instead.
MAX_ZENITH_FOR_BEAM = 87.0
# Solar constant times a generous margin -- no real beam irradiance exceeds this.
DNI_CAP = 1361.0


def hour_midpoints_utc(hour_starts_utc) -> pd.DatetimeIndex:
    """UTC midpoints for rows labelled by the start of each hour."""
    starts = pd.DatetimeIndex(hour_starts_utc)
    if starts.tz is None:
        starts = starts.tz_localize('UTC')
    return starts + pd.Timedelta(minutes=30)


def solar_zenith(times_utc, lat: float, lon: float) -> np.ndarray:
    """Apparent solar zenith (degrees) at each UTC time for the site."""
    import pvlib
    times = pd.DatetimeIndex(times_utc)
    if times.tz is None:
        times = times.tz_localize('UTC')
    pos = pvlib.solarposition.get_solarposition(times, lat, lon)
    return pos['apparent_zenith'].to_numpy()


def split_ghi_erbs(ghi, times_utc, lat: float, lon: float) -> Tuple[np.ndarray, np.ndarray]:
    """
    DNI and DHI from GHI alone, by the Erbs diffuse-fraction correlation.

    For sources that only provide global irradiance (ERA5 `ssrd`).
    """
    import pvlib
    ghi = np.clip(np.asarray(ghi, dtype=float), 0.0, None)
    times = pd.DatetimeIndex(times_utc)
    if times.tz is None:
        times = times.tz_localize('UTC')
    zenith = solar_zenith(times, lat, lon)
    out = pvlib.irradiance.erbs(ghi, zenith, times)
    dni = np.nan_to_num(np.asarray(out['dni'], dtype=float))
    dhi = np.nan_to_num(np.asarray(out['dhi'], dtype=float))
    low_sun = zenith > MAX_ZENITH_FOR_BEAM
    dni[low_sun] = 0.0
    dhi[low_sun] = ghi[low_sun]
    return np.clip(dni, 0.0, DNI_CAP), np.clip(dhi, 0.0, None)


def split_from_direct_horizontal(ghi, direct_horizontal, times_utc, lat: float,
                                 lon: float) -> Tuple[np.ndarray, np.ndarray]:
    """
    DNI and DHI when the source provides the beam component on a horizontal surface
    (BARRA `rsdsdir`): DNI = beam_h / cos(zenith), DHI = GHI - beam_h.
    """
    ghi = np.clip(np.asarray(ghi, dtype=float), 0.0, None)
    beam_h = np.clip(np.asarray(direct_horizontal, dtype=float), 0.0, None)
    beam_h = np.minimum(beam_h, ghi)
    zenith = solar_zenith(times_utc, lat, lon)
    cos_z = np.cos(np.radians(zenith))
    low_sun = zenith > MAX_ZENITH_FOR_BEAM
    with np.errstate(divide='ignore', invalid='ignore'):
        dni = np.where(low_sun, 0.0, beam_h / cos_z)
    dhi = np.where(low_sun, ghi, ghi - beam_h)
    return np.clip(np.nan_to_num(dni), 0.0, DNI_CAP), np.clip(dhi, 0.0, None)


def relative_humidity(temp_c, dewpoint_c) -> np.ndarray:
    """Relative humidity (%) from temperature and dew point, Magnus formula."""
    a, b = 17.625, 243.04
    t = np.asarray(temp_c, dtype=float)
    td = np.asarray(dewpoint_c, dtype=float)
    rh = 100.0 * np.exp(a * td / (b + td) - a * t / (b + t))
    return np.clip(rh, 0.0, 100.0)


def dewpoint(temp_c, rh_percent) -> np.ndarray:
    """Dew point (degrees C) from temperature and relative humidity, Magnus formula."""
    a, b = 17.625, 243.04
    t = np.asarray(temp_c, dtype=float)
    rh = np.clip(np.asarray(rh_percent, dtype=float), 1.0, 100.0)
    gamma = np.log(rh / 100.0) + a * t / (b + t)
    return b * gamma / (a - gamma)
