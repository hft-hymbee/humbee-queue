from email import encoders
from base64 import decodebytes
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
from core import config
from notification_email.services.dtos.email_dtos import EmailDTO
from notification_email.services.helper import get_mime_type_from_filename


class EmailEngineBase:

    def __init__(self, email_dto: EmailDTO) -> None:
        self.email_dto = email_dto
        if config.test_email_id:
            print(f"Overriding recipient email with test email ID: {config.test_email_id}")
            self.email_dto.recipient = config.test_email_id
        self.smtp_server = self.__smtp_server()
        self.message = None

    def __smtp_server(self):
        try:
            self.server = smtplib.SMTP(config.smtp_server, config.smtp_port)
            self.server.set_debuglevel(1)
            self.server.ehlo()
            self.server.starttls()
            self.server.login(config.smtp_username, config.smtp_password)
            return self.server
        except Exception as e:
            print(f"Failed during spawning smtp server: {e}")

    def __message(self):
        self.message = MIMEMultipart()
        self.message["From"] = config.smtp_email
        self.message["To"] = self.email_dto.recipient
        self.message["Subject"] = self.email_dto.subject

        self.message.attach(MIMEText(self.email_dto.body, "html", "utf-8"))
        if self.email_dto.attachments:
            self.__process_attachment()
        return self.message.as_string()

    def __process_attachment(self):
        for idx in range(len(self.email_dto.filenames)):
            result = get_mime_type_from_filename(filename=self.email_dto.filenames[idx])
            if result is None:
                return None

            f, typ = result.split("/")
            file_mime = MIMEBase(f, typ)
            file_mime.set_payload(
                decodebytes(bytes(self.email_dto.attachments[idx], "utf-8"))
            )

            encoders.encode_base64(file_mime)
            file_mime.add_header(
                "Content-Disposition",
                "attachment",
                filename=self.email_dto.filenames[idx],
            )
            self.message.attach(file_mime)

    def send_mail(self):
        try:
            if self.smtp_server is None:
                self.smtp_server = self.__smtp_server()
            self.smtp_server.sendmail(config.smtp_email, self.email_dto.recipient, self.__message())
            self.smtp_server.quit()
            return True
        except Exception as e:
            print(f"Mail not sent to: {self.email_dto.recipient}, an error occurred: {e}")
            return False
