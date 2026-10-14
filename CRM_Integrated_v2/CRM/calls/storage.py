import os
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage

from . import conf


class PrivateRecordingStorage(FileSystemStorage):
    """
    App call recordings are stored outside MEDIA_ROOT so nobody can download them by
    guessing a /media/ URL. They are only served through drive.views.drive_stream_recording,
    which applies the CRM's role-based access checks.

    The folder is read from settings.CALLS['PRIVATE_MEDIA_ROOT'] on every use, so it can be
    changed per environment (and in tests) without a migration.
    """

    def __init__(self):
        super().__init__(base_url=None)

    @property
    def base_location(self):
        return str(conf.get("PRIVATE_MEDIA_ROOT") or Path(settings.BASE_DIR) / "private_media")

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    def url(self, name):
        raise ValueError("Private call recordings have no public URL; use drive_stream_recording.")


def private_storage():
    return PrivateRecordingStorage()
