import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from myvenv.src.db.models.models import User

# Инициализация логгера внутри модуля
logger = logging.getLogger(__name__)

class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_user(self, user_data: dict) -> User:
        """Создает нового пользователя в базе данных"""
        try:
            user = User(**user_data)
            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)
            logger.info(f"User created in DB with ID: {user.id}")
            return user
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}", exc_info=True)
            await self.session.rollback()
            raise

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Находит пользователя по email"""
        try:
            result = await self.session.execute(
                select(User).where(User.email == email)
            )
            user = result.scalars().first()
            logger.debug(f"User lookup by email {email}: {user is not None}")
            return user
        except Exception as e:
            logger.error(f"Error finding user by email: {str(e)}", exc_info=True)
            raise