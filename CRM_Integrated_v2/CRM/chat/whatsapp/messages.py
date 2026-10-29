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
    Strictly sanitizes lengths to comply with Meta Cloud API limits:
    - Button text: max 20 characters
    - Section title: max 24 characters
    - Row title: max 24 characters (CRITICAL: Meta rejects if > 24)
    - Row description: max 72 characters
    - Total rows: max 10
    """
    client = WhatsAppClient(business_account=business_account)
    recipient = clean_phone_number(to_phone_number)

    # Sanitize sections and rows
    sanitized_sections: List[Dict[str, Any]] = []
    total_rows = 0

    for s_idx, sec in enumerate(sections or []):
        sec_title = str(sec.get('title') or f"Menu {s_idx + 1}").strip()[:24]
        raw_rows = sec.get('rows') or []
        sanitized_rows = []

        for r_idx, r in enumerate(raw_rows):
            if total_rows >= 10:
                break
            raw_title = str(r.get('title') or '').strip()
            if not raw_title:
                continue
            r_id = str(r.get('id') or f"row_{s_idx + 1}_{r_idx + 1}").strip()[:200]
            # Meta enforces strict 24-character limit for row title
            clean_title = raw_title[:24]

            row_data: Dict[str, str] = {
                "id": r_id,
                "title": clean_title,
            }
            raw_desc = str(r.get('description') or '').strip()
            if raw_desc:
                row_data["description"] = raw_desc[:72]

            sanitized_rows.append(row_data)
            total_rows += 1

        if sanitized_rows:
            sanitized_sections.append({
                "title": sec_title or "Options",
                "rows": sanitized_rows
            })

    # If no rows exist (e.g. database empty or unconfigured), fallback to clean text message so bot never hangs
    if not sanitized_sections or total_rows == 0:
        logger.warning("send_interactive_list called with 0 valid rows; falling back to text message for %s", recipient)
        return send_text_message(
            to_phone_number=to_phone_number,
            message_text=body_text or "Please choose an option:",
            business_account=business_account
        )

    btn_label = str(button_text or 'View Options').strip()[:20]
    if not btn_label:
        btn_label = 'View Options'

    interactive_obj: Dict[str, Any] = {
        "type": "list",
        "body": {
            "text": (body_text or "Please choose an option:")[:1024]
        },
        "action": {
            "button": btn_label,
            "sections": sanitized_sections
        }
    }

    if header_text and str(header_text).strip():
        interactive_obj["header"] = {
            "type": "text",
            "text": str(header_text).strip()[:60]
        }

    if footer_text and str(footer_text).strip():
        interactive_obj["footer"] = {
            "text": str(footer_text).strip()[:60]
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

