from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from myvenv.src_meterology.core.config import settings
from myvenv.src_meterology.db.models import Base


class Database:
    def __init__(self):
        self.engine = None
        self.session_factory = None
        self._is_connected = False

    async def connect(self):
        """Устанавливает подключение к базе данных и создает таблицы"""
        if self._is_connected:
            return

        # Создаем асинхронный движок
        self.engine = create_async_engine(
            settings.get_db_url(),
            echo=False,
            pool_size=10,
            max_overflow=20
        )

        # Создаем фабрику сессий
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # Создаем таблицы в базе данных
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        self._is_connected = True
        print("Database connected and tables created")

    async def disconnect(self):
        """Закрывает подключение к базе данных"""
        if self.engine:
            await self.engine.dispose()
        self._is_connected = False
        print("Database disconnected")

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    def get_session(self) -> AsyncSession:
        """Возвращает новую сессию для работы с БД"""
        if not self._is_connected:
            raise RuntimeError("Database is not connected")
        return self.session_factory()

    async def get_db(self):
        """Генератор для получения сессии (для использования в зависимостях)"""
        async with self.session_factory() as session:
            try:
                yield session
            finally:
                await session.close()

database = Database()