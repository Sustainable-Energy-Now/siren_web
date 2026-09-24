# ============================================================================
# common/mixins.py
# ============================================================================
# common/mixins.py
from siren_web.models import ReportComment

class CommentsMixin:
    """
    Mixin to add comments functionality to RET dashboard views.
    
    Usage in your existing views:
    
    For function-based views, use the helper function:
        context = get_comments_context('monthly', year, month=month)
        # Add to your existing context
    
    For class-based views, inherit from this mixin.
    """
    
    def get_comments_context(self, report_type, year, month=None, quarter=None):
        """
        Get the comments context for a report.
        
        Args:
            report_type: 'monthly', 'quarterly', or 'annual'
            year: The year
            month: The month (for monthly reports)
            quarter: The quarter (for quarterly reports)
        
        Returns:
            dict with 'comments' and 'report_type' keys
        """
        comments = ReportComment.get_comments_for_report(
            report_type, year, month=month, quarter=quarter
        )
        
        return {
            'comments': comments,
            'report_type': report_type,
        }

def get_comments_context(report_type, year, month=None, quarter=None):
    """
    Helper function to get comments context for function-based views.
    
    Usage in your ret_dashboard_views.py:
    
        from ..mixins import get_comments_context
        
        def ret_dashboard(request, year=None, month=None):
            # ... existing code ...
            
            # Add comments
            comments_ctx = get_comments_context('monthly', year, month=month)
            context.update(comments_ctx)
            
            return render(request, 'ret_dashboard/dashboard.html', context)
    """
    comments = ReportComment.get_comments_for_report(
        report_type, year, month=month, quarter=quarter
    )
    
    return {
        'comments': comments,
        'report_type': report_type,
    }