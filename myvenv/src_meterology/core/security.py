from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
import random
import redis
from .config import settings

# Инициализация компонентов безопасности
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
r = redis.Redis.from_url(settings.REDIS_URL) if settings.REDIS_URL else None

# Проверяет соответствие пароля и его хеша
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# Генерирует хеш пароля
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# Создает JWT токен
def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    expire = datetime.now() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

# Генерирует 4-значный код подтверждения
def generate_verification_code() -> str:
    return str(random.randint(1000, 9999))

# Сохраняет код подтверждения в Redis
def save_verification_code(email: str, code: str):
    if not r:
        raise RuntimeError("Redis connection not initialized")
    r.setex(f"verification:{email}", settings.CODE_EXPIRATION_SECONDS, code)

# Проверяет код подтверждения
def verify_code(email: str, code: str) -> bool:
    if not r:
        raise RuntimeError("Redis connection not initialized")
    stored_code = r.get(f"verification:{email}")
    return stored_code and stored_code.decode() == code