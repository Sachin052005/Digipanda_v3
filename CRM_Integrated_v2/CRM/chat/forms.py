from django import forms
from .models import Message, Conversation
from django.conf import settings


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['conversation', 'message_text', 'message_type', 'media_file']

    def clean_media_file(self):
        media = self.cleaned_data.get('media_file')
        if media:
            if media.size > getattr(settings, 'MAX_UPLOAD_SIZE', 16 * 1024 * 1024):
                raise forms.ValidationError("Uploaded file exceeds the maximum allowed size (16MB).")
            # Content type check
            content_type = getattr(media, 'content_type', None)
            allowed_types = getattr(settings, 'ALLOWED_MEDIA_TYPES', [])
            if content_type and allowed_types and content_type not in allowed_types:
                raise forms.ValidationError(f"File type '{content_type}' is not supported.")
        return media
