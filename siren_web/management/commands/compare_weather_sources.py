"""
Compare SAM output from different weather sources against each facility's SCADA.

For each facility it runs the normal SAM path (process_hybrid_facility: turbine
resolution, hybrids, solar scaling) once per weather source, without storing anything,
and scores each run against the facility's half-hourly SCADA summed to UTC hours.

Usage:
    python manage.py compare_weather_sources --facility YANDIN_WF1 --facility SBSOLAR1_CUNDERDIN_PV1
    python manage.py compare_weather_sources --all-with-scada --year 2025 --csv results.csv
    python manage.py compare_weather_sources --facility YANDIN_WF1 --wind-profile bracket,10-100

Sources: 'era5' (nearest stored grid-point file) and 'barra_c2' (the facility's own
BARRA-C2 cell, fetched and cached on first use -- run fetch_barra_c2_weather first to
avoid waiting). For BARRA-C2 wind, '--wind-profile bracket,10-100' also runs the 10 m /
100 m profile ERA5 uses, separating the effect of the data from that of its extra levels.

Metrics (all on hours where both series exist; SCADA below zero, i.e. station load at
night, is counted as zero):
    energy    simulated / SCADA energy
    CF        capacity factor of each series
    r_hour    Pearson correlation of hourly MW
    r_day     Pearson correlation of daily MWh (complete days only)
    nRMSE     RMSE of hourly MW / capacity
    nBias     mean (sim - SCADA) / capacity
    lag       shift of the simulation, in hours (-3..+3), with the best correlation;
              anything but 0 means a time-zone or labelling error
    r_diurnal correlation of the mean 24-hour shapes
"Masked" repeats the scores without hours that look like curtailment or outage:
SCADA below 2% of capacity while the simulation is above 30%.

Bias factors (FacilityGenerationBias): each run also reports the factor that would make
the simulation's masked energy match SCADA (SCADA / simulated), and the scores after
applying it ("fitted", in-sample). SAM runs here always use the raw simulation. With
--set-bias the factor is stored for (facility, source) and is then applied in every SAM
simulation run with that weather source. A factor is not stored when the masked hourly
correlation is below --bias-min-r or it falls outside --bias-range; use --exclude for
facilities whose SCADA is not comparable (e.g. a solar farm whose meter includes a
battery). --clear-bias removes stored factors.

    python manage.py compare_weather_sources --all-with-scada --sources barra_c2         --exclude SBSOLAR1_CUNDERDIN_PV1 --set-bias
"""

import csv
import logging
from pathlib import Path

import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from siren_web.services.generation_bias import (  # shared with the comparison page
    KW_PER_MW, MASK_SCADA_BELOW, MASK_SIM_ABOVE, masked, scada_hourly_mw,
)

MAX_LAG_H = 3


def _corr(a, b):
    ok = ~(np.isnan(a) | np.isnan(b))
    if ok.sum() < 3 or np.std(a[ok]) == 0 or np.std(b[ok]) == 0:
        return float('nan')
    return float(np.corrcoef(a[ok], b[ok])[0, 1])


def _shift(x, lag):
    """x moved `lag` hours later (positive) or earlier (negative), NaN-padded."""
    out = np.full_like(x, np.nan)
    if lag > 0:
        out[lag:] = x[:-lag]
    elif lag < 0:
        out[:lag] = x[-lag:]
    else:
        out[:] = x
    return out


def score(sim_mw, scada_mw, capacity_mw):
    """Agreement metrics between two hourly MW series of equal length (see module doc)."""
    n = min(len(sim_mw), len(scada_mw))
    sim = np.asarray(sim_mw[:n], dtype=float)
    obs = np.asarray(scada_mw[:n], dtype=float)
    both = ~(np.isnan(sim) | np.isnan(obs))
    s, o = sim[both], obs[both]
    if s.size == 0:
        return None
    hours = np.arange(n)

    days = n // 24
    sim_d = sim[:days * 24].reshape(days, 24)
    obs_d = obs[:days * 24].reshape(days, 24)
    complete = ~(np.isnan(sim_d).any(axis=1) | np.isnan(obs_d).any(axis=1))

    lags = {lag: _corr(_shift(sim, lag), obs) for lag in range(-MAX_LAG_H, MAX_LAG_H + 1)}
    best_lag = max(lags, key=lambda k: -1 if np.isnan(lags[k]) else lags[k])

    hod = hours[both] % 24
    diurnal_s = np.array([s[hod == h].mean() if np.any(hod == h) else np.nan for h in range(24)])
    diurnal_o = np.array([o[hod == h].mean() if np.any(hod == h) else np.nan for h in range(24)])

    return {
        'hours': int(s.size),
        'energy': float(s.sum() / o.sum()) if o.sum() > 0 else float('nan'),
        'cf_sim': float(s.mean() / capacity_mw),
        'cf_scada': float(o.mean() / capacity_mw),
        'r_hour': _corr(s, o),
        'r_day': _corr(sim_d[complete].sum(axis=1), obs_d[complete].sum(axis=1)),
        'nrmse': float(np.sqrt(np.mean((s - o) ** 2)) / capacity_mw),
        'nbias': float(np.mean(s - o) / capacity_mw),
        'lag': int(best_lag),
        'r_diurnal': _corr(diurnal_s, diurnal_o),
    }


def monthly_ratios(sim_mw, scada_mw, year):
    """Simulated / SCADA energy per month, on hours where both exist."""
    import pandas as pd
    n = min(len(sim_mw), len(scada_mw))
    months = pd.date_range(f'{year}-01-01', periods=n, freq='h', tz='UTC').month.to_numpy()
    sim = np.asarray(sim_mw[:n], dtype=float)
    obs = np.asarray(scada_mw[:n], dtype=float)
    both = ~(np.isnan(sim) | np.isnan(obs))
    out = []
    for m in range(1, 13):
        sel = both & (months == m)
        o = obs[sel].sum()
        out.append(float(sim[sel].sum() / o) if o > 0 else float('nan'))
    return out


class Command(BaseCommand):
    help = 'Score SAM output from each weather source against facility SCADA'

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, default=2025)
        parser.add_argument('--facility', action='append', default=[],
                            help='Facility code (repeatable)')
        parser.add_argument('--all-with-scada', action='store_true',
                            help='Every wind/solar facility with SCADA in --year')
        parser.add_argument('--sources', default='era5,barra_c2')
        parser.add_argument('--wind-profile', default='bracket',
                            help="BARRA-C2 wind profile(s): 'bracket', '10-100' or both, comma-separated")
        parser.add_argument('--min-coverage', type=float, default=0.5,
                            help='Skip facilities whose SCADA covers less of the year than this')
        parser.add_argument('--csv', help='Write every metric to this CSV file')
        parser.add_argument('--hourly-dir', help='Write each run\'s aligned hourly series here')
        parser.add_argument('--monthly', action='store_true', help='Print monthly energy ratios')
        parser.add_argument('--exclude', action='append', default=[],
                            help='Facility code to leave out, e.g. one whose SCADA includes a battery (repeatable)')
        parser.add_argument('--set-bias', action='store_true',
                            help='Store each fitted bias factor (FacilityGenerationBias) for the source; '
                                 'for BARRA-C2 wind only the --wind-profile bracket run is stored')
        parser.add_argument('--clear-bias', action='store_true',
                            help='Delete the stored bias factors for the chosen facilities and sources, then stop')
        parser.add_argument('--bias-min-r', type=float, default=0.6,
                            help='Do not store a factor when masked hourly correlation is below this')
        parser.add_argument('--bias-range', default='0.5,1.5',
                            help='Do not store a factor outside this range (min,max)')

    def handle(self, *args, **opts):
        from powermapui.views.sam_resource_processor import SAMResourceProcessor, WEATHER_SOURCES
        from powermatchui.views.power_views import process_hybrid_facility
        from siren_web.models import facilities
        from siren_web.services import generation_bias
        from siren_web.management.commands.fetch_barra_c2_weather import (
            facilities_with_scada, facility_technologies,
        )

        # SAM and the weather code log every run at INFO; keep the table readable.
        for name in ('powermapui', 'powermatchui', 'siren_web', 'urllib3'):
            logging.getLogger(name).setLevel(logging.WARNING)

        year = opts['year']
        sources = [s.strip() for s in opts['sources'].split(',') if s.strip()]
        for s in sources:
            if s not in WEATHER_SOURCES:
                raise CommandError(f'Unknown source {s!r}; expected {", ".join(WEATHER_SOURCES)}')
        profiles = [p.strip() for p in opts['wind_profile'].split(',') if p.strip()]

        chosen = []
        for code in opts['facility']:
            try:
                chosen.append(facilities.objects.get(facility_code=code))
            except facilities.DoesNotExist:
                raise CommandError(f'No facility with code {code}')
        if opts['all_with_scada']:
            chosen.extend(f for f in facilities_with_scada(year) if f not in chosen)
        chosen = [f for f in chosen if f.facility_code not in set(opts['exclude'])]
        if not chosen:
            raise CommandError('Give --facility or --all-with-scada')
        try:
            bias_min, bias_max = (float(v) for v in opts['bias_range'].split(','))
        except ValueError:
            raise CommandError('--bias-range must be min,max')

        if opts['clear_bias']:
            for f in chosen:
                for source in sources:
                    if generation_bias.clear_factor(f.idfacilities, source):
                        self.stdout.write(f'Cleared {source} bias for {f.facility_name}')
            return

        processors = {}

        def processor(source, profile):
            key = (source, profile)
            if key not in processors:
                processors[key] = SAMResourceProcessor(
                    weather_data_dir=settings.WEATHER_DATA_DIR,
                    weather_source=source, wind_profile=profile)
            return processors[key]

        rows = []
        hourly_dir = Path(opts['hourly_dir']) if opts['hourly_dir'] else None
        if hourly_dir:
            hourly_dir.mkdir(parents=True, exist_ok=True)

        for f in chosen:
            capacity = float(f.capacity or 0)
            obs = scada_hourly_mw(year, f.idfacilities)
            coverage = 0.0 if obs is None else float(np.mean(~np.isnan(obs)))
            techs = facility_technologies(f)
            self.stdout.write(f'\n{f.facility_name} ({f.facility_code}), {"+".join(techs)}, '
                              f'{capacity:g} MW, SCADA coverage {coverage:.0%}')
            if obs is None or coverage < opts['min_coverage'] or capacity <= 0:
                self.stdout.write('  skipped: not enough SCADA or no capacity')
                continue

            variants = []
            for source in sources:
                if source == 'barra_c2' and 'wind' in techs:
                    variants += [(source, p) for p in profiles]
                else:
                    variants.append((source, 'bracket'))
            labelled = [(s, p, s if len(profiles) == 1 or s != 'barra_c2' or 'wind' not in techs
                         else f'{s}/{p}') for s, p in variants]

            for source, profile, label in labelled:
                # Raw SAM output: any stored bias is left off so the fit starts clean
                results, reason = process_hybrid_facility(processor(source, profile), f, str(year),
                                                          apply_bias=False)
                if not results or not results.hourly_generation:
                    self.stdout.write(f'  {label:16s} no SAM result{": " + reason if reason else ""}')
                    continue
                sim = np.asarray(results.hourly_generation, dtype=float) / KW_PER_MW
                raw = score(sim, obs, capacity)
                sim_m, obs_m, n_dropped = masked(sim, obs, capacity)
                msk = score(sim_m, obs_m, capacity)
                self.stdout.write(self._line(label, 'all', raw))
                self.stdout.write(self._line('', f'masked -{n_dropped}h', msk))

                # Bias factor: SCADA / simulated energy on the masked hours, and the score
                # the corrected simulation would get (in-sample, the same year it was fitted on)
                fitted = generation_bias.fit_energy_factor(sim_m, obs_m)
                stored = generation_bias.get_factor(f.idfacilities, source)
                corrected = None
                if fitted is not None:
                    sim_c = generation_bias.apply_factor(sim, fitted, capacity)
                    sim_cm, obs_cm, _ = masked(sim_c, obs, capacity)
                    corrected = score(sim_cm, obs_cm, capacity)
                    self.stdout.write(self._line('', f'fitted x{fitted:.3f}', corrected))
                status = self._bias_status(fitted, msk, source, profile, techs, bias_min, bias_max,
                                           opts['bias_min_r'])
                if opts['set_bias'] and status == 'ok':
                    generation_bias.set_factor(
                        f.idfacilities, source, fitted, fitted_year=year,
                        fitted_hours=msk['hours'], r_hour=msk['r_hour'],
                        scada_energy_mwh=float(np.nansum(obs_m)),
                        simulated_energy_mwh=float(np.nansum(sim_m)),
                        notes=f'compare_weather_sources {label}, masked hours')
                    status = 'stored'
                self.stdout.write(f'  {"":16s} bias: stored {"none" if stored is None else f"x{stored:.3f}"}, '
                                  f'fitted {"--" if fitted is None else f"x{fitted:.3f}"} ({status})')
                if opts['monthly']:
                    ratios = monthly_ratios(sim, obs, year)
                    self.stdout.write('      monthly energy: ' + ' '.join(
                        '  -- ' if np.isnan(r) else f'{r:5.2f}' for r in ratios))
                rows.append({'facility_code': f.facility_code, 'facility': f.facility_name,
                             'technology': '+'.join(techs), 'capacity_mw': capacity,
                             'scada_coverage': round(coverage, 4), 'source': label,
                             **{f'{k}': v for k, v in raw.items()},
                             **{f'masked_{k}': v for k, v in msk.items()},
                             'masked_hours_dropped': n_dropped,
                             'fitted_bias': fitted, 'stored_bias_before': stored, 'bias_status': status,
                             **{f'corrected_{k}': v for k, v in (corrected or {}).items()}})
                if hourly_dir:
                    path = hourly_dir / f'{f.facility_code}_{label.replace("/", "_")}_{year}.csv'
                    with open(path, 'w', newline='') as fh:
                        w = csv.writer(fh)
                        w.writerow(['hour_utc', 'sim_mw', 'scada_mw'])
                        for h in range(min(len(sim), len(obs))):
                            w.writerow([h, f'{sim[h]:.4f}',
                                        '' if np.isnan(obs[h]) else f'{obs[h]:.4f}'])

        if rows:
            self._summary(rows)
        if opts['csv'] and rows:
            with open(opts['csv'], 'w', newline='') as fh:
                fields = list(dict.fromkeys(k for r in rows for k in r))
                w = csv.DictWriter(fh, fieldnames=fields)
                w.writeheader()
                w.writerows(rows)
            self.stdout.write(f'\nWrote {opts["csv"]}')

    @staticmethod
    def _bias_status(fitted, msk, source, profile, techs, bias_min, bias_max, min_r):
        """'ok' when the fitted factor may be stored, otherwise why not."""
        if fitted is None or msk is None:
            return 'no fit'
        if source == 'barra_c2' and 'wind' in techs and profile != 'bracket':
            return 'not stored: only the bracket profile run is stored'
        if np.isnan(msk['r_hour']) or msk['r_hour'] < min_r:
            return f'not stored: r_hour {msk["r_hour"]:.2f} < {min_r:g}'
        if not bias_min <= fitted <= bias_max:
            return f'not stored: outside {bias_min:g}-{bias_max:g}'
        return 'ok'

    @staticmethod
    def _line(label, kind, m):
        if m is None:
            return f'  {label:16s} {kind:14s} no overlapping hours'
        return (f'  {label:16s} {kind:14s} energy {m["energy"]:5.2f}  CF {m["cf_sim"]:.3f} vs '
                f'{m["cf_scada"]:.3f}  r_hour {m["r_hour"]:.3f}  r_day {m["r_day"]:.3f}  '
                f'nRMSE {m["nrmse"]:.3f}  nBias {m["nbias"]:+.3f}  lag {m["lag"]:+d}  '
                f'r_diurnal {m["r_diurnal"]:.3f}')

    def _summary(self, rows):
        """Median of each masked metric per source, and how often each source wins."""
        self.stdout.write('\nSummary (masked metrics, median across facilities)')
        sources = list(dict.fromkeys(r['source'] for r in rows))
        for src in sources:
            mine = [r for r in rows if r['source'] == src]
            med = {k: float(np.nanmedian([r[f'masked_{k}'] for r in mine]))
                   for k in ('energy', 'r_hour', 'r_day', 'nrmse', 'nbias')}
            self.stdout.write(f'  {src:16s} n={len(mine):2d}  energy {med["energy"]:.2f}  '
                              f'r_hour {med["r_hour"]:.3f}  r_day {med["r_day"]:.3f}  '
                              f'nRMSE {med["nrmse"]:.3f}  nBias {med["nbias"]:+.3f}')
        if len(sources) > 1:
            by_fac = {}
            for r in rows:
                by_fac.setdefault(r['facility_code'], {})[r['source']] = r
            wins = {s: 0 for s in sources}
            for runs in by_fac.values():
                scored = {s: r['masked_nrmse'] for s, r in runs.items()
                          if not np.isnan(r['masked_nrmse'])}
                if len(scored) > 1:
                    wins[min(scored, key=scored.get)] += 1
            self.stdout.write('  lowest nRMSE wins: ' +
                              ', '.join(f'{s} {n}' for s, n in wins.items()))
