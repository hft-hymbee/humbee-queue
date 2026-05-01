from fastapi import FastAPI

from api.notification.routes import notification_router
from api.system.routes import router as health_router
from api.templates.sms.routes import router as sms_templates_router
from core.logging import get_logger

logger = get_logger("main")

app = FastAPI(
    title="HUMBEE Notification Engine",
    description="Async notification engine supporting multiple channels",
    version="1.0.0",
)

# Include routers
app.include_router(health_router)
app.include_router(notification_router)

app.include_router(sms_templates_router, prefix="/api/v1/templates")

logger.info("Notification Engine started", extra={"application_mode": "starting"})