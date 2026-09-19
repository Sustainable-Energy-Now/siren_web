"""
Build the CSV wind-turbine library used by the SAM wind path.

    python manage.py import_turbine_library                  # build / refresh
    python manage.py import_turbine_library --dry-run        # report only
    python manage.py import_turbine_library --link-db        # show WindTurbines -> library matches
    python manage.py import_turbine_library --link-db --apply

Reads vendored snapshots from <library>/_sources/ (NREL turbine-models, SAM
'Wind Turbines.csv', windpowerlib/OEDB, Zenodo cross-check) plus the legacy
SIREN `.pow` files in plant_data/, normalises every curve onto a 0.5 m/s grid,
validates it, removes duplicates (source priority: .pow, NREL, SAM,
windpowerlib) and writes index.csv, curves/<slug>.csv and SOURCES.md.
"""

import csv
import math
import re
import statistics
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from powermapui.utils import turbine_library as lib

# Duplicate test: same application, rotor within DUP_DIAMETER_M, rating within DUP_RATED_FRACTION.
DUP_DIAMETER_M = 1.5
DUP_RATED_FRACTION = 0.025
MIN_RATED_KW = 500.0            # SAM / windpowerlib entries below this are noise here
ONSHORE_ALLOWLIST_OVER_5MW = ('e-126', 'e126')   # >= 5 MW commercial models that are onshore
OFFSHORE_NAME_HINTS = ('offshore', 'multibrid', 'bard', 'm5000', 'leanwind', 'dtu', 'floating')

# name fragment -> manufacturer, first match wins
MANUFACTURERS = [
    ('vestas', 'Vestas'), ('siemens gamesa', 'Siemens Gamesa'), ('siemens', 'Siemens'),
    ('gamesa', 'Gamesa'), ('enercon', 'Enercon'), ('general electric', 'GE'), ('ge energy', 'GE'),
    ('ge ', 'GE'), ('nordex', 'Nordex'), ('senvion', 'Senvion'), ('repower', 'REpower'),
    ('suzlon', 'Suzlon'), ('goldwind', 'Goldwind'), ('acciona', 'Acciona'),
    ('mitsubishi', 'Mitsubishi'), ('fuhrlander', 'Fuhrlander'), ('bonus', 'Bonus'),
    ('neg micon', 'NEG Micon'), ('vergnet', 'Vergnet'), ('westwind', 'Westwind'),
    ('windflow', 'Windflow'), ('dewind', 'DeWind'), ('clipper', 'Clipper'),
    ('adwen', 'Adwen'), ('areva', 'Areva'), ('ampair', 'Ampair'), ('bergey', 'Bergey'),
]

# (source key, display, licence, url) in priority order
SOURCES = OrderedDict([
    ('pow', ('SIREN plant_data .pow files', 'Local (SIREN plant_data)',
             'siren_web/siren_files/siren_data/plant_data/*.pow')),
    ('nrel', ('NREL/NLR turbine-models', 'BSD-3-Clause',
              'https://github.com/NatLabRockies/turbine-models')),
    ('sam', ('NREL SAM Wind Turbines.csv', 'BSD-3-Clause',
             'https://github.com/NREL/SAM/blob/develop/deploy/libraries/Wind%20Turbines.csv')),
    ('windpowerlib', ('windpowerlib / OpenEnergy Database', 'ODbL-1.0 (attribution + share-alike)',
                      'https://github.com/wind-python/windpowerlib')),
])


@dataclass
class Candidate:
    name: str
    manufacturer: str
    application: str
    rated_kw: float
    rotor_diameter_m: float
    hub_height_m: Optional[float]
    iec_class: str
    vintage_year: Optional[int]
    is_reference: bool
    source_key: str
    wind_speeds: List[float]
    powers: List[float]
    aliases: List[str] = field(default_factory=list)   # this entry's own other names (used for DB linking)
    merged: List[str] = field(default_factory=list)    # near-identical entries folded into this one (never linked)
    hub_note: str = ''
    # filled in when accepted
    slug: str = ''
    warnings: List[str] = field(default_factory=list)

    @property
    def source_name(self) -> str:
        return SOURCES[self.source_key][0]

    @property
    def licence(self) -> str:
        return SOURCES[self.source_key][1]


def guess_manufacturer(name: str) -> str:
    low = f"{name.lower()} "
    for fragment, manufacturer in MANUFACTURERS:
        if fragment in low:
            return manufacturer
    return ''


def infer_application(name: str, rated_kw: float) -> str:
    low = name.lower()
    if any(hint in low for hint in OFFSHORE_NAME_HINTS):
        return 'offshore'
    if rated_kw >= 5000 and not any(tag in low for tag in ONSHORE_ALLOWLIST_OVER_5MW):
        return 'offshore'
    return 'onshore'


def parse_simple_yaml(text: str) -> Dict[str, str]:
    """Flat `key: value  # comment` files (the NREL spec YAMLs). No nesting."""
    out: Dict[str, str] = {}
    for line in text.splitlines():
        m = re.match(r'^([A-Za-z_]\w*):\s*(.*)$', line)
        if not m:
            continue
        key, value = m.groups()
        value = re.sub(r'\s+#.*$', '', value).strip()
        if value.startswith('#') or value == '[]':
            value = ''
        out[key] = value.strip('\'"')
    return out


def num(value) -> Optional[float]:
    if value is None:
        return None
    m = re.search(r'-?\d+(?:\.\d+)?', str(value).replace(',', '.'))
    return float(m.group()) if m else None


class Command(BaseCommand):
    help = "Build the CSV wind-turbine library (index + curves) from the vendored sources."

    def add_arguments(self, parser):
        parser.add_argument('--library-dir', help="Output directory (default: settings.TURBINE_LIBRARY_DIR)")
        parser.add_argument('--pow-dir', help="Legacy .pow directory (default: settings.POWER_CURVES_DIR)")
        parser.add_argument('--dry-run', action='store_true', help="Report only; write nothing")
        parser.add_argument('--link-db', action='store_true',
                            help="Match WindTurbines rows to library entries (report only unless --apply)")
        parser.add_argument('--apply', action='store_true', help="With --link-db, write the matches")

    # ------------------------------------------------------------------ main
    def handle(self, *args, **options):
        self.library_dir = Path(options['library_dir'] or settings.TURBINE_LIBRARY_DIR)
        self.sources_dir = self.library_dir / '_sources'
        self.pow_dir = Path(options['pow_dir'] or settings.POWER_CURVES_DIR)
        self.report: Dict[str, Counter] = {k: Counter() for k in SOURCES}
        self.skipped: List[Tuple[str, str, str]] = []      # (source, name, reason)
        self.warned: List[Tuple[str, str, str]] = []
        self.dups: List[Tuple[str, str, str]] = []

        if not self.sources_dir.is_dir() and not options['link_db']:
            raise CommandError(f"Vendored sources not found at {self.sources_dir}")

        candidates: List[Candidate] = []
        for key, reader in (('pow', self.read_pow), ('nrel', self.read_nrel),
                            ('sam', self.read_sam), ('windpowerlib', self.read_windpowerlib)):
            found = reader()
            self.report[key]['read'] = len(found)
            candidates += found

        accepted = self.accept(candidates)
        zen = self.cross_check_zenodo(accepted)

        if not options['dry_run']:
            self.assign_slugs(accepted)
            self.write_library(accepted)
        else:
            self.assign_slugs(accepted)
        self.print_report(accepted, zen, options['dry_run'])

        if options['link_db']:
            self.link_database(accepted, options['apply'])

    # --------------------------------------------------------------- readers
    def _make(self, source_key, name, rated_kw, diameter, hub, ws, powers, **extra):
        manufacturer = extra.pop('manufacturer', '') or guess_manufacturer(name)
        application = extra.pop('application', None) or infer_application(name, rated_kw)
        return Candidate(
            name=name.strip(), manufacturer=manufacturer, application=application,
            rated_kw=float(rated_kw), rotor_diameter_m=float(diameter), hub_height_m=hub,
            iec_class=extra.pop('iec_class', '') or '', vintage_year=extra.pop('vintage_year', None),
            is_reference=extra.pop('is_reference', False), source_key=source_key,
            wind_speeds=ws, powers=powers, **extra,
        )

    def read_pow(self) -> List[Candidate]:
        out = []
        for path in sorted(self.pow_dir.glob('*.pow')):
            try:
                pf = lib.parse_pow_file(path)
            except (ValueError, OSError) as e:
                self.skipped.append(('pow', path.name, f"unreadable: {e}"))
                continue
            out.append(self._make('pow', pf.name, pf.rated_kw, pf.rotor_diameter, None,
                                  pf.wind_speeds, pf.power_kw, application='onshore',
                                  aliases=[path.stem, pf.name]))
        return out

    def read_nrel(self) -> List[Candidate]:
        base = self.sources_dir / 'nrel'
        out = []
        for group in ('Onshore', 'Offshore'):
            for spec_path in sorted((base / 'specs' / group).glob('*.yaml')):
                spec = parse_simple_yaml(spec_path.read_text(encoding='utf-8'))
                name = spec.get('nickname') or spec.get('name') or spec_path.stem
                rated, diameter = num(spec.get('rated_power')), num(spec.get('rotor_diameter'))
                curve_path = base / 'data' / (spec.get('power_curve_file') or f"{group}/{spec_path.stem}.csv")
                if not rated or not diameter:
                    self.skipped.append(('nrel', name, "no rated power / rotor diameter (normalised composite)"))
                    continue
                if not curve_path.exists():
                    self.skipped.append(('nrel', name, "curve file missing"))
                    continue
                ws, powers = self._read_nrel_curve(curve_path)
                if not ws:
                    self.skipped.append(('nrel', name, "no 'Power [kW]' column"))
                    continue
                year = re.match(r'^(20\d\d)', spec.get('name') or spec_path.stem)
                out.append(self._make(
                    'nrel', name.replace('_', ' '), rated, diameter, num(spec.get('hub_height')),
                    ws, powers, application=group.lower(),
                    manufacturer=spec.get('manufacturer', ''),
                    iec_class=spec.get('turbine_class') or spec.get('iec_class') or '',
                    vintage_year=int(year.group(1)) if year else None,
                    is_reference=(spec.get('origin') or '') == 'reference model',
                    aliases=[spec_path.stem],
                ))
        return out

    @staticmethod
    def _read_nrel_curve(path: Path) -> Tuple[List[float], List[float]]:
        with open(path, newline='', encoding='utf-8') as f:
            rows = list(csv.reader(f))
        header = [c.strip().lower() for c in rows[0]]
        ws_col = next((i for i, c in enumerate(header) if 'wind speed' in c), None)
        p_col = next((i for i, c in enumerate(header) if c.startswith('power') and 'kw' in c), None)
        if ws_col is None or p_col is None:
            return [], []
        ws, powers = [], []
        for row in rows[1:]:
            try:
                ws.append(float(row[ws_col]))
                powers.append(float(row[p_col]))
            except (ValueError, IndexError):
                continue
        return ws, powers

    def read_sam(self) -> List[Candidate]:
        path = self.sources_dir / 'sam' / 'Wind Turbines.csv'
        if not path.exists():
            return []
        out = []
        with open(path, newline='', encoding='latin-1') as f:
            rows = list(csv.reader(f))
        for row in rows[1:]:
            if len(row) < 6 or row[0].strip() in ('Units', '[0]'):
                continue
            name, rated, diameter = row[0].strip(), num(row[1]), num(row[2])
            if not rated or not diameter:
                self.skipped.append(('sam', name, "unparseable rating/diameter"))
                continue
            if rated < MIN_RATED_KW:
                self.report['sam']['below_min_size'] += 1
                continue
            try:
                ws = [float(x) for x in row[4].split('|')]
                powers = [float(x) for x in row[5].split('|')]
            except ValueError:
                self.skipped.append(('sam', name, "unparseable curve"))
                continue
            if len(ws) != len(powers):
                self.skipped.append(('sam', name, "wind speed / power array lengths differ"))
                continue
            out.append(self._make(
                'sam', name, rated, diameter, None, ws, powers,
                iec_class='' if row[3].strip().lower() in ('unknown', 'not listed', '0', '') else row[3].strip(),
                is_reference=bool(re.search(r'\b(ATB|RWT|Reference)\b', name)),
                vintage_year=int(m.group(1)) if (m := re.search(r'\b(20\d\d)\b', name)) else None,
            ))
        return out

    def read_windpowerlib(self) -> List[Candidate]:
        base = self.sources_dir / 'windpowerlib'
        if not (base / 'turbine_data.csv').exists():
            return []
        curves: Dict[str, Tuple[List[float], List[float]]] = {}
        with open(base / 'power_curves.csv', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            speeds = [float(x) for x in next(reader)[1:]]
            for row in reader:
                pts = [(s, float(v) / 1000.0) for s, v in zip(speeds, row[1:]) if v.strip() != '']
                curves[row[0]] = ([s for s, _ in pts], [p for _, p in pts])
        out = []
        with open(base / 'turbine_data.csv', newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                ttype = row['turbine_type']
                rated, diameter = num(row['nominal_power']), num(row['rotor_diameter'])
                if row['has_power_curve'] != 'True' or ttype not in curves or not rated or not diameter:
                    self.report['windpowerlib']['no_curve'] += 1
                    continue
                rated_kw = rated / 1000.0
                if rated_kw < MIN_RATED_KW:
                    self.report['windpowerlib']['below_min_size'] += 1
                    continue
                hubs = []
                for piece in (row['hub_height'] or '').split(';'):
                    v = num(piece)
                    if v:
                        hubs.append(v)
                hub = statistics.median_low(hubs) if hubs else None
                ws, powers = curves[ttype]
                name = f"{row['manufacturer']} {ttype}".strip()
                out.append(self._make(
                    'windpowerlib', name, rated_kw, diameter, hub, ws, powers,
                    manufacturer=row['manufacturer'],
                    iec_class=(row['wind_class_iec'] or '').strip(),
                    hub_note=f"hub heights offered: {row['hub_height']}" if hubs else '',
                    aliases=[ttype],
                ))
        return out

    # ------------------------------------------------------ dedupe / accept
    def accept(self, candidates: List[Candidate]) -> List[Candidate]:
        accepted: List[Candidate] = []
        for cand in candidates:
            fatal, warnings = lib.validate_curve(cand.wind_speeds, cand.powers, cand.rated_kw)
            if fatal:
                self.skipped.append((cand.source_key, cand.name, '; '.join(fatal)))
                self.report[cand.source_key]['skipped'] += 1
                continue
            twin = next((a for a in accepted if a.application == cand.application
                         and abs(a.rotor_diameter_m - cand.rotor_diameter_m) <= DUP_DIAMETER_M
                         and abs(a.rated_kw / cand.rated_kw - 1) <= DUP_RATED_FRACTION), None)
            if twin is not None:
                self.dups.append((cand.source_key, cand.name, twin.name))
                self.report[cand.source_key]['duplicate'] += 1
                twin.merged.append(cand.name)
                # Hub height is a property of the size class, so borrowing it is fine. The
                # manufacturer is not: it must stay whatever this entry's own source said.
                if twin.hub_height_m is None and cand.hub_height_m:
                    twin.hub_height_m, twin.hub_note = cand.hub_height_m, cand.hub_note
                continue
            try:
                cand.wind_speeds, cand.powers = lib.normalise_curve(
                    cand.wind_speeds, cand.powers, cand.rated_kw)
            except ValueError as e:
                self.skipped.append((cand.source_key, cand.name, str(e)))
                self.report[cand.source_key]['skipped'] += 1
                continue
            cand.warnings = warnings
            for w in warnings:
                self.warned.append((cand.source_key, cand.name, w))
            self.report[cand.source_key]['accepted'] += 1
            accepted.append(cand)
        return accepted

    # -------------------------------------------------------- zenodo check
    def cross_check_zenodo(self, accepted: List[Candidate]) -> Dict[str, list]:
        result = {'filled': [], 'discrepancies': [], 'unavailable': None}
        path = self.sources_dir / 'zenodo' / 'wind_turbine_data_v2.xlsx'
        if not path.exists():
            result['unavailable'] = 'file not vendored'
            return result
        try:
            import pandas as pd
            df = pd.read_excel(path)
            rated_col = next(c for c in df.columns if str(c).lower().startswith('rater power'))
            rows = [(float(r[rated_col]), float(r['Diameter (m)']), float(r['Hub height (m)']))
                    for _, r in df.iterrows()
                    if pd.notna(r[rated_col]) and pd.notna(r['Diameter (m)']) and pd.notna(r['Hub height (m)'])]
        except Exception as e:
            result['unavailable'] = f"could not read: {e}"
            return result

        for cand in accepted:
            hubs = [h for (kw, d, h) in rows
                    if abs(d - cand.rotor_diameter_m) <= DUP_DIAMETER_M
                    and abs(kw / cand.rated_kw - 1) <= DUP_RATED_FRACTION]
            if not hubs:
                continue
            if cand.hub_height_m is None:
                cand.hub_height_m = statistics.median_low(hubs)
                cand.hub_note = 'hub height from Zenodo 150-turbine dataset (CC-BY-4.0)'
                result['filled'].append(cand.name)
            elif all(abs(h - cand.hub_height_m) > 15 for h in hubs):
                result['discrepancies'].append(
                    f"{cand.name}: hub {cand.hub_height_m:.0f} m vs Zenodo {sorted(set(hubs))}")
        return result

    # ------------------------------------------------------------- writing
    def assign_slugs(self, accepted: List[Candidate]):
        used = set()
        accepted.sort(key=lambda c: (c.application, c.rated_kw, c.name.lower()))
        for cand in accepted:
            base = lib.slugify(cand.name)
            slug, i = base, 2
            while slug in used:
                slug = f"{base}-{i}"
                i += 1
            used.add(slug)
            cand.slug = slug

    def write_library(self, accepted: List[Candidate]):
        curves_dir = self.library_dir / lib.CURVES_SUBDIR
        curves_dir.mkdir(parents=True, exist_ok=True)
        keep = set()
        for cand in accepted:
            keep.add(f"{cand.slug}.csv")
            with open(curves_dir / f"{cand.slug}.csv", 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f, lineterminator='\n')
                w.writerow(lib.CURVE_COLUMNS)
                for ws, p in zip(cand.wind_speeds, cand.powers):
                    w.writerow([f"{ws:.1f}", f"{p:.3f}".rstrip('0').rstrip('.') if p else '0'])
        for stale in curves_dir.glob('*.csv'):
            if stale.name not in keep:
                stale.unlink()

        with open(self.library_dir / lib.INDEX_FILE, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f, lineterminator='\n')
            w.writerow(lib.INDEX_COLUMNS)
            for c in accepted:
                w.writerow([
                    c.slug, c.name, c.manufacturer, c.application, f"{c.rated_kw:g}",
                    f"{c.rotor_diameter_m:g}", f"{c.hub_height_m:g}" if c.hub_height_m else '',
                    c.iec_class, c.vintage_year or '', 'true' if c.is_reference else 'false',
                    c.source_name, c.licence, f"{lib.CURVES_SUBDIR}/{c.slug}.csv",
                ])
        (self.library_dir / 'SOURCES.md').write_text(self.render_sources(accepted), encoding='utf-8')

    def render_sources(self, accepted: List[Candidate]) -> str:
        counts = Counter(c.source_key for c in accepted)
        lines = [
            "# Turbine library sources", "",
            "Generated by `manage.py import_turbine_library`; do not edit by hand.", "",
            "| Source | Licence | Turbines in library | Location |", "|---|---|---|---|",
        ]
        for key, (name, licence, url) in SOURCES.items():
            lines.append(f"| {name} | {licence} | {counts.get(key, 0)} | {url} |")
        lines += [
            "", "Hub heights missing from the primary source were filled from the Zenodo "
            "150-turbine dataset (CC-BY-4.0, https://zenodo.org/records/21357769, "
            "Zisos, National Technical University of Athens) where a turbine of the same "
            "rating and rotor diameter is listed. That dataset holds specifications and "
            "fitted-curve parameters, not power curves.", "",
            "Entries derived from windpowerlib / OEDB are ODbL-1.0: attribution and share-alike "
            "apply to that subset. Filter on the `licence` column of `index.csv` to exclude it.", "",
            "Not included: the IEA 22 MW offshore reference turbine (Apache-2.0, "
            "https://github.com/IEAWindSystems/IEA-22-280-RWT). Its repository holds no "
            "tabulated power curve (the data sits in a DTU GitLab store that was not "
            "reachable when this library was built). The IEA 15 MW reference is included via "
            "NREL turbine-models. Offshore entries are never selected for onshore facilities.", "",
            "Where several sources describe the same turbine (same application, rotor within "
            f"{DUP_DIAMETER_M} m, rating within {DUP_RATED_FRACTION:.1%}) the highest-priority "
            "source is kept, in the order listed above.", "",
        ]
        return '\n'.join(lines)

    # ------------------------------------------------------------- reporting
    def print_report(self, accepted, zen, dry_run):
        out = self.stdout.write
        out(self.style.MIGRATE_HEADING("Turbine library import" + (" (dry run, nothing written)" if dry_run else "")))
        for key, (name, _, _) in SOURCES.items():
            r = self.report[key]
            extra = ', '.join(f"{k} {v}" for k, v in r.items() if k not in ('read', 'accepted'))
            out(f"  {name:38} read {r['read']:4}  accepted {r['accepted']:4}" + (f"  ({extra})" if extra else ''))
        by_app = Counter(c.application for c in accepted)
        out(f"Library: {len(accepted)} turbines  " + '  '.join(f"{k} {v}" for k, v in sorted(by_app.items())))
        onshore_big = [c for c in accepted if c.application == 'onshore' and c.rated_kw >= 3000]
        out(f"  onshore >= 3 MW: {len(onshore_big)}; >= 5 MW: {sum(c.rated_kw >= 5000 for c in onshore_big)}; "
            f"no hub height: {sum(c.hub_height_m is None for c in accepted)}")
        if self.skipped:
            out(self.style.WARNING(f"Skipped ({len(self.skipped)}):"))
            for src, name, why in self.skipped:
                out(f"    [{src}] {name}: {why}")
        if self.warned:
            out(f"Warnings ({len(self.warned)}):")
            for src, name, why in self.warned:
                out(f"    [{src}] {name}: {why}")
        out(f"Duplicates dropped: {len(self.dups)}")
        if zen['unavailable']:
            out(self.style.WARNING(f"Zenodo cross-check unavailable: {zen['unavailable']}"))
        else:
            out(f"Zenodo cross-check: filled {len(zen['filled'])} hub heights; "
                f"{len(zen['discrepancies'])} discrepancies")
            for d in zen['discrepancies']:
                out(f"    {d}")

    # -------------------------------------------------------------- DB link
    def link_database(self, accepted: List[Candidate], apply: bool):
        from siren_web.models import WindTurbines
        out = self.stdout.write
        out(self.style.MIGRATE_HEADING("WindTurbines -> library" + ("" if apply else " (report only; use --apply to write)")))

        def key(text):
            return re.sub(r'[^a-z0-9]+', '', (text or '').lower())

        def names_match(wanted: str, have: str) -> bool:
            """Equal, or one ends with the other ('v1504.2mw' vs 'vestasv1504.2mw')."""
            if wanted == have:
                return True
            shorter, longer = sorted((wanted, have), key=len)
            return len(shorter) >= 8 and longer.endswith(shorter)

        # Only an entry's own names are linked. Entries folded into it as near-duplicates
        # (same rating and rotor, possibly another manufacturer) are deliberately excluded:
        # they are fine as one representative curve but not as "the" curve for a named model.
        indexed = [(c, {key(a) for a in [c.name, c.slug] + c.aliases if key(a)}) for c in accepted]
        linked = unmatched = 0
        for wt in WindTurbines.objects.filter(Q(power_curve_csv__isnull=True) | Q(power_curve_csv='')):
            wanted = [k for k in (key(wt.turbine_model),
                                  key(f"{wt.manufacturer or ''} {wt.turbine_model}")) if len(k) >= 4]
            matches = [c for c, keys in indexed
                       if any(names_match(w, have) for w in wanted for have in keys)]
            if wt.rated_power:
                matches = [c for c in matches if abs(c.rated_kw / wt.rated_power - 1) <= 0.05]
            if wt.rotor_diameter:
                matches = [c for c in matches if abs(c.rotor_diameter_m - wt.rotor_diameter) <= 2.0]
            how = 'name'
            if len(matches) != 1 and wt.rated_power and wt.rotor_diameter:
                # Names differ between the DB and the sources ('V82-1.65' vs 'Vestas V82-1.65mw'):
                # fall back to same manufacturer with the same rating and rotor.
                maker = guess_manufacturer(f"{wt.manufacturer or ''} {wt.turbine_model}")
                physical = [c for c in accepted
                            if maker and (c.manufacturer or guess_manufacturer(c.name)) == maker
                            and abs(c.rated_kw / wt.rated_power - 1) <= 0.05
                            and abs(c.rotor_diameter_m - wt.rotor_diameter) <= 1.0]
                if len(physical) == 1:
                    matches, how = physical, 'manufacturer + rating + rotor'
            if len(matches) != 1:
                unmatched += 1
                out(f"  no unique match: {wt.turbine_model!r} ({len(matches)} candidates)")
                continue
            c = matches[0]
            linked += 1
            out(f"  {wt.turbine_model!r} -> {c.slug}  ({c.rated_kw:g} kW, {c.rotor_diameter_m:g} m)"
                + ('' if how == 'name' else f"  [by {how}]"))
            if apply:
                wt.power_curve_csv = c.slug
                wt.rated_power = wt.rated_power or c.rated_kw
                wt.rotor_diameter = wt.rotor_diameter or c.rotor_diameter_m
                wt.hub_height = wt.hub_height or c.hub_height_m
                wt.vintage_year = wt.vintage_year or c.vintage_year
                wt.source = wt.source or c.source_name
                wt.save()
        out(f"{'Linked' if apply else 'Would link'} {linked}; unmatched {unmatched}")
