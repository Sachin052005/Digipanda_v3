"""
WhatsApp Cloud API Message Sending Services.
Builds compliant Meta payloads for text, media, and templates.
"""

from typing import Optional, List, Dict, Any
from .client import WhatsAppClient


def clean_phone_number(phone: str) -> str:
    """Format phone number by stripping +, spaces, dashes."""
    return ''.join(c for c in phone if c.isdigit())


def send_text_message(to_phone_number: str, text: str, preview_url: bool = False, business_account=None) -> Dict[str, Any]:
    """
    Sends a standard WhatsApp text message.
    """
    client = WhatsAppClient(business_account=business_account)
    recipient = clean_phone_number(to_phone_number)

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "text",
        "text": {
            "preview_url": preview_url,
            "body": text
        }
    }

    return client.send_payload(payload)


def send_media_message(
    to_phone_number: str,
    media_type: str,
    media_url_or_id: str,
    caption: Optional[str] = None,
    filename: Optional[str] = None,
    business_account=None
) -> Dict[str, Any]:
    """
    Sends an image, video, audio, or document message via WhatsApp Cloud API.
    Accepts either an externally accessible HTTPS URL or a WhatsApp media ID.
    """
    client = WhatsAppClient(business_account=business_account)
    recipient = clean_phone_number(to_phone_number)

    media_obj: Dict[str, Any] = {}
    if media_url_or_id.startswith("http://") or media_url_or_id.startswith("https://"):
        media_obj["link"] = media_url_or_id
    else:
        media_obj["id"] = media_url_or_id

    if caption and media_type in ['image', 'video', 'document']:
        media_obj["caption"] = caption

    if filename and media_type == 'document':
        media_obj["filename"] = filename

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": media_type,
        media_type: media_obj
    }

    return client.send_payload(payload)


def send_template_message(
    to_phone_number: str,
    template_name: str,
    language_code: str = "en_US",
    components: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Sends a pre-approved Meta WhatsApp Template message.
    Required when initiating conversations outside the 24-hour customer service window.
    """
    client = WhatsAppClient()
    recipient = clean_phone_number(to_phone_number)

    template_payload: Dict[str, Any] = {
        "name": template_name,
        "language": {
            "code": language_code
        }
    }

    if components:
        template_payload["components"] = components

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "template",
        "template": template_payload
    }

    return client.send_payload(payload)


def send_interactive_buttons(
    to_phone_number: str,
    body_text: str,
    buttons: List[Dict[str, str]],
    header_text: Optional[str] = None,
    footer_text: Optional[str] = None,
    business_account=None
) -> Dict[str, Any]:
    """
    Sends interactive reply buttons (up to 3 buttons) via Meta WhatsApp Cloud API.
    buttons format: [{"id": "btn_1", "title": "Training"}, ...]
    """
    client = WhatsAppClient(business_account=business_account)
    recipient = clean_phone_number(to_phone_number)

    formatted_buttons = []
    for btn in buttons[:3]:  # WhatsApp supports max 3 reply buttons
        formatted_buttons.append({
            "type": "reply",
            "reply": {
                "id": str(btn.get("id", btn.get("title", "")))[:256],
                "title": str(btn.get("title", ""))[:20]  # Max 20 chars for button title
            }
        })

    interactive_obj: Dict[str, Any] = {
        "type": "button",
        "body": {
            "text": body_text
        },
        "action": {
            "buttons": formatted_buttons
        }
    }

    if header_text:
        interactive_obj["header"] = {
            "type": "text",
            "text": header_text[:60]
        }

    if footer_text:
        interactive_obj["footer"] = {
            "text": footer_text[:60]
        }

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "interactive",
        "interactive": interactive_obj
    }

    return client.send_payload(payload)


def send_interactive_list(
    to_phone_number: str,
    body_text: str,
    button_text: str,
    sections: List[Dict[str, Any]],
    header_text: Optional[str] = None,
    footer_text: Optional[str] = None,
    business_account=None
) -> Dict[str, Any]:
    """
    Sends an interactive list menu (up to 10 rows) via WhatsApp Cloud API.
    sections: [{"title": "Courses", "rows": [{"id": "py", "title": "Python", "description": "3 Mos"}, ...]}]
    """
    client = WhatsAppClient(business_account=business_account)
    recipient = clean_phone_number(to_phone_number)

    interactive_obj: Dict[str, Any] = {
        "type": "list",
        "body": {
            "text": body_text
        },
        "action": {
            "button": button_text[:20],
            "sections": sections
        }
    }

    if header_text:
        interactive_obj["header"] = {
            "type": "text",
            "text": header_text[:60]
        }

    if footer_text:
        interactive_obj["footer"] = {
            "text": footer_text[:60]
        }

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "interactive",
        "interactive": interactive_obj
    }

    return client.send_payload(payload)


def send_location_message(
    to_phone_number: str,
    latitude: float,
    longitude: float,
    name: str,
    address: str,
    business_account=None
) -> Dict[str, Any]:
    """
    Sends a WhatsApp location pin message with name and address.
    """
    client = WhatsAppClient(business_account=business_account)
    recipient = clean_phone_number(to_phone_number)

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "location",
        "location": {
            "latitude": float(latitude),
            "longitude": float(longitude),
            "name": name,
            "address": address
        }
    }

    return client.send_payload(payload)

