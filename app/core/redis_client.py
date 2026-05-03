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
            try:
                cls._instance.client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_timeout=5,
                )
                # Test connection
                cls._instance.client.ping()
                logger.info("Connected to Redis successfully")
            except Exception as e:
                logger.error(f"Failed to connect to Redis at {settings.REDIS_URL}: {e}")
                cls._instance.client = None
        return cls._instance

    @property
    def connection(self):
        return self.client

# Singleton instance
redis_client = RedisClient()
