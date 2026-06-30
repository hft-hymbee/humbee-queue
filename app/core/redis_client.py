"""
Redis Client Singleton
=====================
Centralized Redis connection for caching and other operations.
"""

import redis
from core.config import settings
from core.logging import get_logger

logger = get_logger("core.redis")

class RedisClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisClient, cls).__new__(cls)
            cls._instance.client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=5,
            )
            try:
                # Test connection
                cls._instance.client.ping()
                logger.info("Connected to Redis successfully")
            except Exception as e:
                logger.warning(
                    f"Redis is not available at startup ({settings.REDIS_URL}). "
                    f"Will attempt lazy reconnection. Error: {e}"
                )
        return cls._instance

    @property
    def connection(self):
        return self.client

# Singleton instance
redis_client = RedisClient()
