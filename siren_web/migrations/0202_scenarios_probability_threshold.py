from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("siren_web", "0201_fix_gencost_technologyyears_units"),
    ]

    operations = [
        migrations.AddField(
            model_name="scenarios",
            name="probability_threshold",
            field=models.FloatField(
                blank=True,
                null=True,
                help_text=(
                    "Minimum effective commissioning probability a proposed/planned "
                    "facility needed to be included, used when this Expected-band "
                    "scenario was last generated. Null for other bands and manual scenarios."
                ),
            ),
        ),
    ]
