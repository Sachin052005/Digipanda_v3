"""
Background Auto-Sync Engine for Facebook Lead Ads.
Periodically fetches leads from Meta Graph API for all active Facebook Pages
without blocking HTTP requests or requiring external broker dependencies.
"""

import logging
import threading
import time
from datetime import timedelta
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger("crm")

_worker_thread = None
_stop_event = threading.Event()
_scheduler_lock = threading.Lock()


def run_auto_sync_cycle():
    """
    Checks all connected Facebook Pages where auto_sync_enabled=True.
    If next_sync_at is null or due (<= now), executes sync_page_leads.
    """
    from fb_leads.models import FacebookPage
    from fb_leads.facebook import sync_page_leads

    now = timezone.now()
    # Query pages due for sync
    due_pages = FacebookPage.objects.filter(
        status='CONNECTED',
        auto_sync_enabled=True,
    )

    synced_any = False
    for page in due_pages:
        # Check if due: either never scheduled or next_sync_at <= now
        if page.next_sync_at and page.next_sync_at > now:
            continue

        interval_mins = page.sync_interval_minutes or 3
        next_due = now + timedelta(minutes=interval_mins)

        # Atomic reservation: advance next_sync_at immediately to prevent race conditions
        updated_rows = FacebookPage.objects.filter(
            id=page.id,
            status='CONNECTED',
            auto_sync_enabled=True,
        ).update(next_sync_at=next_due, last_sync_status="Syncing...")

        if not updated_rows:
            continue

        try:
            logger.info("Auto-syncing Facebook leads for page %s (interval: %sm)", page.page_name, interval_mins)
            new_leads = sync_page_leads(page.page_id)
            FacebookPage.objects.filter(id=page.id).update(
                last_sync_at=timezone.now(),
                next_sync_at=timezone.now() + timedelta(minutes=interval_mins),
                last_sync_status=f"Auto-synced {new_leads} new lead(s)",
                last_error=""
            )
            synced_any = True
        except Exception as exc:
            err_msg = str(exc)
            logger.warning("Auto-sync error for page %s: %s", page.page_name, err_msg)

            # Adaptive backoff for rate limits or auth errors
            err_lower = err_msg.lower()
            if "limit" in err_lower or "calls" in err_lower or "request limit" in err_lower:
                # Meta rate limit backoff: pause 5 minutes
                backoff_time = timezone.now() + timedelta(minutes=5)
                status_desc = "Rate limit backoff (retry in 5m)"
            elif "token" in err_lower or "session" in err_lower or "permissions" in err_lower:
                backoff_time = timezone.now() + timedelta(minutes=15)
                status_desc = "Auth Error (Check Token)"
            else:
                backoff_time = timezone.now() + timedelta(minutes=interval_mins)
                status_desc = f"Sync error: {err_msg[:45]}"

            FacebookPage.objects.filter(id=page.id).update(
                last_sync_at=timezone.now(),
                next_sync_at=backoff_time,
                last_sync_status=status_desc,
                last_error=err_msg[:255]
            )

    return synced_any


def _worker_loop():
    """Continuous background worker loop checking every 30 seconds."""
    logger.info("Facebook Leads Auto-Sync background worker started.")
    while not _stop_event.is_set():
        try:
            run_auto_sync_cycle()
        except Exception as e:
            logger.exception("Unexpected error in Facebook Auto-Sync loop: %s", e)

        # Sleep in short increments to allow graceful shutdown
        for _ in range(30):
            if _stop_event.is_set():
                break
            time.sleep(1)

    logger.info("Facebook Leads Auto-Sync background worker stopped.")


def ensure_scheduler_running():
    """
    Idempotent call to start the background auto-sync worker thread if not running.
    Safe to call on requests, views, or application readiness.
    """
    global _worker_thread, _stop_event
    with _scheduler_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return True

        _stop_event.clear()
        _worker_thread = threading.Thread(
            target=_worker_loop,
            daemon=True,
            name="FacebookAutoSyncWorker"
        )
        _worker_thread.start()
        return True


def stop_auto_sync_background_worker():
    """Gracefully signal the background worker to terminate."""
    global _stop_event, _worker_thread
    with _scheduler_lock:
        if _stop_event:
            _stop_event.set()
        if _worker_thread and _worker_thread.is_alive():
            _worker_thread.join(timeout=2)
            _worker_thread = None


def trigger_immediate_page_sync(page_id: str) -> int:
    """
    Manually triggers immediate synchronization for a FacebookPage,
    resetting its next_sync_at schedule timer.
    """
    from fb_leads.models import FacebookPage
    from fb_leads.facebook import sync_page_leads

    page = FacebookPage.objects.filter(page_id=page_id).first()
    if not page:
        raise ValueError(f"FacebookPage with page_id {page_id} not found.")

    new_count = sync_page_leads(page_id)
    interval_mins = page.sync_interval_minutes or 3
    next_due = timezone.now() + timedelta(minutes=interval_mins)

    FacebookPage.objects.filter(id=page.id).update(
        last_sync_at=timezone.now(),
        next_sync_at=next_due,
        last_sync_status=f"Synced {new_count} new lead(s)",
        last_error=""
    )
    return new_count
