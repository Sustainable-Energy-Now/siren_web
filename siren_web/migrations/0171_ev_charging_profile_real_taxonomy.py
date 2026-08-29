# Generated manually on 2026-08-26 — EvChargingProfile redesigned to
# match the real AEMO IASR EV workbook taxonomy (see model docstring).
# Table had zero rows (no real data had been ingested against the
# original home/public/commercial schema), so this drops and recreates
# it rather than a field-by-field alter.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("siren_web", "0170_ev_uptake_charging_load_models"),
    ]

    operations = [
        migrations.DeleteModel(name="EvChargingProfile"),
        migrations.CreateModel(
            name="EvChargingProfile",
            fields=[
                (
                    "idevchargingprofile",
                    models.AutoField(
                        db_column="idevchargingprofile",
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "region",
                    models.CharField(
                        help_text="Source region, e.g. 'WEM' (WA) or a NEM region borrowed per O5",
                        max_length=50,
                    ),
                ),
                (
                    "charging_type_label",
                    models.CharField(
                        help_text="Raw AEMO charging-type label, e.g. 'Off-peak and Solar Charging'",
                        max_length=100,
                    ),
                ),
                (
                    "charging_mode",
                    models.CharField(
                        choices=[
                            ("unmanaged", "Unmanaged — arrival-based charging (D3 honest baseline)"),
                            ("managed", "Managed — TOU/off-peak/coordinated charging (D3/D11 lever)"),
                            ("v2x", "Vehicle-to-home/grid (dormant, D4/FR-17 — excluded from trace synthesis)"),
                            ("other", "Unrecognised source label — excluded from trace synthesis until classified"),
                        ],
                        help_text="D3 unmanaged/managed bucket this charging_type_label was classified into",
                        max_length=10,
                    ),
                ),
                (
                    "share_of_charging",
                    models.FloatField(
                        help_text="Fraction of fleet using this charging type (D8: Step Change scenario)"
                    ),
                ),
                (
                    "weekday_halfhourly_shape",
                    models.JSONField(
                        help_text="48 fractions (sum to 1) — relative charging energy per half-hour, weekday"
                    ),
                ),
                (
                    "weekend_halfhourly_shape",
                    models.JSONField(
                        help_text="48 fractions (sum to 1) — relative charging energy per half-hour, weekend"
                    ),
                ),
                ("report_citation", models.CharField(blank=True, max_length=255)),
                ("page_ref", models.CharField(blank=True, max_length=50)),
                ("table_ref", models.CharField(blank=True, max_length=100)),
                ("citation_year", models.PositiveIntegerField(blank=True, null=True)),
                (
                    "source_document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="charging_profiles",
                        to="siren_web.evsourcedocument",
                    ),
                ),
            ],
            options={
                "verbose_name": "EV Charging Profile",
                "verbose_name_plural": "EV Charging Profiles",
                "db_table": "ev_charging_profile",
                "unique_together": {("source_document", "region", "charging_type_label")},
            },
        ),
    ]
