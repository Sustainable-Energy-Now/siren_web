from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("siren_web", "0193_wind_turbine_library_assumed_turbine"),
    ]

    operations = [
        migrations.AlterField(
            model_name="esoofigure",
            name="demand_basis",
            field=models.CharField(
                choices=[
                    ("operational", "Operational"),
                    ("underlying", "Underlying"),
                    ("delivered", "Delivered"),
                    ("other", "Other"),
                ],
                default="operational",
                max_length=20,
            ),
        ),
    ]
