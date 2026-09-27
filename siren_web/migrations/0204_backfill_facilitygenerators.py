# Data migration: seed a FacilityGenerators override row for every existing
# Generator-category facility, copying the values from its Technology's
# GeneratorAttributes row. This makes dispatch behavior identical immediately
# after migration -- facilities can then be given distinct capacity_min/
# capacity_max values going forward. Uses the legacy facilities.idtechnologies
# FK, the same link ScenariosTechnologies.update_capacity() already relies on.

from django.db import migrations


def backfill_facility_generators(apps, schema_editor):
    facilities = apps.get_model('siren_web', 'facilities')
    Generatorattributes = apps.get_model('siren_web', 'Generatorattributes')
    FacilityGenerators = apps.get_model('siren_web', 'FacilityGenerators')

    generator_facilities = facilities.objects.filter(
        idtechnologies__category='Generator'
    ).select_related('idtechnologies')

    for facility in generator_facilities:
        technology = facility.idtechnologies
        generator_attrs = Generatorattributes.objects.filter(
            idtechnologies=technology
        ).first()
        if generator_attrs is None:
            continue

        FacilityGenerators.objects.get_or_create(
            idfacilities=facility,
            idtechnologies=technology,
            defaults={
                'capacity_max': generator_attrs.capacity_max,
                'capacity_min': generator_attrs.capacity_min,
                'rampdown_max': generator_attrs.rampdown_max,
                'rampup_max': generator_attrs.rampup_max,
                'is_active': True,
            }
        )


def noop_reverse(apps, schema_editor):
    # Not reversed: deleting these rows would be destructive to any per-facility
    # edits made after this migration ran. A rollback of the schema migration
    # (0203) will cascade-delete this table anyway.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("siren_web", "0203_facilitygenerators"),
    ]

    operations = [
        migrations.RunPython(backfill_facility_generators, noop_reverse),
    ]
