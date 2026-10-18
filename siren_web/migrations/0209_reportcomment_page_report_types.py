from django.db import migrations, models


class Migration(migrations.Migration):
    """Choices-only change (no schema change): page-wide comment threads for
    the EV uptake tracker and the grid map."""

    dependencies = [
        ("siren_web", "0208_cel_source_watch"),
    ]

    operations = [
        migrations.AlterField(
            model_name="reportcomment",
            name="report_type",
            field=models.CharField(
                choices=[
                    ("monthly", "Monthly Dashboard"),
                    ("quarterly", "Quarterly Report"),
                    ("annual", "Annual Review"),
                    ("ev_uptake", "EV Uptake Tracker"),
                    ("grid_map", "Grid Map"),
                ],
                max_length=20,
            ),
        ),
    ]
