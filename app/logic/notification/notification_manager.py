
from api.notification.dtos.notification_dtos import SendNotificationDTO

from logic.notification.send_notification import SendNotification


class NotificationManager:
    def __init__(self):
        pass

    def send_notification(self, notification_dto: SendNotificationDTO):
        # Logic to send notification based on the DTO
        print("Sending notification with DTO:", notification_dto)
        send_notification = SendNotification(dto=notification_dto)
        send_notification.execute()
    