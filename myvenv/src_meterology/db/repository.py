from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .models import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_by_email(self, email: str) -> User | None:
        """Асинхронно ищет пользователя по email"""
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalars().first()

    async def create_user(self, user_data: dict) -> User:
        """Асинхронно создает нового пользователя"""
        # Создаем объект пользователя
        user = User(
            email=user_data['email'],
            hashed_password=user_data['hashed_password'],
            is_active=True
        )

        # Добавляем в сессию и сохраняем
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)

        return user
