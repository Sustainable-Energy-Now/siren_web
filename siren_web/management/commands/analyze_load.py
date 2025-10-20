# powerplot/management/commands/analyze_load.py
from django.core.management.base import BaseCommand
from powerplotui.services.load_analyzer import LoadAnalyzer
from siren_web.models import LoadAnalysisSummary
from datetime import datetime, date
import json
import calendar

class Command(BaseCommand):
    help = 'Calculate and analyze SWIS load data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--year',
            type=int,
            help='Year to analyze',
        )
        parser.add_argument(
            '--month',
            type=int,
            help='Month to analyze (1-12)',
        )
        parser.add_argument(
            '--recalculate',
            action='store_true',
            help='Recalculate even if summary already exists',
        )
        parser.add_argument(
            '--all-months',
            action='store_true',
            help='Calculate all months in specified year',
        )
        parser.add_argument(
            '--ytd',
            action='store_true',
            help='Calculate year-to-date summary',
        )
        parser.add_argument(
            '--output',
            type=str,
            choices=['table', 'json', 'summary'],
            default='summary',
            help='Output format',
        )
        parser.add_argument(
            '--save-json',
            type=str,
            help='Save output to JSON file',
        )
    
    def handle(self, *args, **options):
        analyzer = LoadAnalyzer()
        
        # Determine year and month
        year = options.get('year')
        month = options.get('month')
        
        if not year:
            # Default to current year
            year = datetime.now().year
        
        # Calculate all months in year
        if options['all_months']:
            self.stdout.write(
                self.style.WARNING(f'\nCalculating all months for {year}...\n')
            )
            
            results = []
            for m in range(1, 13):
                try:
                    self.stdout.write(f'Processing {year}-{m:02d}...')
                    summary = self._calculate_month(
                        analyzer, year, m, options['recalculate']
                    )
                    
                    if summary:
                        results.append(summary)
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'  ✓ {calendar.month_name[m]}: '
                                f'{summary.operational_demand:.1f} GWh, '
                                f'RE: {summary.re_percentage_operational:.1f}%'
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(f'  ⊘ No data for {calendar.month_name[m]}')
                        )
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'  ✗ Error: {str(e)}')
                    )
            
            # Print year summary
            if results:
                self._print_year_summary(results, year)
                
                if options['save_json']:
                    self._save_json(results, options['save_json'])
            
            return
        
        # Calculate single month or YTD
        if not month:
            # Default to current month or YTD
            if options['ytd']:
                month = datetime.now().month
                self._calculate_ytd(analyzer, year, month, options)
            else:
                month = datetime.now().month
                self._calculate_single_month(analyzer, year, month, options)
        else:
            if not 1 <= month <= 12:
                self.stdout.write(
                    self.style.ERROR('Month must be between 1 and 12')
                )
                return
            
            self._calculate_single_month(analyzer, year, month, options)
    
    def _calculate_month(self, analyzer, year, month, recalculate=False):
        """Calculate monthly summary"""
        # Check if already exists
        existing = LoadAnalysisSummary.objects.filter(
            period_date=date(year, month, 1),
            period_type='MONTHLY'
        ).first()
        
        if existing and not recalculate:
            return existing
        
        # Calculate new summary
        summary = analyzer.calculate_monthly_summary(year, month)
        return summary
    
    def _calculate_single_month(self, analyzer, year, month, options):
        """Calculate and display single month analysis"""
        self.stdout.write(
            f'\nCalculating load analysis for {calendar.month_name[month]} {year}...\n'
        )
        
        try:
            summary = self._calculate_month(analyzer, year, month, options['recalculate'])
            
            if not summary:
                self.stdout.write(
                    self.style.ERROR(f'No SCADA data found for {year}-{month:02d}')
                )
                return
            
            # Display results based on output format
            if options['output'] == 'json':
                self._print_json(summary)
            elif options['output'] == 'table':
                self._print_table(summary)
            else:  # summary
                self._print_summary(summary)
            
            # Save to file if requested
            if options['save_json']:
                self._save_json([summary], options['save_json'])
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error calculating summary: {str(e)}')
            )
            raise
    
    def _calculate_ytd(self, analyzer, year, month, options):
        """Calculate year-to-date summary"""
        self.stdout.write(
            f'\nCalculating YTD analysis for {year} through {calendar.month_name[month]}...\n'
        )
        
        summaries = []
        for m in range(1, month + 1):
            try:
                summary = self._calculate_month(analyzer, year, m, options['recalculate'])
                if summary:
                    summaries.append(summary)
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'Warning: Could not calculate {year}-{m:02d}: {str(e)}')
                )
        
        if not summaries:
            self.stdout.write(
                self.style.ERROR('No data available for YTD calculation')
            )
            return
        
        # Aggregate YTD
        ytd_summary = self._aggregate_summaries(summaries, year, month)
        
        # Display
        if options['output'] == 'json':
            self._print_json(ytd_summary)
        else:
            self._print_ytd_summary(ytd_summary, summaries)
        
        if options['save_json']:
            self._save_json(summaries, options['save_json'])
    
    def _print_summary(self, summary):
        """Print formatted summary"""
        self.stdout.write('\n' + '='*70)
        self.stdout.write(
            self.style.SUCCESS(
                f'SWIS LOAD ANALYSIS - {calendar.month_name[summary.period_date.month]} '
                f'{summary.period_date.year}'
            )
        )
        self.stdout.write('='*70 + '\n')
        
        # Demand metrics
        self.stdout.write(self.style.WARNING('DEMAND METRICS'))
        self.stdout.write(f'  Operational Demand:     {summary.operational_demand:>10.2f} GWh')
        self.stdout.write(f'  Underlying Demand:      {summary.underlying_demand:>10.2f} GWh')
        self.stdout.write(f'  DPV Generation:         {summary.dpv_generation:>10.2f} GWh')
        
        # Generation breakdown
        self.stdout.write(f'\n{self.style.WARNING("GENERATION BREAKDOWN")}')
        self.stdout.write(f'  Wind:                   {summary.wind_generation:>10.2f} GWh')
        self.stdout.write(f'  Solar (Utility):        {summary.solar_generation:>10.2f} GWh')
        self.stdout.write(f'  Fossil:                 {summary.fossil_generation:>10.2f} GWh')
        
        # Battery
        self.stdout.write(f'\n{self.style.WARNING("BATTERY STORAGE (BESS)")}')
        self.stdout.write(f'  Discharge:              {summary.battery_discharge:>10.2f} GWh')
        self.stdout.write(f'  Charge:                 {summary.battery_charge:>10.2f} GWh')
        net_battery = summary.battery_discharge - summary.battery_charge
        efficiency = (summary.battery_discharge / summary.battery_charge * 100) if summary.battery_charge > 0 else 0
        self.stdout.write(f'  Net Contribution:       {net_battery:>10.2f} GWh')
        self.stdout.write(f'  Round-trip Efficiency:  {efficiency:>10.1f} %')
        
        # Renewable percentages
        self.stdout.write(f'\n{self.style.SUCCESS("RENEWABLE ENERGY METRICS")}')
        self.stdout.write(f'  RE % (Operational):     {summary.re_percentage_operational:>10.1f} %')
        self.stdout.write(f'  RE % (Underlying):      {summary.re_percentage_underlying:>10.1f} %')
        self.stdout.write(f'  DPV % (Underlying):     {summary.dpv_percentage_underlying:>10.1f} %')
        
        total_re = summary.wind_generation + summary.solar_generation + summary.dpv_generation
        self.stdout.write(f'  Total RE Generation:    {total_re:>10.2f} GWh')
        
        self.stdout.write('\n' + '='*70 + '\n')
    
    def _print_table(self, summary):
        """Print table format"""
        data = [
            ['Metric', 'Value', 'Unit'],
            ['-'*30, '-'*15, '-'*10],
            ['Operational Demand', f'{summary.operational_demand:.2f}', 'GWh'],
            ['Underlying Demand', f'{summary.underlying_demand:.2f}', 'GWh'],
            ['Wind Generation', f'{summary.wind_generation:.2f}', 'GWh'],
            ['Solar Generation', f'{summary.solar_generation:.2f}', 'GWh'],
            ['DPV Generation', f'{summary.dpv_generation:.2f}', 'GWh'],
            ['Fossil Generation', f'{summary.fossil_generation:.2f}', 'GWh'],
            ['Battery Discharge', f'{summary.battery_discharge:.2f}', 'GWh'],
            ['Battery Charge', f'{summary.battery_charge:.2f}', 'GWh'],
            ['RE % (Operational)', f'{summary.re_percentage_operational:.1f}', '%'],
            ['RE % (Underlying)', f'{summary.re_percentage_underlying:.1f}', '%'],
            ['DPV % (Underlying)', f'{summary.dpv_percentage_underlying:.1f}', '%'],
        ]
        
        for row in data:
            self.stdout.write(f'{row[0]:<30} {row[1]:>15} {row[2]:>10}')
    
    def _print_json(self, summary):
        """Print JSON format"""
        data = {
            'period': str(summary.period_date),
            'period_type': summary.period_type,
            'operational_demand_gwh': float(summary.operational_demand),
            'underlying_demand_gwh': float(summary.underlying_demand),
            'dpv_generation_gwh': float(summary.dpv_generation),
            'wind_generation_gwh': float(summary.wind_generation),
            'solar_generation_gwh': float(summary.solar_generation),
            'fossil_generation_gwh': float(summary.fossil_generation),
            'battery_discharge_gwh': float(summary.battery_discharge),
            'battery_charge_gwh': float(summary.battery_charge),
            're_percentage_operational': float(summary.re_percentage_operational),
            're_percentage_underlying': float(summary.re_percentage_underlying),
            'dpv_percentage_underlying': float(summary.dpv_percentage_underlying),
        }
        
        self.stdout.write(json.dumps(data, indent=2))
    
    def _print_ytd_summary(self, ytd, monthly_summaries):
        """Print YTD summary"""
        self.stdout.write('\n' + '='*70)
        self.stdout.write(
            self.style.SUCCESS(
                f'YEAR-TO-DATE ANALYSIS - {ytd["year"]} through '
                f'{calendar.month_name[ytd["month"]]}'
            )
        )
        self.stdout.write('='*70 + '\n')
        
        self.stdout.write(f'Months Included: {len(monthly_summaries)}')
        self.stdout.write(f'\n{self.style.WARNING("CUMULATIVE METRICS")}')
        self.stdout.write(f'  Total Operational Demand:   {ytd["operational_demand"]:>10.2f} GWh')
        self.stdout.write(f'  Total Underlying Demand:    {ytd["underlying_demand"]:>10.2f} GWh')
        self.stdout.write(f'  Total RE Generation:        {ytd["total_re"]:>10.2f} GWh')
        self.stdout.write(f'  Total DPV:                  {ytd["dpv_generation"]:>10.2f} GWh')
        
        self.stdout.write(f'\n{self.style.SUCCESS("RENEWABLE ENERGY METRICS")}')
        self.stdout.write(f'  RE % (Operational):         {ytd["re_percentage_operational"]:>10.1f} %')
        self.stdout.write(f'  RE % (Underlying):          {ytd["re_percentage_underlying"]:>10.1f} %')
        self.stdout.write(f'  DPV % (Underlying):         {ytd["dpv_percentage_underlying"]:>10.1f} %')
        
        self.stdout.write('\n' + '='*70 + '\n')
    
    def _print_year_summary(self, summaries, year):
        """Print summary for all months in year"""
        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.SUCCESS(f'YEAR {year} SUMMARY'))
        self.stdout.write('='*70 + '\n')
        
        # Calculate totals
        total_op = sum(s.operational_demand for s in summaries)
        total_under = sum(s.underlying_demand for s in summaries)
        total_wind = sum(s.wind_generation for s in summaries)
        total_solar = sum(s.solar_generation for s in summaries)
        total_dpv = sum(s.dpv_generation for s in summaries)
        total_re = total_wind + total_solar
        
        # Calculate percentages
        re_pct_op = (total_re / total_op * 100) if total_op > 0 else 0
        re_pct_under = ((total_re + total_dpv) / total_under * 100) if total_under > 0 else 0
        dpv_pct = (total_dpv / total_under * 100) if total_under > 0 else 0
        
        self.stdout.write(f'Total Operational Demand:   {total_op:>10.2f} GWh')
        self.stdout.write(f'Total Underlying Demand:    {total_under:>10.2f} GWh')
        self.stdout.write(f'Total Wind:                 {total_wind:>10.2f} GWh')
        self.stdout.write(f'Total Solar:                {total_solar:>10.2f} GWh')
        self.stdout.write(f'Total DPV:                  {total_dpv:>10.2f} GWh')
        self.stdout.write(f'\nRE % (Operational):         {re_pct_op:>10.1f} %')
        self.stdout.write(f'RE % (Underlying):          {re_pct_under:>10.1f} %')
        self.stdout.write(f'DPV % (Underlying):         {dpv_pct:>10.1f} %')
        
        self.stdout.write('\n' + '='*70 + '\n')
    
    def _aggregate_summaries(self, summaries, year, month):
        """Aggregate multiple monthly summaries"""
        total_op = sum(s.operational_demand for s in summaries)
        total_under = sum(s.underlying_demand for s in summaries)
        total_wind = sum(s.wind_generation for s in summaries)
        total_solar = sum(s.solar_generation for s in summaries)
        total_dpv = sum(s.dpv_generation for s in summaries)
        total_re = total_wind + total_solar
        
        return {
            'year': year,
            'month': month,
            'operational_demand': total_op,
            'underlying_demand': total_under,
            'wind_generation': total_wind,
            'solar_generation': total_solar,
            'dpv_generation': total_dpv,
            'total_re': total_re,
            're_percentage_operational': (total_re / total_op * 100) if total_op > 0 else 0,
            're_percentage_underlying': ((total_re + total_dpv) / total_under * 100) if total_under > 0 else 0,
            'dpv_percentage_underlying': (total_dpv / total_under * 100) if total_under > 0 else 0,
        }
    
    def _save_json(self, summaries, filename):
        """Save results to JSON file"""
        if isinstance(summaries, list):
            data = [
                {
                    'period': str(s.period_date),
                    'operational_demand': float(s.operational_demand),
                    'underlying_demand': float(s.underlying_demand),
                    're_percentage_operational': float(s.re_percentage_operational),
                    're_percentage_underlying': float(s.re_percentage_underlying),
                }
                for s in summaries
            ]
        else:
            data = summaries
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        self.stdout.write(
            self.style.SUCCESS(f'\n✓ Results saved to {filename}')
        )