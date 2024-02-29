from django import template

register = template.Library()

@register.filter
def get_dynamic_attr(obj, attr_name):
    """
    Custom template filter to dynamically access attributes of an object.
    """
    try:
        value = getattr(obj, attr_name)
        return str(value) if value is not None else ""
    except AttributeError:
        return None
