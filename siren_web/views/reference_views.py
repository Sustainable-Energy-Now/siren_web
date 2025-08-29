from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from siren_web.models import Reference
from siren_web.forms import ReferenceForm


@login_required
def reference_list(request):
    """List all references with search and filtering"""
    references = Reference.objects.filter(is_active=True)
    
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
    
    # Pagination
    paginator = Paginator(references, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'ref_type': ref_type,
        'reference_types': Reference.REFERENCE_TYPES,
    }
    return render(request, 'references/list.html', context)

@login_required
def reference_detail(request, pk):
    """Show detailed view of a reference"""
    reference = get_object_or_404(Reference, pk=pk)
    return render(request, 'references/detail.html', {'reference': reference})

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
            # Handle form errors and display specific messages for fields
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
    """Soft delete a reference"""
    reference = get_object_or_404(Reference, pk=pk)
    reference.is_active = False
    reference.save()
    messages.success(request, f'Reference "{reference.source}" has been archived.')
    return redirect('reference_list')

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
