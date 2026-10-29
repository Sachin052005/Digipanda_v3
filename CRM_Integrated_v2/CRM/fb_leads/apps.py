import os
import sys
from django.apps import AppConfig


class FbLeadsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "fb_leads"
    verbose_name = "Facebook Leads"

    def ready(self):
        # Only start scheduler when running runserver
        if "runserver" in sys.argv and os.environ.get("RUN_MAIN") == "true":
            try:
                from .scheduler import ensure_scheduler_running
                ensure_scheduler_running()
            except Exception:
                pass
