import django.db.models.deletion
from django.db import migrations, models


def delete_legacy_analysis(apps, schema_editor):
    # Saved analyses predating this migration don't record their Demand
    # Scenario; they are derived data and are rebuilt by re-running the baseline.
    apps.get_model('siren_web', 'Analysis').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('siren_web', '0205_alter_scenarios_forecast_year'),
    ]

    operations = [
        migrations.AddField(
            model_name='analysis',
            name='iddemandscenarios',
            field=models.ForeignKey(
                null=True, db_column='idDemandScenarios',
                on_delete=django.db.models.deletion.CASCADE, to='siren_web.demandscenarios',
            ),
        ),
        migrations.RunPython(delete_legacy_analysis, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='analysis',
            name='iddemandscenarios',
            field=models.ForeignKey(
                db_column='idDemandScenarios',
                on_delete=django.db.models.deletion.CASCADE, to='siren_web.demandscenarios',
            ),
        ),
    ]
