from pydantic import BaseModel
from typing import Optional


class SendNotificationDTO(BaseModel):
    notification_type: str
    template_id: str
    receipient: str # Can be email, phone number, or any identifier based on the notification type
    subject: Optional[str] = None
    payload: dict
