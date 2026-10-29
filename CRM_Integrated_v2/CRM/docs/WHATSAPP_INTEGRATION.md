# WhatsApp Business Cloud API — Integration & Webhook Guide

## 1. Webhook Configuration & Handshake

The WhatsApp Business Cloud API interacts with the CRM via HTTP webhooks at `/webhook/whatsapp/`.

### 1.1 Webhook Verification (GET)
- **Parameters**: `hub.mode=subscribe`, `hub.verify_token`, `hub.challenge`
- **Verification**: Handled by `verify_webhook_token` in `CRM/chat/whatsapp/webhook.py`.
- **Response**: Echoes back `hub.challenge` if token matches `WHATSAPP_VERIFY_TOKEN` (configured in settings / environment).

### 1.2 Webhook Inbound Ingestion (POST)
- Receives payload containing `entry[0].changes[0].value`.
- Authenticates business phone number ID and associates conversation with `BusinessAccount`.
- Deduplicates messages using WhatsApp Message ID (`wamid`) to eliminate re-delivery spikes.
- Distinguishes standard text, `button_reply`, `list_reply`, and media attachments.

---

## 2. Meta WhatsApp Cloud API Strict Message Constraints

To prevent message rejection by Meta Graph API servers, the application strictly adheres to the following constraints:

| Interactive Type | Field | Character Limit | Enforcement & Behavior |
| :--- | :--- | :--- | :--- |
| **Buttons** | Button Count | **Max 3 buttons** | Meta hard limit. Validated client-side and server-side. For 4+ options, use List Menu. |
| **Buttons** | Button Title | **Max 20 chars** | Truncated / sanitized automatically (`[:20]`). |
| **Buttons** | Body Text | Max 1024 chars | Standard body limit. |
| **List Menu** | Row Count | **Max 10 rows** | Total rows across sections cannot exceed 10. |
| **List Menu** | Button Label | Max 20 chars | Action button text (e.g., "Select Status"). |
| **List Menu** | Section Title | Max 24 chars | Header for row groups. |
| **List Menu** | Row Title | **Max 24 chars** | Meta rejects if $> 24$ chars. Truncated automatically (`[:24]`). |
| **List Menu** | Row Description | Max 72 chars | Optional sub-text (`[:72]`). |

---

## 3. Dispatched Message Payloads

### 3.1 Quick-Reply Buttons Payload
```json
{
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "to": "+919876543210",
  "type": "interactive",
  "interactive": {
    "type": "button",
    "header": { "type": "text", "text": "Question 1" },
    "body": { "text": "What are you looking for?" },
    "footer": { "text": "Select an option" },
    "action": {
      "buttons": [
        { "type": "reply", "reply": { "id": "opt_1", "title": "Training" } },
        { "type": "reply", "reply": { "id": "opt_2", "title": "Train + Placement" } }
      ]
    }
  }
}
```

### 3.2 Interactive List Menu Payload
```json
{
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "to": "+919876543210",
  "type": "interactive",
  "interactive": {
    "type": "list",
    "header": { "type": "text", "text": "Current Status" },
    "body": { "text": "What is your current status?" },
    "footer": { "text": "Tap button to view choices" },
    "action": {
      "button": "Select Status",
      "sections": [
        {
          "title": "Status Options",
          "rows": [
            { "id": "row_1", "title": "College Student", "description": "Currently enrolled" },
            { "id": "row_2", "title": "Fresher / Job Seeker", "description": "Looking for employment" },
            { "id": "row_3", "title": "Working Professional", "description": "Up-skilling" },
            { "id": "row_4", "title": "Business Owner / Entrep", "description": "Entrepreneur or business" }
          ]
        }
      ]
    }
  }
}
```
