from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('siren_web', '0154_gridlines_terminals_lifecycle_status'),
    ]

    operations = [
        # CELProgram: add start_date
        migrations.AddField(
            model_name='celprogram',
            name='start_date',
            field=models.DateField(blank=True, null=True),
        ),

        # CELStage: add start_date
        migrations.AddField(
            model_name='celstage',
            name='start_date',
            field=models.DateField(blank=True, null=True),
        ),

        # CELStage: remove geographic fields
        migrations.RemoveField(
            model_name='celstage',
            name='route_coordinates',
        ),
        migrations.RemoveField(
            model_name='celstage',
            name='from_latitude',
        ),
        migrations.RemoveField(
            model_name='celstage',
            name='from_longitude',
        ),
        migrations.RemoveField(
            model_name='celstage',
            name='to_latitude',
        ),
        migrations.RemoveField(
            model_name='celstage',
            name='to_longitude',
        ),
    ]
