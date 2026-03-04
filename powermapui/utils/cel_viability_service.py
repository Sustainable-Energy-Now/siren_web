"""
CEL Viability Service
=====================
Computes and persists transmission viability scores for RE facilities against
Clean Energy Link (CEL) transmission stages.

The SWIS network is fully congested at scale.  A proposed/planned RE facility
can only be expected to commission if it geographically aligns with a CEL stage
that has sufficient remaining capacity and a credible funding status.

Viability score = cel_funding_weight × facility_status_weight × capacity_feasibility_score

All three components are in [0.0, 1.0].  Results are stored in
FacilityCELAlignment for fast map/dashboard retrieval.

Usage
-----
    from powermapui.utils.cel_viability_service import CELViabilityService

    # Full recompute (called by management command)
    stats = CELViabilityService.score_all_facilities()

    # Single stage (called from admin action)
    count = CELViabilityService.score_facilities_for_stage(stage)

    # Dashboard summary
    summary = CELViabilityService.get_pipeline_summary()
"""

import logging
import math

from django.db import transaction

from siren_web.models import (
    CELStage,
    FacilityCELAlignment,
    FACILITY_STATUS_CHOICES,
    facilities as FacilitiesModel,
)

logger = logging.getLogger(__name__)

# Probability weight for each facility development status.
# Answers: "If this project has transmission access, how likely is it to be built?"
FACILITY_STATUS_WEIGHTS = {
    'proposed':          0.30,
    'planned':           0.60,
    'under_construction': 0.85,
    'commissioned':      1.00,
    'decommissioned':    0.00,
}

# Statuses that make sense to score — pipeline only (exclude commissioned and decommissioned)
SCOREABLE_STATUSES = {'proposed', 'planned', 'under_construction'}


# ---------------------------------------------------------------------------
# Geometry helpers (no GeoDjango required)
# ---------------------------------------------------------------------------

def _haversine_km(lat1, lon1, lat2, lon2):
    """Straight-line distance between two (lat, lon) points in km."""
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _point_to_segment_distance_km(plat, plon, lat1, lon1, lat2, lon2):
    """
    Minimum distance from point P to line segment AB in km.

    Projects onto a local flat-earth coordinate system centred at the
    segment midpoint.  Accurate to within ~0.1% for segments up to 200 km,
    which covers all realistic CEL stage segments.
    """
    # Approximate degree-to-km conversion at the centre of the segment
    mid_lat = math.radians((lat1 + lat2) / 2)
    km_per_lat = 111.0
    km_per_lon = 111.0 * math.cos(mid_lat)

    # Cartesian projection
    ax = (lon1 - plon) * km_per_lon
    ay = (lat1 - plat) * km_per_lat
    bx = (lon2 - plon) * km_per_lon
    by = (lat2 - plat) * km_per_lat

    ab_sq = ax * ax + ay * ay + bx * bx + by * by - 2 * (ax * bx + ay * by)
    # ab_sq is |AB|², derived below without intermediate vars:
    abx = bx - ax
    aby = by - ay
    ab_sq = abx * abx + aby * aby

    if ab_sq == 0:
        # Degenerate segment — just distance to endpoint
        return math.sqrt(ax * ax + ay * ay)

    # Parameter t for the projection of P onto AB (clamped to [0, 1])
    t = max(0.0, min(1.0, -(ax * abx + ay * aby) / ab_sq))

    # Closest point on segment to P
    cx = ax + t * abx
    cy = ay + t * aby
    return math.sqrt(cx * cx + cy * cy)


def distance_to_route_km(facility_lat, facility_lon, route_coords):
    """
    Minimum distance from (facility_lat, facility_lon) to a polyline
    defined by route_coords = [[lat, lon], [lat, lon], ...].

    Returns float distance in km, or None if route_coords is empty.
    """
    if not route_coords:
        return None

    if len(route_coords) == 1:
        return _haversine_km(facility_lat, facility_lon,
                             route_coords[0][0], route_coords[0][1])

    min_dist = float('inf')
    for i in range(len(route_coords) - 1):
        d = _point_to_segment_distance_km(
            facility_lat, facility_lon,
            route_coords[i][0], route_coords[i][1],
            route_coords[i + 1][0], route_coords[i + 1][1],
        )
        if d < min_dist:
            min_dist = d

    return min_dist


# ---------------------------------------------------------------------------
# Main service class
# ---------------------------------------------------------------------------

class CELViabilityService:
    """
    Service for computing RE facility viability against CEL transmission stages.

    All public methods are class methods — no instantiation required.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def score_all_facilities(cls, scenario=None, verbosity=1):
        """
        Recompute viability scores for every active CEL stage against every
        scoreable facility.  Existing exception records are preserved.

        Args:
            scenario:  Optional Scenarios instance.  When supplied, only
                       facilities linked to that scenario are scored.
            verbosity: 0 = silent, 1 = summary, 2 = per-facility detail.

        Returns:
            dict with keys: stages_processed, facilities_scored,
                            alignments_created, alignments_updated
        """
        stages = CELStage.objects.filter(is_active=True).select_related('cel_program')
        if not stages.exists():
            logger.warning("No active CEL stages found — nothing to score.")
            return {'stages_processed': 0, 'facilities_scored': 0,
                    'alignments_created': 0, 'alignments_updated': 0}

        facility_qs = cls._get_facility_queryset(scenario)

        totals = {'stages_processed': 0, 'facilities_scored': 0,
                  'alignments_created': 0, 'alignments_updated': 0}

        for stage in stages:
            counts = cls._score_stage(stage, facility_qs, verbosity)
            totals['stages_processed'] += 1
            totals['facilities_scored'] += counts['facilities_scored']
            totals['alignments_created'] += counts['created']
            totals['alignments_updated'] += counts['updated']

        if verbosity >= 1:
            logger.info(
                "CEL viability complete: %d stages, %d facilities, "
                "%d created, %d updated",
                totals['stages_processed'], totals['facilities_scored'],
                totals['alignments_created'], totals['alignments_updated'],
            )
        return totals

    @classmethod
    def score_facilities_for_stage(cls, stage, verbosity=1):
        """
        Recompute viability scores for all scoreable facilities against a
        single CEL stage.  Used by the admin 'recompute_viability' action.

        Returns:
            int — number of alignment records created or updated.
        """
        facility_qs = cls._get_facility_queryset()
        counts = cls._score_stage(stage, facility_qs, verbosity)
        return counts['created'] + counts['updated']

    @classmethod
    def score_facility(cls, facility):
        """
        Score a single facility against all active CEL stages and persist results.

        Returns:
            list of dicts, one per active stage, with keys:
            stage_id, stage_name, is_aligned, distance_km, viability_score,
            viability_label, cel_funding_weight, facility_status_weight,
            capacity_feasibility_score
        """
        stages = CELStage.objects.filter(is_active=True).select_related('cel_program')
        results = []

        for stage in stages:
            result = cls._compute_alignment(facility, stage)
            cls._persist_alignment(facility, stage, result, preserve_exceptions=True)
            results.append(result)

        return results

    @classmethod
    def get_pipeline_summary(cls):
        """
        Aggregated transmission capacity and pipeline summary for the dashboard.

        Returns a dict with:
          by_viability  — count and total MW per viability tier
          by_stage      — per-stage capacity and pipeline breakdown
          totals        — headline figures
        """
        from django.db.models import Sum, Count

        alignments = (
            FacilityCELAlignment.objects
            .filter(is_aligned=True)
            .select_related('facility', 'cel_stage', 'cel_stage__cel_program')
        )

        by_viability = {
            tier: {'count': 0, 'capacity_mw': 0.0}
            for tier in ('high', 'medium', 'low', 'exception', 'unscored')
        }

        for a in alignments:
            cap = a.facility.capacity or 0.0
            tier = a.viability_label
            by_viability[tier]['count'] += 1
            by_viability[tier]['capacity_mw'] += cap

        # Per-stage breakdown
        stages = CELStage.objects.filter(is_active=True).select_related('cel_program')
        by_stage = []
        for stage in stages:
            stage_alignments = alignments.filter(cel_stage=stage, is_aligned=True)
            high_mw = sum(
                (a.facility.capacity or 0.0)
                for a in stage_alignments
                if a.viability_label == 'high'
            )
            by_stage.append({
                'stage_id': stage.cel_stage_id,
                'stage_name': stage.name,
                'program_name': stage.cel_program.name,
                'program_code': stage.cel_program.code,
                'funding_status': stage.funding_status,
                'funding_status_weight': stage.funding_status_weight,
                'total_capacity_mw': stage.total_capacity_mw,
                'reserved_capacity_mw': stage.reserved_capacity_mw or 0.0,
                'available_capacity_mw': stage.available_capacity_mw,
                'aligned_facility_count': stage_alignments.count(),
                'high_viability_pipeline_mw': high_mw,
                'display_color': stage.display_color,
            })

        active_stages = CELStage.objects.filter(is_active=True)
        total_cel_capacity = sum(s.total_capacity_mw for s in active_stages)
        total_available = sum(s.available_capacity_mw for s in active_stages)
        total_pipeline = sum(
            v['capacity_mw'] for v in by_viability.values()
        )

        return {
            'by_viability': by_viability,
            'by_stage': by_stage,
            'totals': {
                'pipeline_mw': round(total_pipeline, 1),
                'high_viability_mw': round(by_viability['high']['capacity_mw'], 1),
                'cel_total_capacity_mw': round(total_cel_capacity, 1),
                'cel_available_capacity_mw': round(total_available, 1),
                'active_stage_count': active_stages.count(),
            },
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @classmethod
    def _get_facility_queryset(cls, scenario=None):
        """Return the facility queryset to score, optionally filtered by scenario."""
        qs = FacilitiesModel.objects.filter(
            active=True,
            status__in=SCOREABLE_STATUSES,
            latitude__isnull=False,
            longitude__isnull=False,
        )
        if scenario is not None:
            qs = qs.filter(scenarios=scenario)
        return qs

    @classmethod
    def _score_stage(cls, stage, facility_qs, verbosity):
        """Score all facilities in facility_qs against stage. Returns count dict."""
        route_coords = stage.get_route_coordinates()
        if not route_coords:
            logger.warning(
                "CEL stage '%s' has no route coordinates — skipping.", stage.name
            )
            return {'facilities_scored': 0, 'created': 0, 'updated': 0}

        created = updated = 0

        for facility in facility_qs.iterator():
            result = cls._compute_alignment(facility, stage, route_coords)
            was_created = cls._persist_alignment(
                facility, stage, result, preserve_exceptions=True
            )
            if was_created:
                created += 1
            else:
                updated += 1

            if verbosity >= 2:
                logger.debug(
                    "  %s → %s: dist=%.1f km, aligned=%s, score=%.3f (%s)",
                    facility.facility_name, stage.name,
                    result['distance_km'] or 0,
                    result['is_aligned'],
                    result['viability_score'] or 0,
                    result['viability_label'],
                )

        return {
            'facilities_scored': facility_qs.count(),
            'created': created,
            'updated': updated,
        }

    @classmethod
    def _compute_alignment(cls, facility, stage, route_coords=None):
        """
        Compute all alignment fields for one (facility, stage) pair.

        Returns a dict ready to be unpacked into a FacilityCELAlignment.
        Does NOT touch the database.
        """
        if route_coords is None:
            route_coords = stage.get_route_coordinates()

        dist_km = distance_to_route_km(
            facility.latitude, facility.longitude, route_coords
        )

        is_aligned = (
            dist_km is not None and dist_km <= stage.alignment_radius_km
        )

        if not is_aligned:
            return {
                'distance_km': dist_km,
                'is_aligned': False,
                'viability_score': None,
                'cel_funding_weight': None,
                'facility_status_weight': None,
                'capacity_feasibility_score': None,
                'viability_label': 'unscored',
            }

        cel_w = stage.funding_status_weight
        fac_w = FACILITY_STATUS_WEIGHTS.get(facility.status, 0.30)
        cap_score = cls._capacity_feasibility_score(
            facility.capacity or 0.0,
            stage.available_capacity_mw,
            stage.total_capacity_mw,
        )
        score = round(cel_w * fac_w * cap_score, 4)

        # Determine label without constructing a model instance
        if score >= 0.70:
            label = 'high'
        elif score >= 0.40:
            label = 'medium'
        else:
            label = 'low'

        return {
            'distance_km': dist_km,
            'is_aligned': True,
            'viability_score': score,
            'cel_funding_weight': cel_w,
            'facility_status_weight': fac_w,
            'capacity_feasibility_score': cap_score,
            'viability_label': label,
        }

    @classmethod
    @transaction.atomic
    def _persist_alignment(cls, facility, stage, result, preserve_exceptions=True):
        """
        Create or update the FacilityCELAlignment record.

        When preserve_exceptions=True, any record already marked is_exception
        will not have its exception flags overwritten.

        Returns True if the record was newly created, False if updated.
        """
        existing = FacilityCELAlignment.objects.filter(
            facility=facility, cel_stage=stage
        ).first()

        # Preserve manually-set exception flags
        is_exception = False
        exception_reason = ''
        notes = ''
        if existing and preserve_exceptions and existing.is_exception:
            is_exception = existing.is_exception
            exception_reason = existing.exception_reason
            notes = existing.notes

        defaults = {
            'distance_to_route_km': result['distance_km'],
            'is_aligned': result['is_aligned'],
            'viability_score': result['viability_score'],
            'cel_funding_weight': result['cel_funding_weight'],
            'facility_status_weight': result['facility_status_weight'],
            'capacity_feasibility_score': result['capacity_feasibility_score'],
            'is_exception': is_exception,
            'exception_reason': exception_reason,
            'notes': notes,
        }

        _, created = FacilityCELAlignment.objects.update_or_create(
            facility=facility,
            cel_stage=stage,
            defaults=defaults,
        )
        return created

    @classmethod
    def _capacity_feasibility_score(cls, facility_mw, available_mw, total_mw):
        """
        Score (0.0–1.0) reflecting whether the CEL stage can accommodate
        this facility's capacity requirement.

          1.0  — facility fits within available (uncommitted) headroom
          0.1–1.0 — partial fit: facility is larger than available but
                    smaller than total stage capacity (scaled linearly)
          0.1  — facility exceeds total stage capacity (would require
                 program expansion beyond current scope)

        A facility with zero capacity returns 0.5 (neutral — insufficient
        data to assess capacity feasibility).
        """
        if not facility_mw or facility_mw <= 0:
            return 0.5

        if available_mw >= facility_mw:
            return 1.0

        if total_mw > 0 and facility_mw <= total_mw:
            # Partial fit: scale between 0.1 and 1.0
            return max(0.1, available_mw / facility_mw)

        # Oversized — needs program expansion
        return 0.1
