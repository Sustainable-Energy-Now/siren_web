"""
Repairs TechnologyYears rows written by apply_gencost_cost_case before it
converted units:

1. capex: GenCost publishes capex in $/kW, but TechnologyYears (and the
   PowerMatch engine, which does capacity_MW * capex) use $/MW. Every
   GenCost-written row carries a non-null capex_premium_pct, so those rows
   are scaled x1000. The capex < 100,000 guard means a row already in $/MW
   (< $100/kW is not a real generation capex) is never scaled twice.

2. fom/vom/fuel: apply_gencost_cost_case only writes capex, so rows it
   created for years the spreadsheet import never covered (2034+) have
   null fom/vom/fuel, which the engine silently treats as 0. Each null is
   filled from that technology's latest earlier non-null value.

Not reversible: the pre-fix values were wrong, and filled-forward values
can't be told apart from real ones afterwards.
"""
from django.db import migrations

KW_TO_MW = 1000
MAX_PER_KW_CAPEX = 100_000
FILL_FIELDS = ('fom', 'vom', 'fuel')


def fix_technologyyears(apps, schema_editor):
    TechnologyYears = apps.get_model('siren_web', 'TechnologyYears')

    # Batched writes: the remote MariaDB host has enough per-query latency
    # that one save() per row is slow (see apply_gencost_cost_case.py).
    rows = list(TechnologyYears.objects.order_by('idtechnologies_id', 'year'))
    changed = []
    last_seen = {}  # technology id -> {field: latest non-null value}
    for row in rows:
        dirty = False
        if (row.capex_premium_pct is not None and row.capex is not None
                and row.capex < MAX_PER_KW_CAPEX):
            row.capex = row.capex * KW_TO_MW
            dirty = True
        seen = last_seen.setdefault(row.idtechnologies_id, {})
        for field in FILL_FIELDS:
            value = getattr(row, field)
            if value is None:
                if field in seen:
                    setattr(row, field, seen[field])
                    dirty = True
            else:
                seen[field] = value
        if dirty:
            changed.append(row)

    TechnologyYears.objects.bulk_update(changed, ['capex', *FILL_FIELDS], batch_size=200)


class Migration(migrations.Migration):

    dependencies = [
        ("siren_web", "0200_seed_scenario_types_and_backfill"),
    ]

    operations = [
        migrations.RunPython(fix_technologyyears, migrations.RunPython.noop),
    ]
