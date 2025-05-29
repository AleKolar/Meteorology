from contextlib import asynccontextmanager
from fastapi import FastAPI
import logging
import asyncio
from sqlalchemy import text

from myvenv.src.core.config import settings
from myvenv.src.core.redis import redis_client
from myvenv.src.db.database import database
from myvenv.src.routers import auth
from myvenv.meteorology.routers import router as weather_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting application initialization...")

    try:
        # Подключение и миграция БД
        logger.info("🔌 Connecting to database and creating tables...")
        await database.connect()

        # Проверка подключения с использованием text()
        async with database.get_session() as session:
            await session.execute(text("SELECT 1"))  # Исправлено здесь
            logger.info("✅ Database connection verified")

        # Redis
        logger.info("🔗 Connecting to Redis...")
        await redis_client.initialize(settings.REDIS_URL)
        app.state.redis = redis_client

        logger.info("✅ All services initialized")
        yield

    except Exception as e:
        logger.critical(f"❌ Initialization failed: {e}")
        await asyncio.sleep(5)
        raise

    finally:
        logger.info("🛑 Shutting down...")
        cleanup_tasks = [
            ("Database", database.disconnect() if database.is_connected else None),
            ("Redis", redis_client.close() if redis_client.is_initialized else None)
        ]

        for service, task in cleanup_tasks:
            if task:
                try:
                    await task
                    logger.info(f"🔌 {service} disconnected")
                except Exception as e:
                    logger.error(f"❌ Error disconnecting {service}: {e}")


app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
    docs_url="/docs"
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(weather_router, prefix="/weather", tags=["weather"])

# if __name__ == "__main__":
#     import uvicorn
#
#     uvicorn.run(
#         app,
#         host="0.0.0.0",
#         port=8000,
#         reload=settings.is_development
#     )
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        reload=settings.is_development
    )