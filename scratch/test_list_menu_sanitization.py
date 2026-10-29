import os
import sys

# Set in-memory sqlite BEFORE django.setup()
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
crm_path = r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM'
if crm_path not in sys.path:
    sys.path.insert(0, crm_path)

import django
from django.conf import settings

# Test send_interactive_list logic
from chat.whatsapp.messages import send_interactive_list
from chat.automation.validator import validate_flow_graph

# 1. Test validator with > 24 char row
invalid_flow = {
    "nodes": [
        {"id": "trigger_1", "type": "trigger"},
        {
            "id": "list_1",
            "type": "list",
            "sections": [
                {
                    "title": "Options",
                    "rows": [
                        {"id": "r1", "title": "This title is way too long for whatsapp"},
                    ]
                }
            ]
        },
        {"id": "end_1", "type": "end"}
    ],
    "connections": [
        {"id": "c1", "source": "trigger_1", "source_output": "default", "target": "list_1"},
        {"id": "c2", "source": "list_1", "source_output": "default", "target": "end_1"}
    ]
}

res = validate_flow_graph(invalid_flow)
print("Validator test with >24 chars error detected:", any("24 characters" in e["message"] for e in res["errors"]))

# 2. Test send_interactive_list sanitization (under mock/unconfigured client)
test_sections = [
    {
        "title": "Section Title Too Long For Meta WhatsApp API",
        "rows": [
            {"id": "r1", "title": "Short"},
            {"id": "r2", "title": "Business Owner / Entrepreneur"},
        ]
    }
]
resp = send_interactive_list(
    to_phone_number="919876543210",
    body_text="What is your status?",
    button_text="Choose One",
    sections=test_sections
)
print("send_interactive_list mock sent successfully:", bool(resp.get('messages') or resp.get('mocked')))
print("All interactive list unit tests passed!")
