# resources_app/templatetags/query_transform.py
from django import template
from urllib.parse import urlencode

register = template.Library()

@register.simple_tag
def query_transform(request, **kwargs):
    """
    Return encoded querystring updating request.GET with kwargs.
    Usage: ?{% query_transform request page=3 %}
    """
    updated = request.GET.copy()
    for k, v in kwargs.items():
        updated[k] = v
    # remove empty values
    for key in list(updated.keys()):
        if updated.get(key) in [None, '']:
            updated.pop(key)
    return updated.urlencode()
