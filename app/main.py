from fastapi import FastAPI

from api.notification.notification_crud import notification_router

app = FastAPI()

app.include_router(notification_router)