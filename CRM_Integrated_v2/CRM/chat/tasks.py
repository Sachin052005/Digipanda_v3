"""
Celery / Asynchronous Background Worker Tasks for WhatsApp Campaigns.
Supports both Celery task execution (when Celery/Redis are configured)
and safe fallback to asynchronous Python daemon threads in single-process environments.
"""

import threading
import logging
from chat.campaign_service import run_campaign_worker_loop

logger = logging.getLogger(__name__)


def trigger_campaign_execution_async(campaign_id: int):
    """
    Kicks off campaign execution in the background without blocking the Django HTTP request.
    If Celery is installed and configured, queues to Celery. Otherwise runs in a daemon thread.
    """
    try:
        # Check if celery app is available
        from celery import current_app
        if current_app.conf.broker_url:
            execute_campaign_task.delay(campaign_id)
            return "celery"
    except Exception:
        pass

    # Threaded fallback for immediate zero-dependency background execution
    t = threading.Thread(
        target=run_campaign_worker_loop,
        args=(campaign_id,),
        daemon=True,
        name=f"WhatsAppCampaignWorker-{campaign_id}"
    )
    t.start()
    return "thread"


# Optional Celery Task decorator definition
try:
    from celery import shared_task

    @shared_task(bind=True, max_retries=3, default_retry_delay=60)
    def execute_campaign_task(self, campaign_id: int):
        logger.info(f"Celery task processing WhatsApp campaign #{campaign_id}")
        run_campaign_worker_loop(campaign_id)
except ImportError:
    pass
