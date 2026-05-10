"""
System API Routes
=================
FastAPI endpoints for system-level monitoring (health, version, etc).
"""

from fastapi import APIRouter
from api.system.dtos import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint for monitoring liveness/readiness."""
    return HealthResponse(
        status="healthy",
        service="humbee-queue",
        version="1.0.0",
    )
