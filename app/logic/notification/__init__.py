from api.notification.dtos.notification_dtos import SendNotificationDTO


class NotificationManager:
    def __init__(self):
        # Initialize any necessary resources, e.g., database connections, message queues, etc.
        pass

    def send_notification(self, dto: SendNotificationDTO):
        # Logic to send a notification based on the type, template, and payload
        
        print(f"Sending {dto.notification_type} notification using template {dto.template_id} with payload {dto.payload}")
    
