"""
Zones CRUD views — edit zone boundaries stored as GeoJSON in kml_data
"""
import json
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from siren_web.models import Zones


def zones_list(request):
    """List all zones"""
    search_query = request.GET.get('search', '')
    zones = Zones.objects.all().order_by('name')

    if search_query:
        zones = zones.filter(name__icontains=search_query)

    paginator = Paginator(zones, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # annotate with waypoint count
    zones_with_count = []
    for zone in page_obj.object_list:
        waypoint_count = 0
        if zone.kml_data:
            try:
                geom = json.loads(zone.kml_data)
                waypoint_count = len(geom.get('coordinates', []))
            except (json.JSONDecodeError, AttributeError):
                pass
        zones_with_count.append((zone, waypoint_count))

    context = {
        'page_obj': page_obj,
        'zones_with_count': zones_with_count,
        'search_query': search_query,
        'total_count': zones.count(),
    }
    return render(request, 'zones/list.html', context)


def zone_detail(request, pk):
    """Detail view for a zone"""
    zone = get_object_or_404(Zones, pk=pk)

    waypoint_count = 0
    geom_json = ''
    if zone.kml_data:
        try:
            geom = json.loads(zone.kml_data)
            waypoint_count = len(geom.get('coordinates', []))
            geom_json = zone.kml_data
        except (json.JSONDecodeError, AttributeError):
            pass

    context = {
        'zone': zone,
        'waypoint_count': waypoint_count,
        'geom_json': geom_json,
    }
    return render(request, 'zones/detail.html', context)


def zone_create(request):
    """Create a new zone"""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        kml_geometry_raw = request.POST.get('kml_geometry', '').strip()

        if not name:
            messages.error(request, 'Zone name is required.')
            return render(request, 'zones/create.html', _create_context(request.POST))

        if Zones.objects.filter(name=name).exists():
            messages.error(request, 'A zone with this name already exists.')
            return render(request, 'zones/create.html', _create_context(request.POST))

        kml_data = None
        if kml_geometry_raw:
            try:
                json.loads(kml_geometry_raw)
                kml_data = kml_geometry_raw
            except (json.JSONDecodeError, ValueError):
                messages.warning(request, 'Boundary geometry JSON was invalid and has not been saved.')

        # Compute next available ID (not an AutoField)
        max_id = Zones.objects.order_by('-idzones').values_list('idzones', flat=True).first()
        next_id = (max_id or 0) + 1

        zone = Zones.objects.create(
            idzones=next_id,
            name=name,
            description=description or None,
            kml_data=kml_data,
        )
        messages.success(request, f'Zone "{name}" created successfully.')
        return redirect('powermapui:zone_detail', pk=zone.pk)

    return render(request, 'zones/create.html', _create_context())


def zone_edit(request, pk):
    """Edit an existing zone"""
    zone = get_object_or_404(Zones, pk=pk)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        kml_geometry_raw = request.POST.get('kml_geometry', '').strip()

        if not name:
            messages.error(request, 'Zone name is required.')
            return render(request, 'zones/edit.html', _edit_context(zone))

        if Zones.objects.filter(name=name).exclude(pk=pk).exists():
            messages.error(request, 'A zone with this name already exists.')
            return render(request, 'zones/edit.html', _edit_context(zone))

        zone.name = name
        zone.description = description or None

        if kml_geometry_raw:
            try:
                json.loads(kml_geometry_raw)
                zone.kml_data = kml_geometry_raw
            except (json.JSONDecodeError, ValueError):
                messages.warning(request, 'Boundary geometry JSON was invalid and has not been changed.')
        else:
            zone.kml_data = None

        zone.save()
        messages.success(request, f'Zone "{name}" updated successfully.')
        return redirect('powermapui:zone_detail', pk=zone.pk)

    return render(request, 'zones/edit.html', _edit_context(zone))


@require_POST
def zone_delete(request, pk):
    """Delete a zone"""
    zone = get_object_or_404(Zones, pk=pk)
    name = zone.name
    zone.delete()
    messages.success(request, f'Zone "{name}" deleted successfully.')
    return redirect('powermapui:zones_list')


# ── helpers ──────────────────────────────────────────────────────────────────

def _create_context(form_data=None):
    ctx = {}
    if form_data:
        ctx['form_data'] = form_data
    return ctx


def _edit_context(zone):
    return {'zone': zone}
