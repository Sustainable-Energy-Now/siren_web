# views/ret_comments_views.py

from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.template.loader import render_to_string
from siren_web.models import ReportComment
from ..forms import ReportCommentForm, CommentEditForm


@login_required
@require_POST
def add_comment(request):
    """
    Add a comment to a report.
    Expects POST data: report_type, year, month (optional), quarter (optional), content, category
    """
    form = ReportCommentForm(request.POST)
    
    if form.is_valid():
        comment = form.save(commit=False)
        comment.author = request.user
        comment.report_type = request.POST.get('report_type')
        comment.year = int(request.POST.get('year'))
        
        # Set month/quarter based on report type
        if comment.report_type == 'monthly':
            comment.month = int(request.POST.get('month'))
        elif comment.report_type == 'quarterly':
            comment.quarter = int(request.POST.get('quarter'))
        
        comment.save()
        # Send notification
        # send_mail(
        #     subject=f'New comment on {comment.get_period_display()}',
        #     message=f'{comment.author_name} added a comment:\n\n{comment.content}',
        #     from_email='noreply@sen.asn.au',
        #     recipient_list=['webmaster@sen.asn.au'],
        # )
        # Return JSON for AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            html = render_to_string('ret_dashboard/partials/comment_item.html', {
                'comment': comment,
                'user': request.user,
            }, request=request)
            return JsonResponse({
                'success': True,
                'html': html,
                'comment_id': comment.id,
            })
        
        # Redirect for non-AJAX
        return redirect(request.POST.get('next', request.META.get('HTTP_REFERER', '/')))
    
    # Handle form errors
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': False,
            'errors': form.errors,
        }, status=400)
    
    return redirect(request.POST.get('next', request.META.get('HTTP_REFERER', '/')))


@login_required
@require_POST
def edit_comment(request, comment_id):
    """Edit an existing comment."""
    comment = get_object_or_404(ReportComment, id=comment_id)
    
    # Check permissions: only author or staff can edit
    if comment.author != request.user and not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    form = CommentEditForm(request.POST, instance=comment)
    
    if form.is_valid():
        form.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            html = render_to_string('ret_dashboard/partials/comment_item.html', {
                'comment': comment,
                'user': request.user,
            }, request=request)
            return JsonResponse({
                'success': True,
                'html': html,
            })
        
        return redirect(request.POST.get('next', request.META.get('HTTP_REFERER', '/')))
    
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)


@login_required
@require_POST
def delete_comment(request, comment_id):
    """Delete a comment."""
    comment = get_object_or_404(ReportComment, id=comment_id)
    
    # Check permissions: only author or staff can delete
    if comment.author != request.user and not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    comment.delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    return redirect(request.POST.get('next', request.META.get('HTTP_REFERER', '/')))


@login_required
@require_POST
def toggle_pin_comment(request, comment_id):
    """Toggle the pinned status of a comment (staff only)."""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    comment = get_object_or_404(ReportComment, id=comment_id)
    comment.is_pinned = not comment.is_pinned
    comment.save(update_fields=['is_pinned'])
    
    return JsonResponse({
        'success': True,
        'is_pinned': comment.is_pinned,
    })


@login_required
@require_POST
def toggle_resolve_comment(request, comment_id):
    """Toggle the resolved status of a comment."""
    comment = get_object_or_404(ReportComment, id=comment_id)
    
    # Only author, staff, or users who can manage the report can resolve
    if comment.author != request.user and not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    comment.is_resolved = not comment.is_resolved
    comment.save(update_fields=['is_resolved'])
    
    return JsonResponse({
        'success': True,
        'is_resolved': comment.is_resolved,
    })


@login_required
def get_comments(request, report_type, year, period=None):
    """
    Get all comments for a specific report (AJAX endpoint).
    period is month for monthly, quarter for quarterly, None for annual
    """
    if report_type == 'monthly':
        comments = ReportComment.get_comments_for_report(report_type, year, month=period)
    elif report_type == 'quarterly':
        comments = ReportComment.get_comments_for_report(report_type, year, quarter=period)
    else:
        comments = ReportComment.get_comments_for_report(report_type, year)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        html = render_to_string('ret_dashboard/partials/comments_list.html', {
            'comments': comments,
            'user': request.user,
        }, request=request)
        return JsonResponse({
            'success': True,
            'html': html,
            'count': comments.count(),
        })
    
    # For non-AJAX, return the queryset (used by template context)
    return comments
