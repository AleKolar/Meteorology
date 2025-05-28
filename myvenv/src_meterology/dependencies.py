from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .core.security import get_password_hash
from .db.database import database
from .services.auth import UserService
from sqlalchemy.ext.asyncio import AsyncSession

def get_db() -> AsyncSession:
    # !!!! вызов асинхронной функции — это асинхронный генератор, так что нужно использовать Depends
    return database.get_db()

def get_auth_service(db: AsyncSession = Depends(get_db)): # !!!! ЗДЕСЬ
    return UserService(db)

def get_password_hasher():
    return get_password_hash