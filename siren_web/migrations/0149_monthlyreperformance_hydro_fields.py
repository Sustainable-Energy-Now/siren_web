from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('siren_web', '0148_demandfactor_steepness'),
    ]

    operations = [
        migrations.AddField(
            model_name='monthlyreperformance',
            name='hydro_discharge',
            field=models.FloatField(default=0, help_text='Hydro discharge generation in GWh'),
        ),
        migrations.AddField(
            model_name='monthlyreperformance',
            name='hydro_charge',
            field=models.FloatField(default=0, help_text='Hydro pumping consumption in GWh'),
        ),
    ]