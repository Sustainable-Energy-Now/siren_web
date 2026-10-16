import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("siren_web", "0207_facilitygenerationbias"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CELSourceWatch",
            fields=[
                ("idcelsourcewatch", models.AutoField(primary_key=True, serialize=False)),
                ("url", models.CharField(max_length=500, unique=True)),
                ("label", models.CharField(blank=True, max_length=200)),
                ("source_kind", models.CharField(
                    choices=[("html", "Web page"), ("pdf", "PDF")], default="html", max_length=10)),
                ("origin", models.CharField(
                    choices=[("seed", "Seed list"), ("discovered", "Discovered link"),
                             ("manual", "Added by hand")],
                    default="manual", max_length=12)),
                ("discover_links", models.BooleanField(
                    default=False,
                    help_text="Add CEL-looking links on this page as new watches (one hop only)")),
                ("is_active", models.BooleanField(default=True)),
                ("content_hash", models.CharField(blank=True, max_length=64)),
                ("last_checked_at", models.DateTimeField(blank=True, null=True)),
                ("last_changed_at", models.DateTimeField(blank=True, null=True)),
                ("last_status_code", models.IntegerField(blank=True, null=True)),
                ("last_error", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("cel_program", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="source_watches", to="siren_web.celprogram",
                    help_text="Program this source is about, used when its text doesn't name one")),
            ],
            options={"db_table": "cel_source_watch", "ordering": ["-last_changed_at", "label"]},
        ),
        migrations.CreateModel(
            name="CELSourceSnapshot",
            fields=[
                ("idcelsourcesnapshot", models.AutoField(primary_key=True, serialize=False)),
                ("retrieved_at", models.DateTimeField(auto_now_add=True)),
                ("content_hash", models.CharField(max_length=64)),
                ("text", models.TextField()),
                ("added_text", models.TextField(
                    blank=True,
                    help_text="Lines new since the previous snapshot (all text on the first one)")),
                ("is_initial", models.BooleanField(default=False)),
                ("watch", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="snapshots",
                    to="siren_web.celsourcewatch")),
            ],
            options={"db_table": "cel_source_snapshot", "ordering": ["-retrieved_at"]},
        ),
        migrations.CreateModel(
            name="CELProposedUpdate",
            fields=[
                ("idcelproposedupdate", models.AutoField(primary_key=True, serialize=False)),
                ("source", models.CharField(
                    choices=[("document", "Published document"), ("gis", "Western Power GIS"),
                             ("derived", "Derived from facilities")],
                    max_length=10)),
                ("source_url", models.CharField(blank=True, max_length=500)),
                ("field_name", models.CharField(
                    choices=[("funding_status", "Funding status"),
                             ("expected_operational_date", "Expected operational date"),
                             ("actual_operational_date", "Actual operational date"),
                             ("capacity_new_mw", "New capacity (MW)"),
                             ("capacity_unlocked_existing_mw", "Unlocked existing capacity (MW)"),
                             ("reserved_capacity_mw", "Reserved capacity (MW)")],
                    max_length=40)),
                ("current_value", models.CharField(blank=True, max_length=100)),
                ("proposed_value", models.CharField(max_length=100)),
                ("evidence", models.TextField(
                    help_text="Quoted sentence or matched-asset summary behind the proposal")),
                ("status", models.CharField(
                    choices=[("pending", "Pending"), ("accepted", "Accepted"),
                             ("rejected", "Rejected"), ("superseded", "Superseded")],
                    default="pending", max_length=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("cel_program", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="proposed_updates",
                    to="siren_web.celprogram")),
                ("cel_stage", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name="proposed_updates", to="siren_web.celstage")),
                ("snapshot", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="proposals", to="siren_web.celsourcesnapshot")),
                ("reviewed_by", models.ForeignKey(
                    blank=True, db_constraint=False, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="cel_proposal_reviews", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "cel_proposed_update", "ordering": ["-created_at"]},
        ),
    ]
