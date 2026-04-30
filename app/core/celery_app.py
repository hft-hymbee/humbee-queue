from celery import Celery
from celery.signals import setup_logging

from core.config import settings

@setup_logging.connect
def config_loggers(*args, **kwargs):
    from core.logging import setup_logging as custom_setup_logging
    custom_setup_logging()


celery_app = Celery(
    "notification_engine",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Reliability — ACK only after task completes, re-queue if worker dies
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,

    # Timeouts
    task_soft_time_limit=120,   # 2 min soft limit (raises SoftTimeLimitExceeded)
    task_time_limit=180,        # 3 min hard kill

    # Results
    result_expires=86400,       # 24 hours

    # Broker
    broker_connection_retry_on_startup=True,
    broker_transport_options={"visibility_timeout": 3600},

    # Queue routing
    task_routes={
        "notification.send_email": {"queue": "email_queue"},
        "notification.send_sms": {"queue": "sms_queue"},
        "notification.send_whatsapp": {"queue": "whatsapp_queue"},
        "notification.send_inapp": {"queue": "inapp_queue"},
    },

    # Timezone
    timezone="Asia/Kolkata",
    enable_utc=True,
)

# Auto-discover tasks from the tasks package
celery_app.autodiscover_tasks(["tasks"])
