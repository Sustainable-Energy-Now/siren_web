# powerplot/management/commands/analyze_facility.py
from django.core.management.base import BaseCommand
from powerplotui.services.facility_analyzer import FacilityAnalyzer
from datetime import datetime
import json

class Command(BaseCommand):
    help = 'Analyze facility generation/consumption patterns'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--facility',
            type=str,
            help='Facility code to analyze',
        )
        parser.add_argument(
            '--all-batteries',
            action='store_true',
            help='Analyze all battery facilities',
        )
        parser.add_argument(
            '--start-date',
            type=str,
            required=True,
            help='Start date (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--end-date',
            type=str,
            required=True,
            help='End date (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--output',
            type=str,
            choices=['table', 'json'],
            default='table',
            help='Output format',
        )
    
    def handle(self, *args, **options):
        analyzer = FacilityAnalyzer()
        
        start_date = datetime.strptime(options['start_date'], '%Y-%m-%d')
        end_date = datetime.strptime(options['end_date'], '%Y-%m-%d')
        
        if options['all_batteries']:
            results = analyzer.analyze_all_batteries(start_date, end_date)
            
            if options['output'] == 'json':
                self.stdout.write(json.dumps(results, indent=2, default=str))
            else:
                self._print_battery_table(results)
        
        elif options['facility']:
            result = analyzer.analyze_facility_behavior(
                options['facility'], 
                start_date, 
                end_date
            )
            
            if result:
                if options['output'] == 'json':
                    self.stdout.write(json.dumps(result, indent=2, default=str))
                else:
                    self._print_facility_analysis(result)
            else:
                self.stdout.write(self.style.ERROR('No data found for facility'))
        
        else:
            self.stdout.write(self.style.ERROR('Must specify --facility or --all-batteries'))
    
    def _print_facility_analysis(self, analysis):
        """Print detailed facility analysis"""
        self.stdout.write(self.style.SUCCESS(f"\n{'='*60}"))
        self.stdout.write(self.style.SUCCESS(f"Facility Analysis: {analysis['facility_code']}"))
        self.stdout.write(self.style.SUCCESS(f"Period: {analysis['start_date']} to {analysis['end_date']}"))
        self.stdout.write(self.style.SUCCESS(f"{'='*60}\n"))
        
        self.stdout.write(f"Total Intervals: {analysis['total_intervals']:,}")
        
        self.stdout.write(f"\n{self.style.WARNING('GENERATION (Positive Values):')}")
        self.stdout.write(f"  Intervals: {analysis['generation_intervals']:,} ({analysis['generation_percentage']:.1f}%)")
        self.stdout.write(f"  Total: {analysis['total_generation_mwh']:,.2f} MWh")
        self.stdout.write(f"  Average: {analysis['avg_generation_mw']:.2f} MW")
        self.stdout.write(f"  Maximum: {analysis['max_generation_mw']:.2f} MW")
        
        if analysis['consumption_intervals'] > 0:
            self.stdout.write(f"\n{self.style.ERROR('CONSUMPTION (Negative Values):')}")
            self.stdout.write(f"  Intervals: {analysis['consumption_intervals']:,} ({analysis['consumption_percentage']:.1f}%)")
            self.stdout.write(f"  Total: {analysis['total_consumption_mwh']:,.2f} MWh")
            self.stdout.write(f"  Average: {analysis['avg_consumption_mw']:.2f} MW")
            self.stdout.write(f"  Maximum: {analysis['max_consumption_mw']:.2f} MW")
        
        if 'round_trip_efficiency' in analysis:
            efficiency_color = self.style.SUCCESS if analysis['round_trip_efficiency'] > 80 else self.style.WARNING
            self.stdout.write(f"\n{efficiency_color('Round-Trip Efficiency:')} {analysis['round_trip_efficiency']:.1f}%")
        
        self.stdout.write(f"\n{self.style.SUCCESS('NET CONTRIBUTION:')}")
        self.stdout.write(f"  {analysis['net_energy_mwh']:,.2f} MWh")
        
        if analysis['zero_intervals'] > 0:
            self.stdout.write(f"\nOffline/Zero: {analysis['zero_intervals']:,} intervals ({analysis['offline_percentage']:.1f}%)")
    
    def _print_battery_table(self, results):
        """Print summary table for all batteries"""
        self.stdout.write(self.style.SUCCESS(f"\n{'='*120}"))
        self.stdout.write(self.style.SUCCESS("Battery Facility Summary"))
        self.stdout.write(self.style.SUCCESS(f"{'='*120}\n"))
        
        # Header
        header = f"{'Facility':<20} {'Generation':<15} {'Consumption':<15} {'Net':<12} {'Efficiency':<12} {'Active %':<10}"
        self.stdout.write(self.style.SUCCESS(header))
        self.stdout.write(self.style.SUCCESS('-' * 120))
        
        # Data rows
        for result in results:
            efficiency = result.get('round_trip_efficiency', 0)
            active_pct = result['generation_percentage'] + result['consumption_percentage']
            
            row = (
                f"{result['facility_code']:<20} "
                f"{result['total_generation_mwh']:>10,.1f} MWh  "
                f"{result['total_consumption_mwh']:>10,.1f} MWh  "
                f"{result['net_energy_mwh']:>10,.1f} MWh "
                f"{efficiency:>10,.1f}%  "
                f"{active_pct:>9,.1f}%"
            )
            self.stdout.write(row)