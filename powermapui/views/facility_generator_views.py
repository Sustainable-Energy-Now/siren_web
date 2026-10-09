from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from siren_web.models import Technologies, FacilityGenerators, facilities


def facility_generator_detail(request, pk):
    """Detail view for a specific facility generator installation"""

    installation = get_object_or_404(
        FacilityGenerators.objects.select_related('idfacilities', 'idtechnologies'),
        pk=pk
    )

    context = {
        'installation': installation,
        'generator_attrs': installation.generator_attrs,
    }

    return render(request, 'facility_generator/detail.html', context)


def facility_generator_create(request, facility_id):
    """Create a new generator installation (override) for a specific facility"""
    facility = get_object_or_404(facilities, pk=facility_id)

    if request.method == 'POST':
        try:
            technology_id = request.POST.get('technology')
            capacity_min = request.POST.get('capacity_min')
            capacity_max = request.POST.get('capacity_max')
            rampup_max = request.POST.get('rampup_max')
            rampdown_max = request.POST.get('rampdown_max')

            if not technology_id:
                messages.error(request, 'Generator technology is required.')
                return render(request, 'facility_generator/create.html', {
                    'facility': facility,
                    'technologies': Technologies.objects.filter(category='Generator').order_by('technology_name'),
                    'form_data': request.POST
                })

            technology = get_object_or_404(Technologies, pk=technology_id, category='Generator')

            if FacilityGenerators.objects.filter(idfacilities=facility, idtechnologies=technology).exists():
                messages.error(request, 'This facility already has a generator override for this technology.')
                return render(request, 'facility_generator/create.html', {
                    'facility': facility,
                    'technologies': Technologies.objects.filter(category='Generator').order_by('technology_name'),
                    'form_data': request.POST
                })

            installation = FacilityGenerators.objects.create(
                idfacilities=facility,
                idtechnologies=technology,
                capacity_min=float(capacity_min) if capacity_min else None,
                capacity_max=float(capacity_max) if capacity_max else None,
                rampup_max=int(rampup_max) if rampup_max else None,
                rampdown_max=int(rampdown_max) if rampdown_max else None,
                is_active=True
            )

            messages.success(request, f'Generator override created successfully for {facility.facility_name}.')
            return redirect('powermapui:facility_generator_detail', pk=installation.pk)

        except ValueError as e:
            messages.error(request, f'Invalid numeric value provided: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error creating generator override: {str(e)}')

    context = {
        'facility': facility,
        'technologies': Technologies.objects.filter(category='Generator').order_by('technology_name')
    }

    if request.method == 'POST':
        context['form_data'] = request.POST

    return render(request, 'facility_generator/create.html', context)


def facility_generator_edit(request, pk):
    """Edit an existing facility generator installation (override)"""
    installation = get_object_or_404(FacilityGenerators, pk=pk)

    if request.method == 'POST':
        try:
            capacity_min = request.POST.get('capacity_min')
            capacity_max = request.POST.get('capacity_max')
            rampup_max = request.POST.get('rampup_max')
            rampdown_max = request.POST.get('rampdown_max')
            is_active = request.POST.get('is_active') == 'on'

            installation.capacity_min = float(capacity_min) if capacity_min else None
            installation.capacity_max = float(capacity_max) if capacity_max else None
            installation.rampup_max = int(rampup_max) if rampup_max else None
            installation.rampdown_max = int(rampdown_max) if rampdown_max else None
            installation.is_active = is_active
            installation.save()

            messages.success(request, 'Generator override updated successfully.')
            return redirect('powermapui:facility_detail', pk=installation.facility.idfacilities)

        except ValueError as e:
            messages.error(request, f'Invalid numeric value provided: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error updating installation: {str(e)}')

    context = {
        'installation': installation,
        'generator_attrs': installation.generator_attrs,
    }
    return render(request, 'facility_generator/edit.html', context)


@require_POST
def facility_generator_delete(request, pk):
    """Delete a facility generator installation (override)"""
    installation = get_object_or_404(FacilityGenerators, pk=pk)

    facility_id = installation.facility.idfacilities
    facility_name = installation.facility.facility_name
    technology_name = installation.technology.technology_name

    installation.delete()
    messages.success(request, f'Removed {technology_name} override from {facility_name}.')
    return redirect('powermapui:facility_detail', pk=facility_id)


def get_facility_generator_json(request):
    """Return facility generator installations (overrides) as JSON"""
    installations = FacilityGenerators.objects.select_related(
        'idfacilities',
        'idtechnologies'
    ).filter(is_active=True)

    data = []
    for install in installations:
        data.append({
            'id': install.idfacilitygenerators,
            'facility_id': install.idfacilities.idfacilities,
            'facility_name': install.idfacilities.facility_name,
            'technology_id': install.idtechnologies.idtechnologies,
            'technology_name': install.idtechnologies.technology_name,
            'capacity_min': install.effective_capacity_min,
            'capacity_max': install.effective_capacity_max,
            'rampup_max': install.rampup_max,
            'rampdown_max': install.rampdown_max,
            'is_active': install.is_active,
        })

    return JsonResponse({
        'installations': data,
        'count': len(data),
    })
