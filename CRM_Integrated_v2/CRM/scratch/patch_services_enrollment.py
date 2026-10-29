path = r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\leads\services_enrollment.py'
with open(path, 'r', encoding='utf-8') as f:
    code = f.read()

target = """    # 7. Update Lead status to ENROLLED if not already
    if lead.status != LeadStatus.ENROLLED:
        lead.status = LeadStatus.ENROLLED
        lead.save(update_fields=['status', 'updated_at'])"""

replacement = """    # 7. Update Lead status to ENROLLED if not already
    if lead.status != LeadStatus.ENROLLED:
        lead.status = LeadStatus.ENROLLED
        lead.save(update_fields=['status', 'updated_at'])

    # Sync student email back to lead record if lead email is empty
    if student_email and not lead.email:
        lead.email = student_email
        lead.save(update_fields=['email', 'updated_at'])"""

target_lambda = "transaction.on_commit(lambda: send_enrollment_confirmation_email(enrollment))"
replacement_lambda = """def safe_send_enrollment_email():
            try:
                send_enrollment_confirmation_email(enrollment)
            except Exception as e:
                logger.error("Failed to send enrollment confirmation email for #%s: %s", getattr(enrollment, 'enrollment_number', 'N/A'), e)
        transaction.on_commit(safe_send_enrollment_email)"""

if target in code:
    code = code.replace(target, replacement)
    print("Replaced lead status update block")
else:
    print("Target not found for lead status update")

if target_lambda in code:
    code = code.replace(target_lambda, replacement_lambda)
    print("Replaced lambda with safe_send_enrollment_email")
else:
    print("Target lambda not found")

with open(path, 'w', encoding='utf-8') as f:
    f.write(code)

print("Updated services_enrollment.py")
