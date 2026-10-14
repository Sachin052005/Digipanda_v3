"""
WhatsApp Cloud API Media Management.
Handles validation, uploading outbound media, and downloading incoming media.
"""

import os
import requests
import logging
from django.conf import settings
from .client import WhatsAppClient

logger = logging.getLogger(__name__)


def validate_media_file(file_obj) -> bool:
    """
    Validates file size and content type before dispatching or saving.
    """
    max_size = getattr(settings, 'MAX_UPLOAD_SIZE', 16 * 1024 * 1024)
    if hasattr(file_obj, 'size') and file_obj.size > max_size:
        raise ValueError(f"File size exceeds maximum allowed ({max_size // (1024*1024)}MB).")

    allowed_types = getattr(settings, 'ALLOWED_MEDIA_TYPES', [])
    content_type = getattr(file_obj, 'content_type', None)
    if content_type and allowed_types and content_type not in allowed_types:
        raise ValueError(f"Content type '{content_type}' is not in allowed media types.")

    return True


def download_whatsapp_media(media_id: str, destination_dir: str = None) -> str:
    """
    Downloads media from WhatsApp Cloud API servers and saves it locally into MEDIA_ROOT.
    Returns relative path to the saved file.
    """
    client = WhatsAppClient()
    if not client.is_configured:
        logger.info(f"WhatsApp credentials not configured; media download {media_id} skipped.")
        return ""

    media_url = client.get_media_url(media_id)
    if not media_url:
        logger.error(f"Could not retrieve media URL for ID {media_id}")
        return ""

    headers = {"Authorization": f"Bearer {client.access_token}"}
    response = requests.get(media_url, headers=headers, stream=True, timeout=30)
    response.raise_for_status()

    target_dir = destination_dir or os.path.join(settings.MEDIA_ROOT, 'downloads')
    os.makedirs(target_dir, exist_ok=True)

    filename = f"wa_{media_id}"
    # Guess extension from Content-Type if available
    content_type = response.headers.get('Content-Type', '')
    ext_map = {
        'image/jpeg': '.jpg',
        'image/png': '.png',
        'image/webp': '.webp',
        'application/pdf': '.pdf',
        'audio/mpeg': '.mp3',
        'audio/ogg': '.ogg',
        'video/mp4': '.mp4',
    }
    filename += ext_map.get(content_type, '')
    full_path = os.path.join(target_dir, filename)

    with open(full_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    return os.path.relpath(full_path, settings.MEDIA_ROOT)


def upload_whatsapp_media(file_path_or_bytes, mime_type: str) -> str:
    """
    Uploads media to Meta Cloud API servers to acquire a media ID.
    """
    client = WhatsAppClient()
    if not client.is_configured:
        return f"mock_media_id_{mime_type.replace('/', '_')}"

    url = f"{client.base_url}/{client.phone_number_id}/media"
    headers = {"Authorization": f"Bearer {client.access_token}"}

    files = {
        'file': ('media_upload', file_path_or_bytes, mime_type),
    }
    data = {
        'messaging_product': 'whatsapp',
        'type': mime_type
    }

    response = requests.post(url, headers=headers, data=data, files=files, timeout=30)
    response.raise_for_status()
    return response.json().get('id', '')
