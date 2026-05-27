"""
Tasks Package
=============
Celery task definitions for all notification channels.
Import all task modules here for auto-discovery.
"""

from tasks.email_task import send_email_notification
from tasks.sms_task import send_sms_notification
from tasks.whatsapp_task import send_whatsapp_notification
from tasks.push_task import send_push_notification
