# Merges EsooSourceDocument + EvSourceDocument into a single
# SourceDocument model with two nullable vintage FKs (esoo_vintage /
# ev_vintage) and a CheckConstraint enforcing exactly one is set.
#
# Existing rows are preserved. EV source-document primary keys are
# carried over verbatim onto the new `source_document` table so the
# ev_charging_profile.source_document_id foreign keys stay valid across
# the FK retarget; ESOO rows are re-keyed above the EV id range.
#
# Not reversible: the merge is a one-way structural consolidation.
import django.db.models.deletion
from django.db import migrations, models


def copy_source_documents(apps, schema_editor):
    EsooSourceDocument = apps.get_model('siren_web', 'EsooSourceDocument')
    EvSourceDocument = apps.get_model('siren_web', 'EvSourceDocument')
    SourceDocument = apps.get_model('siren_web', 'SourceDocument')

    ev_docs = list(EvSourceDocument.objects.all())
    # Offset ESOO ids above every EV id so the two id spaces never collide
    # while EV ids stay untouched (ev_charging_profile FKs point at them).
    offset = max((d.pk for d in ev_docs), default=0)

    SourceDocument.objects.bulk_create([
        SourceDocument(
            idsourcedocument=d.pk,
            ev_vintage_id=d.vintage_id,
            doc_type=d.doc_type,
            source_url=d.source_url,
            checksum=d.checksum,
            local_file_path=d.local_file_path,
            retrieved_at=d.retrieved_at,
        )
        for d in ev_docs
    ])

    SourceDocument.objects.bulk_create([
        SourceDocument(
            idsourcedocument=offset + d.pk,
            esoo_vintage_id=d.vintage_id,
            doc_type=d.doc_type,
            source_url=d.source_url,
            checksum=d.checksum,
            local_file_path=d.local_file_path,
            retrieved_at=d.retrieved_at,
        )
        for d in EsooSourceDocument.objects.all()
    ])


def reverse_not_supported(apps, schema_editor):
    raise RuntimeError(
        "Migration 0174 (unify SourceDocument) is not reversible; "
        "restore the esoo_source_document / ev_source_document tables from backup."
    )


class Migration(migrations.Migration):

    dependencies = [
        ('siren_web', '0174_ev_actuals_documents_and_quarters'),
    ]

    operations = [
        # Free up the `source_documents` reverse accessor on the vintage
        # models before the new model claims it (avoids an accessor clash
        # while both old and new models briefly coexist in migration state).
        migrations.AlterField(
            model_name='esoosourcedocument',
            name='vintage',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='+',
                to='siren_web.esoovintage',
            ),
        ),
        migrations.AlterField(
            model_name='evsourcedocument',
            name='vintage',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='+',
                to='siren_web.evvintage',
            ),
        ),
        migrations.CreateModel(
            name='SourceDocument',
            fields=[
                (
                    'idsourcedocument',
                    models.AutoField(
                        db_column='idsourcedocument', primary_key=True, serialize=False
                    ),
                ),
                (
                    'doc_type',
                    models.CharField(
                        choices=[
                            ('report', 'ESOO — Main report (PDF)'),
                            ('data_register', 'ESOO — Data Register workbook (XLSX) — or its "Figures" half, in years AEMO split it'),
                            ('data_register_tables', 'ESOO — Data Register "Tables" workbook (XLSX) — years where AEMO split the register in two'),
                            ('demand_traces', 'ESOO — Demand Traces workbook (XLSB)'),
                            ('reliability_methodology', 'ESOO — EY Reliability Assessment Methodology report'),
                            ('csiro_postcode_fleet_csv', 'EV — CSIRO postcode-level fleet/consumption CSV (one per TECH_TYPE, real CSIRO Data Shop export)'),
                            ('csiro_summary', 'EV — CSIRO state-level summary CSV (WA_SUMMARY_*.csv, no postcode breakdown)'),
                            ('csiro_report', 'EV — CSIRO EV Projections report/methodology document'),
                            ('aemo_isp_step_change', 'EV — AEMO ISP Step Change charging-profile document'),
                            ('other', 'Other'),
                        ],
                        max_length=30,
                    ),
                ),
                ('source_url', models.URLField(blank=True, max_length=500)),
                ('checksum', models.CharField(blank=True, max_length=64)),
                (
                    'local_file_path',
                    models.CharField(
                        blank=True,
                        help_text='Path (relative to ESOO_ARCHIVE_DIR / EV_ARCHIVE_DIR) of the retrieved document',
                        max_length=500,
                    ),
                ),
                ('retrieved_at', models.DateTimeField(blank=True, null=True)),
                (
                    'esoo_vintage',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='source_documents',
                        to='siren_web.esoovintage',
                    ),
                ),
                (
                    'ev_vintage',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='source_documents',
                        to='siren_web.evvintage',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Source Document',
                'verbose_name_plural': 'Source Documents',
                'db_table': 'source_document',
            },
        ),
        migrations.AddConstraint(
            model_name='sourcedocument',
            constraint=models.UniqueConstraint(
                fields=('esoo_vintage', 'doc_type'), name='uniq_esoo_source_document'
            ),
        ),
        migrations.AddConstraint(
            model_name='sourcedocument',
            constraint=models.UniqueConstraint(
                fields=('ev_vintage', 'doc_type', 'local_file_path'),
                name='uniq_ev_source_document',
            ),
        ),
        migrations.AddConstraint(
            model_name='sourcedocument',
            constraint=models.CheckConstraint(
                check=(
                    models.Q(('esoo_vintage__isnull', False), ('ev_vintage__isnull', True))
                    | models.Q(('esoo_vintage__isnull', True), ('ev_vintage__isnull', False))
                ),
                name='source_document_exactly_one_vintage',
            ),
        ),
        migrations.RunPython(copy_source_documents, reverse_not_supported),
        migrations.AlterField(
            model_name='evchargingprofile',
            name='source_document',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='charging_profiles',
                to='siren_web.sourcedocument',
            ),
        ),
        migrations.DeleteModel(name='EvSourceDocument'),
        migrations.DeleteModel(name='EsooSourceDocument'),
    ]
