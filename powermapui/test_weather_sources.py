"""
Tests for the weather sources behind SAM: the BARRA-C2 fetch/cache/CSV service, the
shared irradiance splitting, the ERA5 GRIB radiation fix, the processor's source switch,
solar time zone and hub-height bracketing, and the SCADA comparison metrics.

No test touches the network: BARRA-C2 requests are replaced by synthetic series.
"""

import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
import pandas as pd
from django.test import SimpleTestCase, TestCase

from powermapui.views.sam_resource_processor import SAMResourceProcessor, WeatherData
from siren_web.services import barra_c2
from siren_web.utilities import solar_geometry as sg

LAT, LON = -31.65, 117.29

ASCII_SAMPLE = (
    'Dataset {\n    Grid {\n    } rsds;\n} x.nc;\n'
    '---------------------------------------------\n'
    'rsds.rsds[4][1][1]\n[0][0], 164715\n[1][0], 213252\n[2][0], 242789\n[3][0], 199034\n\n'
    'rsds.time[4]\n27425.020833333332, 27425.0625, 27425.104166666668, 27425.145833333332\n\n'
    'rsds.lat[1]\n-31.01\n\nrsds.lon[1]\n115.98\n\n\n'
)

DAS_SAMPLE = '''Attributes {
    time {
        String units "days since 1949-12-01";
        String calendar "proleptic_gregorian";
    }
    rsds {
        Int32 _FillValue -2147483647;
        String units "W m-2";
        Float64 add_offset 0.0;
        Float64 scale_factor 0.00390625;
    }
}'''


def synthetic_month(var, year, month, i, j):
    """What fetch_point returns, built locally: plausible values in BARRA's units."""
    n = barra_c2._n_times_hint(year, month)
    start = pd.Timestamp(year=year, month=month, day=1, tz='UTC')
    mean_var = var in ('rsds', 'rsdsdir')
    times = start + pd.to_timedelta(np.arange(n), unit='h') + pd.Timedelta(minutes=30 if mean_var else 0)
    if mean_var:
        cos_z = np.clip(np.cos(np.radians(sg.solar_zenith(times, LAT, LON))), 0, None)
        ghi = 1000.0 * cos_z
        values = ghi if var == 'rsds' else 0.75 * ghi
        units = 'W m-2'
    elif var == 'tas':
        values, units = np.full(n, 293.15), 'K'
    elif var == 'ps':
        values, units = np.full(n, 98000.0), 'Pa'
    elif var == 'hurs':
        values, units = np.full(n, 50.0), '%'
    else:  # wind components: speed grows with height, blowing from the west
        height = {'uas': 10, 'vas': 10}.get(var) or int(var[2:-1])
        values = np.full(n, 4.0 + height / 25.0) if var.startswith('u') else np.zeros(n)
        units = 'm s-1'
    return pd.DatetimeIndex(times), values.astype(float), units


class BarraParsingTests(SimpleTestCase):

    def test_ascii_response_is_parsed_into_named_arrays(self):
        arrays = barra_c2.parse_ascii(ASCII_SAMPLE)
        self.assertEqual(list(arrays['rsds']), [164715, 213252, 242789, 199034])
        self.assertEqual(len(arrays['time']), 4)
        self.assertAlmostEqual(arrays['lat'][0], -31.01)

    def test_das_attributes_are_read_per_variable(self):
        attrs = barra_c2.parse_das(DAS_SAMPLE, 'rsds')
        self.assertEqual(attrs['units'], 'W m-2')
        self.assertEqual(attrs['scale_factor'], 0.00390625)
        self.assertEqual(attrs['_FillValue'], -2147483647)
        self.assertEqual(barra_c2.parse_das(DAS_SAMPLE, 'time')['units'], 'days since 1949-12-01')

    def test_fetch_point_unpacks_values_and_times(self):
        def fake_get(url):
            return DAS_SAMPLE if url.endswith('.das') else ASCII_SAMPLE
        with mock.patch.object(barra_c2, '_get', side_effect=fake_get), \
                mock.patch.object(barra_c2, '_n_times_hint', return_value=4):
            times, values, units = barra_c2.fetch_point('rsds', 2025, 1, 367, 199)
        self.assertAlmostEqual(values[0], 164715 * 0.00390625)
        self.assertEqual(str(times[0]), '2025-01-01 00:30:00+00:00')
        self.assertEqual(units, 'W m-2')


class PlaceOnHoursTests(SimpleTestCase):

    def test_half_past_and_on_the_hour_samples_land_in_the_same_row(self):
        rows = barra_c2.hour_rows(2025)
        mean = barra_c2.place_on_hours(rows + pd.Timedelta(minutes=30), np.arange(len(rows), dtype=float), 2025)
        inst = barra_c2.place_on_hours(rows, np.arange(len(rows), dtype=float), 2025)
        np.testing.assert_array_equal(mean, inst)
        self.assertEqual(len(mean), 8760)

    def test_short_gaps_are_interpolated_and_long_gaps_raise(self):
        rows = barra_c2.hour_rows(2025)
        values = np.arange(len(rows), dtype=float)
        short = np.delete(np.arange(len(rows)), [100, 101])
        out = barra_c2.place_on_hours(rows[short], values[short], 2025)
        self.assertAlmostEqual(out[100], 100.0)
        long_gap = np.delete(np.arange(len(rows)), range(200, 240))
        with self.assertRaises(barra_c2.BarraError):
            barra_c2.place_on_hours(rows[long_gap], values[long_gap], 2025)

    def test_units_are_converted_and_unexpected_units_rejected(self):
        np.testing.assert_allclose(barra_c2._to_si('tas', np.array([273.15]), 'K'), [0.0])
        with self.assertRaises(barra_c2.BarraError):
            barra_c2._to_si('tas', np.array([1.0]), 'furlongs')


class IrradianceSplitTests(SimpleTestCase):

    def setUp(self):
        self.times = sg.hour_midpoints_utc(pd.date_range('2025-01-15', periods=24, freq='h', tz='UTC'))
        self.zenith = sg.solar_zenith(self.times, LAT, LON)

    def test_noon_is_near_four_utc_in_western_australia(self):
        # Solar noon at 117.3 E in mid-January is about 04:20 UTC (12:20 AWST), so the
        # hour whose midpoint is nearest is the one starting at 04:00 (midpoint 04:30).
        self.assertEqual(int(np.argmin(self.zenith)), 4)

    def test_beam_and_diffuse_rebuild_ghi(self):
        ghi = 900.0 * np.clip(np.cos(np.radians(self.zenith)), 0, None)
        dni, dhi = sg.split_from_direct_horizontal(ghi, 0.7 * ghi, self.times, LAT, LON)
        up = self.zenith < sg.MAX_ZENITH_FOR_BEAM
        np.testing.assert_allclose(dni[up] * np.cos(np.radians(self.zenith[up])) + dhi[up], ghi[up], atol=0.5)
        self.assertTrue(np.all(dni[~up] == 0))

    def test_erbs_split_gives_beam_at_noon_and_nothing_at_night(self):
        ghi = 900.0 * np.clip(np.cos(np.radians(self.zenith)), 0, None)
        dni, dhi = sg.split_ghi_erbs(ghi, self.times, LAT, LON)
        self.assertGreater(dni[3], 300)
        night = self.zenith > 95
        self.assertTrue(np.all(dni[night] == 0) and np.all(dhi[night] == 0))

    def test_dewpoint_and_humidity_round_trip(self):
        td = sg.dewpoint([25.0], [40.0])
        self.assertAlmostEqual(float(sg.relative_humidity([25.0], td)[0]), 40.0, places=3)


class BarraCacheTests(SimpleTestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        root = barra_c2.cache_root(self.dir)
        root.mkdir(parents=True)
        lat = np.round(np.arange(-45.69, -5.0, 0.04), 2)
        lon = np.round(np.arange(108.02, 159.92, 0.04), 2)
        np.savez(root / 'grid.npz', lat=lat, lon=lon)

    def test_grid_cell_is_the_cell_holding_the_point(self):
        i, j, cell_lat, cell_lon = barra_c2.grid_cell(LAT, LON, self.dir)
        self.assertLessEqual(abs(cell_lat - LAT), 0.02)
        self.assertLessEqual(abs(cell_lon - LON), 0.02)
        with self.assertRaises(barra_c2.BarraError):
            barra_c2.grid_cell(-50.0, LON, self.dir)

    def test_cached_file_is_used_without_any_request(self):
        _, _, cell_lat, cell_lon = barra_c2.grid_cell(LAT, LON, self.dir)
        path = barra_c2.csv_path('solar', cell_lat, cell_lon, 2025, self.dir)
        path.parent.mkdir(parents=True)
        path.write_text('cached')
        with mock.patch.object(barra_c2, 'fetch_point', side_effect=AssertionError('network')):
            self.assertEqual(barra_c2.get_or_fetch('solar', LAT, LON, 2025, self.dir), path)

    def test_built_files_read_back_through_the_sam_parser(self):
        processor = SAMResourceProcessor(str(self.dir))
        with mock.patch.object(barra_c2, 'fetch_point', side_effect=synthetic_month):
            solar_path = barra_c2.get_or_fetch('solar', LAT, LON, 2025, self.dir)
            wind_path = barra_c2.get_or_fetch('wind', LAT, LON, 2025, self.dir)
        solar = processor.load_weather_data(solar_path)
        self.assertEqual(len(solar.ghi), 8760)
        self.assertEqual(solar.utc_offset_hours, 0)
        self.assertEqual(solar.year, 2025)
        self.assertGreater(max(solar.dni), 500)
        wind = processor.load_weather_data(wind_path)
        self.assertEqual(len(wind.wind_speed), 8760)
        self.assertAlmostEqual(wind.wind_speed[0], 8.0, places=2)     # 4 + 100/25
        self.assertAlmostEqual(wind.wind_speed_10m[0], 4.4, places=2)
        self.assertAlmostEqual(wind.wind_speed_50m[0], 6.0, places=2)
        self.assertAlmostEqual(wind.wind_speed_150m[0], 10.0, places=2)
        # Raw variable-months were cached, so a rebuild needs no requests
        self.assertTrue(any((barra_c2.cache_root(self.dir) / 'raw').rglob('ua150m_202512.npz')))

    def test_processor_routes_barra_requests_to_the_cache(self):
        processor = SAMResourceProcessor(str(self.dir), weather_source='barra_c2')
        with mock.patch.object(barra_c2, 'fetch_point', side_effect=synthetic_month):
            path = processor.get_weather_file_path(LAT, LON, 'wind', '2025')
        self.assertIn('barra_c2', str(path))
        with mock.patch.object(barra_c2, 'fetch_point', side_effect=barra_c2.BarraError('down')):
            self.assertIsNone(processor.get_weather_file_path(LAT, LON, 'solar', '2025'))


class ProcessorTimeAndHeightTests(SimpleTestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.facility = SimpleNamespace(facility_name='Synthetic', facility_code='SYNTH_TEST',
                                        latitude=LAT, longitude=LON)

    def sam_csv_header(self, utc_offset, year):
        processor = SAMResourceProcessor(self._tmp.name)
        path = processor._create_sam_csv_weather_file([0.0] * 8760, [0.0] * 8760, [0.0] * 8760,
                                                      [20.0] * 8760, [3.0] * 8760, self.facility,
                                                      utc_offset_hours=utc_offset, year=year)
        try:
            lines = path.read_text().splitlines()
        finally:
            path.unlink()
        return lines[1].split(','), lines[3].split(',')

    def test_utc_rows_are_declared_utc_with_their_own_year_at_mid_hour(self):
        header, first = self.sam_csv_header(0, 2025)
        self.assertEqual(header[7], '0')
        self.assertEqual(first[:5], ['2025', '1', '1', '0', '30'])

    def test_legacy_local_rows_keep_awst_and_a_leap_year_is_stamped_non_leap(self):
        header, first = self.sam_csv_header(None, 2024)
        self.assertEqual(header[7], '8')
        self.assertEqual(first[:5], ['2019', '1', '1', '0', '0'])

    def test_bracket_profile_interpolates_between_the_levels_around_the_hub(self):
        n = 3
        weather = WeatherData(wind_speed=[8.0] * n, wind_speed_10m=[5.0] * n,
                              wind_speed_50m=[7.0] * n, wind_speed_150m=[9.0] * n)
        bracket = SAMResourceProcessor(self._tmp.name, wind_profile='bracket')
        speeds, method = bracket._hub_speeds(weather, 130.0)
        self.assertIn('100-150', method)
        self.assertTrue(8.0 < speeds[0] < 9.0)
        old = SAMResourceProcessor(self._tmp.name, wind_profile='10-100')
        old_speeds, old_method = old._hub_speeds(weather, 130.0)
        self.assertEqual(old_method, 'profile')
        self.assertNotAlmostEqual(old_speeds[0], speeds[0], places=3)

    def test_era5_files_without_extra_levels_are_unchanged_by_the_bracket_profile(self):
        weather = WeatherData(wind_speed=[8.0] * 3, wind_speed_10m=[5.0] * 3)
        a, _ = SAMResourceProcessor(self._tmp.name, wind_profile='bracket')._hub_speeds(weather, 130.0)
        b, _ = SAMResourceProcessor(self._tmp.name, wind_profile='10-100')._hub_speeds(weather, 130.0)
        self.assertEqual(a, b)

    def test_unknown_source_is_rejected(self):
        with self.assertRaises(ValueError):
            SAMResourceProcessor(self._tmp.name, weather_source='merra')


class Era5RadiationFixTests(SimpleTestCase):
    """ERA5 steps are per-hour accumulations: placed at valid time - 1 h, never differenced."""

    def test_hourly_accumulations_pass_through_undifferenced(self):
        import xarray as xr
        from siren_web.management.commands.grib_to_sam_csv import Command
        hours = pd.date_range('2025-01-01', periods=48, freq='h').values
        init = pd.to_datetime(['2024-12-31T18:00', '2025-01-01T06:00',
                               '2025-01-01T18:00', '2025-01-02T06:00']).values
        steps = pd.to_timedelta(np.arange(1, 13), unit='h').values
        valid = init[:, None] + steps[None, :]
        # The accumulation for the hour ending at V is (hours since 2025-01-01 at V) x 3600
        per_hour = ((valid - np.datetime64('2025-01-01')) / np.timedelta64(1, 'h')).astype(float) * 3600
        data = per_hour[:, :, None, None] * np.ones((1, 1, 1, 1))
        ds = xr.Dataset({'ssrd': (('time', 'step', 'latitude', 'longitude'), data),
                         'ssr': (('time', 'step', 'latitude', 'longitude'), data)},
                        coords={'time': init, 'step': steps, 'latitude': [-31.0], 'longitude': [116.0],
                                'valid_time': (('time', 'step'), valid)})
        cmd = Command()
        cmd.xr = xr
        cmd.times, cmd.lats, cmd.lons = hours, np.array([-31.0]), np.array([116.0])
        cmd.stdout = mock.Mock()
        cmd.process_accumulated_radiation([ds])
        # Row h (hour starting h) holds the value valid at h+1, i.e. (h+1) x 3600. The
        # forecasts end at 18:00 on 2 January, which covers rows 0-41.
        np.testing.assert_allclose(cmd.ssrd_hourly[:42, 0, 0], (np.arange(42) + 1) * 3600.0)
        # Later rows have no value in the files (like the last hour of a year): each is
        # filled from the same hour a day earlier
        np.testing.assert_allclose(cmd.ssrd_hourly[42:48, 0, 0], cmd.ssrd_hourly[18:24, 0, 0])


class ComparisonMetricTests(SimpleTestCase):

    def setUp(self):
        from siren_web.management.commands import compare_weather_sources as cws
        self.cws = cws
        hours = np.arange(24 * 60)
        self.obs = np.clip(50 * np.sin((hours % 24 - 22) / 24 * 2 * np.pi), 0, None) + 1.0

    def test_identical_series_score_perfectly(self):
        m = self.cws.score(self.obs, self.obs, 100.0)
        self.assertAlmostEqual(m['r_hour'], 1.0)
        self.assertAlmostEqual(m['energy'], 1.0)
        self.assertEqual(m['lag'], 0)
        self.assertAlmostEqual(m['nrmse'], 0.0)

    def test_a_shifted_simulation_is_reported_as_a_lag(self):
        early = self.cws._shift(self.obs, -2)  # simulation two hours early
        self.assertEqual(self.cws.score(early, self.obs, 100.0)['lag'], 2)

    def test_curtailment_mask_drops_hours_where_scada_is_off_but_sim_is_high(self):
        sunny = np.flatnonzero(self.obs > 31)[:10]  # simulation above 30% of 100 MW
        obs = self.obs.copy()
        obs[sunny] = 0.0
        sim, masked_obs, dropped = self.cws.masked(self.obs, obs, 100.0)
        self.assertEqual(dropped, len(sunny))
        self.assertTrue(np.isnan(masked_obs[sunny]).all() and np.isnan(sim[sunny]).all())


class GenerationBiasServiceTests(SimpleTestCase):

    def test_factor_scales_and_caps_at_capacity(self):
        from siren_web.services import generation_bias as gb
        np.testing.assert_allclose(gb.apply_factor([10.0, 50.0], 0.8), [8.0, 40.0])
        np.testing.assert_allclose(gb.apply_factor([10.0, 90.0], 1.5, capacity_kw=100.0), [15.0, 100.0])

    def test_energy_factor_uses_only_hours_where_both_exist(self):
        from siren_web.services import generation_bias as gb
        sim = np.array([10.0, 10.0, 10.0, np.nan])
        obs = np.array([8.0, 8.0, np.nan, 100.0])
        self.assertAlmostEqual(gb.fit_energy_factor(sim, obs), 0.8)
        self.assertIsNone(gb.fit_energy_factor([0.0], [5.0]))

    def test_only_sound_fits_are_stored(self):
        from siren_web.management.commands.compare_weather_sources import Command
        good = {'r_hour': 0.8}
        status = Command._bias_status
        self.assertEqual(status(0.9, good, 'barra_c2', 'bracket', ['wind'], 0.5, 1.5, 0.6), 'ok')
        self.assertIn('bracket', status(0.9, good, 'barra_c2', '10-100', ['wind'], 0.5, 1.5, 0.6))
        self.assertIn('r_hour', status(0.9, {'r_hour': 0.4}, 'barra_c2', 'bracket', ['wind'], 0.5, 1.5, 0.6))
        self.assertIn('outside', status(0.3, good, 'era5', 'bracket', ['solar'], 0.5, 1.5, 0.6))


class GenerationBiasInSimulationTests(TestCase):
    """The stored factor is applied inside the SAM run, per weather source."""

    def setUp(self):
        from datetime import date
        from siren_web.models import FacilityWindTurbines, Technologies, facilities
        tech = Technologies.objects.create(
            technology_name='Onshore Wind', technology_signature='ONW', category='Wind',
            renewable=1, dispatchable=0, fuel_type='WIND')
        self.facility = facilities.objects.create(
            facility_name='Bias Farm', facility_code='BIASFARM', active=True, existing=True,
            status='operating', commissioning_date=date(2020, 1, 1), latitude=-31.0, longitude=116.0,
            idtechnologies=tech, capacity=10.0)
        FacilityWindTurbines.objects.create(idfacilities=self.facility, idtechnologies=tech,
                                            no_turbines=2, nameplate_capacity=10.0)

    def run_sam(self, source, apply_bias=True, kw=6000.0):
        from powermapui.views.sam_resource_processor import SimulationResults
        from powermatchui.views import power_views
        turbine = SimpleNamespace(name='T', kind='named', installation_capacity_mw=10.0, basis='')
        sam = SimulationResults(annual_energy=kw * 8760, hourly_generation=[kw] * 8760, capacity_factor=60.0)
        with mock.patch.object(power_views, 'resolve_wind_installation', return_value=turbine), \
                mock.patch.object(power_views, 'process_wind_installation', return_value=sam):
            results, _ = power_views.process_hybrid_facility(
                SimpleNamespace(weather_source=source), self.facility, '2025', apply_bias=apply_bias)
        return results

    def test_no_factor_leaves_output_alone(self):
        self.assertEqual(self.run_sam('barra_c2').hourly_generation[0], 6000.0)

    def test_factor_applies_only_to_its_own_source_and_can_be_bypassed(self):
        from siren_web.services import generation_bias as gb
        gb.set_factor(self.facility.idfacilities, 'barra_c2', 0.8, fitted_year=2025)
        barra = self.run_sam('barra_c2')
        self.assertAlmostEqual(barra.hourly_generation[0], 4800.0)
        self.assertAlmostEqual(barra.annual_energy, 4800.0 * 8760)
        self.assertAlmostEqual(barra.capacity_factor, 48.0)
        self.assertEqual(barra.additional_metrics['bias_factor'], 0.8)
        self.assertEqual(self.run_sam('era5').hourly_generation[0], 6000.0)
        self.assertEqual(self.run_sam('barra_c2', apply_bias=False).hourly_generation[0], 6000.0)

    def test_a_factor_above_one_is_capped_at_capacity(self):
        from siren_web.services import generation_bias as gb
        gb.set_factor(self.facility.idfacilities, 'barra_c2', 1.4)
        self.assertAlmostEqual(self.run_sam('barra_c2', kw=9000.0).hourly_generation[0], 10000.0)
        self.assertTrue(gb.clear_factor(self.facility.idfacilities, 'barra_c2'))
        self.assertIsNone(gb.get_factor(self.facility.idfacilities, 'barra_c2'))


class LocalTimeWindowTests(SimpleTestCase):
    """Peak-hour windows are AWST; the hourly series are UTC-indexed."""

    def test_peak_filter_selects_local_evening_hours(self):
        from powerplotui.services.time_series_aligner import TimeSeriesAligner
        hours = list(range(1, 49))  # 1-based UTC hours of 1-2 January
        aligned = {'hours': hours, 'scada_values': hours, 'supply_values': hours,
                   'overlap_percentage': 100, 'scada_only_hours': 0, 'supply_only_hours': 0,
                   'total_unique_hours': 48}
        out = TimeSeriesAligner().filter_aligned_to_peak_hours(aligned, 'peak')
        # 4pm-9pm AWST is 08:00-13:00 UTC, i.e. UTC hours of year 9-13 on day one
        self.assertEqual(out['hours'][:5], [9, 10, 11, 12, 13])
        wrapped = TimeSeriesAligner().filter_aligned_to_peak_hours(aligned, 'excl_midday')
        self.assertEqual(len(wrapped['hours']), 2 * 17)  # 4pm-9am is 17 hours a day

    def test_window_mask_matches_local_hours(self):
        from siren_web.services.generation_bias import window_mask
        m = window_mask(24, 10, 15)  # 10am-3pm AWST = 02:00-07:00 UTC
        self.assertEqual(list(np.flatnonzero(m)), [2, 3, 4, 5, 6])
        self.assertEqual(window_mask(24, 16, 9).sum(), 17)
        self.assertTrue(window_mask(24, 0, 24).all())


class BiasFitAndEndpointTests(TestCase):

    def setUp(self):
        from datetime import date
        from django.contrib.auth import get_user_model
        from siren_web.models import FacilityWindTurbines, Technologies, facilities
        tech = Technologies.objects.create(
            technology_name='Onshore Wind', technology_signature='ONW', category='Wind',
            renewable=1, dispatchable=0, fuel_type='WIND')
        self.facility = facilities.objects.create(
            facility_name='Fit Farm', facility_code='FITFARM', active=True, existing=True,
            status='operating', commissioning_date=date(2020, 1, 1), latitude=-31.0, longitude=116.0,
            idtechnologies=tech, capacity=10.0)
        FacilityWindTurbines.objects.create(idfacilities=self.facility, idtechnologies=tech,
                                            no_turbines=2, nameplate_capacity=10.0)
        self.user = get_user_model().objects.create_user('tester', password='pw')

    def fake_run(self):
        """SAM gives 5 MW every hour; SCADA is 4 MW, but 0 at local midday (curtailed)."""
        from powermapui.views.sam_resource_processor import SimulationResults
        sim = SimulationResults(annual_energy=0, hourly_generation=[5000.0] * 8760, capacity_factor=50.0)
        local = (np.arange(8760) + 8) % 24
        scada = np.where((local >= 10) & (local < 15), 0.0, 4.0)
        return (mock.patch('powermatchui.views.power_views.process_hybrid_facility', return_value=(sim, None)),
                mock.patch('siren_web.services.generation_bias.scada_hourly_mw', return_value=scada),
                mock.patch('powermapui.views.sam_resource_processor.SAMResourceProcessor'))

    def test_window_choice_removes_midday_curtailment_from_the_fit(self):
        from siren_web.services import generation_bias as gb
        p1, p2, p3 = self.fake_run()
        with p1, p2, p3:
            # 0 MW SCADA vs 5 MW simulated is 50% of capacity, so the mask drops midday anyway
            masked_all = gb.fit_facility(self.facility, 2025, (0, 24), 'barra_c2')
            outside = gb.fit_facility(self.facility, 2025, (16, 9), 'barra_c2', 'excl_midday')
        self.assertAlmostEqual(masked_all['factor'], 0.8)
        self.assertAlmostEqual(outside['factor'], 0.8)
        self.assertEqual(masked_all['masked_hours'], 365 * 5)
        self.assertEqual(outside['hours'], 365 * 17)

    def test_endpoint_requires_login_and_fits_saves_and_clears(self):
        from siren_web.services import generation_bias as gb
        url = '/facility_generation_bias/'
        fid = self.facility.idfacilities
        self.assertEqual(self.client.get(url, {'facility_id': fid}).status_code, 302)
        self.client.force_login(self.user)
        info = self.client.get(url, {'facility_id': fid}).json()
        self.assertIsNone(info['stored_factor'])
        self.assertEqual(info['recommended_window'], 'excl_midday')

        good = {'factor': 0.85, 'status': 'ok', 'facility_id': fid, 'year': 2025,
                'weather_source': 'barra_c2', 'window': 'excl_midday', 'hours': 5000,
                'r_hour': 0.8, 'scada_energy_mwh': 1.0, 'simulated_energy_mwh': 1.0,
                'stored_factor': None}
        with mock.patch.object(gb, 'fit_facility', return_value=dict(good)):
            fit = self.client.post(url, {'facility_id': fid, 'year': 2025, 'peak_filter': 'excl_midday',
                                         'action': 'fit'}).json()
            self.assertFalse(fit['saved'])
            self.assertIsNone(gb.get_factor(fid, 'barra_c2'))
            saved = self.client.post(url, {'facility_id': fid, 'year': 2025, 'peak_filter': 'excl_midday',
                                           'action': 'save'}).json()
        self.assertTrue(saved['saved'])
        self.assertAlmostEqual(gb.get_factor(fid, 'barra_c2'), 0.85)

        bad = dict(good, status='not storable: hourly correlation 0.40 is below 0.6')
        with mock.patch.object(gb, 'fit_facility', return_value=bad):
            refused = self.client.post(url, {'facility_id': fid, 'year': 2025, 'action': 'save'})
        self.assertEqual(refused.status_code, 400)
        self.assertAlmostEqual(gb.get_factor(fid, 'barra_c2'), 0.85)

        cleared = self.client.post(url, {'facility_id': fid, 'action': 'clear'}).json()
        self.assertTrue(cleared['cleared'])
        self.assertIsNone(gb.get_factor(fid, 'barra_c2'))
