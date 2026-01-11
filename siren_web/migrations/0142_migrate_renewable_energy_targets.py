# Generated migration to migrate RenewableEnergyTarget data to unified TargetScenario model

from django.db import migrations


def migrate_renewable_energy_targets(apps, schema_editor):
    """
    Migrate existing RenewableEnergyTarget records into TargetScenario model.
    Maps:
    - target_year -> year
    - target_percentage -> target_re_percentage
    - is_interim_target -> target_type ('interim' or 'major')
    - description -> description
    - target_emissions_tonnes -> target_emissions_tonnes
    """
    RenewableEnergyTarget = apps.get_model('siren_web', 'RenewableEnergyTarget')
    TargetScenario = apps.get_model('siren_web', 'TargetScenario')

    # Get all existing renewable energy targets
    existing_targets = RenewableEnergyTarget.objects.all()

    for old_target in existing_targets:
        # Determine target_type based on is_interim_target flag
        if old_target.is_interim_target:
            target_type = 'interim'
            type_label = 'Interim'
        else:
            target_type = 'major'
            type_label = 'Major'

        # Create scenario_name
        scenario_name = f"{old_target.target_year} {type_label} Target"

        # Check if a TargetScenario already exists for this year with base_case scenario_type
        # to avoid duplicate migration if run multiple times
        existing_scenario = TargetScenario.objects.filter(
            scenario_type='base_case',
            year=old_target.target_year
        ).first()

        if existing_scenario:
            # Update existing record with target data
            existing_scenario.scenario_name = scenario_name
            existing_scenario.target_type = target_type
            existing_scenario.description = old_target.description or ''
            existing_scenario.target_re_percentage = old_target.target_percentage
            existing_scenario.target_emissions_tonnes = old_target.target_emissions_tonnes
            existing_scenario.save()
            print(f"Updated existing TargetScenario for {old_target.target_year}")
        else:
            # Create new TargetScenario record
            TargetScenario.objects.create(
                scenario_name=scenario_name,
                scenario_type='base_case',
                year=old_target.target_year,
                target_type=target_type,
                description=old_target.description or '',
                target_re_percentage=old_target.target_percentage,
                target_emissions_tonnes=old_target.target_emissions_tonnes,
                # Generation fields default to 0
                wind_generation=0,
                solar_generation=0,
                dpv_generation=0,
                biomass_generation=0,
                gas_generation=0,
                # Other nullable fields
                operational_demand=None,
                underlying_demand=None,
                storage=None,
                probability_percentage=None,
                is_active=True,  # Set migrated targets as active by default
            )
            print(f"Migrated target for {old_target.target_year}: {old_target.target_percentage}% RE")


def reverse_migration(apps, schema_editor):
    """
    Reverse migration - delete TargetScenario records that came from RenewableEnergyTarget.
    This is a simple approach that removes all base_case scenarios with major/interim target_type.
    """
    TargetScenario = apps.get_model('siren_web', 'TargetScenario')

    # Delete scenarios that look like migrated targets
    TargetScenario.objects.filter(
        scenario_type='base_case',
        target_type__in=['major', 'interim']
    ).delete()
    print("Deleted migrated target scenarios")


class Migration(migrations.Migration):

    dependencies = [
        ('siren_web', '0141_alter_targetscenario_options_and_more'),
    ]

    operations = [
        migrations.RunPython(migrate_renewable_energy_targets, reverse_migration),
    ]