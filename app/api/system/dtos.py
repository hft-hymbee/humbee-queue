"""
System API DTOs
===============
Request/Response models for system-level endpoints (health, version, etc).
"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response for GET /health"""

    status: str
    service: str
    version: str
