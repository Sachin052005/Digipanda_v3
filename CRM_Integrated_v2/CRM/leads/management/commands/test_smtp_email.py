"""
Management command to safely diagnose Gmail SMTP configuration and optionally send a test email.
Usage:
    python manage.py test_smtp_email
    python manage.py test_smtp_email --send-to recipient@example.com
"""

import socket
import smtplib
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection


class Command(BaseCommand):
    help = "Diagnose Gmail SMTP connectivity, authentication, and optionally send a test message."

    def add_arguments(self, parser):
        parser.add_argument(
            '--send-to',
            type=str,
            dest='send_to',
            default='',
            help='Specify an email address to send a real test email to.'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== TECHPANDA CRM SMTP Configuration Diagnostic ==="))

        host = getattr(settings, 'EMAIL_HOST', 'smtp.gmail.com')
        port = int(getattr(settings, 'EMAIL_PORT', 587))
        use_tls = bool(getattr(settings, 'EMAIL_USE_TLS', True))
        use_ssl = bool(getattr(settings, 'EMAIL_USE_SSL', False))
        user = getattr(settings, 'EMAIL_HOST_USER', '')
        password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '')
        timeout = int(getattr(settings, 'EMAIL_TIMEOUT', 20))

        # 1. Print configuration summary safely
        self.stdout.write(f"EMAIL_BACKEND   : {getattr(settings, 'EMAIL_BACKEND', '')}")
        self.stdout.write(f"EMAIL_HOST      : {host}")
        self.stdout.write(f"EMAIL_PORT      : {port}")
        self.stdout.write(f"EMAIL_USE_TLS   : {use_tls}")
        self.stdout.write(f"EMAIL_USE_SSL   : {use_ssl}")
        self.stdout.write(f"EMAIL_HOST_USER : {user if user else '<NOT SET>'}")
        self.stdout.write(f"EMAIL_HOST_PASSWORD: {'[CONFIGURED]' if bool(password) else '<NOT SET / EMPTY>'}")
        self.stdout.write(f"DEFAULT_FROM_EMAIL : {from_email}")
        self.stdout.write(f"EMAIL_TIMEOUT   : {timeout}s")
        self.stdout.write("")

        if use_tls and use_ssl:
            self.stdout.write(self.style.ERROR("[!] Warning: Both EMAIL_USE_TLS and EMAIL_USE_SSL are True. Gmail SMTP typically requires TLS on 587 or SSL on 465, not both."))

        # 2. Network socket check
        self.stdout.write(f"Step 1: Checking TCP socket connectivity to {host}:{port}...")
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
            sock.close()
            self.stdout.write(self.style.SUCCESS(f"  [OK] Successfully connected to {host}:{port}."))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"  [FAIL] Cannot connect to {host}:{port}: {exc}"))
            return

        # 3. SMTP handshake & Authentication check
        self.stdout.write("Step 2: Checking SMTP handshake and authentication...")
        try:
            if use_ssl:
                server = smtplib.SMTP_SSL(host, port, timeout=timeout)
            else:
                server = smtplib.SMTP(host, port, timeout=timeout)

            server.ehlo()
            if use_tls and not use_ssl:
                server.starttls()
                server.ehlo()

            if user and password:
                server.login(user, password)
                self.stdout.write(self.style.SUCCESS("  [OK] SMTP authentication successful."))
            elif not user or not password:
                self.stdout.write(self.style.WARNING("  [SKIP] EMAIL_HOST_USER or EMAIL_HOST_PASSWORD not set. Skipping authentication check."))

            server.quit()
        except smtplib.SMTPAuthenticationError as auth_err:
            self.stdout.write(self.style.ERROR(f"  [FAIL] SMTP Authentication failed: {auth_err.smtp_code} - {auth_err.smtp_error}"))
            self.stdout.write(self.style.NOTICE("  -> Tip for Gmail: Verify that 2-Step Verification is enabled and you are using a 16-character Gmail App Password (not your normal Google account password)."))
            return
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"  [FAIL] SMTP connection or TLS handshake failed: {exc}"))
            return

        # 4. Optional test message dispatch
        send_to = options.get('send_to', '').strip()
        if send_to:
            self.stdout.write(f"Step 3: Sending actual test message to '{send_to}'...")
            try:
                subject = "TECHPANDA CRM — SMTP Test Message"
                body = "This is a diagnostic test message sent from TECHPANDA CRM verifying Gmail SMTP delivery."
                html = "<p>This is a diagnostic test message sent from <strong>TECHPANDA CRM</strong> verifying Gmail SMTP delivery.</p>"

                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=body,
                    from_email=from_email or user,
                    to=[send_to]
                )
                msg.attach_alternative(html, "text/html")
                sent_count = msg.send(fail_silently=False)
                if sent_count > 0:
                    self.stdout.write(self.style.SUCCESS(f"  [OK] Test email successfully submitted to SMTP server for '{send_to}'."))
                else:
                    self.stdout.write(self.style.WARNING(f"  [WARNING] send() returned {sent_count}."))
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"  [FAIL] Failed sending test message: {exc}"))
        else:
            self.stdout.write("Step 3: Test email dispatch skipped (use --send-to your_email@domain.com to send a live test message).")

        self.stdout.write(self.style.SUCCESS("\nDiagnostic complete."))
