from django import template

register = template.Library()


@register.simple_tag
def google_calls_for(lead, limit=20):
    """Google Ads number calls synced from telecaller phones for this lead (newest first)."""
    if lead is None or not getattr(lead, 'pk', None):
        return []
    return list(lead.call_events.select_related('telecaller').order_by('-started_at')[:limit])


@register.simple_tag
def pending_callbacks_for(lead):
    if lead is None or not getattr(lead, 'pk', None):
        return 0
    return lead.call_events.filter(needs_callback=True).count()


@register.simple_tag(takes_context=True)
def missed_callbacks_count(context):
    """Sidebar badge: leads this user can see that are waiting for a missed-call call back."""
    request = context.get('request')
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return 0
    try:
        from calls.sync_services import leads_with_pending_callback
        return leads_with_pending_callback(user).count()
    except Exception:
        return 0


@register.simple_tag
def whatsapp_chats_for(lead):
    """WhatsApp conversations (any business number) with this lead's phone or alternate phone."""
    if lead is None or not getattr(lead, 'pk', None):
        return []
    try:
        from chat.models import Conversation
        from calls.sync_services import phone10
    except Exception:
        return []
    tails = {n[-10:] for n in (phone10(lead.phone), phone10(lead.alternate_phone)) if n}
    if not tails:
        return []
    chats = []
    for t in tails:
        chats.extend(Conversation.objects.filter(phone_number__endswith=t).select_related('business_account'))
    return sorted({c.pk: c for c in chats}.values(),
                  key=lambda c: c.last_message_time or c.created_at, reverse=True)


@register.simple_tag
def facebook_entries_for(lead):
    """Facebook Lead Ad submissions that created or touched this lead."""
    if lead is None or not getattr(lead, 'pk', None):
        return []
    try:
        return list(lead.facebook_entries.order_by('-created_on_facebook', '-received_at')[:10])
    except Exception:
        return []


@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    """
    Returns the current query string with specified parameters replaced or added.
    Preserves all existing GET parameters (e.g., search, branch, status) across pagination links.
    Usage: <a href="?{% url_replace page=page_obj.next_page_number %}">
    """
    request = context.get('request')
    if not request or not hasattr(request, 'GET'):
        from urllib.parse import urlencode
        return urlencode({k: str(v) for k, v in kwargs.items() if v is not None and v != ''})
    query = request.GET.copy()
    for k, v in kwargs.items():
        if v is None or v == '':
            query.pop(k, None)
        else:
            query[k] = str(v)
    return query.urlencode()
