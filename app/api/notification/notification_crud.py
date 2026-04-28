from fastapi.routing import APIRouter
from starlette.requests import Request

from api.notification.dtos.notification_dtos import SendNotificationDTO

from logic.notification.notification_manager import NotificationManager

notification_router = APIRouter(prefix="/notification", tags=["notification"])

@notification_router.post("/")
def send_notification(
    request: Request,
    dto: SendNotificationDTO
):
    # Your logic to send notification goes here
    notification_manager = NotificationManager()
    notification_manager.send_notification(notification_dto=dto)
    return {"message": "Notification sent successfully"}