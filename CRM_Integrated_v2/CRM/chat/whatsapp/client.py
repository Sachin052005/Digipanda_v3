"""
Official Meta WhatsApp Cloud API HTTP Client.
Handles authorization, endpoint paths, and network communication with Graph API.
"""

import logging
import requests
from django.conf import settings

import os
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class WhatsAppClient:
    """
    Client for interacting with the Meta WhatsApp Cloud API.
    Uses credentials defined in settings or dynamically loaded from .env.
    """

    def __init__(self, access_token=None, phone_number_id=None, api_version=None, business_account=None):
        # Refresh environment from .env if needed
        base_dir = getattr(settings, 'BASE_DIR', Path('.'))
        env_file = base_dir / '.env'
        if env_file.exists():
            load_dotenv(env_file, override=True)

        if business_account:
            phone_number_id = phone_number_id or getattr(business_account, 'phone_number_id', None)
            if getattr(business_account, 'access_token', None):
                access_token = access_token or business_account.access_token

        self.access_token = (
            access_token
            or os.getenv('WHATSAPP_ACCESS_TOKEN')
            or getattr(settings, 'WHATSAPP_ACCESS_TOKEN', '')
        )
        self.phone_number_id = (
            phone_number_id
            or os.getenv('WHATSAPP_PHONE_NUMBER_ID')
            or getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', '')
        )
        self.api_version = (
            api_version
            or os.getenv('WHATSAPP_API_VERSION')
            or getattr(settings, 'WHATSAPP_API_VERSION', 'v21.0')
        )
        self.base_url = f"https://graph.facebook.com/{self.api_version}"

    @property
    def is_configured(self) -> bool:
        """Returns True if minimum required credentials are configured."""
        return bool(self.access_token and self.phone_number_id)

    def get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def send_payload(self, payload: dict) -> dict:
        """
        Sends an arbitrary JSON payload to the /messages endpoint of the Cloud API.
        """
        if not self.is_configured:
            logger.warning(
                "WhatsApp Cloud API credentials not configured. "
                "Simulating outbound delivery in development mode."
            )
            # Return realistic response structure for development without throwing
            return {
                "messaging_product": "whatsapp",
                "contacts": [{"input": payload.get("to"), "wa_id": payload.get("to")}],
                "messages": [{"id": f"wamid.mock_{payload.get('to')}_{payload.get('type')}"}],
                "mocked": True,
            }

        url = f"{self.base_url}/{self.phone_number_id}/messages"
        try:
            response = requests.post(
                url,
                json=payload,
                headers=self.get_headers(),
                timeout=15
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as exc:
            error_msg = f"WhatsApp Cloud API request failed: {exc}"
            if hasattr(exc, 'response') and exc.response is not None:
                try:
                    error_msg += f" - Response: {exc.response.text}"
                except Exception:
                    pass
            logger.error(error_msg)
            raise RuntimeError(error_msg) from exc

    def upload_media(self, file_path_or_file, mime_type: str = 'application/octet-stream') -> str:
        """
        Uploads local media directly to Meta WhatsApp Cloud API via:
        POST /{PHONE_NUMBER_ID}/media
        Returns the Meta media ID string.
        """
        if not self.is_configured:
            return "mock_media_id_12345"

        url = f"{self.base_url}/{self.phone_number_id}/media"
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }

        # Check if file_path_or_file is a file-like object or a path string
        if hasattr(file_path_or_file, 'read'):
            files = {
                'file': (getattr(file_path_or_file, 'name', 'file'), file_path_or_file, mime_type)
            }
            data = {
                'messaging_product': 'whatsapp'
            }
            response = requests.post(url, headers=headers, files=files, data=data, timeout=30)
        else:
            with open(file_path_or_file, 'rb') as f:
                import os
                filename = os.path.basename(file_path_or_file)
                files = {
                    'file': (filename, f, mime_type)
                }
                data = {
                    'messaging_product': 'whatsapp'
                }
                response = requests.post(url, headers=headers, files=files, data=data, timeout=30)

        response.raise_for_status()
        return response.json().get('id', '')

    def get_media_url(self, media_id: str) -> str:
        """
        Queries Graph API to retrieve the download URL for a given media_id.
        """
        if not self.is_configured:
            return ""

        url = f"{self.base_url}/{media_id}"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json().get('url', '')
