"""
BARRA-C2 weather for one facility: fetch from NCI, cache, and write SAM CSVs.

BARRA-C2 is the Bureau of Meteorology's 4.4 km (0.04 degree) convection-permitting
reanalysis for Australia, hourly from 1979 and running a few months behind real time.
It is published on NCI's THREDDS server (project ob53) as one NetCDF file per variable
per month. Only one grid cell's time series is needed per facility, so each request
asks the server's OPeNDAP endpoint for that one cell as plain text: about 4 seconds and
40 KB per variable-month, with no login and no NetCDF network client needed.

Cache layout, under WEATHER_DATA_DIR/barra_c2/:
    grid.npz                                   the lat/lon axes (fetched once)
    raw/<i>_<j>/<var>_<YYYYMM>.npz             each variable-month as fetched, so an
                                               interrupted year resumes where it stopped
    {wind,solar}_weather/<year>/<tech>_<lat>_<lon>_<year>.csv
                                               the SAM CSVs, named like the ERA5 ones

The CSVs use the same layouts the ERA5 converters write, so the existing parser and
SAM paths read them unchanged. Every row is one UTC hour, labelled by the start of the
hour: hourly means BARRA stamps at HH:30 and instantaneous values stamped HH:00 both
land in row HH. The wind CSV adds speed columns at 50 m and 150 m after the usual
10 m / 100 m columns.
"""

import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

import numpy as np
import pandas as pd
import requests

from siren_web.utilities.solar_geometry import (
    dewpoint, hour_midpoints_utc, split_from_direct_horizontal,
)

logger = logging.getLogger(__name__)

THREDDS_BASE = ('https://thredds.nci.org.au/thredds/dodsC/ob53/output/reanalysis/AUST-04/'
                'BOM/ERA5/historical/hres/BARRA-C2/v1/1hr')
CACHE_SUBDIR = 'barra_c2'

SOLAR_VARS = ('rsds', 'rsdsdir', 'tas', 'hurs', 'ps', 'uas', 'vas')
WIND_VARS = ('uas', 'vas', 'ua50m', 'va50m', 'ua100m', 'va100m', 'ua150m', 'va150m',
             'tas', 'ps')
VARS_FOR = {'solar': SOLAR_VARS, 'wind': WIND_VARS}

# A cell is only accepted when the point lies within it (half the 0.04 degree spacing,
# plus a little slack for rounding of the axis values).
CELL_TOLERANCE_DEG = 0.021
# Short runs of missing hours are interpolated; anything longer fails the build.
MAX_GAP_HOURS = 6

REQUEST_TIMEOUT_S = 300
RETRY_DELAYS_S = (5, 15, 45, 120)
_DASHES = '-' * 45

_session = None


class BarraError(Exception):
    """BARRA-C2 data could not be fetched or assembled."""


# --------------------------------------------------------------------------- network

def month_url(var: str, year: int, month: int) -> str:
    ym = f'{year:04d}{month:02d}'
    return (f'{THREDDS_BASE}/{var}/latest/'
            f'{var}_AUST-04_ERA5_historical_hres_BOM_BARRA-C2_v1_1hr_{ym}-{ym}.nc')


def _get(url: str) -> str:
    """GET with retries and backoff. Requests are made one at a time, on purpose."""
    global _session
    if _session is None:
        _session = requests.Session()
    last_error = None
    for attempt, delay in enumerate((0,) + RETRY_DELAYS_S):
        if delay:
            time.sleep(delay)
        try:
            response = _session.get(url, timeout=REQUEST_TIMEOUT_S)
            if response.status_code == 404:
                raise BarraError(f'Not on the server (404): {url}')
            response.raise_for_status()
            return response.text
        except BarraError:
            raise
        except requests.RequestException as e:
            last_error = e
            logger.warning(f'BARRA-C2 request failed (attempt {attempt + 1}): {e}')
    raise BarraError(f'Request failed after {len(RETRY_DELAYS_S) + 1} attempts: {last_error}')


def parse_ascii(text: str) -> Dict[str, np.ndarray]:
    """
    Parse an OPeNDAP .ascii response into {short name: flat float array}.

    The data section follows a line of dashes and holds blank-line-separated blocks:
        rsds.rsds[744][1][1]          rsds.time[744]
        [0][0], 164715                27425.0208, 27425.0625, ...
        [1][0], 213252
    """
    if _DASHES not in text:
        raise BarraError(f'Unexpected OPeNDAP response: {text[:200]!r}')
    body = text.split(_DASHES, 1)[1]
    arrays = {}
    for block in re.split(r'\n\s*\n', body.strip()):
        lines = block.strip().splitlines()
        if not lines:
            continue
        name = lines[0].split('[', 1)[0].strip().split('.')[-1]
        values = []
        for line in lines[1:]:
            line = re.sub(r'^(\[\d+\])+,\s*', '', line.strip())
            values.extend(float(v) for v in line.split(',') if v.strip())
        arrays[name] = np.asarray(values, dtype=float)
    return arrays


def parse_das(text: str, var: str) -> Dict[str, object]:
    """The attributes of one variable from an OPeNDAP .das response."""
    match = re.search(rf'\n\s*{re.escape(var)} \{{(.*?)\n\s*\}}', text, re.S)
    if not match:
        raise BarraError(f'No attributes for {var} in the .das response')
    attrs = {}
    for line in match.group(1).splitlines():
        m = re.match(r'\s*\S+\s+(\S+)\s+(.*);\s*$', line)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        if value.startswith('"'):
            attrs[key] = value.strip('"')
        else:
            try:
                attrs[key] = float(value)
            except ValueError:
                attrs[key] = value
    return attrs


def _time_origin(units: str) -> pd.Timestamp:
    m = re.match(r'\s*days since\s+(.+)$', units)
    if not m:
        raise BarraError(f'Unexpected time units {units!r}')
    return pd.Timestamp(m.group(1).strip(), tz='UTC')


def fetch_point(var: str, year: int, month: int, i: int, j: int):
    """
    One variable-month at one cell, from the server.

    Returns (UTC times as a DatetimeIndex, values in the variable's own units with fill
    values as NaN, units string).
    """
    url = month_url(var, year, month)
    das = _get(url + '.das')
    attrs = parse_das(das, var)
    if 'units' not in _time_units_cache:
        _time_units_cache['units'] = str(parse_das(das, 'time')['units'])
    arrays = parse_ascii(_get(f'{url}.ascii?{var}[0:1:{_n_times_hint(year, month) - 1}][{i}][{j}]'))
    raw = arrays.get(var)
    days = arrays.get('time')
    if raw is None or days is None or len(raw) != len(days):
        raise BarraError(f'Incomplete response for {var} {year}-{month:02d}')
    fill = attrs.get('_FillValue')
    values = raw * float(attrs.get('scale_factor', 1.0)) + float(attrs.get('add_offset', 0.0))
    if fill is not None:
        values[raw == float(fill)] = np.nan
    origin = _time_origin(_time_units_cache['units'])
    times = origin + pd.to_timedelta(days, unit='D')
    return pd.DatetimeIndex(times).round('min'), values, str(attrs.get('units', ''))


# Time units of the dataset family, identical across BARRA-C2 files; read from the
# first .das fetched.
_time_units_cache: Dict[str, str] = {}


def _n_times_hint(year: int, month: int) -> int:
    """Hours in the month: the time-axis length of every BARRA-C2 1hr file."""
    start = datetime(year, month, 1)
    end = datetime(year + (month == 12), month % 12 + 1, 1)
    return int((end - start).total_seconds() // 3600)


# ------------------------------------------------------------------------------ grid

def cache_root(weather_data_dir) -> Path:
    return Path(weather_data_dir) / CACHE_SUBDIR


def load_grid(weather_data_dir) -> Tuple[np.ndarray, np.ndarray]:
    """The BARRA-C2 latitude and longitude axes, fetched once and cached."""
    path = cache_root(weather_data_dir) / 'grid.npz'
    if path.exists():
        with np.load(path) as z:
            return z['lat'], z['lon']
    url = month_url('rsds', 2000, 1)
    dds = _get(url + '.dds')
    n_lat = int(re.search(r'lat\[lat = (\d+)\]', dds).group(1))
    n_lon = int(re.search(r'lon\[lon = (\d+)\]', dds).group(1))
    arrays = parse_ascii(_get(f'{url}.ascii?lat[0:1:{n_lat - 1}],lon[0:1:{n_lon - 1}]'))
    lat, lon = arrays['lat'], arrays['lon']
    if len(lat) != n_lat or len(lon) != n_lon:
        raise BarraError('Incomplete BARRA-C2 grid axes')
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, lat=lat, lon=lon)
    return lat, lon


def grid_cell(lat: float, lon: float, weather_data_dir) -> Tuple[int, int, float, float]:
    """(lat index, lon index, cell centre lat, cell centre lon) of the cell holding a point."""
    lats, lons = load_grid(weather_data_dir)
    i = int(np.abs(lats - lat).argmin())
    j = int(np.abs(lons - lon).argmin())
    if abs(lats[i] - lat) > CELL_TOLERANCE_DEG or abs(lons[j] - lon) > CELL_TOLERANCE_DEG:
        raise BarraError(f'({lat}, {lon}) is outside the BARRA-C2 domain')
    return i, j, round(float(lats[i]), 4), round(float(lons[j]), 4)


# ------------------------------------------------------------------- year assembly

def _raw_path(weather_data_dir, i, j, var, year, month) -> Path:
    return cache_root(weather_data_dir) / 'raw' / f'{i}_{j}' / f'{var}_{year:04d}{month:02d}.npz'


def _month_series(weather_data_dir, i, j, var, year, month):
    """One variable-month, from the raw cache or the server (then cached)."""
    path = _raw_path(weather_data_dir, i, j, var, year, month)
    if path.exists():
        with np.load(path) as z:
            return pd.DatetimeIndex(z['times'].astype('datetime64[s]')).tz_localize('UTC'), \
                z['values'], str(z['units'])
    times, values, units = fetch_point(var, year, month, i, j)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp.npz')
    np.savez(tmp, times=times.tz_convert(None).values.astype('datetime64[s]'),
             values=values, units=np.array(units))
    os.replace(tmp, path)
    return times, values, units


def hour_rows(year: int) -> pd.DatetimeIndex:
    """UTC hour starts for every hour of the year."""
    return pd.date_range(f'{year}-01-01', f'{year + 1}-01-01', freq='h',
                         inclusive='left', tz='UTC')


def place_on_hours(times: pd.DatetimeIndex, values: np.ndarray, year: int) -> np.ndarray:
    """
    Put a variable's samples on the year's hourly rows: a sample stamped anywhere in
    [HH:00, HH+1:00) -- HH:30 for hourly means, HH:00 for instantaneous values -- goes
    in row HH. Short gaps are interpolated; longer ones raise.
    """
    rows = hour_rows(year)
    out = np.full(len(rows), np.nan)
    idx = ((times - rows[0]) // pd.Timedelta(hours=1)).to_numpy()
    ok = (idx >= 0) & (idx < len(rows))
    out[idx[ok]] = values[ok]
    missing = np.isnan(out)
    if missing.any():
        series = pd.Series(out)
        filled = series.interpolate(limit=MAX_GAP_HOURS, limit_direction='both').to_numpy()
        if np.isnan(filled).any():
            raise BarraError(f'{int(np.isnan(filled).sum())} hours missing in {year}, '
                             f'including gaps longer than {MAX_GAP_HOURS} h')
        logger.info(f'Interpolated {int(missing.sum())} missing hours')
        out = filled
    return out


def fetch_year(technology: str, i: int, j: int, year: int, weather_data_dir,
               progress: Optional[Callable[[str], None]] = None) -> Dict[str, np.ndarray]:
    """Every variable the technology needs, on the year's hourly rows, in SI units."""
    series = {}
    for var in VARS_FOR[technology]:
        all_times, all_values, units = [], [], ''
        for month in range(1, 13):
            if progress:
                progress(f'{var} {year}-{month:02d}')
            t, v, units = _month_series(weather_data_dir, i, j, var, year, month)
            all_times.append(t)
            all_values.append(v)
        times = all_times[0].append(all_times[1:])
        values = place_on_hours(times, np.concatenate(all_values), year)
        series[var] = _to_si(var, values, units)
    return series


def _to_si(var: str, values: np.ndarray, units: str) -> np.ndarray:
    """Temperatures to degrees C, pressures to Pa; check the units are what we expect."""
    units = units.strip()
    if var == 'tas':
        if units == 'K':
            return values - 273.15
        if units in ('degC', 'C'):
            return values
    elif var == 'ps':
        if units == 'Pa':
            return values
        if units == 'hPa':
            return values * 100.0
    elif var in ('rsds', 'rsdsdir'):
        if units == 'W m-2':
            return values
    elif var == 'hurs':
        if units == '%':
            return values
    elif units in ('m s-1', 'm/s'):
        return values
    raise BarraError(f'Unexpected units {units!r} for {var}')


# ------------------------------------------------------------------------- CSV files

def _speed_dir(u, v):
    speed = np.hypot(u, v)
    direction = (270.0 - np.degrees(np.arctan2(v, u))) % 360.0
    return speed, direction


def csv_path(technology: str, cell_lat: float, cell_lon: float, year: int,
             weather_data_dir) -> Path:
    return (cache_root(weather_data_dir) / f'{technology}_weather' / str(year) /
            f'{technology}_{cell_lat:.4f}_{cell_lon:.4f}_{year}.csv')


def write_solar_csv(path: Path, cell_lat: float, cell_lon: float, year: int,
                    s: Dict[str, np.ndarray]) -> None:
    rows = hour_rows(year)
    ghi = np.clip(s['rsds'], 0.0, None)
    dni, dhi = split_from_direct_horizontal(ghi, s['rsdsdir'], hour_midpoints_utc(rows),
                                            cell_lat, cell_lon)
    tdew = dewpoint(s['tas'], s['hurs'])
    wspd, wdir = _speed_dir(s['uas'], s['vas'])
    pres_mbar = s['ps'] / 100.0
    lines = ['Latitude,Longitude,Time Zone,Elevation',
             f'{cell_lat:.4f},{cell_lon:.4f},0,0',
             'Year,Month,Day,Hour,Minute,GHI,DNI,DHI,Tdry,Tdew,RH,Pres,Wspd,Wdir']
    for k, t in enumerate(rows):
        lines.append(f'{t.year},{t.month},{t.day},{t.hour},0,'
                     f'{ghi[k]:.1f},{dni[k]:.1f},{dhi[k]:.1f},'
                     f'{s["tas"][k]:.1f},{tdew[k]:.1f},{np.clip(s["hurs"][k], 0, 100):.0f},'
                     f'{pres_mbar[k]:.1f},{wspd[k]:.1f},{wdir[k]:.0f}')
    _write_atomic(path, lines)


def write_wind_csv(path: Path, cell_lat: float, cell_lon: float, year: int,
                   s: Dict[str, np.ndarray]) -> None:
    rows = hour_rows(year)
    s10, d10 = _speed_dir(s['uas'], s['vas'])
    s50, _ = _speed_dir(s['ua50m'], s['va50m'])
    s100, d100 = _speed_dir(s['ua100m'], s['va100m'])
    s150, _ = _speed_dir(s['ua150m'], s['va150m'])
    pres_atm = s['ps'] / 101325.0
    lines = [f'SiteID,BARRA-C2_{cell_lat:.2f}_{cell_lon:.2f},Site Timezone,8,Data Timezone,0,'
             f'Longitude,{cell_lon:.4f},Latitude,{cell_lat:.4f},Elevation,0',
             'Temperature at 2m,Pressure at 0m,Speed at 10m,Direction at 10m,'
             'Speed at 100m,Direction at 100m,Speed at 50m,Speed at 150m']
    for k in range(len(rows)):
        lines.append(f'{s["tas"][k]:.2f},{pres_atm[k]:.5f},{s10[k]:.2f},{d10[k]:.0f},'
                     f'{s100[k]:.2f},{d100[k]:.0f},{s50[k]:.2f},{s150[k]:.2f}')
    _write_atomic(path, lines)


def _write_atomic(path: Path, lines) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    with open(tmp, 'w', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')
    os.replace(tmp, path)


# ---------------------------------------------------------------------- entry point

def get_or_fetch(technology: str, lat: float, lon: float, year: int, weather_data_dir,
                 progress: Optional[Callable[[str], None]] = None) -> Path:
    """
    Path to the SAM CSV for the BARRA-C2 cell holding (lat, lon), fetching and caching
    it first if needed. Only the point's own cell is ever used.
    """
    if technology not in VARS_FOR:
        raise BarraError(f'Unknown technology {technology!r}')
    i, j, cell_lat, cell_lon = grid_cell(lat, lon, weather_data_dir)
    path = csv_path(technology, cell_lat, cell_lon, year, weather_data_dir)
    if path.exists():
        return path
    logger.info(f'Fetching BARRA-C2 {technology} {year} for cell ({cell_lat}, {cell_lon})')
    started = time.time()
    series = fetch_year(technology, i, j, year, weather_data_dir, progress)
    writer = write_solar_csv if technology == 'solar' else write_wind_csv
    writer(path, cell_lat, cell_lon, year, series)
    logger.info(f'Wrote {path} in {time.time() - started:.0f} s')
    return path
