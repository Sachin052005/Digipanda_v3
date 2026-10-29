path = r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\leads\detail_service.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Patch find_val and field_origins
target_1 = """    # 1. Notes parsed attributes lookup
    notes_attrs = extract_parsed_lead_attributes(lead.notes)

    def find_val(keys, default=''):
        for k in keys:
            if k in notes_attrs and notes_attrs[k]:
                return notes_attrs[k]
        return default"""

repl_1 = """    # 1. Notes parsed attributes lookup & custom_fields inspection
    notes_attrs = extract_parsed_lead_attributes(lead.notes)
    cf = dict(lead.custom_fields or {})
    field_origins = dict(cf.get('_field_origins') or {})

    def find_val(keys, default=''):
        for k in keys:
            if k in cf and cf[k] and str(cf[k]).strip() not in ('', 'Empty', 'None', 'null'):
                return str(cf[k]).strip()
        for k in keys:
            if k in notes_attrs and notes_attrs[k] and str(notes_attrs[k]).strip() not in ('', 'Empty', 'None', 'null'):
                return str(notes_attrs[k]).strip()
        return default"""

# 2. Patch return dict to include smart_pitch and tag fields with origin
target_2 = """    # 8. Navigation position (< Prev, Next >, position "X of Y")
    nav = get_lead_navigation(lead, user)

    # 9. Status and Activity History defaults
    status_history = list(lead.status_history.select_related('changed_by').order_by('-created_at')[:25])

    return {
        'lead': lead,
        'assignee_name': assignee_name,
        'assignee_initials': assignee_initials,
        'col1_fields': col1_fields,
        'col2_fields': col2_fields,
        'status_history': status_history,
        'whatsapp_phone': whatsapp_phone,
        'phone_display': phone_display,
        'chat_conversation': chat_conversation,
        'lead_status_choices': LeadStatus.choices,
        'call_outcome_choices': CallOutcome.choices,
        'call_status_choices': CallStatus.choices,
        'nav': nav,
    }"""

repl_2 = """    # 8. Navigation position (< Prev, Next >, position "X of Y")
    nav = get_lead_navigation(lead, user)

    # 9. Status and Activity History defaults
    status_history = list(lead.status_history.select_related('changed_by').order_by('-created_at')[:25])

    # 10. Tag fields with origin (Facebook, WhatsApp, Google Sheets, etc.)
    for f in col1_fields + col2_fields:
        f['origin'] = field_origins.get(f['key'], '')

    # 11. Generate Smart Pre-Call Pitch
    from .qualification import generate_smart_precall_pitch
    smart_pitch = generate_smart_precall_pitch(lead)

    return {
        'lead': lead,
        'assignee_name': assignee_name,
        'assignee_initials': assignee_initials,
        'col1_fields': col1_fields,
        'col2_fields': col2_fields,
        'status_history': status_history,
        'whatsapp_phone': whatsapp_phone,
        'phone_display': phone_display,
        'chat_conversation': chat_conversation,
        'lead_status_choices': LeadStatus.choices,
        'call_outcome_choices': CallOutcome.choices,
        'call_status_choices': CallStatus.choices,
        'nav': nav,
        'smart_pitch': smart_pitch,
    }"""

# 3. Patch update_lead_attribute to save to custom_fields as Manual origin
target_3 = """    # Record Activity Log
    log_activity("""

repl_3 = """    # Synchronize to lead.custom_fields with 'Manual' origin
    cf = dict(lead.custom_fields or {})
    cf[field_key] = val_str if val_str != 'Empty' else ''
    field_origins = dict(cf.get('_field_origins') or {})
    field_origins[field_key] = 'Manual'
    cf['_field_origins'] = field_origins
    lead.custom_fields = cf
    lead.save(update_fields=['custom_fields', 'updated_at'])

    # Record Activity Log
    log_activity("""

text_norm = text.replace('\r\n', '\n')
target_1_norm = target_1.replace('\r\n', '\n')
target_2_norm = target_2.replace('\r\n', '\n')
target_3_norm = target_3.replace('\r\n', '\n')

assert target_1_norm in text_norm, "Target 1 not found"
assert target_2_norm in text_norm, "Target 2 not found"
assert target_3_norm in text_norm, "Target 3 not found"

text_norm = text_norm.replace(target_1_norm, repl_1.replace('\r\n', '\n'), 1)
text_norm = text_norm.replace(target_2_norm, repl_2.replace('\r\n', '\n'), 1)
text_norm = text_norm.replace(target_3_norm, repl_3.replace('\r\n', '\n'), 1)

with open(path, 'w', encoding='utf-8', newline='\r\n') as f:
    f.write(text_norm)

print("Successfully updated detail_service.py")
