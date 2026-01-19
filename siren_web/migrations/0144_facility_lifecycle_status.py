# Generated migration for facility lifecycle status tracking

from django.db import migrations, models
import django.core.validators


def migrate_status_from_active_existing(apps, schema_editor):
    """
    Migrate existing active/existing boolean fields to the new status field.

    Mapping:
    - active=True, existing=True → 'commissioned'
    - active=False, existing=True → 'decommissioned'
    - active=True, existing=False → 'planned'
    - active=False, existing=False → 'proposed'
    """
    facilities = apps.get_model('siren_web', 'facilities')

    for facility in facilities.objects.all():
        if facility.active and facility.existing:
            facility.status = 'commissioned'
        elif not facility.active and facility.existing:
            facility.status = 'decommissioned'
        elif facility.active and not facility.existing:
            facility.status = 'planned'
        else:  # not active and not existing
            facility.status = 'proposed'
        facility.save(update_fields=['status'])


def reverse_migrate_status(apps, schema_editor):
    """
    Reverse migration - nothing to do since we're keeping active/existing columns.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('siren_web', '0143_delete_renewableenergytarget_and_more'),
    ]

    operations = [
        # Step 1: Add new lifecycle fields
        migrations.AddField(
            model_name='facilities',
            name='status',
            field=models.CharField(
                choices=[
                    ('proposed', 'Proposed'),
                    ('planned', 'Planned'),
                    ('under_construction', 'Under Construction'),
                    ('commissioned', 'Commissioned'),
                    ('decommissioned', 'Decommissioned'),
                ],
                default='commissioned',
                help_text='Current lifecycle status of the facility',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='facilities',
            name='commissioning_date',
            field=models.DateField(
                blank=True,
                help_text='Actual or expected commissioning date',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='facilities',
            name='decommissioning_date',
            field=models.DateField(
                blank=True,
                help_text='Actual or expected decommissioning date',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='facilities',
            name='commissioning_probability',
            field=models.FloatField(
                blank=True,
                help_text='Probability of commissioning (0-1), relevant for proposed/planned facilities',
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(0.0),
                    django.core.validators.MaxValueValidator(1.0),
                ],
            ),
        ),
        # Step 2: Migrate data from active/existing to status
        migrations.RunPython(
            migrate_status_from_active_existing,
            reverse_migrate_status,
        ),
        # Note: active and existing columns are kept for backward compatibility
        # They can be removed in a future migration
    ]
