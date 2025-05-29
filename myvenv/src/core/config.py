import os
from enum import Enum
from pydantic import ValidationError
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

__all__ = ['Settings', 'settings']

load_dotenv()


class EnvironmentEnum(str, Enum):
    """Перечисление для возможных сред выполнения"""
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


class Settings(BaseSettings):
    # Определение среды выполнения
    ENV: EnvironmentEnum = EnvironmentEnum.PRODUCTION

    # Настройки для запросов для Погоды из ТЗ
    WEATHER_CACHE_EXPIRATION: int
    MAX_HISTORY_ITEMS: int

    # Настройки базы данных
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str

    # Настройки JWT аутентификации
    SECRET_KEY: str = os.environ.get("SECRET_KEY", default="secret-key")
    ALGORITHM: str = os.environ.get("ALGORITHM", default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", default=30))

    # Настройки Redis для двухфакторной аутентификации
    REDIS_URL: str = os.environ.get("REDIS_URL", default="redis://localhost:6379/0")
    CODE_EXPIRATION_SECONDS: int = int(os.environ.get("CODE_EXPIRATION_SECONDS", default=300))  # 5 минут

    # Настройки приложения
    APP_NAME: str = os.environ.get("APP_NAME", default="FastAPI Auth Service")

    # Настройки email для отправки кодов подтверждения
    EMAIL_HOST: str = os.environ.get("EMAIL_HOST", default="smtp.yandex.ru")
    EMAIL_PORT: int = int(os.environ.get("EMAIL_PORT", default=465))
    EMAIL_HOST_USER: str = os.environ.get("EMAIL_HOST_USER", default="gefest-173@yandex.ru")
    EMAIL_HOST_PASSWORD: str = os.environ.get("EMAIL_HOST_PASSWORD", default="lppxxgxpqpdqabzw")
    EMAIL_USE_SSL: bool = os.environ.get("EMAIL_USE_SSL", default=True)

    class Config:
        env_file = ".env"
        case_sensitive = True
        env_file_encoding = 'utf-8'  # Явное указание кодировки

    def get_db_url(self) -> str:
        """Формирует URL для подключения к PostgreSQL"""
        return (f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@"
                f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}")

    def get_redis_config(self) -> dict:
        """Возвращает конфигурацию для Redis"""
        return {
            "url": self.REDIS_URL,
            "encoding": "utf-8",
            "decode_responses": True
        }

    def get_email_config(self) -> dict:
        """Возвращает конфигурацию для отправки email"""
        return {
            "host": self.EMAIL_HOST,
            "port": self.EMAIL_PORT,
            "username": self.EMAIL_HOST_USER,
            "password": self.EMAIL_HOST_PASSWORD,
            "use_ssl": self.EMAIL_USE_SSL
        }

    @property
    def is_development(self) -> bool:
        """Проверяет, является ли среда разработческой"""
        return self.ENV == EnvironmentEnum.DEVELOPMENT

    @property
    def is_production(self) -> bool:
        """Проверяет, является ли среда production"""
        return self.ENV == EnvironmentEnum.PRODUCTION


try:
    settings = Settings()
except ValidationError as e:
    print(f"Ошибка валидации настроек: {e}")
    exit(1)