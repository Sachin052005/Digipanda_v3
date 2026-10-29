import os
import pymupdf
from django.test import TestCase, RequestFactory
from leads.models_enrollment import PaymentTransaction, PaymentTransactionStatus
from leads.views_enrollment import get_receipt_context, generate_receipt_pdf


class SignaturePdfIntegrationTest(TestCase):
    """
    Automated test verifying that the authentic Shashi Sign image is properly
    embedded in approved/official invoice PDFs, and excluded from unapproved documents.
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get('/')
        self.txn = PaymentTransaction.objects.filter(
            status__in=[PaymentTransactionStatus.APPROVED, PaymentTransactionStatus.SUCCESS]
        ).first()

    def test_authorized_receipt_embeds_shashi_signature(self):
        if not self.txn:
            self.skipTest("No approved transaction found in database fixture")

        ctx = get_receipt_context(self.request, self.txn)

        # Context assertions
        self.assertTrue(ctx.get('is_authorized'))
        self.assertIsNotNone(ctx.get('signature_path'))
        self.assertTrue(os.path.exists(ctx['signature_path']))
        self.assertIsNotNone(ctx.get('signature_data_uri'))

        # PDF rendering assertion
        pdf_bytes = generate_receipt_pdf(ctx)
        self.assertIsNotNone(pdf_bytes)
        self.assertGreater(len(pdf_bytes), 0)

        # PyMuPDF embedded image check
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        self.assertEqual(len(doc), 1, "Invoice must fit on exactly 1 single A4 page")

        page = doc[0]
        images = page.get_images()
        self.assertGreaterEqual(len(images), 2, "Invoice must contain both company logo and signature image")

        sig_found = False
        for img_info in images:
            xref = img_info[0]
            base_img = doc.extract_image(xref)
            if base_img["width"] == 1024 and base_img["height"] == 1024:
                sig_found = True
                break

        self.assertTrue(sig_found, "Authentic 1024x1024 signature image must be embedded as an XObject")

    def test_unapproved_receipt_excludes_signature(self):
        if not self.txn:
            self.skipTest("No approved transaction found in database fixture")

        from unittest.mock import MagicMock
        mock_txn = MagicMock()
        mock_txn.id = 999999
        mock_txn.status = PaymentTransactionStatus.PENDING
        mock_txn.enrollment = self.txn.enrollment
        mock_txn.receipt_number = "DRAFT-001"
        mock_txn.amount = self.txn.amount
        mock_txn.payment_date = self.txn.payment_date
        mock_txn.created_at = self.txn.created_at

        mock_ctx = get_receipt_context(self.request, mock_txn)

        self.assertFalse(mock_ctx.get('is_authorized'))
        self.assertIsNone(mock_ctx.get('signature_path'))
        self.assertIsNone(mock_ctx.get('signature_data_uri'))

        pdf_bytes = generate_receipt_pdf(mock_ctx)
        self.assertIsNotNone(pdf_bytes)

        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        for img_info in doc[0].get_images():
            xref = img_info[0]
            base_img = doc.extract_image(xref)
            self.assertFalse(
                base_img["width"] == 1024 and base_img["height"] == 1024,
                "Unapproved / draft receipts must never embed the authorized signature"
            )
