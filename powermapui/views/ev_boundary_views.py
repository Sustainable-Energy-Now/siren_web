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

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from siren_web.models import EV_BOUNDARY_STATUS_CHOICES, SwisBoundaryMembership


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
