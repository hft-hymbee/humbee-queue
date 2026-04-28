from string import Template

from notification_email.services.dtos.email_dtos import SendEmailNotificationDTO, EmailDTO
from notification_email.services.email_engine import EmailEngineBase


class EmailNotificationManager:
    def __init__(self, dto: SendEmailNotificationDTO):
        self.recipient_email = dto.recipient_email
        self.template_id = dto.template_id
        self.subject = dto.subject
        self.payload = dto.payload
        """
        payload: {
            "humbee_po_number": "12345",
            "user_po_number": "54321",
            "buyer_name": "John Doe",
            "product_details": [
                {
                    "product_name": "Product 1",
                    "quantity": 10,
                    "unit": "MT"
                }
            ],
            "attachments": [
                {
                    "file_name": "attachment1.pdf",
                    "base64": "f3rsdsd"
                }
            ]
        }
        """

        self.TEMPLATE_TO_MAIL_HTML_MAPPING = {
            "order.create.erw_angles": "notification_email/email_templates/dispatch_plan_created.html",
            "order.create.tmt": "notification_email/email_templates/dispatch_plan_created.html",
            "order.create.fmcg": "notification_email/email_templates/dispatch_plan_created_without_order_booking.html",
            "purchase_order.create": "notification_email/email_templates/po_created_mail.html",
            # Add more template mappings as needed
        }
    
    def execute(self):
        print("Executing EmailNotificationManager with DTO")
        self._validate_template_id()
        self._get_template_path()
        self._render_email_content()
        self._send_email()

    def _validate_template_id(self):
        print(f"Validating template ID: {self.template_id}")
        if self.template_id not in self.TEMPLATE_TO_MAIL_HTML_MAPPING:
            raise ValueError(f"Invalid template ID: {self.template_id}")
    
    def _get_template_path(self):
        print(f"Getting template path for template ID: {self.template_id}")
        self.template_path = self.TEMPLATE_TO_MAIL_HTML_MAPPING.get(self.template_id)
        if not self.template_path:
            raise ValueError(f"No template path found for template ID: {self.template_id}")
    
    def _render_email_content(self):
        # Here you would implement the logic to render the email content using the template and payload
        # For example, you could use Jinja2 to render the template with the payload
        print("Rendering email content using template and payload")
        table_data = self.__prepare_table_data()
        # Render the template with the table_data and other payload data
        with open(self.template_path, 'r') as f:
            file_content = f.read()

        mail_template = Template(file_content)
        order_booking_id = self.payload.get("humbee_po_number")
        supplier_name = self.payload.get("supplier_name")
        user_po_number = self.payload.get("user_po_number", "")
        buyer_name = self.payload.get("buyer_name")
        if order_booking_id is not None:
            DISPATCH_PLAN_BODY = mail_template.substitute(
                cement_co_name=supplier_name,
                order_booking_id= order_booking_id,
                user_po_id=user_po_number,
                buyer_company_name=buyer_name,
                dispatch_plan_table=table_data
            )
        else:
            DISPATCH_PLAN_BODY = mail_template.substitute(
                cement_co_name=supplier_name,
                buyer_company_name=buyer_name,
                dispatch_plan_table=table_data
            )
        
        print(f"Rendered email content: {DISPATCH_PLAN_BODY}")
        self.email_content = DISPATCH_PLAN_BODY

    def _send_email(self):
        # Here you would implement the logic to send the email using your preferred email service
        # For example, you could use SMTP or an email-sending service like SendGrid
        print(f"Sending email to: {self.recipient_email}")
        print(f"Email content: {self.email_content}")
        attachments = self.payload.get("attachments", [])
        base64_attachments = [attachment.get("base64") for attachment in attachments]
        filenames = [attachment.get("file_name") for attachment in attachments]
        email_dto = EmailDTO(
            recipient=self.recipient_email,
            body=self.email_content,
            subject=self.subject,
            attachments=base64_attachments,
            filenames=filenames
        )
        print(f"Constructed EmailDTO: {email_dto}")
        result = EmailEngineBase(email_dto).send_mail()
        print("Email sent successfully")

    def __prepare_table_data(self):
        print("Preparing table data for email content")
        table_row_data = []
        product_details = self.payload.get("product_details", [])
        for product_detail in product_details:
            product_name = product_detail.get("product_name", "")
            quantity = product_detail.get("quantity", 0)
            unit = product_detail.get("unit", "")
            table_dispatch_data = '<td style="border: 1px solid black; border-collapse: collapse; padding: 10px;">{} {}</td>'
            table_product_data = '<td style="border: 1px solid black; border-collapse: collapse; padding: 10px;">{}</td>'
            table_data = table_product_data.format(product_name) + table_dispatch_data.format(
                quantity, unit)
            table_data = "<tr>" + table_data + "</tr>"
            table_row_data.append(table_data)

        table_data = ''.join(table_row_data)
        print(f"Prepared table data: {table_data}")
        return table_data
