from django.urls import path

from . import views

# Mounted at /drive/ (kept for existing links). Recordings come from the CRM Call Sync app.
urlpatterns = [
    path('', views.call_recordings_list, name='drive_dashboard'),            # old name, same page
    path('recordings/', views.call_recordings_list, name='call_recordings_list'),
    path('recordings/retry-matching/', views.recordings_retry_match, name='recordings_retry_match'),
    path('stream/<int:recording_id>/', views.drive_stream_recording, name='drive_stream_recording'),
]
