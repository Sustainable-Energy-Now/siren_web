from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("siren_web", "0162_facilities_build_probability_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="facilities",
            name="approvals",
            field=models.CharField(
                blank=True,
                choices=[
                    ("early", "Early Stage"),
                    ("progressing", "Progressing"),
                    ("advanced", "Advanced"),
                    ("approved", "Approved"),
                ],
                default="early",
                help_text="Progress through environmental and planning approval processes",
                max_length=15,
            ),
        ),
    ]
