from api.notification.dtos.notification_dtos import SendNotificationDTO

from logic.pdf.pdf_manager import PDFManager
from logic.pdf.dtos.pdf_dtos import GeneratePDFDTO
from logic.notification.dtos.notification_dtos import SendEmailNotificationDTO

from core.celery_app import celery_app

PDF_GENERATION_NOTIFICATION_TYPES = ["email"]

class SendNotification:
    def __init__(self, dto: SendNotificationDTO):
        self.notification_type = dto.notification_type
        self.template_id = dto.template_id
        self.payload = dto.payload
        self.subject = dto.subject

        self.pdf_generation_required = True
    
    def execute(self):
        # Logic to send a notification based on the type, template, and payload
        print(f"Sending {self.notification_type} notification using template {self.template_id} with payload {self.payload}")
        # Validate the API key
        # Validate the notification type
        # Validate the template ID
        # Validate the payload
        # Decide whether pdf generation is needed based on the template
        self._decide_pdf_generation()
        # If pdf generation is needed, generate the pdf and include it in the notification
        self._generate_pdf()
        # Send the notification using the appropriate channel (email, sms, push notification, etc.)
        self._prepare_notification_worker_payload()
        if self.notification_type == "email":
            # Logic to send an email notification
            self._send_email_notification()
            pass
        elif self.notification_type == "sms":
            # Logic to send an SMS notification
            pass
        elif self.notification_type == "push":
            # Logic to send a push notification
            pass
        elif self.notification_type == "whatsapp":
            # Logic to send a WhatsApp notification
            pass
        else:
            return
    
    def _validate_api_key(self):
        # Logic to validate the API key
        pass

    def _validate_notification_type(self):
        # Logic to validate the notification type
        pass

    def _validate_template_id(self):
        # Logic to validate the template ID
        pass

    def _decide_pdf_generation(self):
        # Logic to decide whether pdf generation is needed based on the template
        if not self.notification_type in PDF_GENERATION_NOTIFICATION_TYPES:
            self.pdf_generation_required = False
            return

    def _validate_payload(self):
        # Logic to validate the payload
        pass

    def _generate_pdf(self):
        # Logic to generate a PDF based on the template and payload
        if not self.pdf_generation_required:
            return
        
        pdf_manager: PDFManager = PDFManager(
            dto=GeneratePDFDTO(
                template_id=self.template_id,
                content=self.payload
            )
        )
        pdf_manager.execute()
        self.attachments = pdf_manager.get_pdf_attachments()
    
    def _prepare_notification_worker_payload(self):
        # Logic to prepare the payload for the notification worker (e.g., email worker, sms worker, etc.)
        # Identify type of notification and prepare the payload accordingly
        """
            For SMS, the template_id would be module.operation.message_template_id
            For Push notification, the template_id would be module.operation.message_template_id
            For WhatsApp, the template_id would be module.operation.industry

        """
        module, operation, industry = self.template_id.split(".") # For Email template IDs in the format of module.operation.industry (e.g., order.create.erw_angles)

        if module == "order":
            order_details = self.payload.get("order_details", {})
            order_id = order_details.get("order_id", "")
            humbee_po_number = order_details.get("humbee_po_number", "")
            user_po_number = order_details.get("user_po_number", "")
            supplier_name = order_details.get("supplier_name", "")
            
            buyer_details = self.payload.get("buyer_details", {})
            buyer_name = buyer_details.get("buyer_name", "")
            delivery_details = self.payload.get("delivery_details", [])
            product_details = []
            for delivery in delivery_details:
                products_info = delivery.get("products_info", [])
                for product in products_info:
                    product_details.append({
                        "product_name": product.get("product_name", ""),
                        "quantity": product.get("quantity", 0),
                        "unit": product.get("unit", "")
                    })

            if operation == "create":
                if industry in ["erw_angles", "tmt", "fmcg"]:
                    self.subject = f"Dispatch Plan Created - {order_id}"
                else:
                    self.subject = f"Order Created - {order_id}"
                
                self.notification_payload = {
                    "humbee_po_number": humbee_po_number,
                    "user_po_number": user_po_number,
                    "buyer_name": buyer_name,
                    "supplier_name": supplier_name,
                    "product_details": product_details,
                    "attachments": [
                        {
                            "file_name": attachment.get("file_name"),
                            "base64": attachment.get("base64")
                        } for attachment in self.attachments
                    ]
                }
            else:
                self.subject = f"{operation.capitalize()} Notification for Order - {order_id}"
        elif module == "purchase_order":
            po_id = self.payload.get("po_details", {}).get("po_id", "")
            if operation == "create":
                self.subject = f"Purchase Order Created - {po_id}"
            else:
                self.subject = f"{operation.capitalize()} Notification for Purchase Order - {po_id}"
        else:
            self.subject = self.subject or "Notification"

    def _send_email_notification(self):
        # Logic to send an email notification
        send_email_dto = SendEmailNotificationDTO(
            recipient_email="felix.ferrao@20p95.com",
            template_id=self.template_id,
            subject=self.subject,
            payload=self.notification_payload
        )
        celery_app.send_task(
            "notification_email.send",
            args=[send_email_dto.dict()],
            queue="email_queue"
        )
    
    def _send_sms_notification(self):
        # Logic to send an SMS notification
        pass

    def _send_push_notification(self):
        # Logic to send a push notification
        pass

    def _send_whatsapp_notification(self):
        # Logic to send a WhatsApp notification
        pass
    