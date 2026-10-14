from django.apps import AppConfig


class ChannelsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'lead_channels'
    # Keep the original app label so database tables (channels_*) and migration history are unchanged.
    # The folder was renamed from 'channels' because that name is taken by the Django Channels package
    # used by the WhatsApp live inbox.
    label = 'channels'
    verbose_name = 'Channels'
