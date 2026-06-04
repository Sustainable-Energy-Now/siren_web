from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("siren_web", "0163_facilities_approvals"),
    ]

    operations = [
        migrations.AlterField(
            model_name="facilitywindturbines",
            name="idwindturbines",
            field=models.ForeignKey(
                blank=True,
                db_column="idwindturbines",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="siren_web.windturbines",
            ),
        ),
    ]
