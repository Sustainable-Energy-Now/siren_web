"""
Management command to import risk analysis data from Excel spreadsheet.

Usage:
    python manage.py import_risk_data --file=risk_data.xlsx [--dry-run]

Expected Excel format:
    Sheet 1: "Categories" - Risk categories
        Columns: name, description, display_order, color_code, icon

    Sheet 2: "Scenarios" - Risk scenarios
        Columns: name, short_name, description, target_year, status, is_baseline,
                 wind_pct, solar_pct, storage_pct, gas_pct, coal_pct, hydro_pct,
                 hydrogen_pct, nuclear_pct, biomass_pct, other_pct

    Sheet 3: "RiskEvents" - Risk events
        Columns: scenario_short_name, category_name, risk_title, risk_description,
                 risk_cause, risk_source, inherent_likelihood, inherent_consequence,
                 mitigation_strategies, residual_likelihood, residual_consequence,
                 assumptions, data_sources
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from siren_web.models import RiskCategory, RiskScenario, RiskEvent
import os


class Command(BaseCommand):
    help = 'Import risk analysis data from Excel spreadsheet'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            required=False,
            help='Path to Excel file containing risk data'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without making database changes'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before import'
        )
        parser.add_argument(
            '--seed-categories',
            action='store_true',
            help='Seed default risk categories (no Excel file needed)'
        )
        parser.add_argument(
            '--seed-scenarios',
            action='store_true',
            help='Seed 2026 SWIS scenarios (no Excel file needed)'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if options['seed_categories']:
            self.seed_default_categories(dry_run)
            return

        if options['seed_scenarios']:
            self.seed_2026_scenarios(dry_run)
            return

        file_path = options['file']

        if not file_path:
            raise CommandError('--file is required unless using --seed-categories or --seed-scenarios')

        if not os.path.exists(file_path):
            raise CommandError(f'File not found: {file_path}')

        try:
            import pandas as pd
        except ImportError:
            raise CommandError('pandas is required. Install with: pip install pandas openpyxl')

        self.stdout.write(f'Reading Excel file: {file_path}')

        if options['clear'] and not dry_run:
            self.stdout.write(self.style.WARNING('Clearing existing data...'))
            RiskEvent.objects.all().delete()
            RiskScenario.objects.all().delete()
            RiskCategory.objects.all().delete()

        try:
            with transaction.atomic():
                # Import categories
                if 'Categories' in pd.ExcelFile(file_path).sheet_names:
                    categories_df = pd.read_excel(file_path, sheet_name='Categories')
                    self.import_categories(categories_df, dry_run)

                # Import scenarios
                if 'Scenarios' in pd.ExcelFile(file_path).sheet_names:
                    scenarios_df = pd.read_excel(file_path, sheet_name='Scenarios')
                    self.import_scenarios(scenarios_df, dry_run)

                # Import risk events
                if 'RiskEvents' in pd.ExcelFile(file_path).sheet_names:
                    events_df = pd.read_excel(file_path, sheet_name='RiskEvents')
                    self.import_events(events_df, dry_run)

                if dry_run:
                    self.stdout.write(self.style.WARNING('DRY RUN - No changes made'))
                    raise Exception('Dry run rollback')

        except Exception as e:
            if 'Dry run rollback' in str(e):
                pass
            else:
                raise CommandError(f'Import failed: {e}')

        self.stdout.write(self.style.SUCCESS('Import completed successfully'))

    def import_categories(self, df, dry_run):
        self.stdout.write(f'Importing {len(df)} categories...')

        for _, row in df.iterrows():
            name = str(row.get('name', '')).strip()
            if not name:
                continue

            defaults = {
                'description': str(row.get('description', '')),
                'display_order': int(row.get('display_order', 0)),
                'color_code': str(row.get('color_code', '#6c757d')),
                'icon': str(row.get('icon', '')) if pd.notna(row.get('icon')) else None,
                'is_active': True
            }

            if not dry_run:
                RiskCategory.objects.update_or_create(name=name, defaults=defaults)

            self.stdout.write(f'  - {name}')

    def import_scenarios(self, df, dry_run):
        self.stdout.write(f'Importing {len(df)} scenarios...')

        for _, row in df.iterrows():
            short_name = str(row.get('short_name', '')).strip()
            if not short_name:
                continue

            # Handle NaN values for percentages
            def get_pct(key):
                val = row.get(key, 0)
                return float(val) if pd.notna(val) else 0.0

            defaults = {
                'name': str(row.get('name', short_name)),
                'description': str(row.get('description', '')),
                'target_year': int(row.get('target_year', 2040)),
                'status': str(row.get('status', 'draft')),
                'is_baseline': bool(row.get('is_baseline', False)),
                'wind_pct': get_pct('wind_pct'),
                'solar_pct': get_pct('solar_pct'),
                'storage_pct': get_pct('storage_pct'),
                'gas_pct': get_pct('gas_pct'),
                'coal_pct': get_pct('coal_pct'),
                'hydro_pct': get_pct('hydro_pct'),
                'hydrogen_pct': get_pct('hydrogen_pct'),
                'nuclear_pct': get_pct('nuclear_pct'),
                'biomass_pct': get_pct('biomass_pct'),
                'other_pct': get_pct('other_pct'),
            }

            if not dry_run:
                RiskScenario.objects.update_or_create(short_name=short_name, defaults=defaults)

            self.stdout.write(f'  - {short_name}: {defaults["name"]}')

    def import_events(self, df, dry_run):
        self.stdout.write(f'Importing {len(df)} risk events...')

        # Build lookup dicts
        scenarios = {s.short_name: s for s in RiskScenario.objects.all()}
        categories = {c.name: c for c in RiskCategory.objects.all()}

        imported = 0
        skipped = 0

        for _, row in df.iterrows():
            scenario_name = str(row.get('scenario_short_name', '')).strip()
            category_name = str(row.get('category_name', '')).strip()
            risk_title = str(row.get('risk_title', '')).strip()

            if not scenario_name or not category_name or not risk_title:
                skipped += 1
                continue

            scenario = scenarios.get(scenario_name)
            category = categories.get(category_name)

            if not scenario:
                self.stdout.write(self.style.WARNING(f'  Scenario not found: {scenario_name}'))
                skipped += 1
                continue

            if not category:
                self.stdout.write(self.style.WARNING(f'  Category not found: {category_name}'))
                skipped += 1
                continue

            def get_int(key):
                val = row.get(key)
                return int(val) if pd.notna(val) else None

            defaults = {
                'risk_description': str(row.get('risk_description', '')),
                'risk_cause': str(row.get('risk_cause', '')) if pd.notna(row.get('risk_cause')) else '',
                'risk_source': str(row.get('risk_source', '')) if pd.notna(row.get('risk_source')) else '',
                'inherent_likelihood': get_int('inherent_likelihood') or 1,
                'inherent_consequence': get_int('inherent_consequence') or 1,
                'mitigation_strategies': str(row.get('mitigation_strategies', '')) if pd.notna(row.get('mitigation_strategies')) else '',
                'residual_likelihood': get_int('residual_likelihood'),
                'residual_consequence': get_int('residual_consequence'),
                'assumptions': str(row.get('assumptions', '')) if pd.notna(row.get('assumptions')) else '',
                'data_sources': str(row.get('data_sources', '')) if pd.notna(row.get('data_sources')) else '',
            }

            if not dry_run:
                RiskEvent.objects.update_or_create(
                    scenario=scenario,
                    category=category,
                    risk_title=risk_title,
                    defaults=defaults
                )

            imported += 1

        self.stdout.write(f'  Imported: {imported}, Skipped: {skipped}')

    def seed_default_categories(self, dry_run):
        """Seed default risk categories for SWIS analysis."""
        self.stdout.write('Seeding default risk categories...')

        categories = [
            {'name': 'Safety', 'description': 'Risks to human health and safety', 'display_order': 1, 'color_code': '#e74c3c', 'icon': 'bi-shield-exclamation'},
            {'name': 'Cost', 'description': 'Financial and economic risks', 'display_order': 2, 'color_code': '#f39c12', 'icon': 'bi-currency-dollar'},
            {'name': 'Environment', 'description': 'Environmental impact and sustainability risks', 'display_order': 3, 'color_code': '#27ae60', 'icon': 'bi-tree'},
            {'name': 'Production', 'description': 'Energy production and reliability risks', 'display_order': 4, 'color_code': '#3498db', 'icon': 'bi-lightning'},
            {'name': 'Reputation', 'description': 'Social license and public support', 'display_order': 5, 'color_code': '#9b59b6', 'icon': 'bi-diagram-3'},
        ]

        for cat_data in categories:
            if not dry_run:
                RiskCategory.objects.update_or_create(
                    name=cat_data['name'],
                    defaults=cat_data
                )
            self.stdout.write(f"  - {cat_data['name']}")

        self.stdout.write(self.style.SUCCESS(f'Seeded {len(categories)} categories'))

    def seed_2026_scenarios(self, dry_run):
        """Seed 2026 SWIS energy scenarios."""
        self.stdout.write('Seeding 2026 SWIS scenarios...')

        scenarios = [
            {
                'short_name': 'VRE_BESS_GAS',
                'name': 'VRE + BESS + Gas',
                'description': 'Wind + Solar + Battery Energy Storage + Gas backup. Represents current SWIS pathway with large-scale battery deployment.',
                'target_year': 2040,
                'status': 'active',
                'is_baseline': True,
                'wind_percentage': 35.0, 'solar_percentage': 30.0, 'storage_percentage': 15.0, 'gas_percentage': 15.0, 'coal_percentage': 0.0, 'hydro_percentage': 0.0, 'hydrogen_percentage': 0.0, 'nuclear_percentage': 0.0, 'biomass_percentage': 5.0, 'other_percentage': 0.0
            },
            {
                'short_name': 'VRE_PHES',
                'name': 'VRE + Pumped Hydro',
                'description': 'Wind + Solar + Pumped Hydro Energy Storage with minimal gas backup. Long-duration storage focus.',
                'target_year': 2040,
                'status': 'active',
                'wind_percentage': 35.0, 'solar_percentage': 30.0, 'storage_percentage': 5.0, 'gas_percentage': 5.0, 'coal_percentage': 0.0, 'hydro_percentage': 20.0, 'hydrogen_percentage': 0.0, 'nuclear_percentage': 0.0, 'biomass_percentage': 5.0, 'other_percentage': 0.0
            },
            {
                'short_name': 'VRE_H2',
                'name': 'VRE + Green Hydrogen',
                'description': 'Wind + Solar with green hydrogen production, storage, and hydrogen turbines for dispatchable power.',
                'target_year': 2040,
                'status': 'active',
                'wind_percentage': 40.0, 'solar_percentage': 25.0, 'storage_percentage': 5.0, 'gas_percentage': 0.0, 'coal_percentage': 0.0, 'hydro_percentage': 0.0, 'hydrogen_percentage': 25.0, 'nuclear_percentage': 0.0, 'biomass_percentage': 5.0, 'other_percentage': 0.0
            },
            {
                'short_name': 'NUCLEAR_SMR',
                'name': 'Nuclear SMR Hybrid',
                'description': 'Small Modular Reactor baseload with VRE complement. Provides firm dispatchable capacity.',
                'target_year': 2045,
                'status': 'active',
                'wind_percentage': 20.0, 'solar_percentage': 20.0, 'storage_percentage': 5.0, 'gas_percentage': 5.0, 'coal_percentage': 0.0, 'hydro_percentage': 0.0, 'hydrogen_percentage': 0.0, 'nuclear_percentage': 45.0, 'biomass_percentage': 5.0, 'other_percentage': 0.0
            },
            {
                'short_name': 'BAU_GAS',
                'name': 'BAU Gas Transition',
                'description': 'Business as usual coal phase-out with gas expansion. Conservative transition pathway.',
                'target_year': 2035,
                'status': 'active',
                'wind_percentage': 25.0, 'solar_percentage': 20.0, 'storage_percentage': 5.0, 'gas_percentage': 40.0, 'coal_percentage': 5.0, 'hydro_percentage': 0.0, 'hydrogen_percentage': 0.0, 'nuclear_percentage': 0.0, 'biomass_percentage': 5.0, 'other_percentage': 0.0
            },
            {
                'short_name': 'HIGH_DPV',
                'name': 'High DPV + Storage',
                'description': 'Maximum rooftop solar + distributed battery storage. Consumer-led energy transition.',
                'target_year': 2040,
                'status': 'active',
                'wind_percentage': 20.0, 'solar_percentage': 45.0, 'storage_percentage': 20.0, 'gas_percentage': 10.0, 'coal_percentage': 0.0, 'hydro_percentage': 0.0, 'hydrogen_percentage': 0.0, 'nuclear_percentage': 0.0, 'biomass_percentage': 5.0, 'other_percentage': 0.0
            },
            {
                'short_name': 'RE_100',
                'name': '100% Renewable',
                'description': 'Full renewable energy with no fossil fuel backup. Requires substantial oversizing and storage.',
                'target_year': 2045,
                'status': 'active',
                'wind_percentage': 40.0, 'solar_percentage': 30.0, 'storage_percentage': 20.0, 'gas_percentage': 0.0, 'coal_percentage': 0.0, 'hydro_percentage': 5.0, 'hydrogen_percentage': 0.0, 'nuclear_percentage': 0.0, 'biomass_percentage': 5.0, 'other_percentage': 0.0
            },
        ]

        for scenario_data in scenarios:
            if not dry_run:
                RiskScenario.objects.update_or_create(
                    short_name=scenario_data['short_name'],
                    defaults=scenario_data
                )
            self.stdout.write(f"  - {scenario_data['short_name']}: {scenario_data['name']}")

        self.stdout.write(self.style.SUCCESS(f'Seeded {len(scenarios)} scenarios'))
