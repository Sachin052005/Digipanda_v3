"""
Settings for the CRM Call Sync integration (Android app -> CRM).
Override any key in config/settings.py:

CALLS = {
    "PRIVATE_MEDIA_ROOT": BASE_DIR / "private_media",  # app recordings live here, NOT in /media/
    "MAX_RECORDING_MB": 50,
    "CALLBACK_WITHIN_MINUTES": 15,      # missed Google call -> follow-up due this soon
    "MATCH_WINDOW_SECONDS": 600,        # recording <-> call matching tolerance
    "GOOGLE_CALL_SOURCE": "Google Call", # Lead.source for leads created by Google Ads calls
    "APP_LOGIN_ROLES": ("TELECALLER", "COUNSELOR", "BRANCH_HEAD"),
    "ON_MISSED_CALL": None,             # optional dotted path: function(call_event)
}
"""
from django.conf import settings

DEFAULTS = {
    "PRIVATE_MEDIA_ROOT": None,  # None -> BASE_DIR / "private_media"
    "MAX_RECORDING_MB": 50,
    "CALLBACK_WITHIN_MINUTES": 15,
    "MATCH_WINDOW_SECONDS": 600,
    "GOOGLE_CALL_SOURCE": "Google Call",
    "APP_LOGIN_ROLES": ("TELECALLER", "COUNSELOR", "BRANCH_HEAD"),
    "ON_MISSED_CALL": None,
    "ALLOWED_AUDIO_EXTENSIONS": (
        "mp3", "m4a", "aac", "amr", "awb", "wav", "ogg", "oga", "opus", "3gp", "3gpp", "mp4", "webm", "flac",
    ),
}


def get(key):
    return {**DEFAULTS, **getattr(settings, "CALLS", {})}[key]
