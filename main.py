from contextlib import asynccontextmanager
from fastapi import FastAPI
from myvenv.src_meterology.core.config import settings
from myvenv.src_meterology.routers import auth
from myvenv.src_meterology.db.database import database
from myvenv.src_meterology.core.redis import redis_client
import logging
import asyncio

# Настройка логгера
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    logger.info("🚀 Starting application initialization...")

    try:
        # Подключение к базе данных
        logger.info("🔌 Connecting to database...")
        await database.connect()

        # Инициализация Redis
        logger.info("🔗 Connecting to Redis...")
        await redis_client.initialize(settings.REDIS_URL)
        app.state.redis = redis_client

        logger.info("✅ Application initialization completed successfully")
        yield

    except Exception as e:
        logger.error(f"❌ Application initialization failed: {e}")
        # Принудительная задержка для диагностики
        await asyncio.sleep(5)
        raise

    finally:
        logger.info("🛑 Shutting down application...")

        # Закрытие подключений с обработкой ошибок
        if database.is_connected:
            try:
                logger.info("🔌 Disconnecting from database...")
                await database.disconnect()
            except Exception as e:
                logger.error(f"❌ Error disconnecting database: {e}")

        if redis_client.is_initialized:
            try:
                logger.info("🔗 Closing Redis connection...")
                await redis_client.close()
            except Exception as e:
                logger.error(f"❌ Error closing Redis: {e}")

        logger.info("👋 Application shutdown completed")


app = FastAPI(
    title=settings.APP_NAME,
    description="Сервис аутентификации с двухфакторной верификацией",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Подключение роутеров
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_config=None,
        access_log=True,
        reload=settings.is_development
    )
    # server = uvicorn.Server(config)
    # loop.run_until_complete(server.serve())