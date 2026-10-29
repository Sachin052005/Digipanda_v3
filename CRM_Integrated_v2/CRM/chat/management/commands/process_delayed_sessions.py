"""
Durable Delayed Execution Worker for WhatsApp Automation Sessions.

Polls for sessions in STATUS_PAUSED whose resume_at timestamp has arrived.
Uses database row locking (select_for_update with skip_locked where supported)
to guarantee safe, idempotent resume across multiple worker processes and server restarts.
Enforces Meta's 24-hour customer service window prior to sending freeform messages.
"""

from datetime import timedelta
import logging
import time
from typing import Optional

from django.core.management.base import BaseCommand
from django.db import connection, transaction, NotSupportedError
from django.utils import timezone

from chat.models import Conversation, Message, UserFlowSession, AutomationExecution

logger = logging.getLogger('chat.automation.scheduler')


class Command(BaseCommand):
    help = "Processes paused automation sessions whose scheduled resume time has arrived."

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=0,
            help="Continuous worker polling interval in seconds. 0 = single pass (default: 0).",
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help="Maximum sessions to resume per batch (default: 50).",
        )
        parser.add_argument(
            '--session-id',
            type=int,
            default=None,
            help="Resume a specific paused session immediately (used for testing or manual resume).",
        )

    def handle(self, *args, **options):
        interval = options.get('interval') or 0
        batch_size = options.get('batch_size') or 50
        session_id = options.get('session_id')

        self.stdout.write(self.style.SUCCESS(
            f"Starting DigiPanda Durable Delay Worker (interval={interval}s, batch_size={batch_size})..."
        ))

        if session_id:
            res = self.process_single_session(session_id)
            self.stdout.write(f"Processed single session {session_id}: {res}")
            return

        if interval > 0:
            try:
                while True:
                    count = self.process_batch(batch_size)
                    if count > 0:
                        self.stdout.write(f"Resumed {count} delayed session(s).")
                    time.sleep(interval)
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("Worker stopped by user."))
        else:
            count = self.process_batch(batch_size)
            self.stdout.write(self.style.SUCCESS(f"Completed single pass. Resumed {count} session(s)."))

    def _fetch_candidate_session_ids(self, limit: int) -> list:
        """
        Fetches IDs of paused sessions ready to wake up.
        Uses select_for_update(skip_locked=True) when database backend supports it.
        """
        now = timezone.now()
        qs = UserFlowSession.objects.filter(
            status=UserFlowSession.STATUS_PAUSED,
            resume_at__isnull=False,
            resume_at__lte=now,
        ).order_by('resume_at')

        try:
            with transaction.atomic():
                # Attempt skip_locked (MySQL 8+ / Postgres)
                return list(qs.select_for_update(skip_locked=True).values_list('id', flat=True)[:limit])
        except (NotSupportedError, Exception):
            # Fallback for SQLite in local test suites
            return list(qs.values_list('id', flat=True)[:limit])

    def process_batch(self, batch_size: int) -> int:
        session_ids = self._fetch_candidate_session_ids(batch_size)
        if not session_ids:
            return 0

        resumed_count = 0
        for s_id in session_ids:
            if self.process_single_session(s_id):
                resumed_count += 1

        return resumed_count

    def process_single_session(self, session_id: int) -> bool:
        """
        Processes a single paused session atomically with row-locking.
        Checks 24h customer messaging window before executing downstream nodes.
        """
        from chat.automation.engine import AutomationEngine

        with transaction.atomic():
            try:
                session = UserFlowSession.objects.select_for_update().select_related(
                    'conversation', 'flow', 'flow_version_ref'
                ).get(id=session_id)
            except UserFlowSession.DoesNotExist:
                return False

            if session.status != UserFlowSession.STATUS_PAUSED:
                return False

            if session.resume_at and session.resume_at > timezone.now():
                # Not yet due
                return False

            conversation = session.conversation
            target_node_id = session.resume_node_id or session.paused_node_id

            if not target_node_id:
                logger.warning(f"Session {session.id} has no resume_node_id or paused_node_id. Completing session.")
                session.status = UserFlowSession.STATUS_COMPLETED
                session.completed_at = timezone.now()
                session.save(update_fields=['status', 'completed_at', 'updated_at'])
                return False

            # Check Meta 24-hour customer service window
            is_window_open, window_msg = self.check_24h_window(conversation, session)
            if not is_window_open:
                logger.warning(
                    f"Session {session.id} delay wake-up halted: 24h messaging window expired ({window_msg}). "
                    f"Handing over to counselor."
                )
                session.status = UserFlowSession.STATUS_HANDED_OVER
                session.handed_over_at = timezone.now()
                session.save(update_fields=['status', 'handed_over_at', 'updated_at'])
                AutomationEngine.log_execution(
                    session=session,
                    flow=session.flow,
                    node_id=session.paused_node_id or "delay",
                    event_type="DELAY_WINDOW_EXPIRED",
                    error=f"Customer 24h messaging window expired: {window_msg}"
                )
                return False

            # Resume session state
            session.status = UserFlowSession.STATUS_ACTIVE
            session.resume_at = None
            paused_node = session.paused_node_id
            session.paused_node_id = ""
            session.resume_node_id = ""
            session.save(update_fields=['status', 'resume_at', 'paused_node_id', 'resume_node_id', 'updated_at'])

            AutomationEngine.log_execution(
                session=session,
                flow=session.flow,
                node_id=paused_node or target_node_id,
                event_type="DELAY_RESUMED",
                output_data={"target_node_id": target_node_id}
            )

        # Execute downstream node outside the row lock of fetch
        try:
            return AutomationEngine.execute_node(conversation, session, target_node_id)
        except Exception as exc:
            logger.error(f"Error resuming delayed session {session.id} at node '{target_node_id}': {exc}", exc_info=True)
            self._handle_delay_failure(session, target_node_id, str(exc))
            return False

    def check_24h_window(self, conversation: Conversation, session: UserFlowSession) -> tuple[bool, str]:
        """
        Determines whether the WhatsApp 24-hour customer care window is open.
        Under Meta policies, businesses may only send freeform messages within
        24 hours of the customer's last inbound message.
        """
        last_customer_msg = Message.objects.filter(
            conversation=conversation,
            sender=Message.SENDER_CUSTOMER
        ).order_by('-timestamp').first()

        last_activity = last_customer_msg.timestamp if last_customer_msg else (
            conversation.last_message_time or session.started_at
        )

        if not last_activity:
            return True, "No timestamp recorded; proceeding"

        elapsed_seconds = (timezone.now() - last_activity).total_seconds()
        if elapsed_seconds > (24 * 3600):
            return False, f"Elapsed time {elapsed_seconds / 3600:.1f}h exceeds 24 hours"

        return True, f"Elapsed time {elapsed_seconds / 3600:.1f}h within 24-hour window"

    def _handle_delay_failure(self, session: UserFlowSession, target_node_id: str, error_message: str):
        """Exponential retry on transient failure up to 3 attempts."""
        from chat.automation.engine import AutomationEngine

        retries = int(session.collected_data.get('__delay_retries', 0)) + 1
        session.collected_data['__delay_retries'] = retries

        if retries <= 3:
            backoff_seconds = (2 ** retries) * 60  # 2m, 4m, 8m
            session.status = UserFlowSession.STATUS_PAUSED
            session.resume_at = timezone.now() + timedelta(seconds=backoff_seconds)
            session.resume_node_id = target_node_id
            session.save(update_fields=['collected_data', 'status', 'resume_at', 'resume_node_id', 'updated_at'])

            AutomationEngine.log_execution(
                session=session,
                flow=session.flow,
                node_id=target_node_id,
                event_type="DELAY_RETRY_SCHEDULED",
                output_data={"attempt": retries, "retry_in_seconds": backoff_seconds},
                error=error_message
            )
        else:
            session.status = UserFlowSession.STATUS_FAILED
            session.completed_at = timezone.now()
            session.save(update_fields=['collected_data', 'status', 'completed_at', 'updated_at'])

            AutomationEngine.log_execution(
                session=session,
                flow=session.flow,
                node_id=target_node_id,
                event_type="DELAY_FAILED_MAX_RETRIES",
                error=f"Exceeded max retries (3): {error_message}"
            )
