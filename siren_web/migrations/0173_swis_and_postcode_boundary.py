import json

from django.db import migrations, models


def seed_swis_boundary(apps, schema_editor):
    """Seed the single SwisBoundary row from the committed GeoJSON file."""
    SwisBoundary = apps.get_model('siren_web', 'SwisBoundary')
    if SwisBoundary.objects.filter(name='SWIS').exists():
        return
    try:
        from powermapui.utils.swis_boundary import (
            boundary_geometry_from_file, polygon_vertex_count,
        )
        geojson = boundary_geometry_from_file()
    except Exception:
        # Keep migrations runnable in stripped environments (file missing etc.).
        return
    SwisBoundary.objects.create(
        name='SWIS',
        geojson=json.dumps(geojson),
        source='kml_seed',
        vertex_count=polygon_vertex_count(geojson),
    )


def unseed_swis_boundary(apps, schema_editor):
    SwisBoundary = apps.get_model('siren_web', 'SwisBoundary')
    SwisBoundary.objects.filter(name='SWIS').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('siren_web', '0172_ev_source_document_multifile'),
    ]

    operations = [
        migrations.CreateModel(
            name='SwisBoundary',
            fields=[
                ('idswisboundary', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(default='SWIS', max_length=50, unique=True)),
                ('geojson', models.TextField(help_text='GeoJSON Polygon geometry, WGS84 lon/lat')),
                ('source', models.CharField(default='kml_seed', help_text="'kml_seed' (seeded from swis_boundary.geojson) or 'hand_edited'", max_length=20)),
                ('vertex_count', models.PositiveIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'SWIS Boundary',
                'verbose_name_plural': 'SWIS Boundary',
                'db_table': 'swis_boundary',
            },
        ),
        migrations.CreateModel(
            name='PostcodeBoundary',
            fields=[
                ('idpostcodeboundary', models.AutoField(primary_key=True, serialize=False)),
                ('postcode', models.CharField(max_length=10, unique=True)),
                ('geojson', models.TextField(help_text='Simplified GeoJSON geometry, WGS84 lon/lat')),
                ('centroid_lat', models.FloatField(blank=True, null=True)),
                ('centroid_lon', models.FloatField(blank=True, null=True)),
                ('area_sqkm', models.FloatField(blank=True, null=True)),
                ('source', models.CharField(default='ABS POA 2021', max_length=40)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Postcode Boundary',
                'verbose_name_plural': 'Postcode Boundaries',
                'db_table': 'postcode_boundary',
                'ordering': ['postcode'],
            },
        ),
        migrations.RunPython(seed_swis_boundary, unseed_swis_boundary),
    ]
