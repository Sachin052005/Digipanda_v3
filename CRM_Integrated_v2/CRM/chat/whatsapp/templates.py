"""
Meta WhatsApp Template Builders.
Helps construct valid template components according to Cloud API specifications.
"""

from typing import List, Dict, Any, Optional


def build_template_payload(
    template_name: str,
    language_code: str = "en_US",
    body_parameters: Optional[List[str]] = None,
    button_parameters: Optional[List[Dict[str, str]]] = None,
    header_image_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Constructs components list for WhatsApp template sending.
    """
    components = []

    # Header component (if image)
    if header_image_url:
        components.append({
            "type": "header",
            "parameters": [
                {
                    "type": "image",
                    "image": {"link": header_image_url}
                }
            ]
        })

    # Body component with positional text variables
    if body_parameters:
        components.append({
            "type": "body",
            "parameters": [
                {"type": "text", "text": str(val)} for val in body_parameters
            ]
        })

    # Quick reply or call-to-action buttons
    if button_parameters:
        for idx, btn in enumerate(button_parameters):
            components.append({
                "type": "button",
                "sub_type": btn.get("sub_type", "quick_reply"),
                "index": str(idx),
                "parameters": [
                    {
                        "type": btn.get("type", "payload"),
                        "payload": btn.get("payload", "")
                    }
                ]
            })

    return {
        "name": template_name,
        "language": {"code": language_code},
        "components": components
    }
