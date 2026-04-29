from fastapi import FastAPI

from api.notification.routes import notification_router, health_router
from core.logging import get_logger

logger = get_logger("main")

app = FastAPI(
    title="Humbee Notification Engine",
    description="Async notification engine supporting multiple channels",
    version="1.0.0",
)

# Include routers
app.include_router(health_router)
app.include_router(notification_router)

logger.info("Notification Engine started", extra={"application_mode": "starting"})