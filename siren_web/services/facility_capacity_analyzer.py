"""
Derives per-facility capacity attributes (observed max/min output as a
fraction of nameplate, round-trip efficiency, capacity factor) from one full
calendar year of FacilityScadaMatrix, and writes them back onto the existing
model fields that already exist for exactly this purpose:

  - FacilityGenerators.capacity_max / capacity_min (per-facility override
    fractions, falling back to Generatorattributes technology defaults)
  - Storageattributes.round_trip_efficiency (technology-level; only written
    when the technology isn't shared by more than one active storage
    installation, since overwriting it would silently change the assumption
    used by every other facility on that technology)
  - facilities.capacityfactor (existing field, previously only ever
    hardcoded to 1 by the facility-import commands)

No schema changes. See powerplotui/services/facility_analyzer.py for the
pre-existing ad-hoc CLI analogue (deprecated-FK battery detection, prints
only) -- this module is the pipeline-writing counterpart and does not
replace it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np

from siren_web.models import FacilityScadaMatrix, facilities
from siren_web.services.facility_scada_matrix import facility_row_index, load_year_matrix

MIN_COVERAGE_DEFAULT = 0.9


@dataclass
class FacilityAnalysisResult:
    facility_id: int
    facility_name: str
    coverage: float
    max_mw: float | None = None
    min_mw: float | None = None
    discharge_mwh: float | None = None
    charge_mwh: float | None = None
    capacity_factor: float | None = None
    round_trip_efficiency: float | None = None
    applied: dict = field(default_factory=dict)
    skip_reason: str | None = None


def get_latest_full_scada_year() -> int:
    """The most recent calendar year with a FacilityScadaMatrix row that
    isn't the (necessarily incomplete) year in progress."""
    row = FacilityScadaMatrix.objects.filter(year__lt=date.today().year).order_by('-year').first()
    if row is None:
        raise FacilityScadaMatrix.DoesNotExist('No full calendar year of FacilityScadaMatrix data found.')
    return row.year


def _nameplate_mw(facility: facilities) -> float | None:
    """Best-available nameplate capacity for turning observed MW into a
    fraction. Prefers the facility's own total_capacity (override or summed
    installations); falls back to summed active storage power_capacity,
    since get_capacity_by_technology() doesn't include FacilityGenerators
    (it has no nameplate field of its own -- only fraction overrides)."""
    if facility.total_capacity:
        return facility.total_capacity
    storage_mw = sum(
        inst.power_capacity or 0
        for inst in facility.storage_installations.filter(is_active=True)
    )
    return storage_mw or None


def analyze_year(year: int, min_coverage: float = MIN_COVERAGE_DEFAULT) -> list[FacilityAnalysisResult]:
    """Analyze every facility present in `year`'s FacilityScadaMatrix."""
    facility_ids, matrix = load_year_matrix(year)
    scada_row = FacilityScadaMatrix.objects.get(year=year)
    hours_in_year = scada_row.n_intervals / 2

    facility_by_id = facilities.objects.in_bulk(facility_ids)
    idx = facility_row_index(facility_ids)

    results = []
    for facility_id in facility_ids:
        facility = facility_by_id.get(facility_id)
        if facility is None:
            results.append(FacilityAnalysisResult(
                facility_id=facility_id, facility_name='(unknown)', coverage=0.0,
                skip_reason='No matching facilities row for this facility_id.',
            ))
            continue

        trace = matrix[idx[facility_id], :]
        valid = ~np.isnan(trace)
        coverage = float(valid.mean()) if trace.size else 0.0

        result = FacilityAnalysisResult(
            facility_id=facility_id, facility_name=facility.facility_name, coverage=coverage,
        )

        if coverage < min_coverage:
            result.skip_reason = (
                f'Insufficient interval coverage ({coverage:.1%} < {min_coverage:.1%} required).'
            )
            results.append(result)
            continue

        valid_trace = trace[valid]
        mw = valid_trace * 2
        result.max_mw = float(np.max(mw))
        result.min_mw = float(np.min(mw))
        result.discharge_mwh = float(np.sum(valid_trace[valid_trace > 0]))

        # Round-trip efficiency only makes sense for storage facilities --
        # generators/renewables can show small negative readings from
        # station-service/parasitic load, which would otherwise be
        # misread as "charging" and produce a meaningless ratio.
        if facility.has_storage:
            charge_mwh = float(-np.sum(valid_trace[valid_trace < 0]))
            result.charge_mwh = charge_mwh
            if charge_mwh > 0:
                result.round_trip_efficiency = result.discharge_mwh / charge_mwh

        nameplate_mw = _nameplate_mw(facility)
        if nameplate_mw:
            result.capacity_factor = result.discharge_mwh / (nameplate_mw * hours_in_year)

        results.append(result)

    return results


def apply_results(results: list[FacilityAnalysisResult], dry_run: bool = False) -> dict:
    """Write derived values onto the existing model fields. Returns a
    summary dict: {'analyzed': N, 'applied': M, 'skipped': K}."""
    summary = {'analyzed': len(results), 'applied': 0, 'skipped': 0}

    for result in results:
        if result.skip_reason:
            summary['skipped'] += 1
            continue

        facility = facilities.objects.filter(pk=result.facility_id).first()
        if facility is None:
            summary['skipped'] += 1
            continue

        nameplate_mw = _nameplate_mw(facility)

        if facility.is_generator and nameplate_mw and result.max_mw is not None:
            capacity_max = max(0.0, min(result.max_mw / nameplate_mw, 1.2))
            capacity_min = max(0.0, min(max(result.min_mw, 0.0) / nameplate_mw, 1.0))
            for installation in facility.generator_installations.filter(is_active=True):
                result.applied[f'generator_installation_{installation.pk}'] = True
                if not dry_run:
                    installation.capacity_max = capacity_max
                    installation.capacity_min = capacity_min
                    installation.save(update_fields=['capacity_max', 'capacity_min', 'updated_at'])

        if facility.has_storage and result.round_trip_efficiency is not None:
            for installation in facility.storage_installations.filter(is_active=True):
                technology = installation.idtechnologies
                shared_count = technology.facility_installations.filter(is_active=True).count()
                if shared_count > 1:
                    result.applied[f'storage_installation_{installation.pk}_rte'] = False
                    continue
                storage_attrs = technology.storage_attrs
                result.applied[f'storage_installation_{installation.pk}_rte'] = True
                if not dry_run and storage_attrs is not None:
                    storage_attrs.round_trip_efficiency = result.round_trip_efficiency
                    storage_attrs.save(update_fields=['round_trip_efficiency'])

        if result.capacity_factor is not None:
            result.applied['capacityfactor'] = True
            if not dry_run:
                facility.capacityfactor = result.capacity_factor
                facility.save(update_fields=['capacityfactor'])

        if any(result.applied.values()):
            summary['applied'] += 1
        else:
            summary['skipped'] += 1

    return summary
