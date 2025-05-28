class Settings:
    DATABASE_URL = "sqlite:///./test.db"
    SECRET_KEY = "secret-key"
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    REDIS_URL = "redis://localhost:6379/0"
    APP_NAME = "FastAPI 2FA Auth"

settings = Settings()