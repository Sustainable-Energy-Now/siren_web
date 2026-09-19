"""
Tests for the wind-turbine library, representative-turbine selection and the
SAM wind wiring.

Logic tests use a small synthetic library so they don't depend on the vendored
data; integrity tests run against the real library in TURBINE_LIBRARY_DIR.
"""

import csv
import math
import tempfile
from dataclasses import replace
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from powermapui.utils import representative_turbine as rt
from powermapui.utils import turbine_library as lib
from powermapui.views.sam_resource_processor import SAMResourceProcessor, WeatherData

POW_DIR = Path(settings.POWER_CURVES_DIR)


def generic_curve(rated_kw):
    """0-30 m/s on the library's 0.5 m/s grid: cubic ramp 3-11 m/s, rated to 25, then cut out."""
    speeds = [i * 0.5 for i in range(61)]
    powers = []
    for ws in speeds:
        if ws < 3:
            powers.append(0.0)
        elif ws < 11:
            powers.append(rated_kw * ((ws - 3) / 8) ** 3)
        elif ws < 25:
            powers.append(float(rated_kw))
        else:
            powers.append(0.0)
    return speeds, powers


def write_library(directory, rows):
    """rows: dicts with slug, rated_kw, rotor and optional hub/vintage/application/name."""
    directory = Path(directory)
    (directory / lib.CURVES_SUBDIR).mkdir(parents=True, exist_ok=True)
    with open(directory / lib.INDEX_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(lib.INDEX_COLUMNS)
        for r in rows:
            writer.writerow([
                r['slug'], r.get('name', r['slug']), '', r.get('application', 'onshore'),
                r['rated_kw'], r['rotor'], r.get('hub', ''), '', r.get('vintage', ''),
                'false', 'test', 'test', f"{lib.CURVES_SUBDIR}/{r['slug']}.csv",
            ])
            speeds, powers = generic_curve(r['rated_kw'])
            with open(directory / lib.CURVES_SUBDIR / f"{r['slug']}.csv", 'w', newline='') as cf:
                cw = csv.writer(cf)
                cw.writerow(lib.CURVE_COLUMNS)
                cw.writerows(zip(speeds, powers))


class PowFileTests(SimpleTestCase):
    def test_header_lines_are_not_read_as_power(self):
        # Regression: the old loader read the diameter/cut-out/cut-in header lines as
        # power at 0-3 m/s, shifting the whole curve about 3 m/s to the right.
        pf = lib.parse_pow_file(POW_DIR / 'Vestas V150-4.2Mw.pow')
        self.assertEqual(pf.rotor_diameter, 150.0)
        self.assertEqual(pf.cut_in, 3.0)
        self.assertEqual(pf.cut_out, 22.5)
        curve = dict(zip(pf.wind_speeds, pf.power_kw))
        self.assertEqual([curve[0], curve[1], curve[2]], [0, 0, 0])
        self.assertEqual(curve[3], 42)
        self.assertEqual(curve[4], 257.8)
        self.assertEqual(curve[11], 4200)
        self.assertEqual(pf.rated_kw, 4200)

    def test_rotor_diameter_includes_tenths(self):
        self.assertAlmostEqual(lib.parse_pow_file(POW_DIR / 'E53 52.9m 800kw.pow').rotor_diameter, 52.9)

    def test_every_shipped_pow_file_parses(self):
        files = list(POW_DIR.glob('*.pow'))
        self.assertGreaterEqual(len(files), 20)
        for path in files:
            with self.subTest(file=path.name):
                pf = lib.parse_pow_file(path)
                self.assertGreater(pf.rated_kw, 0)
                self.assertGreater(pf.rotor_diameter, 5)
                # power starts one step after cut-in, i.e. the 1 m/s start is right
                first = next(ws for ws, p in zip(pf.wind_speeds, pf.power_kw) if p > 0)
                self.assertLessEqual(abs(first - pf.cut_in), 1.0)

    def test_find_pow_file_tolerates_manufacturer_prefix(self):
        self.assertEqual(lib.find_pow_file('V150-4.2Mw', POW_DIR).name, 'Vestas V150-4.2Mw.pow')
        self.assertEqual(lib.find_pow_file('E53 52.9m 800kw', POW_DIR).name, 'E53 52.9m 800kw.pow')
        self.assertIsNone(lib.find_pow_file('Mystery X9000', POW_DIR))

    def test_find_pow_file_refuses_ambiguous_match(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'Acme A100.pow').write_text('x')
            (Path(d) / 'Other A100.pow').write_text('x')
            self.assertIsNone(lib.find_pow_file('A100', d))


class CurveNormalisationTests(SimpleTestCase):
    def grid(self, speeds, powers, rated):
        ws, p = lib.normalise_curve(speeds, powers, rated)
        return dict(zip(ws, p))

    def test_linear_interpolation_on_half_metre_grid(self):
        c = self.grid([0, 4, 5, 12, 26], [0, 0, 100, 2000, 2000], 2000)
        self.assertEqual(c[4.5], 50)
        self.assertEqual(len(c), 61)
        self.assertEqual(max(c), 30.0)

    def test_hard_cut_out_holds_rated_until_the_zero_point(self):
        c = self.grid([0, 3, 10, 11, 25, 26], [0, 0, 2000, 4200, 4200, 0], 4200)
        self.assertEqual(c[25.5], 4200)
        self.assertEqual(c[26.0], 0)

    def test_no_generation_below_first_point(self):
        c = self.grid([4, 5, 12], [28, 144, 1650], 1650)
        self.assertEqual(c[3.5], 0)
        self.assertEqual(c[4.0], 28)

    def test_rated_is_held_to_cut_out_past_the_last_point(self):
        c = self.grid([3, 4, 12, 20], [0, 28, 1650, 1650], 1650)
        self.assertEqual(c[24.5], 1650)
        self.assertEqual(c[25.0], 0)

    def test_validation(self):
        speeds = [0, 3, 4, 8, 12, 25]
        fatal, warnings = lib.validate_curve(speeds, [0, 0, 100, 900, 1000, 1000], 1000)
        self.assertEqual((fatal, warnings), ([], []))
        fatal, _ = lib.validate_curve(speeds, [0, 0, 100, 900, 1300, 1300], 1000)
        self.assertTrue(any('from rated' in f for f in fatal))
        fatal, _ = lib.validate_curve([0, 3, 3, 8, 12, 25], [0, 0, 100, 900, 1000, 1000], 1000)
        self.assertTrue(any('increasing' in f for f in fatal))
        fatal, warnings = lib.validate_curve(speeds, [0, -2, 100, 900, 1000, 1000], 1000)
        self.assertEqual(fatal, [])
        self.assertTrue(any('negative' in w for w in warnings))


class VendoredLibraryTests(SimpleTestCase):
    def test_index_and_curves_are_consistent(self):
        index = lib.load_index()
        self.assertGreaterEqual(len(index), 100)
        self.assertEqual(len({t.slug for t in index}), len(index), "slugs must be unique")
        for t in index:
            with self.subTest(slug=t.slug):
                curve = lib.load_curve(t.slug)
                self.assertEqual(len(curve.wind_speeds), 61)
                self.assertEqual(curve.power_kw[0], 0)
                fatal, _ = lib.validate_curve(curve.wind_speeds, curve.power_kw, t.rated_kw)
                self.assertEqual(fatal, [])
                self.assertIn(t.application, ('onshore', 'offshore', 'floating'))

    def test_has_large_onshore_designs_for_the_unspecified_facilities(self):
        big = [t for t in lib.load_index() if t.application == 'onshore' and t.rated_kw >= 5000]
        self.assertGreaterEqual(len(big), 5)

    def test_slug_cannot_escape_the_library(self):
        with self.assertRaises(lib.TurbineLibraryError):
            lib.load_curve('../index')

    def test_index_cache_follows_back_to_back_rewrites(self):
        # Regression: caching on mtime alone served a stale index when a library was
        # rewritten within the filesystem's timestamp granularity.
        with tempfile.TemporaryDirectory() as d:
            for hub in ('', '175', '', '175', ''):
                write_library(d, [dict(slug='t', rated_kw=5000, rotor=150, hub=hub)])
                self.assertEqual(lib.load_index(d)[0].hub_height_m, float(hub) if hub else None)

    def test_missing_index_names_the_fix(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesMessage(lib.TurbineLibraryError, 'import_turbine_library'):
                lib.load_index(d)


class SelectorTests(SimpleTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def select(self, rated_kw, cod_year, rows, **kw):
        write_library(self.dir, rows)
        return rt.select_representative_turbine(rated_kw, cod_year, directory=self.dir, **kw)

    def test_scaled_turbine_keeps_the_requested_rating_exactly(self):
        r = self.select(6000, 2027, [dict(slug='ref5', rated_kw=5000, rotor=150, hub=110, vintage=2023)])
        self.assertEqual(r.reference_slug, 'ref5')
        self.assertAlmostEqual(max(r.power_kw), 6000, places=6)
        self.assertAlmostEqual(r.rated_kw, 6000)
        self.assertAlmostEqual(r.scale, 1.2)

    def test_scaling_holds_specific_power_and_the_wind_speed_axis(self):
        ref = dict(slug='ref5', rated_kw=5000, rotor=150, hub=110, vintage=2023)
        r = self.select(6000, 2027, [ref])
        sp = lambda kw, d: kw * 1000 / (math.pi * (d / 2) ** 2)
        self.assertAlmostEqual(sp(r.rated_kw, r.rotor_diameter), sp(5000, 150), places=6)
        self.assertEqual(r.wind_speeds, tuple(generic_curve(5000)[0]))

    def test_closest_rating_wins(self):
        rows = [dict(slug=f"t{kw}", rated_kw=kw, rotor=int(math.sqrt(kw * 1000 / 260 * 4 / math.pi)), vintage=2023)
                for kw in (3000, 6000, 8000)]
        self.assertEqual(self.select(6300, 2027, rows).reference_slug, 't6000')
        self.assertEqual(self.select(7800, 2027, rows).reference_slug, 't8000')

    def test_vintage_breaks_a_tie(self):
        rows = [dict(slug='old', rated_kw=5000, rotor=150, vintage=2012),
                dict(slug='new', rated_kw=5000, rotor=150, vintage=2024)]
        self.assertEqual(self.select(5000, 2027, rows).reference_slug, 'new')
        self.assertEqual(self.select(5000, 2011, rows).reference_slug, 'old')

    def test_offshore_is_never_picked_for_onshore(self):
        rows = [dict(slug='off6', rated_kw=6000, rotor=170, application='offshore', vintage=2027),
                dict(slug='on4', rated_kw=4000, rotor=145, vintage=2020)]
        self.assertEqual(self.select(6000, 2027, rows).reference_slug, 'on4')
        self.assertEqual(self.select(6000, 2027, rows, application='offshore').reference_slug, 'off6')

    def test_small_turbines_are_not_candidates(self):
        rows = [dict(slug='tiny', rated_kw=800, rotor=53), dict(slug='big', rated_kw=5000, rotor=150)]
        self.assertEqual(self.select(1200, 2027, rows).reference_slug, 'big')

    def test_specific_power_window_prefers_modern_designs(self):
        # same rating: 5 MW on a 100 m rotor (637 W/m2) vs on a 150 m rotor (283 W/m2)
        rows = [dict(slug='old-style', rated_kw=5000, rotor=100, vintage=2023),
                dict(slug='modern', rated_kw=5000, rotor=150, vintage=2023)]
        self.assertEqual(self.select(5000, 2027, rows).reference_slug, 'modern')

    def test_no_onshore_turbine_is_an_error(self):
        rows = [dict(slug='off', rated_kw=6000, rotor=170, application='offshore')]
        with self.assertRaises(rt.NoRepresentativeTurbine):
            self.select(6000, 2027, rows)

    def test_out_of_range_rating_still_resolves_with_a_warning(self):
        with self.assertLogs('powermapui.utils.representative_turbine', 'WARNING'):
            r = self.select(20000, 2030, [dict(slug='ref5', rated_kw=5000, rotor=150)])
        self.assertAlmostEqual(max(r.power_kw), 20000, places=6)

    def test_invalid_rating_is_rejected(self):
        with self.assertRaises(rt.NoRepresentativeTurbine):
            self.select(0, 2027, [dict(slug='ref5', rated_kw=5000, rotor=150)])

    def test_hub_height_rules(self):
        tall = [dict(slug='tall', rated_kw=5000, rotor=150, hub=175)]
        self.assertEqual(self.select(5000, 2027, tall).hub_height, rt.MAX_ASSUMED_HUB_HEIGHT_M)
        self.assertEqual(self.select(5000, 2027, tall, hub_height=125).hub_height, 125)
        self.assertEqual(self.select(5000, 2027, [dict(slug='nohub', rated_kw=5000, rotor=150)]).hub_height,
                         rt.DEFAULT_HUB_HEIGHT_M)

    def test_selection_is_deterministic(self):
        rows = [dict(slug='a', rated_kw=5000, rotor=150), dict(slug='b', rated_kw=5000, rotor=150)]
        self.assertEqual(self.select(5200, 2027, rows), self.select(5200, 2027, rows))

    def test_real_library_serves_the_unspecified_facilities(self):
        # (turbines, MW, commissioning year) for the ten "Unspecified" wind facilities
        cases = [(100, 600, 2027), (400, 3000, 2030), (110, 799.92, 2030), (110, 700.04, 2031),
                 (46, 230, 2027), (82, 549.974, 2030), (25, 200, 2028), (78, 488.982, 2028),
                 (140, 1000.02, 2029), (65, 499.98, 2029)]
        for n, mw, year in cases:
            with self.subTest(turbines=n, mw=mw):
                rated = mw * 1000 / n
                r = rt.select_representative_turbine(rated, year)
                ref = lib.get_turbine(r.reference_slug)
                self.assertEqual(ref.application, 'onshore')
                self.assertAlmostEqual(max(r.power_kw), rated, places=4)
                self.assertGreaterEqual(r.scale, rt.SCALE_MIN)
                self.assertLessEqual(r.scale, rt.SCALE_MAX)
                self.assertLessEqual(r.hub_height, rt.MAX_ASSUMED_HUB_HEIGHT_M)


class ResolveInstallationTests(TestCase):
    """DB-facing resolution: unspecified installations, named turbines, persistence."""

    def setUp(self):
        from siren_web.models import Technologies, facilities
        self.tech = Technologies.objects.create(
            technology_name='Onshore Wind', technology_signature='ONW', category='Wind',
            renewable=1, dispatchable=0, fuel_type='WIND')
        self.facility = facilities.objects.create(
            facility_name='Test Farm', facility_code='TESTFARM', active=True, existing=False,
            status='proposed', commissioning_date=date(2028, 6, 1), latitude=-33.0, longitude=116.0,
            idtechnologies=self.tech)

    def installation(self, **kw):
        from siren_web.models import FacilityWindTurbines
        defaults = dict(idfacilities=self.facility, no_turbines=100, nameplate_capacity=600.0)
        defaults.update(kw)
        return FacilityWindTurbines.objects.create(**defaults)

    def turbine(self, **kw):
        from siren_web.models import WindTurbines
        defaults = dict(turbine_model='Test V150', rated_power=4200, rotor_diameter=150, hub_height=105)
        defaults.update(kw)
        return WindTurbines.objects.create(**defaults)

    def test_unspecified_installation_gets_a_scaled_representative(self):
        inst = self.installation()
        r = rt.resolve_wind_installation(inst)
        self.assertEqual(r.kind, 'assumed')
        self.assertAlmostEqual(r.rated_kw, 6000)
        self.assertAlmostEqual(r.installation_capacity_mw, 600)      # nameplate respected
        inst.refresh_from_db()
        saved = inst.assumed_turbine
        self.assertEqual(saved['reference_slug'], r.reference_slug)
        self.assertEqual(saved['inputs']['cod_year'], 2028)
        self.assertEqual(saved['inputs']['rating_source'], 'installation nameplate')
        self.assertIsNone(inst.idwindturbines, "the row must stay 'Unspecified'")

    def test_resolution_is_idempotent_and_does_not_rewrite(self):
        inst = self.installation()
        rt.resolve_wind_installation(inst)
        inst.refresh_from_db()
        first = inst.assumed_turbine['selected_at']
        rt.resolve_wind_installation(inst)
        inst.refresh_from_db()
        self.assertEqual(inst.assumed_turbine['selected_at'], first)

    def test_changed_inputs_reselect_and_resave(self):
        inst = self.installation()
        rt.resolve_wind_installation(inst)
        inst.nameplate_capacity = 700.0
        r = rt.resolve_wind_installation(inst)
        self.assertAlmostEqual(r.rated_kw, 7000)
        inst.refresh_from_db()
        self.assertAlmostEqual(inst.assumed_turbine['rated_kw'], 7000)

    def test_persist_false_writes_nothing(self):
        inst = self.installation()
        rt.resolve_wind_installation(inst, persist=False)
        inst.refresh_from_db()
        self.assertIsNone(inst.assumed_turbine)

    def test_saving_the_assumption_does_not_fire_the_capacity_signal(self):
        # FacilityWindTurbines' post_save signal rewrites facilities.capacity from the
        # installations; the assumption is a derived cache and must not trigger it.
        from siren_web.models import facilities
        inst = self.installation()
        facilities.objects.filter(pk=self.facility.pk).update(capacity=12345.0)
        rt.resolve_wind_installation(inst)
        self.assertEqual(facilities.objects.get(pk=self.facility.pk).capacity, 12345.0)
        inst.refresh_from_db()
        self.assertIsNotNone(inst.assumed_turbine)

    def test_default_rating_when_nothing_implies_one(self):
        inst = self.installation(nameplate_capacity=None)
        r = rt.resolve_wind_installation(inst)
        self.assertAlmostEqual(r.rated_kw, rt.DEFAULT_RATED_KW)
        inst.refresh_from_db()
        self.assertEqual(inst.assumed_turbine['inputs']['rating_source'], 'default rating')

    def test_hub_height_override_is_honoured(self):
        inst = self.installation(hub_height_override=125.0)
        self.assertEqual(rt.resolve_wind_installation(inst).hub_height, 125.0)

    def test_commissioning_year_falls_back_through_installation_facility_today(self):
        inst = self.installation(commissioning_date=date(2030, 1, 1))
        self.assertEqual(rt.cod_year_for(inst, self.facility), 2030)
        inst.commissioning_date = None
        self.assertEqual(rt.cod_year_for(inst, self.facility), 2028)
        self.facility.commissioning_date = None
        self.assertEqual(rt.cod_year_for(inst, self.facility), date.today().year + rt.DEFAULT_YEARS_AHEAD)

    def test_named_turbine_uses_its_library_curve(self):
        slug = 'vestas-v150-4.2mw'
        inst = self.installation(idwindturbines=self.turbine(power_curve_csv=slug), no_turbines=10,
                                 nameplate_capacity=None)
        r = rt.resolve_wind_installation(inst)
        self.assertEqual((r.kind, r.name, r.reference_slug), ('specified', 'Test V150', slug))
        self.assertEqual(r.hub_height, 105)                     # the turbine's own hub height
        self.assertEqual(r.no_turbines, 10)
        self.assertAlmostEqual(max(r.power_kw), 4200)

    def test_named_turbine_falls_back_to_its_pow_file(self):
        inst = self.installation(idwindturbines=self.turbine(turbine_model='V150-4.2Mw'), no_turbines=10)
        r = rt.resolve_wind_installation(inst)
        self.assertEqual(r.kind, 'specified')
        self.assertIn('Vestas V150-4.2Mw.pow', r.basis)
        curve = dict(zip(r.wind_speeds, r.power_kw))
        self.assertEqual(curve[3.0], 42)                        # not shifted by the header lines
        self.assertEqual(curve[11.0], 4200)

    def test_named_turbine_without_any_curve_gets_a_representative_but_no_saved_assumption(self):
        inst = self.installation(idwindturbines=self.turbine(turbine_model='Mystery X9000', rated_power=5000),
                                 no_turbines=10)
        with self.assertLogs('powermapui.utils.representative_turbine', 'WARNING') as logs:
            r = rt.resolve_wind_installation(inst)
        self.assertEqual(r.kind, 'assumed')
        self.assertAlmostEqual(r.rated_kw, 5000)
        self.assertTrue(any('Mystery X9000' in m for m in logs.output))
        inst.refresh_from_db()
        self.assertIsNone(inst.assumed_turbine)

    def test_choosing_a_turbine_clears_a_stale_assumption(self):
        inst = self.installation()
        rt.resolve_wind_installation(inst)
        inst.refresh_from_db()
        self.assertIsNotNone(inst.assumed_turbine)
        inst.idwindturbines = self.turbine(power_curve_csv='vestas-v150-4.2mw')
        rt.resolve_wind_installation(inst)
        inst.refresh_from_db()
        self.assertIsNone(inst.assumed_turbine)

    def test_facility_without_installations_is_sized_from_its_capacity(self):
        self.facility.capacity = 600.0
        r = rt.resolve_wind_facility(self.facility)
        self.assertEqual(r.no_turbines, 100)
        self.assertAlmostEqual(r.installation_capacity_mw, 600)
        self.facility.capacity = None
        with self.assertRaises(rt.NoRepresentativeTurbine):
            rt.resolve_wind_facility(self.facility)

    def test_wind_technology_falls_back_to_the_facility_then_onshore_wind(self):
        from powermapui.views.power_views import wind_technology_for
        inst = self.installation()                              # created with no technology
        self.assertEqual(wind_technology_for(inst, self.facility), self.tech)
        self.facility.idtechnologies = None
        self.assertEqual(wind_technology_for(inst, self.facility), self.tech)


class SamWindWiringTests(SimpleTestCase):
    """Run the real SAM wind module on synthetic wind and check the resolved turbine reaches it."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.processor = SAMResourceProcessor(self._tmp.name, self._tmp.name)
        self.facility = SimpleNamespace(facility_name='Synthetic', facility_code='SYNTH_TEST',
                                        latitude=-33.0, longitude=116.0)

    def simulate(self, wind_speed, turbines, rated_kw=6000):
        n = 8760
        weather = WeatherData(wind_speed=[wind_speed] * n, wind_direction=[180.0] * n,
                              temperature=[15.0] * n, pressure=[1.0] * n)
        turbine = replace(rt.select_representative_turbine(rated_kw, 2027), no_turbines=turbines)
        return self.processor.process_wind_facility(self.facility, '2025', weather, turbine)

    def test_farm_at_rated_wind_produces_the_nameplate(self):
        for n in (1, 25):
            with self.subTest(turbines=n):
                res = self.simulate(20.0, n)
                # 2% farm losses only; no wake model
                self.assertAlmostEqual(res.hourly_generation[100] / (n * 6000), 0.98, delta=0.01)

    def test_output_scales_with_the_number_of_turbines_less_wake_losses(self):
        # wind_farm_wake_model 0 is SAM's "Simple" wake model, so a farm makes a little
        # less than n x one turbine in mid-range wind (about 7% for 4 turbines at 8D).
        one = sum(self.simulate(8.0, 1).hourly_generation)
        four = sum(self.simulate(8.0, 4).hourly_generation)
        self.assertGreater(one, 0)
        self.assertGreater(four / one, 3.5)
        self.assertLess(four / one, 4.0)

    def test_calm_wind_produces_nothing(self):
        self.assertEqual(sum(self.simulate(1.0, 5).hourly_generation), 0)

    def test_bigger_rated_turbine_produces_proportionally_more(self):
        small = sum(self.simulate(8.0, 10, rated_kw=5000).hourly_generation)
        large = sum(self.simulate(8.0, 10, rated_kw=7500).hourly_generation)
        self.assertGreater(large / small, 1.3)
