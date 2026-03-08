"""
CEL (Clean Energy Link) CRUD views
Provides list/detail/create/edit/delete for CELProgram and CELStage,
plus exception management for FacilityCELAlignment.
"""
import json

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST

from siren_web.models import (
    CELProgram,
    CELStage,
    CELStageGridLine,
    CELStageTerminal,
    FacilityCELAlignment,
    CEL_FUNDING_STATUS_CHOICES,
    GridLines,
    Terminals,
)


# ---------------------------------------------------------------------------
# CEL Program views
# ---------------------------------------------------------------------------

def cel_program_list(request):
    """List all CEL programs with their stages."""
    programs = (
        CELProgram.objects
        .prefetch_related('stages')
        .order_by('name')
    )
    context = {
        'programs': programs,
        'total_programs': programs.count(),
        'active_programs': programs.filter(is_active=True).count(),
    }
    return render(request, 'cel/program_list.html', context)


def cel_program_detail(request, pk):
    """Detail view for a CEL program showing all its stages."""
    program = get_object_or_404(CELProgram, pk=pk)
    stages = (
        program.stages
        .prefetch_related('facility_alignments__facility')
        .order_by('stage_number')
    )
    context = {
        'program': program,
        'stages': stages,
        'total_capacity_new': sum(s.capacity_new_mw or 0 for s in stages),
        'total_capacity_unlocked': sum(s.capacity_unlocked_existing_mw or 0 for s in stages),
    }
    return render(request, 'cel/program_detail.html', context)


def cel_program_create(request):
    """Create a new CEL program."""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip().upper()
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        notes = request.POST.get('notes', '').strip()

        errors = []
        if not name:
            errors.append('Program name is required.')
        if not code:
            errors.append('Program code is required.')
        if CELProgram.objects.filter(name=name).exists():
            errors.append('A CEL program with this name already exists.')
        if CELProgram.objects.filter(code=code).exists():
            errors.append('A CEL program with this code already exists.')

        if errors:
            for msg in errors:
                messages.error(request, msg)
            return render(request, 'cel/program_form.html', {
                'action': 'create', 'program': None,
                'initial': request.POST,
            })

        program = CELProgram.objects.create(
            name=name,
            code=code,
            description=description,
            is_active=is_active,
            notes=notes,
        )
        messages.success(request, f'CEL program "{name}" created successfully.')
        return redirect('powermapui:cel_program_detail', pk=program.pk)

    return render(request, 'cel/program_form.html', {
        'action': 'create', 'program': None, 'initial': {},
    })


def cel_program_edit(request, pk):
    """Edit an existing CEL program."""
    program = get_object_or_404(CELProgram, pk=pk)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip().upper()
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        notes = request.POST.get('notes', '').strip()

        errors = []
        if not name:
            errors.append('Program name is required.')
        if not code:
            errors.append('Program code is required.')
        if CELProgram.objects.filter(name=name).exclude(pk=pk).exists():
            errors.append('A CEL program with this name already exists.')
        if CELProgram.objects.filter(code=code).exclude(pk=pk).exists():
            errors.append('A CEL program with this code already exists.')

        if errors:
            for msg in errors:
                messages.error(request, msg)
            return render(request, 'cel/program_form.html', {
                'program': program, 'action': 'edit',
                'initial': request.POST,
            })

        program.name = name
        program.code = code
        program.description = description
        program.is_active = is_active
        program.notes = notes
        program.save()

        messages.success(request, f'CEL program "{name}" updated successfully.')
        return redirect('powermapui:cel_program_detail', pk=program.pk)

    initial = {
        'name': program.name,
        'code': program.code,
        'description': program.description or '',
        'is_active': program.is_active,
        'notes': program.notes or '',
    }
    return render(request, 'cel/program_form.html', {
        'program': program, 'action': 'edit', 'initial': initial,
    })


@require_POST
def cel_program_delete(request, pk):
    """Delete a CEL program (only if it has no stages)."""
    program = get_object_or_404(CELProgram, pk=pk)
    stage_count = program.stages.count()
    if stage_count:
        messages.error(
            request,
            f'Cannot delete "{program.name}" — it has {stage_count} stage(s). Delete stages first.'
        )
        return redirect('powermapui:cel_program_detail', pk=pk)

    name = program.name
    program.delete()
    messages.success(request, f'CEL program "{name}" deleted.')
    return redirect('powermapui:cel_program_list')


# ---------------------------------------------------------------------------
# CEL Stage views
# ---------------------------------------------------------------------------

def cel_stage_detail(request, pk):
    """Detail view for a CEL stage, including aligned facilities."""
    stage = get_object_or_404(
        CELStage.objects.select_related('cel_program', 'from_terminal', 'to_terminal'), pk=pk
    )
    alignments = (
        FacilityCELAlignment.objects
        .filter(cel_stage=stage)
        .select_related('facility', 'facility__idtechnologies')
        .order_by('-is_aligned', '-viability_score')
    )
    aligned_count = alignments.filter(is_aligned=True).count()
    pipeline_mw = sum(
        a.facility.capacity or 0 for a in alignments if a.is_aligned
    )
    gridline_assocs = (
        stage.stage_gridlines
        .select_related('grid_line')
        .order_by('line_role', 'grid_line__line_name')
    )
    gridline_capacity_total = sum(a.capacity_mw for a in gridline_assocs)
    terminal_assocs = (
        stage.stage_terminals
        .select_related('terminal')
        .order_by('terminal_role', 'terminal__terminal_name')
    )
    terminal_capacity_total = sum(a.capacity_mw for a in terminal_assocs)
    context = {
        'stage': stage,
        'alignments': alignments,
        'aligned_count': aligned_count,
        'pipeline_mw': pipeline_mw,
        'gridline_assocs': gridline_assocs,
        'gridline_capacity_total': gridline_capacity_total,
        'terminal_assocs': terminal_assocs,
        'terminal_capacity_total': terminal_capacity_total,
    }
    return render(request, 'cel/stage_detail.html', context)


def cel_stage_create(request, program_pk):
    """Create a new stage under a CEL program."""
    program = get_object_or_404(CELProgram, pk=program_pk)

    if request.method == 'POST':
        stage, errors = _stage_from_post(request.POST, program=program)
        if errors:
            for msg in errors:
                messages.error(request, msg)
            return render(request, 'cel/stage_form.html', _stage_form_context(
                request.POST, program=program, action='create'
            ))
        messages.success(request, f'Stage "{stage.name}" created successfully.')
        return redirect('powermapui:cel_stage_detail', pk=stage.pk)

    return render(request, 'cel/stage_form.html', _stage_form_context(
        None, program=program, action='create'
    ))


def cel_stage_edit(request, pk):
    """Edit an existing CEL stage."""
    stage = get_object_or_404(CELStage.objects.select_related('cel_program'), pk=pk)

    if request.method == 'POST':
        updated_stage, errors = _stage_from_post(request.POST, stage=stage)
        if errors:
            for msg in errors:
                messages.error(request, msg)
            return render(request, 'cel/stage_form.html', _stage_form_context(
                request.POST, stage=stage, program=stage.cel_program, action='edit'
            ))
        messages.success(request, f'Stage "{updated_stage.name}" updated successfully.')
        return redirect('powermapui:cel_stage_detail', pk=updated_stage.pk)

    return render(request, 'cel/stage_form.html', _stage_form_context(
        None, stage=stage, program=stage.cel_program, action='edit'
    ))


@require_POST
def cel_stage_delete(request, pk):
    """Delete a CEL stage."""
    stage = get_object_or_404(CELStage, pk=pk)
    program_pk = stage.cel_program_id
    name = stage.name
    stage.delete()
    messages.success(request, f'Stage "{name}" deleted.')
    return redirect('powermapui:cel_program_detail', pk=program_pk)


@require_POST
def cel_stage_recompute(request, pk):
    """Trigger viability recompute for a single CEL stage."""
    from powermapui.utils.cel_viability_service import CELViabilityService
    stage = get_object_or_404(CELStage, pk=pk)
    count = CELViabilityService.score_facilities_for_stage(stage)
    messages.success(request, f'Recomputed viability for {count} facility alignment(s).')
    return redirect('powermapui:cel_stage_detail', pk=pk)


# ---------------------------------------------------------------------------
# CELStageGridLine — grid line associations
# ---------------------------------------------------------------------------

def cel_stage_gridline_add(request, stage_pk):
    """Associate a GridLine with a CEL stage, recording the capacity it will carry."""
    stage = get_object_or_404(CELStage, pk=stage_pk)
    already_linked = stage.stage_gridlines.values_list('grid_line_id', flat=True)
    available_gridlines = (
        GridLines.objects.filter(active=True)
        .exclude(idgridlines__in=already_linked)
        .order_by('line_name')
    )

    if request.method == 'POST':
        grid_line_id = request.POST.get('grid_line')
        capacity_mw = _float_or_none(request.POST.get('capacity_mw'))
        line_role = request.POST.get('line_role', 'new')
        notes = request.POST.get('notes', '').strip()

        errors = []
        if not grid_line_id:
            errors.append('Please select a grid line.')
        if capacity_mw is None or capacity_mw <= 0:
            errors.append('Capacity (MW) must be a positive number.')

        if not errors:
            try:
                grid_line = GridLines.objects.get(pk=grid_line_id)
                CELStageGridLine.objects.create(
                    cel_stage=stage,
                    grid_line=grid_line,
                    capacity_mw=capacity_mw,
                    line_role=line_role,
                    notes=notes,
                )
                messages.success(
                    request,
                    f'Grid line "{grid_line.line_name}" linked to stage "{stage.name}" '
                    f'({capacity_mw:,.0f} MW).'
                )
                return redirect('powermapui:cel_stage_detail', pk=stage_pk)
            except GridLines.DoesNotExist:
                errors.append('Selected grid line not found.')

        for msg in errors:
            messages.error(request, msg)

    return render(request, 'cel/stage_gridline_form.html', {
        'stage': stage,
        'available_gridlines': available_gridlines,
        'line_role_choices': CELStageGridLine.LINE_ROLE_CHOICES,
        'initial': request.POST if request.method == 'POST' else {},
        'action': 'add',
    })


def cel_stage_gridline_edit(request, pk):
    """Edit the capacity and role of an existing CELStageGridLine association."""
    association = get_object_or_404(
        CELStageGridLine.objects.select_related('cel_stage', 'grid_line'), pk=pk
    )
    stage = association.cel_stage

    if request.method == 'POST':
        capacity_mw = _float_or_none(request.POST.get('capacity_mw'))
        line_role = request.POST.get('line_role', 'new')
        notes = request.POST.get('notes', '').strip()

        errors = []
        if capacity_mw is None or capacity_mw <= 0:
            errors.append('Capacity (MW) must be a positive number.')

        if not errors:
            association.capacity_mw = capacity_mw
            association.line_role = line_role
            association.notes = notes
            association.save()
            messages.success(
                request,
                f'Updated "{association.grid_line.line_name}" — {capacity_mw:,.0f} MW.'
            )
            return redirect('powermapui:cel_stage_detail', pk=stage.pk)

        for msg in errors:
            messages.error(request, msg)

    initial = request.POST if request.method == 'POST' else {
        'capacity_mw': association.capacity_mw,
        'line_role': association.line_role,
        'notes': association.notes,
    }
    return render(request, 'cel/stage_gridline_form.html', {
        'stage': stage,
        'association': association,
        'line_role_choices': CELStageGridLine.LINE_ROLE_CHOICES,
        'initial': initial,
        'action': 'edit',
    })


@require_POST
def cel_stage_gridline_remove(request, pk):
    """Remove a CELStageGridLine association."""
    association = get_object_or_404(
        CELStageGridLine.objects.select_related('cel_stage', 'grid_line'), pk=pk
    )
    stage_pk = association.cel_stage_id
    line_name = association.grid_line.line_name
    association.delete()
    messages.success(request, f'Grid line "{line_name}" removed from stage.')
    return redirect('powermapui:cel_stage_detail', pk=stage_pk)


# ---------------------------------------------------------------------------
# CELStageTerminal — terminal associations
# ---------------------------------------------------------------------------

def cel_stage_terminal_add(request, stage_pk):
    """Associate a Terminal with a CEL stage, recording the capacity it will handle."""
    stage = get_object_or_404(CELStage, pk=stage_pk)
    already_linked = stage.stage_terminals.values_list('terminal_id', flat=True)
    available_terminals = (
        Terminals.objects.filter(active=True)
        .exclude(idterminals__in=already_linked)
        .order_by('terminal_name')
    )

    if request.method == 'POST':
        terminal_id = request.POST.get('terminal')
        capacity_mw = _float_or_none(request.POST.get('capacity_mw'))
        terminal_role = request.POST.get('terminal_role', 'new')
        notes = request.POST.get('notes', '').strip()

        errors = []
        if not terminal_id:
            errors.append('Please select a terminal.')
        if capacity_mw is None or capacity_mw <= 0:
            errors.append('Capacity (MW) must be a positive number.')

        if not errors:
            try:
                terminal = Terminals.objects.get(pk=terminal_id)
                CELStageTerminal.objects.create(
                    cel_stage=stage,
                    terminal=terminal,
                    capacity_mw=capacity_mw,
                    terminal_role=terminal_role,
                    notes=notes,
                )
                messages.success(
                    request,
                    f'Terminal "{terminal.terminal_name}" linked to stage "{stage.name}" '
                    f'({capacity_mw:,.0f} MW).'
                )
                return redirect('powermapui:cel_stage_detail', pk=stage_pk)
            except Terminals.DoesNotExist:
                errors.append('Selected terminal not found.')

        for msg in errors:
            messages.error(request, msg)

    return render(request, 'cel/stage_terminal_form.html', {
        'stage': stage,
        'available_terminals': available_terminals,
        'terminal_role_choices': CELStageTerminal.TERMINAL_ROLE_CHOICES,
        'initial': request.POST if request.method == 'POST' else {},
        'action': 'add',
    })


def cel_stage_terminal_edit(request, pk):
    """Edit the capacity and role of an existing CELStageTerminal association."""
    association = get_object_or_404(
        CELStageTerminal.objects.select_related('cel_stage', 'terminal'), pk=pk
    )
    stage = association.cel_stage

    if request.method == 'POST':
        capacity_mw = _float_or_none(request.POST.get('capacity_mw'))
        terminal_role = request.POST.get('terminal_role', 'new')
        notes = request.POST.get('notes', '').strip()

        errors = []
        if capacity_mw is None or capacity_mw <= 0:
            errors.append('Capacity (MW) must be a positive number.')

        if not errors:
            association.capacity_mw = capacity_mw
            association.terminal_role = terminal_role
            association.notes = notes
            association.save()
            messages.success(
                request,
                f'Updated "{association.terminal.terminal_name}" — {capacity_mw:,.0f} MW.'
            )
            return redirect('powermapui:cel_stage_detail', pk=stage.pk)

        for msg in errors:
            messages.error(request, msg)

    initial = request.POST if request.method == 'POST' else {
        'capacity_mw': association.capacity_mw,
        'terminal_role': association.terminal_role,
        'notes': association.notes,
    }
    return render(request, 'cel/stage_terminal_form.html', {
        'stage': stage,
        'association': association,
        'terminal_role_choices': CELStageTerminal.TERMINAL_ROLE_CHOICES,
        'initial': initial,
        'action': 'edit',
    })


@require_POST
def cel_stage_terminal_remove(request, pk):
    """Remove a CELStageTerminal association."""
    association = get_object_or_404(
        CELStageTerminal.objects.select_related('cel_stage', 'terminal'), pk=pk
    )
    stage_pk = association.cel_stage_id
    terminal_name = association.terminal.terminal_name
    association.delete()
    messages.success(request, f'Terminal "{terminal_name}" removed from stage.')
    return redirect('powermapui:cel_stage_detail', pk=stage_pk)


# ---------------------------------------------------------------------------
# FacilityCELAlignment — exception management
# ---------------------------------------------------------------------------

def cel_alignment_set_exception(request, pk):
    """Set or clear the exception flag on an alignment record."""
    alignment = get_object_or_404(FacilityCELAlignment, pk=pk)

    if request.method == 'POST':
        is_exception = request.POST.get('is_exception') == 'on'
        exception_reason = request.POST.get('exception_reason', '')
        notes = request.POST.get('notes', '').strip()

        alignment.is_exception = is_exception
        alignment.exception_reason = exception_reason if is_exception else ''
        alignment.notes = notes
        alignment.save(update_fields=['is_exception', 'exception_reason', 'notes'])

        action = 'set' if is_exception else 'cleared'
        messages.success(
            request,
            f'Exception {action} for {alignment.facility.facility_name} / {alignment.cel_stage.name}.'
        )
        return redirect('powermapui:cel_stage_detail', pk=alignment.cel_stage_id)

    exception_reason_choices = FacilityCELAlignment._meta.get_field('exception_reason').choices
    return render(request, 'cel/alignment_exception_form.html', {
        'alignment': alignment,
        'exception_reason_choices': exception_reason_choices,
    })


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _float_or_none(value):
    """Parse a string to float, returning None if blank or invalid."""
    if not value or not str(value).strip():
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _stage_from_post(post_data, program=None, stage=None):
    """
    Validate POST data and create/update a CELStage.

    Returns (stage_instance, errors_list).
    If errors_list is non-empty, no DB write was performed.
    Either `program` (for create) or `stage` (for edit) must be supplied.
    """
    name = post_data.get('name', '').strip()
    stage_number_raw = post_data.get('stage_number', '').strip()
    stage_type = post_data.get('stage_type', 'corridor')
    funding_status = post_data.get('funding_status', 'planning')
    capacity_new_mw = _float_or_none(post_data.get('capacity_new_mw'))
    capacity_unlocked_existing_mw = _float_or_none(post_data.get('capacity_unlocked_existing_mw'))
    reserved_capacity_mw = _float_or_none(post_data.get('reserved_capacity_mw'))
    alignment_radius_km_raw = post_data.get('alignment_radius_km', '50')
    served_region = post_data.get('served_region', '').strip()
    display_color = post_data.get('display_color', '#FF6B35').strip()
    is_active = post_data.get('is_active') == 'on'
    notes = post_data.get('notes', '').strip()
    route_coordinates_raw = post_data.get('route_coordinates', '').strip()

    # Endpoint / terminal fields
    from_latitude = _float_or_none(post_data.get('from_latitude'))
    from_longitude = _float_or_none(post_data.get('from_longitude'))
    to_latitude = _float_or_none(post_data.get('to_latitude'))
    to_longitude = _float_or_none(post_data.get('to_longitude'))
    from_terminal_id = post_data.get('from_terminal') or None
    to_terminal_id = post_data.get('to_terminal') or None
    funding_status_weight_override = _float_or_none(post_data.get('funding_status_weight_override'))

    errors = []

    if not name:
        errors.append('Stage name is required.')

    try:
        stage_number = int(stage_number_raw) if stage_number_raw else None
    except ValueError:
        stage_number = None
        errors.append('Stage number must be a whole number.')

    try:
        alignment_radius_km = float(alignment_radius_km_raw) if alignment_radius_km_raw else 50.0
        if alignment_radius_km <= 0:
            errors.append('Alignment radius must be positive.')
    except ValueError:
        alignment_radius_km = 50.0
        errors.append('Alignment radius must be a number.')

    # Validate and parse route_coordinates JSON
    route_coordinates = None
    if route_coordinates_raw:
        try:
            parsed = json.loads(route_coordinates_raw)
            if not isinstance(parsed, list):
                errors.append('Route coordinates must be a JSON array, e.g. [[lat,lon],...]')
            else:
                route_coordinates = route_coordinates_raw  # store as-is (valid JSON string)
        except json.JSONDecodeError as exc:
            errors.append(f'Route coordinates: invalid JSON — {exc}')

    if errors:
        return None, errors

    # Resolve terminal FK
    from_terminal = None
    to_terminal = None
    if from_terminal_id:
        try:
            from_terminal = Terminals.objects.get(pk=from_terminal_id)
        except Terminals.DoesNotExist:
            errors.append(f'From-terminal ID {from_terminal_id} does not exist.')
    if to_terminal_id:
        try:
            to_terminal = Terminals.objects.get(pk=to_terminal_id)
        except Terminals.DoesNotExist:
            errors.append(f'To-terminal ID {to_terminal_id} does not exist.')

    if errors:
        return None, errors

    # Uniqueness check for stage_number within program
    target_program = program if stage is None else stage.cel_program
    if stage_number is not None:
        qs = CELStage.objects.filter(cel_program=target_program, stage_number=stage_number)
        if stage is not None:
            qs = qs.exclude(pk=stage.pk)
        if qs.exists():
            errors.append(f'Stage number {stage_number} already exists in this program.')

    if errors:
        return None, errors

    fields = dict(
        name=name,
        stage_number=stage_number,
        stage_type=stage_type,
        funding_status=funding_status,
        funding_status_weight_override=funding_status_weight_override,
        capacity_new_mw=capacity_new_mw,
        capacity_unlocked_existing_mw=capacity_unlocked_existing_mw,
        reserved_capacity_mw=reserved_capacity_mw,
        alignment_radius_km=alignment_radius_km,
        served_region=served_region,
        display_color=display_color,
        is_active=is_active,
        notes=notes,
        route_coordinates=route_coordinates,
        from_latitude=from_latitude,
        from_longitude=from_longitude,
        to_latitude=to_latitude,
        to_longitude=to_longitude,
        from_terminal=from_terminal,
        to_terminal=to_terminal,
    )

    if stage is None:
        # Create
        obj = CELStage.objects.create(cel_program=target_program, **fields)
    else:
        # Update
        for attr, val in fields.items():
            setattr(stage, attr, val)
        stage.save()
        obj = stage

    return obj, []


def _stage_form_context(post_data, program, action, stage=None):
    """Build context dict for the stage create/edit form."""
    terminals = Terminals.objects.filter(active=True).order_by('terminal_name')

    # Build initial values: POST data takes priority, then existing stage fields, then defaults
    if post_data:
        initial = post_data
    elif stage:
        initial = {
            'name': stage.name,
            'stage_number': stage.stage_number or '',
            'stage_type': stage.stage_type,
            'funding_status': stage.funding_status,
            'funding_status_weight_override': stage.funding_status_weight_override or '',
            'capacity_new_mw': stage.capacity_new_mw or '',
            'capacity_unlocked_existing_mw': stage.capacity_unlocked_existing_mw or '',
            'reserved_capacity_mw': stage.reserved_capacity_mw or '',
            'alignment_radius_km': stage.alignment_radius_km,
            'served_region': stage.served_region or '',
            'display_color': stage.display_color,
            'is_active': stage.is_active,
            'notes': stage.notes or '',
            'route_coordinates': stage.route_coordinates or '',
            'from_latitude': stage.from_latitude or '',
            'from_longitude': stage.from_longitude or '',
            'to_latitude': stage.to_latitude or '',
            'to_longitude': stage.to_longitude or '',
            'from_terminal': stage.from_terminal_id or '',
            'to_terminal': stage.to_terminal_id or '',
        }
    else:
        initial = {'alignment_radius_km': 50, 'display_color': '#FF6B35', 'is_active': True}

    return {
        'program': program,
        'stage': stage,
        'initial': initial,
        'action': action,
        'terminals': terminals,
        'funding_status_choices': CEL_FUNDING_STATUS_CHOICES,
        'stage_type_choices': CELStage._meta.get_field('stage_type').choices,
    }
