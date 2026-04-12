from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count, Prefetch
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.apps import apps
from siren_web.models import Reference, ReferenceAttribute
from siren_web.forms import ReferenceForm, ReferenceAttributeForm

# Django internal model prefixes to exclude from the model picker
_INTERNAL_PREFIXES = ('Auth', 'Django')


def _project_model_names():
    """Return sorted list of project model names, excluding Django internals."""
    return sorted(
        m.__name__
        for m in apps.get_app_config('siren_web').get_models()
        if not any(m.__name__.startswith(p) for p in _INTERNAL_PREFIXES)
    )


@login_required
def reference_list(request):
    """List all references with search and filtering"""
    references = Reference.objects.filter(is_active=True).prefetch_related('attributes')

    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        references = references.filter(
            Q(source__icontains=search_query) |
            Q(title__icontains=search_query) |
            Q(author__icontains=search_query) |
            Q(notes__icontains=search_query) |
            Q(tags__icontains=search_query)
        )

    # Filter by type
    ref_type = request.GET.get('type', '')
    if ref_type:
        references = references.filter(reference_type=ref_type)

    # Filter by model name
    model_filter = request.GET.get('model', '')
    if model_filter:
        references = references.filter(attributes__model_name=model_filter)

    # Annotate with attribute count
    references = references.annotate(attribute_count=Count('attributes'))

    # Pagination
    paginator = Paginator(references, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Distinct model names for filter dropdown
    model_names = (
        ReferenceAttribute.objects
        .values_list('model_name', flat=True)
        .distinct()
        .order_by('model_name')
    )

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'ref_type': ref_type,
        'reference_types': Reference.REFERENCE_TYPES,
        'model_filter': model_filter,
        'model_names': model_names,
        'total_count': references.count(),
    }
    return render(request, 'references/list.html', context)


@login_required
def reference_detail(request, pk):
    """Show detailed view of a reference"""
    reference = get_object_or_404(Reference, pk=pk)
    attributes = reference.attributes.all()
    attr_form = ReferenceAttributeForm()
    return render(request, 'references/detail.html', {
        'reference': reference,
        'attributes': attributes,
        'attr_form': attr_form,
        'model_names': _project_model_names(),
    })


@login_required
def reference_create(request):
    """Create a new reference"""
    if request.method == 'POST':
        form = ReferenceForm(request.POST)
        if form.is_valid():
            reference = form.save()
            messages.success(request, f'Reference "{reference.source}" created successfully.')
            return redirect('reference_detail', pk=reference.pk)
        else:
            for field_name, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field_name}: {error}")
    else:
        form = ReferenceForm()

    return render(request, 'references/form.html', {
        'form': form,
        'title': 'Add New Reference'
    })


@login_required
def reference_update(request, pk):
    """Update an existing reference"""
    reference = get_object_or_404(Reference, pk=pk)

    if request.method == 'POST':
        form = ReferenceForm(request.POST, instance=reference)
        if form.is_valid():
            form.save()
            messages.success(request, f'Reference "{reference.source}" updated successfully.')
            return redirect('reference_detail', pk=reference.pk)
    else:
        form = ReferenceForm(instance=reference)

    return render(request, 'references/form.html', {
        'form': form,
        'reference': reference,
        'title': 'Edit Reference'
    })


@login_required
@require_http_methods(["POST"])
def reference_delete(request, pk):
    """Delete a reference. Warns if attributes are linked; otherwise permanently deletes."""
    reference = get_object_or_404(Reference, pk=pk)
    attr_count = reference.attributes.count()
    if attr_count > 0:
        messages.error(
            request,
            f'Cannot delete "{reference.source}" — it is still linked to {attr_count} '
            f'model attribute{"s" if attr_count != 1 else ""}. '
            'Remove all linked attributes first.'
        )
        return redirect('reference_detail', pk=pk)
    source = str(reference)
    reference.delete()
    messages.success(request, f'Reference "{source}" has been permanently deleted.')
    return redirect('reference_list')


@login_required
@require_http_methods(["POST"])
def reference_attribute_add(request, pk):
    """Add a model-attribute link to a reference"""
    reference = get_object_or_404(Reference, pk=pk)
    form = ReferenceAttributeForm(request.POST)
    if form.is_valid():
        attr = form.save(commit=False)
        attr.reference = reference
        try:
            attr.save()
            messages.success(request, f'Linked {attr.model_name}.{attr.attribute_name} to this reference.')
        except Exception:
            messages.error(request, f'{attr.model_name}.{attr.attribute_name} is already linked to this reference.')
    else:
        for field_name, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field_name}: {error}")
    return redirect('reference_detail', pk=pk)


@login_required
@require_http_methods(["POST"])
def reference_attribute_remove(request, pk, attr_pk):
    """Remove a model-attribute link from a reference"""
    attr = get_object_or_404(ReferenceAttribute, pk=attr_pk, reference_id=pk)
    attr.delete()
    messages.success(request, f'Removed {attr.model_name}.{attr.attribute_name} from this reference.')
    return redirect('reference_detail', pk=pk)


@login_required
def reference_model_fields_api(request):
    """Return field names for a given model (AJAX)."""
    model_name = request.GET.get('model', '')
    if not model_name:
        return JsonResponse({'fields': []})
    try:
        model = apps.get_model('siren_web', model_name)
    except LookupError:
        return JsonResponse({'fields': []})
    fields = sorted(
        f.name
        for f in model._meta.get_fields()
        if hasattr(f, 'column')   # concrete fields only, no reverse relations
    )
    return JsonResponse({'fields': fields})


@login_required
def reference_search_api(request):
    """API endpoint for AJAX search"""
    query = request.GET.get('q', '')
    if len(query) < 2:
        return JsonResponse({'results': []})

    references = Reference.objects.filter(
        Q(source__icontains=query) |
        Q(title__icontains=query) |
        Q(author__icontains=query),
        is_active=True
    )[:10]

    results = [{
        'id': ref.id,
        'source': ref.source,
        'title': ref.title,
        'author': ref.author,
        'url': ref.get_absolute_url()
    } for ref in references]

    return JsonResponse({'results': results})
