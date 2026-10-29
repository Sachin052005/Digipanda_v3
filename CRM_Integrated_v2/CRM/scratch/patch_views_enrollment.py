import os
import re

file_path = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/leads/views_enrollment.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add imports if not present
if 'TECHPANDA_INVOICE_CONFIG' not in content:
    content = content.replace(
        'from xhtml2pdf import pisa\n',
        'from xhtml2pdf import pisa\nimport os\nfrom .constants import TECHPANDA_INVOICE_CONFIG\nfrom .utils_currency import amount_to_inr_words\n'
    )
    if 'TECHPANDA_INVOICE_CONFIG' not in content:
        # Handle CRLF
        content = content.replace(
            'from xhtml2pdf import pisa\r\n',
            'from xhtml2pdf import pisa\r\nimport os\r\nfrom .constants import TECHPANDA_INVOICE_CONFIG\r\nfrom .utils_currency import amount_to_inr_words\r\n'
        )

# 2. Replace get_receipt_context return dictionary and calculation
old_context_block = """    return {
        'txn': txn,
        'enrollment': enrollment,
        'student_id': student_id,
        'qr_svg': qr_svg,
        'qr_b64': qr_b64,
        'qr_png_bytes': qr_png_bytes,
        'base_course_fee': base_course_fee,
        'taxable_amount': taxable_amount,
        'tax_amount': tax_amount,
        'tax_rate': tax_rate,
        'cgst_rate': cgst_rate,
        'sgst_rate': sgst_rate,
        'cgst_amount': cgst_amount,
        'sgst_amount': sgst_amount,
        'total_payable': total_payable,
        'prior_paid': prior_paid,
        'this_payment': this_payment,
        'cumulative_paid': cumulative_paid,
        'remaining_balance_after_txn': remaining_balance_after_txn,
        'current_outstanding': current_outstanding,
        'next_installment': next_installment,
        'verification_code': verification_code,
        'verification_url': verification_url,
        'branch_name': branch_name,
        'branch_address': branch_address,
        'institution_name': "TECHPANDA SOLUTIONS & ACADEMY",
        'institution_tagline': "Professional Software & Cloud Engineering Institute",
        'institution_email': "admissions@techpanda.org",
        'institution_phone': "+91 98765 43210",
        'institution_website': "www.techpanda.org",
    }"""

new_context_block = """    # Font & Logo local paths for xhtml2pdf rendering
    font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'Arial.ttf').replace('\\\\', '/')
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'techpanda_logo.png').replace('\\\\', '/')

    # Check Inter-state GST (IGST) vs Intra-state GST (CGST + SGST)
    is_interstate = False
    customer_state = getattr(enrollment, 'student_state', '') or ''
    branch_state = getattr(enrollment.branch, 'state', '') or 'Tamil Nadu'
    if customer_state and branch_state and customer_state.strip().lower() != branch_state.strip().lower():
        is_interstate = True
    elif getattr(enrollment, 'gst_treatment', None) == GSTTreatment.INTERSTATE:
        is_interstate = True

    igst_rate = tax_rate if is_interstate else Decimal('0.00')
    igst_amount = tax_amount if is_interstate else Decimal('0.00')
    if is_interstate:
        cgst_rate = Decimal('0.00')
        sgst_rate = Decimal('0.00')
        cgst_amount = Decimal('0.00')
        sgst_amount = Decimal('0.00')

    # Invoice and Student formatting matching reference Tax Invoice PDF
    invoice_number = txn.receipt_number or f"TP{txn.id:05d}"
    if txn.payment_date:
        invoice_date = txn.payment_date.strftime('%d/%m/%Y')
    elif txn.created_at:
        invoice_date = txn.created_at.strftime('%d/%m/%Y')
    else:
        invoice_date = timezone.now().strftime('%d/%m/%Y')

    customer_name = (enrollment.student_name or '').strip().upper()
    customer_mobile = (enrollment.student_phone or (enrollment.lead.phone if enrollment.lead else '') or '').strip()
    customer_email = (enrollment.student_email or (enrollment.lead.email if enrollment.lead else '') or '').strip()
    customer_address = getattr(enrollment, 'student_address', '') or ''
    place_of_supply = branch_state or TECHPANDA_INVOICE_CONFIG.get('default_place_of_supply', 'Tamil Nadu')

    course_name = (enrollment.product.name if enrollment.product else "DATA ANALYTICS COURSE").strip().upper()

    total_amount_in_words = amount_to_inr_words(total_payable)
    received_amount_in_words = amount_to_inr_words(cumulative_paid)
    balance_amount_in_words = amount_to_inr_words(remaining_balance_after_txn)

    return {
        'txn': txn,
        'enrollment': enrollment,
        'student_id': student_id,
        'qr_svg': qr_svg,
        'qr_b64': qr_b64,
        'qr_png_bytes': qr_png_bytes,
        'base_course_fee': base_course_fee,
        'taxable_amount': taxable_amount,
        'tax_amount': tax_amount,
        'tax_rate': tax_rate,
        'cgst_rate': cgst_rate,
        'sgst_rate': sgst_rate,
        'cgst_amount': cgst_amount,
        'sgst_amount': sgst_amount,
        'igst_rate': igst_rate,
        'igst_amount': igst_amount,
        'is_interstate': is_interstate,
        'total_payable': total_payable,
        'prior_paid': prior_paid,
        'this_payment': this_payment,
        'cumulative_paid': cumulative_paid,
        'remaining_balance_after_txn': remaining_balance_after_txn,
        'current_outstanding': current_outstanding,
        'next_installment': next_installment,
        'verification_code': verification_code,
        'verification_url': verification_url,
        'branch_name': branch_name,
        'branch_address': branch_address,
        'institution_name': TECHPANDA_INVOICE_CONFIG['company_name'],
        'institution_tagline': "Professional Software & Technology Training",
        'institution_email': TECHPANDA_INVOICE_CONFIG['email'],
        'institution_phone': TECHPANDA_INVOICE_CONFIG['mobile'],
        'institution_website': TECHPANDA_INVOICE_CONFIG['website'],
        'invoice_config': TECHPANDA_INVOICE_CONFIG,
        'invoice_number': invoice_number,
        'invoice_date': invoice_date,
        'customer_name': customer_name,
        'customer_mobile': customer_mobile,
        'customer_email': customer_email,
        'customer_address': customer_address,
        'place_of_supply': place_of_supply,
        'course_name': course_name,
        'taxable_rate': taxable_amount,
        'total_line_amount': total_payable,
        'total_invoice_amount': total_payable,
        'received_amount': cumulative_paid,
        'balance_amount': remaining_balance_after_txn,
        'total_amount_in_words': total_amount_in_words,
        'received_amount_in_words': received_amount_in_words,
        'balance_amount_in_words': balance_amount_in_words,
        'bank_details': TECHPANDA_INVOICE_CONFIG['bank_details'],
        'terms_and_conditions': TECHPANDA_INVOICE_CONFIG['terms_and_conditions'],
        'signatory_label': TECHPANDA_INVOICE_CONFIG['signatory_label'],
        'font_path': font_path,
        'logo_path': logo_path,
    }"""

# Normalize CRLF for matching
content_norm = content.replace('\r\n', '\n')
old_norm = old_context_block.replace('\r\n', '\n')
new_norm = new_context_block.replace('\r\n', '\n')

if old_norm in content_norm:
    content_norm = content_norm.replace(old_norm, new_norm)
    # Write back with CRLF
    content_final = content_norm.replace('\n', '\r\n')
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content_final)
    print("SUCCESS: views_enrollment.py successfully patched!")
else:
    print("ERROR: old_context_block could not be matched!")
