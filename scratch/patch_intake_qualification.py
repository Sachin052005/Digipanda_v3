import os

path = r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\leads\intake.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update Rule A
target_a = """                if filled_fields:
                    existing_lead.save(update_fields=filled_fields)

                if note:
                    add_note(existing_lead, note)"""

repl_a = """                if filled_fields:
                    existing_lead.save(update_fields=filled_fields)

                if isinstance(data_payload, dict) and data_payload:
                    try:
                        from .qualification import autofill_lead_qualification
                        autofill_lead_qualification(existing_lead, data_payload, source=source, preserve_manual_edits=True)
                    except Exception as e:
                        log.warning("Autofill qualification failed for duplicate lead %s: %s", existing_lead.id, e)

                if note:
                    add_note(existing_lead, note)"""

# 2. Update Rule B
target_b = """                existing_lead.save()

                if branch_changed or not existing_lead.assigned_telecaller_id:"""

repl_b = """                existing_lead.save()

                if isinstance(data_payload, dict) and data_payload:
                    try:
                        from .qualification import autofill_lead_qualification
                        autofill_lead_qualification(existing_lead, data_payload, source=source, preserve_manual_edits=True)
                    except Exception as e:
                        log.warning("Autofill qualification failed for re-enquiry lead %s: %s", existing_lead.id, e)

                if branch_changed or not existing_lead.assigned_telecaller_id:"""

# 3. Update Rule C
target_c = """        lead = Lead.objects.create(
            name=clean_name or number,
            phone=number,
            email=clean_email,
            channel=get_channel(channel_name) if channel_name else None,
            status=LeadStatus.NEW,
            source=source,
            is_offline=is_offline_lead,
            branch=branch,
            product=product,
            current_owner_type=LeadOwnerType.UNASSIGNED,
            assignment_status='Unassigned',
        )
        add_note(lead, f"New lead from {source}" + (f" — {note}" if note else ''))"""

repl_c = """        lead = Lead.objects.create(
            name=clean_name or number,
            phone=number,
            email=clean_email,
            channel=get_channel(channel_name) if channel_name else None,
            status=LeadStatus.NEW,
            source=source,
            is_offline=is_offline_lead,
            branch=branch,
            product=product,
            current_owner_type=LeadOwnerType.UNASSIGNED,
            assignment_status='Unassigned',
        )
        if isinstance(data_payload, dict) and data_payload:
            try:
                from .qualification import autofill_lead_qualification
                autofill_lead_qualification(lead, data_payload, source=source, preserve_manual_edits=False)
            except Exception as e:
                log.warning("Autofill qualification failed for new lead %s: %s", lead.id, e)

        add_note(lead, f"New lead from {source}" + (f" — {note}" if note else ''))"""

text_norm = text.replace('\r\n', '\n')
target_a_norm = target_a.replace('\r\n', '\n')
target_b_norm = target_b.replace('\r\n', '\n')
target_c_norm = target_c.replace('\r\n', '\n')

assert target_a_norm in text_norm, "Target A not found"
assert target_b_norm in text_norm, "Target B not found"
assert target_c_norm in text_norm, "Target C not found"

text_norm = text_norm.replace(target_a_norm, repl_a.replace('\r\n', '\n'), 1)
text_norm = text_norm.replace(target_b_norm, repl_b.replace('\r\n', '\n'), 1)
text_norm = text_norm.replace(target_c_norm, repl_c.replace('\r\n', '\n'), 1)

with open(path, 'w', encoding='utf-8', newline='\r\n') as f:
    f.write(text_norm)

print("Successfully updated intake.py")
