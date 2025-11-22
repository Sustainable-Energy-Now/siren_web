# siren_web/templatetags/math_filters.py
from django import template
from datetime import date, datetime
import calendar

register = template.Library()

@register.filter
def abs(value):
    """Return the absolute value of the number."""
    try:
        return abs(float(value))
    except (ValueError, TypeError):
        return value

@register.filter
def add_months(value, months):
    """
    Add months to a date/datetime, preserving the day if possible.
    Falls back to last day of month if target month is shorter.
    """
    if not value:
        return value

    # Convert string from {% now %} into a date if needed
    if isinstance(value, str):
        try:
            value = datetime.strptime(value, "%d %B %Y").date()
        except ValueError:
            return value

    month = value.month - 1 + int(months)
    year = value.year + month // 12
    month = month % 12 + 1

    day = min(value.day, calendar.monthrange(year, month)[1])

    return date(year, month, day)

@register.filter
def div(value, arg):
    """Divide value by arg"""
    try:
        if float(arg) == 0:
            return 0
        return float(value) / float(arg)
    except (ValueError, TypeError):
        return ''

@register.filter
def mul(value, arg):
    """Multiply value by arg"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return ''

@register.filter
def percent(value, total):
    """Calculate percentage: (value / total) * 100"""
    try:
        value = float(value)
        total = float(total)
        if total != 0:
            return (value / total) * 100
        return 0
    except (ValueError, TypeError):
        return 0

@register.filter
def sub(value, arg):
    """Subtract arg from value"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return ''

@register.filter
def sum_attr(queryset, attr_name):
    """
    Sum a specific attribute across a queryset or list of objects
    Usage: {{ new_capacity|sum_attr:"capacity_mw" }}
    """
    try:
        total = 0
        for obj in queryset:
            value = getattr(obj, attr_name, 0)
            if value is not None:
                total += float(value)
        return total
    except (ValueError, TypeError, AttributeError):
        return 0