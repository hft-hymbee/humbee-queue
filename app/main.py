from fastapi import FastAPI

from api.notification.routes import notification_router
from api.system.routes import router as health_router
from api.templates.sms.routes import router as sms_templates_router
from api.templates.whatsapp.routes import router as whatsapp_templates_router
from api.templates.email.routes import router as email_templates_router
from core.logging import get_logger

logger = get_logger("main")

app = FastAPI(
    title="HUMBEE Queue",
    description="HUMBEE Queue Service",
    version="1.0.0",
)

# Include routers
app.include_router(health_router)
app.include_router(notification_router)

app.include_router(sms_templates_router, prefix="/api/v1/templates")
app.include_router(whatsapp_templates_router, prefix="/api/v1/templates")
app.include_router(email_templates_router, prefix="/api/v1/templates")


logger.info("HUMBEE Queue started", extra={"application_mode": "starting"})