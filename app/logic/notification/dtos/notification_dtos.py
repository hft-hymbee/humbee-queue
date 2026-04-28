from pydantic import BaseModel
from typing import Optional


class SendEmailNotificationDTO(BaseModel):
    recipient_email: str
    template_id: str
    subject: str
    payload: Optional[dict] = None
