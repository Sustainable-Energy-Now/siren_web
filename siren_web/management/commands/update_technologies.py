"""
Django management command to import and update technology data from Excel files.

Requirements:
- pandas (pip install pandas)
- openpyxl (pip install openpyxl)

This file should be placed in your Django app's management/commands directory.
"""

import os
import re
import pandas as pd
import openpyxl  # Explicitly include openpyxl for Excel support
from django.core.management.base import BaseCommand
from django.db import transaction
from django.apps import apps
from pathlib import Path

class Command(BaseCommand):
    help = 'Import technology data from an Excel spreadsheet and update the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='Load Technologies.xlsx',
            help='Path to the Excel file (default: "Load Technologies.xlsx" in the same directory)'
        )
        parser.add_argument(
            '--sheet',
            type=str,
            default=None,
            help='Sheet name to import (default: all sheets)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without making changes to the database'
        )

    def handle(self, *args, **options):
        # Get file path
        file_path = options['file']
        if not os.path.isabs(file_path):
            file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), file_path)
        
        # Check if file exists
        if not os.path.exists(file_path):
            self.stderr.write(self.style.ERROR(f"File not found: {file_path}"))
            return
        
        # Load models
        Technologies = apps.get_model('siren_web', 'Technologies')
        TechnologyYears = apps.get_model('siren_web', 'TechnologyYears')
        Generatorattributes = apps.get_model('siren_web', 'Generatorattributes')  
        Storageattributes = apps.get_model('siren_web', 'Storageattributes')
        
        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made to the database"))
        
        try:
                            # Read the Excel file
            if options['sheet']:
                # Read specific sheet
                self.stdout.write(f"Reading sheet {options['sheet']} from {file_path}")
                df = pd.read_excel(file_path, sheet_name=options['sheet'], engine='openpyxl')
                self._process_sheet(df, options['sheet'], Technologies, TechnologyYears, 
                                   Generatorattributes, Storageattributes, dry_run)
            else:
                # Read all sheets
                self.stdout.write(f"Reading all sheets from {file_path}")
                xl = pd.ExcelFile(file_path, engine='openpyxl')
                for sheet_name in xl.sheet_names:
                    self.stdout.write(f"\nProcessing sheet: {sheet_name}")
                    df = xl.parse(sheet_name)
                    self._process_sheet(df, sheet_name, Technologies, TechnologyYears, 
                                       Generatorattributes, Storageattributes, dry_run)
            
            if not dry_run:
                self.stdout.write(self.style.SUCCESS("Data import completed successfully"))
            else:
                self.stdout.write(self.style.SUCCESS("Dry run completed successfully"))
                
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error importing data: {str(e)}"))
            raise
    
    def _process_sheet(self, df, sheet_name, Technologies, TechnologyYears, 
                      Generatorattributes, Storageattributes, dry_run):
        """Process a single sheet from the Excel file"""
        # Skip empty dataframes
        if df.empty:
            self.stdout.write(self.style.WARNING(f"Sheet '{sheet_name}' is empty, skipping"))
            return
        technologies_created = 0
        technologies_updated = 0
        generator_attrs_created = 0
        generator_attrs_updated = 0
        storage_attrs_created = 0
        storage_attrs_updated = 0
        tech_years_created = 0
        tech_years_updated = 0
        # Process the data based on sheet name
        with transaction.atomic():
            if not dry_run:
                # Begin a transaction - if any part fails, the entire import for this sheet is rolled back
                sid = transaction.savepoint()
            
            try:
                
                # Process sheet based on its name
                if sheet_name == 'Technologies':
                    technologies_created, technologies_updated = \
                        self._process_technologies_sheet(df, Technologies, dry_run)
                elif sheet_name == 'GeneratorAttributes':
                    generator_attrs_created, generator_attrs_updated = \
                        self._process_generator_attributes_sheet(df, Technologies, Generatorattributes, dry_run)
                elif sheet_name == 'StorageAttributes':
                    storage_attrs_created, storage_attrs_updated = \
                        self._process_storage_attributes_sheet(df, Technologies, Storageattributes, dry_run)
                # Check if sheet name matches 'Generators_YYYY' pattern
                elif re.match(r'Generators_\d{4}$', sheet_name):
                    year = int(sheet_name.split('_')[1])
                    tech_years_created, tech_years_updated = \
                        self._process_generators_year_sheet(df, Technologies, TechnologyYears, year, dry_run)
                else:
                    self.stdout.write(self.style.WARNING(
                        f"Sheet '{sheet_name}' is not recognized, skipping"
                    ))
                    return
                
                # Summary for this sheet
                self.stdout.write(self.style.SUCCESS(f"\nSummary for sheet '{sheet_name}':"))
                if technologies_created or technologies_updated:
                    self.stdout.write(f"Technologies: {technologies_created} created, {technologies_updated} updated")
                if generator_attrs_created or generator_attrs_updated:
                    self.stdout.write(f"Generator Attributes: {generator_attrs_created} created, {generator_attrs_updated} updated")
                if storage_attrs_created or storage_attrs_updated:
                    self.stdout.write(f"Storage Attributes: {storage_attrs_created} created, {storage_attrs_updated} updated")
                if tech_years_created or tech_years_updated:
                    self.stdout.write(f"Technology Years: {tech_years_created} created, {tech_years_updated} updated")
                                    
                if not dry_run:
                    # Commit the transaction
                    transaction.savepoint_commit(sid)
            except Exception as e:
                if not dry_run:
                    # Rollback the transaction
                    transaction.savepoint_rollback(sid)
                self.stderr.write(self.style.ERROR(f"Error processing sheet '{sheet_name}': {str(e)}"))
                raise
    
    def _process_technologies_sheet(self, df, Technologies, dry_run):
        """Process the Technologies sheet"""
        technologies_created = 0
        technologies_updated = 0
        # Check for Name column
        if 'Name' not in df.columns:
            self.stdout.write(self.style.WARNING(
                "Technologies sheet does not contain 'Name' column, skipping"
            ))
            return technologies_created, technologies_updated
        
        # Column mappings as specified
        mappings = {
            'Category': 'category',
            'Emissions': 'emissions',
            'Area': 'area',
            'Lifetime': 'lifetime'
        }
        
        # Process each row
        for _, row in df.iterrows():
            # Clean NaN values
            row = row.where(pd.notnull(row), None)
            
            # Skip if no technology name
            tech_name = row.get('Name')
            if not tech_name:
                continue
            
            # Create technology data dictionary
            tech_data = {'technology_name': tech_name}
            
            # Add technology_signature if it exists
            if 'technology_signature' in df.columns and row.get('technology_signature'):
                tech_data['technology_signature'] = row.get('technology_signature')
            
            # Map columns according to the specified mappings
            for sheet_col, db_col in mappings.items():
                if sheet_col in df.columns and row.get(sheet_col) is not None:
                    tech_data[db_col] = row.get(sheet_col)
            
            # Create or update the Technology object
            if not dry_run:
                tech_obj, created = Technologies.objects.update_or_create(
                    technology_name=tech_name,
                    defaults=tech_data
                )
                
                if created:
                    technologies_created += 1
                    self.stdout.write(f"Created technology: {tech_name}")
                else:
                    technologies_updated += 1
                    self.stdout.write(f"Updated technology: {tech_name}")
            return technologies_created, technologies_updated
    
    def _process_generator_attributes_sheet(self, df, Technologies, Generatorattributes, dry_run):
        """Process the GeneratorAttributes sheet"""
        generator_attrs_created = 0
        generator_attrs_updated = 0
        # Check if Name column exists
        if 'Name' not in df.columns:
            self.stdout.write(self.style.WARNING(
                "GeneratorAttributes sheet does not contain 'Name' column, skipping"
            ))
            return generator_attrs_created, generator_attrs_updated
        
        # Column mappings as specified
        mappings = {
            'Capacity Max': 'capacity_max',
            'Capacity Min': 'capacity_min',
            'Rampdown Max': 'rampdown_max',
            'Rampup Max': 'rampup_max',
            'Area': 'area'
        }
        
        # Process each row
        for _, row in df.iterrows():
            # Clean NaN values
            row = row.where(pd.notnull(row), None)
            
            # Skip if no technology name
            tech_name = row.get('Name')
            if not tech_name:
                continue
            
            # Create generator attributes data dictionary
            gen_data = {}
            
            # Map columns according to the specified mappings
            for sheet_col, db_col in mappings.items():
                if sheet_col in df.columns and row.get(sheet_col) is not None:
                    gen_data[db_col] = row.get(sheet_col)
            
            # Skip if no data to update
            if not gen_data:
                continue
            
            # Find the corresponding technology and update attributes
            if not dry_run:
                try:
                    tech_obj = Technologies.objects.get(technology_name=tech_name)
                    
                    gen_attr, gen_created = Generatorattributes.objects.update_or_create(
                        idtechnologies=tech_obj,
                        defaults=gen_data
                    )
                    
                    if gen_created:
                        generator_attrs_created += 1
                        self.stdout.write(f"Created generator attributes for: {tech_name}")
                    else:
                        generator_attrs_updated += 1
                        self.stdout.write(f"Updated generator attributes for: {tech_name}")
                except Technologies.DoesNotExist:
                    self.stdout.write(self.style.WARNING(
                        f"Technology '{tech_name}' not found, skipping generator attributes"
                    ))
            return generator_attrs_created, generator_attrs_updated
    
    def _process_storage_attributes_sheet(self, df, Technologies, Storageattributes, dry_run):
        """Process the StorageAttributes sheet"""
        storage_attrs_created = 0
        storage_attrs_updated = 0
        # Check if Name column exists
        if 'Name' not in df.columns:
            self.stdout.write(self.style.WARNING(
                "StorageAttributes sheet does not contain 'Name' column, skipping"
            ))
            return storage_attrs_created, storage_attrs_updated
        
        # Column mappings as specified
        mappings = {
            'Discharge Loss': 'discharge_loss',
            'Discharge Max': 'discharge_max',
            'Parasitic Loss': 'parasitic_loss',
            'Recharge Loss': 'recharge_loss',
            'Recharge Max': 'recharge_max'
        }
        
        # Process each row
        for _, row in df.iterrows():
            # Clean NaN values
            row = row.where(pd.notnull(row), None)
            
            # Skip if no technology name
            tech_name = row.get('Name')
            if not tech_name:
                continue
            
            # Create storage attributes data dictionary
            storage_data = {}
            
            # Map columns according to the specified mappings
            for sheet_col, db_col in mappings.items():
                if sheet_col in df.columns and row.get(sheet_col) is not None:
                    storage_data[db_col] = row.get(sheet_col)
            
            # Skip if no data to update
            if not storage_data:
                continue
            
            # Find the corresponding technology and update attributes
            if not dry_run:
                try:
                    tech_obj = Technologies.objects.get(technology_name=tech_name)
                    
                    storage_attr, storage_created = Storageattributes.objects.update_or_create(
                        idtechnologies=tech_obj,
                        defaults=storage_data
                    )
                    
                    if storage_created:
                        storage_attrs_created += 1
                        self.stdout.write(f"Created storage attributes for: {tech_name}")
                    else:
                        storage_attrs_updated += 1
                        self.stdout.write(f"Updated storage attributes for: {tech_name}")
                except Technologies.DoesNotExist:
                    self.stdout.write(self.style.WARNING(
                        f"Technology '{tech_name}' not found, skipping storage attributes"
                    ))
            return storage_attrs_created, storage_attrs_updated
    
    def _process_generators_year_sheet(self, df, Technologies, TechnologyYears, year, dry_run):
        """
        Process the Generators_YYYY sheet that contains data for a specific year
        """
        tech_years_created = 0
        tech_years_updated = 0
        # Check if Name column exists
        if 'Name' not in df.columns:
            self.stdout.write(self.style.WARNING(
                f"Generators_{year} sheet does not contain 'Name' column, skipping"
            ))
            return tech_years_created, tech_years_updated
        
        # Column mappings as specified
        mappings = {
            'Capex': 'capex',
            'FOM': 'fom',
            'VOM': 'vom',
            'Fuel': 'fuel'
        }
        
        # Process each row
        for _, row in df.iterrows():
            # Clean NaN values
            row = row.where(pd.notnull(row), None)
            
            # Skip if no technology name
            tech_name = row.get('Name')
            if not tech_name:
                continue
            
            # Create technology years data dictionary
            tech_year_data = {'year': year}
            
            # Map columns according to the specified mappings
            for sheet_col, db_col in mappings.items():
                if sheet_col in df.columns and row.get(sheet_col) is not None:
                    tech_year_data[db_col] = row.get(sheet_col)
            
            # Skip if no data to update
            if len(tech_year_data) <= 1:  # Only has 'year'
                continue
            
            # Find the corresponding technology and update years
            if not dry_run:
                try:
                    tech_obj = Technologies.objects.get(technology_name=tech_name)
                    
                    tech_year, year_created = TechnologyYears.objects.update_or_create(
                        idtechnologies=tech_obj,
                        year=year,
                        defaults=tech_year_data
                    )
                    
                    if year_created:
                        tech_years_created += 1
                        self.stdout.write(f"Created technology year: {tech_name} - {year}")
                    else:
                        tech_years_updated += 1
                        self.stdout.write(f"Updated technology year: {tech_name} - {year}")
                except Technologies.DoesNotExist:
                    self.stdout.write(self.style.WARNING(
                        f"Technology '{tech_name}' not found, skipping year data for {year}"
                    ))
            return tech_years_created, tech_years_updated
