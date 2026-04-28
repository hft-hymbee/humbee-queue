from core.celery_app import celery_app

from notification_email.services.email_notification_manager import EmailNotificationManager
from notification_email.services.dtos.email_dtos import SendEmailNotificationDTO

@celery_app.task(
    name="notification_email.send",
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3}
)
def send_email(self, dto_dict: dict):
    dto = SendEmailNotificationDTO(**dto_dict)
    print("Sending order email with DTO:", dto)
    service = EmailNotificationManager(dto)
    return service.execute()