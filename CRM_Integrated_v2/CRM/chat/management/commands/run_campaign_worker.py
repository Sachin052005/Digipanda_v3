"""
Django management command to run the Bulk WhatsApp Campaign background worker.
Can execute a single campaign, a single batch, or continuously poll for running/scheduled campaigns.
Usage:
    python manage.py run_campaign_worker [--campaign-id 1] [--poll] [--batch-size 50]
"""

import time
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from chat.models import WhatsAppCampaign
from chat.campaign_service import dispatch_campaign_batch

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Processes pending and active Bulk WhatsApp Campaigns"

    def add_arguments(self, parser):
        parser.add_argument(
            '--campaign-id',
            type=int,
            default=None,
            help="Specific campaign ID to process",
        )
        parser.add_argument(
            '--poll',
            action='store_true',
            help="Continuously poll for active or scheduled campaigns",
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help="Batch size per dispatch cycle (default: 50)",
        )

    def handle(self, *args, **options):
        campaign_id = options.get('campaign_id')
        poll = options.get('poll')
        batch_size = options.get('batch_size')

        self.stdout.write(self.style.SUCCESS("Starting TECHPANDA Bulk WhatsApp Campaign Worker..."))

        if campaign_id:
            self.process_single_campaign(campaign_id, batch_size)
        elif poll:
            self.poll_loop(batch_size)
        else:
            self.process_all_active_campaigns(batch_size)

    def process_single_campaign(self, campaign_id: int, batch_size: int):
        campaign = WhatsAppCampaign.objects.filter(id=campaign_id).first()
        if not campaign:
            self.stdout.write(self.style.ERROR(f"Campaign #{campaign_id} not found."))
            return

        self.stdout.write(f"Processing Campaign #{campaign.id}: '{campaign.name}'...")
        while True:
            campaign.refresh_from_db()
            if campaign.status in [WhatsAppCampaign.STATUS_PAUSED, WhatsAppCampaign.STATUS_CANCELLED, WhatsAppCampaign.STATUS_COMPLETED]:
                self.stdout.write(self.style.NOTICE(f"Campaign #{campaign.id} stopped with status: {campaign.status}"))
                break

            processed, remaining = dispatch_campaign_batch(campaign.id, batch_size=batch_size)
            self.stdout.write(f"Batch dispatched: {processed} sent, {remaining} remaining.")
            if remaining == 0 or processed == 0:
                self.stdout.write(self.style.SUCCESS(f"Campaign #{campaign.id} complete!"))
                break

            # Rate limit pacing
            rpm = max(1, campaign.rate_limit_per_minute or 60)
            sleep_time = (processed / rpm) * 60.0
            time.sleep(min(sleep_time, 5.0))

    def process_all_active_campaigns(self, batch_size: int):
        active_campaigns = WhatsAppCampaign.objects.filter(
            status__in=[WhatsAppCampaign.STATUS_RUNNING, WhatsAppCampaign.STATUS_SCHEDULED]
        )
        if not active_campaigns.exists():
            self.stdout.write("No active or scheduled campaigns pending.")
            return

        for camp in active_campaigns:
            if camp.status == WhatsAppCampaign.STATUS_SCHEDULED and camp.scheduled_at and camp.scheduled_at > timezone.now():
                continue
            self.process_single_campaign(camp.id, batch_size)

    def poll_loop(self, batch_size: int):
        self.stdout.write("Polling mode active. Press Ctrl+C to terminate.")
        try:
            while True:
                self.process_all_active_campaigns(batch_size)
                time.sleep(5)
        except KeyboardInterrupt:
            self.stdout.write(self.style.NOTICE("Worker interrupted by user. Exiting safely."))
