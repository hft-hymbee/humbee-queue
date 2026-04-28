from pydantic import BaseModel
from typing import Optional, List


class SendEmailNotificationDTO(BaseModel):
    recipient_email: str
    template_id: str
    subject: str
    payload: Optional[dict] = None


class EmailDTO(BaseModel):
    recipient: str
    body: str
    subject: str
    sender: Optional[str] = None
    attachments: Optional[List[str]]
    filenames: Optional[List[str]]
