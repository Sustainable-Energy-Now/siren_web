# powermapui/views/ev_boundary_views.py
"""
FR-04/05 — build/inspect the postcode -> zone -> SWIS aggregate
membership hierarchy (D9: centroid-in-SWIS flag, apportionment_fraction
reserved but unused this Sprint). A new module rather than extending
zone_views.py, since Zones there models grid-line geometry (kml_data
boundaries for the powermap), a different concept from this postcode-
level administrative hierarchy.

No real ABS postcode-boundary / SWIS-polygon GIS data has been wired up
yet, so the centroid-in-polygon computation FR-04's acceptance criterion
ultimately wants is not automated here -- this gives the reproducible
membership *table* (manual entry + CSV bulk import) that a future
geospatial command can populate programmatically once boundary files are
available, without changing the schema or this view's contract.
"""
import csv
import io
import json

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from siren_web.models import (
    EV_BOUNDARY_STATUS_CHOICES, SwisBoundaryMembership, PostcodeBoundary,
)
from powermapui.utils.swis_boundary import swis_boundary_geojson_str, load_swis_polygon


def swis_boundary_list(request):
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')

    memberships = SwisBoundaryMembership.objects.all().order_by('postcode')
    if search_query:
        memberships = memberships.filter(postcode__icontains=search_query)
    if status_filter:
        memberships = memberships.filter(membership_status=status_filter)

    paginator = Paginator(memberships, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'ev_boundary/list.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'status_choices': EV_BOUNDARY_STATUS_CHOICES,
        'total_count': memberships.count(),
    })


def swis_boundary_edit(request, pk):
    membership = get_object_or_404(SwisBoundaryMembership, pk=pk)

    if request.method == 'POST':
        membership.zone_name = request.POST.get('zone_name', '').strip()
        membership.membership_status = request.POST.get('membership_status', membership.membership_status)
        try:
            membership.apportionment_fraction = float(request.POST.get('apportionment_fraction', 1.0))
        except ValueError:
            messages.error(request, 'apportionment_fraction must be a number.')
            return render(request, 'ev_boundary/form.html', {'membership': membership, 'status_choices': EV_BOUNDARY_STATUS_CHOICES})
        membership.notes = request.POST.get('notes', '').strip()
        membership.save()
        messages.success(request, f'{membership.postcode} updated.')
        return redirect('powermapui:swis_boundary_list')

    return render(request, 'ev_boundary/form.html', {'membership': membership, 'status_choices': EV_BOUNDARY_STATUS_CHOICES})


def swis_boundary_create(request):
    if request.method == 'POST':
        postcode = request.POST.get('postcode', '').strip()
        if not postcode:
            messages.error(request, 'Postcode is required.')
            return render(request, 'ev_boundary/form.html', {'status_choices': EV_BOUNDARY_STATUS_CHOICES})
        if SwisBoundaryMembership.objects.filter(postcode=postcode).exists():
            messages.error(request, f'{postcode} already has a membership row — edit it instead.')
            return render(request, 'ev_boundary/form.html', {'status_choices': EV_BOUNDARY_STATUS_CHOICES})

        membership = SwisBoundaryMembership.objects.create(
            postcode=postcode,
            zone_name=request.POST.get('zone_name', '').strip(),
            membership_status=request.POST.get('membership_status', 'in'),
            apportionment_fraction=float(request.POST.get('apportionment_fraction', 1.0) or 1.0),
            notes=request.POST.get('notes', '').strip(),
        )
        messages.success(request, f'{membership.postcode} created.')
        return redirect('powermapui:swis_boundary_list')

    return render(request, 'ev_boundary/form.html', {'status_choices': EV_BOUNDARY_STATUS_CHOICES})


def swis_boundary_delete(request, pk):
    membership = get_object_or_404(SwisBoundaryMembership, pk=pk)
    if request.method == 'POST':
        postcode = membership.postcode
        membership.delete()
        messages.success(request, f'{postcode} deleted.')
        return redirect('powermapui:swis_boundary_list')
    return render(request, 'ev_boundary/confirm_delete.html', {'membership': membership})


_STATUS_VALUES = {c[0] for c in EV_BOUNDARY_STATUS_CHOICES}


def swis_boundary_map(request):
    """Map of the SWIS boundary + WA postcode polygons, shaded by membership
    status, with click-to-edit apportionment."""
    memberships = {m.postcode: m for m in SwisBoundaryMembership.objects.all()}

    features = []
    counts = {'in': 0, 'out': 0, 'partial': 0, 'unscored': 0}
    for pb in PostcodeBoundary.objects.all():
        try:
            geometry = json.loads(pb.geojson)
        except (ValueError, TypeError):
            continue
        m = memberships.get(pb.postcode)
        status = m.membership_status if m else 'unscored'
        counts[status] = counts.get(status, 0) + 1
        features.append({
            'type': 'Feature',
            'geometry': geometry,
            'properties': {
                'postcode': pb.postcode,
                'status': status,
                'apportionment_fraction': (m.apportionment_fraction if m else None),
                'zone_name': (m.zone_name if m else ''),
                'note': (m.notes if m else ''),
                'area_sqkm': pb.area_sqkm,
            },
        })

    context = {
        'swis_boundary_json': swis_boundary_geojson_str(),
        'postcodes_json': json.dumps({'type': 'FeatureCollection', 'features': features}),
        'has_shapefile': settings.POA_SHAPEFILE_PATH.exists(),
        'poa_shapefile_path': str(settings.POA_SHAPEFILE_PATH),
        'status_choices': EV_BOUNDARY_STATUS_CHOICES,
        'counts': counts,
        'postcode_count': len(features),
    }
    return render(request, 'ev_boundary/map.html', context)


def ajax_update_postcode_membership(request, postcode):
    """Save apportionment_fraction / membership_status for one postcode."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        data = json.loads(request.body)
    except (ValueError, TypeError) as e:
        return JsonResponse({'error': f'Invalid payload: {e}'}, status=400)

    status = (data.get('membership_status') or '').strip()
    if status not in _STATUS_VALUES:
        return JsonResponse({'error': f'membership_status must be one of {sorted(_STATUS_VALUES)}'}, status=400)
    try:
        fraction = float(data.get('apportionment_fraction'))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'apportionment_fraction must be a number'}, status=400)
    fraction = max(0.0, min(1.0, fraction))

    pb = PostcodeBoundary.objects.filter(postcode=postcode).first()
    defaults = {'membership_status': status, 'apportionment_fraction': fraction}
    if pb and pb.centroid_lat is not None:
        defaults.update(centroid_lat=pb.centroid_lat, centroid_lon=pb.centroid_lon)
    m, created = SwisBoundaryMembership.objects.get_or_create(postcode=postcode, defaults=defaults)
    if not created:
        m.membership_status = status
        m.apportionment_fraction = fraction
    m.notes = (m.notes + '\n' if m.notes else '') + 'Adjusted by hand on the SWIS boundary map.'
    m.save()

    return JsonResponse({
        'status': 'ok',
        'postcode': m.postcode,
        'membership_status': m.membership_status,
        'apportionment_fraction': m.apportionment_fraction,
        'created': created,
    })


def ajax_recompute_swis_membership(request):
    """Re-derive every WA postcode's membership from the current SWIS boundary."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    if not settings.POA_SHAPEFILE_PATH.exists():
        return JsonResponse({
            'error': f'ABS POA shapefile not found at {settings.POA_SHAPEFILE_PATH}. '
                     f'See {settings.GIS_DATA_DIR / "README.md"}.'
        }, status=400)
    try:
        from powermapui.utils.swis_membership_service import derive_membership
        result = derive_membership(load_swis_polygon(), settings.POA_SHAPEFILE_PATH)
        return JsonResponse({
            'status': 'ok',
            'in': result['in'], 'out': result['out'], 'partial': result['partial'],
            'created': result['created'], 'updated': result['updated'],
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def swis_boundary_bulk_import(request):
    """
    FR-04/05: CSV bulk import — columns postcode, zone_name,
    membership_status (in/out/partial), apportionment_fraction (optional,
    default 1.0). Upserts by postcode.
    """
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        try:
            decoded = csv_file.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            messages.error(request, 'Could not decode file as UTF-8.')
            return redirect('powermapui:swis_boundary_list')

        reader = csv.DictReader(io.StringIO(decoded))
        required = {'postcode', 'membership_status'}
        if not required.issubset(set(reader.fieldnames or [])):
            messages.error(request, f'CSV must contain columns: {sorted(required)}')
            return redirect('powermapui:swis_boundary_list')

        created, updated, errors = 0, 0, 0
        valid_statuses = {c[0] for c in EV_BOUNDARY_STATUS_CHOICES}
        for row in reader:
            postcode = (row.get('postcode') or '').strip()
            status = (row.get('membership_status') or '').strip()
            if not postcode or status not in valid_statuses:
                errors += 1
                continue
            _, was_created = SwisBoundaryMembership.objects.update_or_create(
                postcode=postcode,
                defaults={
                    'zone_name': (row.get('zone_name') or '').strip(),
                    'membership_status': status,
                    'apportionment_fraction': float(row.get('apportionment_fraction') or 1.0),
                },
            )
            created += 1 if was_created else 0
            updated += 0 if was_created else 1

        messages.success(request, f'Bulk import: {created} created, {updated} updated, {errors} skipped (invalid row).')

    return redirect('powermapui:swis_boundary_list')
