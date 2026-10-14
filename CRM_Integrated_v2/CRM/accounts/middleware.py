import zoneinfo
from django.utils import timezone

class DeviceTimezoneMiddleware:
    """
    Middleware that activates the user's device/browser time zone for each request.
    Reads 'django_timezone' cookie sent by browser JavaScript (Intl.DateTimeFormat().resolvedOptions().timeZone).
    Falls back to settings.TIME_ZONE if not set or invalid.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tzname = request.COOKIES.get('django_timezone')
        if tzname:
            try:
                timezone.activate(zoneinfo.ZoneInfo(tzname))
            except Exception:
                timezone.deactivate()
        else:
            timezone.deactivate()
        return self.get_response(request)
