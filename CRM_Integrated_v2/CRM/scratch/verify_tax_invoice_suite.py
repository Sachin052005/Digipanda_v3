import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

import io
from decimal import Decimal
import pypdf
from django.template.loader import render_to_string
from django.test import RequestFactory
from leads.utils_currency import amount_to_inr_words
from leads.constants import TECHPANDA_INVOICE_CONFIG
from leads.views_enrollment import generate_receipt_pdf, get_receipt_context
from leads.models import PaymentTransaction, Enrollment, PaymentTransactionStatus
from products.models import Product
from branches.models import Branch

print("=" * 60)
print("RUNNING TECHPANDA TAX INVOICE VERIFICATION SUITE")
print("=" * 60)

# 1. Test Number to Words
print("\n[TEST 1] Currency Converter (amount_to_inr_words)...")
test_cases = [
    (41300, "Forty One Thousand Three Hundred Rupees Only"),
    (0, "Zero Rupees Only"),
    (0.50, "Fifty Paise Only"),
    (105000.50, "One Lakh Five Thousand Rupees And Fifty Paise Only"),
    (2500000, "Twenty Five Lakh Rupees Only"),
]
for amt, expected in test_cases:
    res = amount_to_inr_words(amt)
    assert res == expected, f"Failed for {amt}: got '{res}', expected '{expected}'"
    print(f"  PASS: ₹{amt} -> '{res}'")

# 2. Test Context Preparation with existing or dummy PaymentTransaction
print("\n[TEST 2] Testing get_receipt_context...")
factory = RequestFactory()
request = factory.get('/')

txn = PaymentTransaction.objects.select_related('enrollment', 'enrollment__product', 'enrollment__branch').first()
if not txn:
    print("  Creating mock enrollment & payment transaction for testing...")
    branch = Branch.objects.first()
    product = Product.objects.first()
    from leads.models import Lead, LeadStatus
    lead = Lead.objects.create(
        name="M DEEPAK ROSHAN",
        phone="9884678282",
        email="deepak@example.com",
        branch=branch,
        status=LeadStatus.ENROLLED
    )
    enrollment = Enrollment.objects.create(
        lead=lead,
        student_name="M DEEPAK ROSHAN",
        student_phone="9884678282",
        student_email="deepak@example.com",
        branch=branch,
        product=product,
        base_course_fee=Decimal('35000.00'),
        taxable_amount=Decimal('35000.00'),
        tax_amount=Decimal('6300.00'),
        tax_rate=Decimal('18.00'),
        total_payable=Decimal('41300.00'),
        total_paid=Decimal('41300.00'),
        outstanding_balance=Decimal('0.00'),
    )
    txn = PaymentTransaction.objects.create(
        enrollment=enrollment,
        amount=Decimal('41300.00'),
        receipt_number="TP12519",
        status=PaymentTransactionStatus.APPROVED,
    )

ctx = get_receipt_context(request, txn)
print("  Context keys verified:")
required_keys = [
    'invoice_config', 'invoice_number', 'invoice_date', 'customer_name',
    'customer_mobile', 'place_of_supply', 'course_name', 'taxable_rate',
    'total_line_amount', 'total_invoice_amount', 'received_amount',
    'balance_amount', 'total_amount_in_words', 'bank_details',
    'terms_and_conditions', 'signatory_label', 'font_path', 'logo_path'
]
for k in required_keys:
    assert k in ctx, f"Missing required context key: {k}"
    print(f"    - {k}: {str(ctx[k])[:40]}...")

# 3. Test PDF Generation
print("\n[TEST 3] Generating Tax Invoice PDF with xhtml2pdf...")
pdf_bytes = generate_receipt_pdf(ctx)
assert pdf_bytes is not None, "generate_receipt_pdf returned None!"
assert len(pdf_bytes) > 20000, f"PDF too small: {len(pdf_bytes)} bytes"
print(f"  PASS: PDF successfully generated ({len(pdf_bytes)} bytes)")

# 4. Verify PDF Text & Rupee Glyph
print("\n[TEST 4] Inspecting PDF text elements...")
reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
assert len(reader.pages) >= 1, "PDF has no pages!"
page_text = reader.pages[0].extract_text()

checks = [
    ("TechPanda", "Company branding"),
    ("TAX INVOICE", "Tax Invoice badge"),
    ("ORIGINAL FOR RECIPIENT", "Original for Recipient badge"),
    ("Invoice No.:", "Invoice number header"),
    ("BILL TO", "Customer billing label"),
    ("SERVICES", "Services column"),
    ("SUBTOTAL", "Subtotal summary"),
    ("BANK DETAILS", "Bank details header"),
    ("HDFC0000141", "IFSC code"),
    ("TERMS AND CONDITIONS", "Terms header"),
    ("AUTHORISED SIGNATORY", "Signatory label"),
    ("₹", "Unicode Rupee symbol"),
]
for substr, desc in checks:
    assert substr in page_text, f"Missing in PDF text: {desc} ('{substr}')"
    print(f"  PASS: Verified '{substr}' ({desc}) in PDF")

# 5. Test Email HTML Template Rendering
print("\n[TEST 5] Rendering HTML Email Template...")
email_html = render_to_string('emails/payment_receipt.html', ctx)
assert "TAX INVOICE" in email_html
assert "ORIGINAL FOR RECIPIENT" in email_html
assert "admin@itechpanda.com" in email_html
assert "HDFC0000141" in email_html
assert "AUTHORISED SIGNATORY" in email_html
print(f"  PASS: HTML Email rendered ({len(email_html)} characters)")

# 6. Test Email Plaintext Template Rendering
print("\n[TEST 6] Rendering Plaintext Email Template...")
email_txt = render_to_string('emails/payment_receipt.txt', ctx)
assert "TAX INVOICE" in email_txt
assert "ORIGINAL FOR RECIPIENT" in email_txt
assert "HDFC0000141" in email_txt
assert "AUTHORISED SIGNATORY" in email_txt
print(f"  PASS: Plaintext Email rendered ({len(email_txt)} characters)")

# Save verification PDF to scratch
out_pdf_path = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/scratch/verified_tax_invoice_output.pdf'
with open(out_pdf_path, 'wb') as f:
    f.write(pdf_bytes)
print(f"\nSaved verified PDF to: {out_pdf_path}")

print("\n" + "=" * 60)
print("ALL VERIFICATION SUITE CHECKS PASSED (100% SUCCESS)!")
print("=" * 60)
