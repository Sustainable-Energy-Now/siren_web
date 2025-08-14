from django.db.models import Count, Q
from .models import Reference


def get_reference_stats():
    """Get statistics about references"""
    total_refs = Reference.objects.filter(is_active=True).count()
    by_type = Reference.objects.filter(is_active=True).values(
        'reference_type'
    ).annotate(count=Count('id'))
    
    return {
        'total': total_refs,
        'by_type': {item['reference_type']: item['count'] for item in by_type},
        'recent': Reference.objects.filter(is_active=True).order_by('-accessed_date')[:5]
    }


def search_references(query, limit=10):
    """Search references with relevance scoring"""
    if not query:
        return Reference.objects.none()
    
    # Simple relevance scoring - you could enhance this
    return Reference.objects.filter(
        Q(source__icontains=query) |
        Q(title__icontains=query) |
        Q(author__icontains=query) |
        Q(notes__icontains=query) |
        Q(tags__icontains=query),
        is_active=True
    ).order_by('-accessed_date')[:limit]


def get_popular_tags():
    """Get most commonly used tags"""
    references = Reference.objects.filter(is_active=True, tags__isnull=False).exclude(tags='')
    tag_counts = {}
    
    for ref in references:
        for tag in ref.get_tags_list():
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    return sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:20]
