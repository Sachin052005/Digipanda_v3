"""
Django Template Tag Library for TechPanda CRM Dynamic Breadcrumbs.
Provides {% render_breadcrumbs %} and {% get_breadcrumbs as breadcrumb_list %}.
"""
from django import template
from accounts.breadcrumbs import resolve_breadcrumbs, BreadcrumbItem

register = template.Library()


@register.simple_tag(takes_context=True)
def get_breadcrumbs(context):
    """
    Returns the resolved breadcrumbs list from the current template context.
    If 'breadcrumbs' or 'page_breadcrumbs' is explicitly provided in context, it uses that.
    Otherwise, it resolves dynamically from the current named route and active objects.
    """
    explicit = context.get('breadcrumbs') or context.get('page_breadcrumbs')
    if explicit is not None:
        if isinstance(explicit, (list, tuple)):
            # Normalize tuples (label, url) to BreadcrumbItem if needed
            normalized = []
            for item in explicit:
                if isinstance(item, BreadcrumbItem):
                    normalized.append(item)
                elif isinstance(item, (tuple, list)) and len(item) == 2:
                    normalized.append(BreadcrumbItem(label=str(item[0]), url=item[1]))
                elif isinstance(item, str):
                    normalized.append(BreadcrumbItem(label=item, url=None))
            return normalized
        return []
    return resolve_breadcrumbs(context)


@register.inclusion_tag('components/breadcrumbs.html', takes_context=True)
def render_breadcrumbs(context):
    """
    Renders the semantic HTML5 breadcrumb component.
    """
    items = get_breadcrumbs(context)
    return {
        'breadcrumbs': items,
        'request': context.get('request'),
        'user': context.get('user'),
    }
