from django import template

register = template.Library()

@register.filter
def get_dynamic_attr(obj, attr_name):
    """
    Custom template filter to dynamically access attributes of an object.
    """
    try:
        return getattr(obj, attr_name)
    except AttributeError:
        return None
