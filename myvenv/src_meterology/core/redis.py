import redis.asyncio as redis
import logging

logger = logging.getLogger(__name__)


class RedisClient:
    def __init__(self):
        self.client = None
        self._is_initialized = False

    async def initialize(self, url: str):
        """Инициализирует подключение к Redis"""
        if self._is_initialized:
            return

        try:
            self.client = redis.from_url(
                url,
                encoding="utf-8",
                decode_responses=True
            )
            # Проверяем подключение
            await self.client.ping()
            self._is_initialized = True
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            raise

    async def close(self):
        """Закрывает подключение к Redis"""
        if self.client:
            await self.client.close()
        self._is_initialized = False

    @property
    def is_initialized(self) -> bool:
        return self._is_initialized

    async def setex(self, key: str, time: int, value: str):
        """Сохраняет значение с истекающим сроком"""
        if not self._is_initialized:
            raise RuntimeError("Redis is not initialized")
        return await self.client.setex(key, time, value)

    async def get(self, key: str):
        """Получает значение по ключу"""
        if not self._is_initialized:
            raise RuntimeError("Redis is not initialized")
        return await self.client.get(key)


redis_client = RedisClient()