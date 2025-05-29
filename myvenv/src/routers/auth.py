from typing import cast

from fastapi import APIRouter, HTTPException, status
from ..db.database import database
from ..core.redis import redis_client
from ..core.config import settings
from ..db.models.models import User
from ..schemas.auth import UserCreate, VerifyCode, UserLogin
from ..core.security import (
    generate_verification_code,
    send_verification_email,
    get_password_hash,
    create_access_token, verify_password
)
from ..db.repository import UserRepository
from sqlalchemy.exc import IntegrityError
import logging


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/register", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def register(user_data: UserCreate):
    """Регистрирует нового пользователя и отправляет код подтверждения"""
    try:
        async with database.get_session() as session:
            repo = UserRepository(session)

            # Проверяем существование пользователя
            existing_user = await repo.get_user_by_email(user_data.email)
            if existing_user:
                logger.warning(f"Registration attempt with existing email: {user_data.email}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email уже зарегистрирован"
                )

            # Генерируем 4-значный код подтверждения
            code = generate_verification_code()
            logger.info(f"Generated verification code for {user_data.email}: {code}")

            # Сохраняем код в Redis
            await redis_client.setex(
                key=f"reg_confirm:{user_data.email}",
                time=settings.CODE_EXPIRATION_SECONDS,
                value=code
            )

            # Сохраняем хеш пароля во временном хранилище
            password_hash = get_password_hash(user_data.password)
            await redis_client.setex(
                key=f"pwd_hash:{user_data.email}",
                time=settings.CODE_EXPIRATION_SECONDS,
                value=password_hash
            )

            # Отправляем email с кодом подтверждения
            email_sent = await send_verification_email(user_data.email, code)
            if not email_sent:
                logger.error(f"Failed to send verification email to {user_data.email}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Не удалось отправить код подтверждения"
                )

            return {
                "message": "Код подтверждения отправлен на ваш email",
                "email": user_data.email
            }

    except Exception as e:
        logger.error(f"Error in registration: {str(e)}")
        raise


@router.post("/verify", response_model=dict, status_code=status.HTTP_201_CREATED)
async def verify(verification: VerifyCode):
    """Подтверждает регистрацию пользователя по коду из email"""
    try:
        async with database.get_session() as session:
            repo = UserRepository(session)

            # Проверяем код подтверждения
            stored_code = await redis_client.get(f"reg_confirm:{verification.email}")
            if not stored_code or stored_code != verification.code:
                logger.warning(f"Invalid verification code for {verification.email}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Неверный код подтверждения"
                )

            # Получаем сохраненный хеш пароля
            password_hash = await redis_client.get(f"pwd_hash:{verification.email}")
            if not password_hash:
                logger.warning(f"Password hash expired for {verification.email}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Срок действия кода истек, начните регистрацию заново"
                )

            # Создаем пользователя в БД
            try:
                user = await repo.create_user({
                    "email": verification.email,
                    "hashed_password": password_hash
                })
                logger.info(f"User created: {verification.email}")

                # Удаляем временные данные из Redis
                await redis_client.client.delete(f"reg_confirm:{verification.email}")
                await redis_client.client.delete(f"pwd_hash:{verification.email}")

                # Генерируем JWT токен
                access_token = create_access_token(data={"sub": user.email})

                return {
                    "message": "Пользователь успешно зарегистрирован",
                    "user_id": user.id,
                    "email": user.email,
                    "access_token": access_token,
                    "token_type": "bearer"
                }

            except IntegrityError:
                logger.error(f"Integrity error for user {verification.email}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Пользователь с таким email уже существует"
                )

    except HTTPException:
        raise  # Перебрасываем уже обработанные HTTP исключения

    except Exception as e:
        logger.error(f"Error in verification: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при создании пользователя: {str(e)}"
        )


@router.post("/login/send_code")
async def send_login_code(user_login: UserLogin):
    try:
        async with database.get_session() as session:
            repo = UserRepository(session)
            user = await repo.get_user_by_email(user_login.email)
            if not user:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректный email или пароль")

            user = cast(User, user)

            if not verify_password(user_login.password, user.hashed_password):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректный email или пароль")

            # Генерируем 4-значный код
            code = generate_verification_code()
            logger.info(f"Login code for {user.email}: {code}")

            # Сохраняем код в Redis
            await redis_client.setex(
                key=f"login_code:{user.email}",
                time=settings.CODE_EXPIRATION_SECONDS,
                value=code
            )

            # Отправляем код через email
            email_sent = await send_verification_email(user.email, code)
            if not email_sent:
                logger.error(f"Failed to send login code to {user.email}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Не удалось отправить код подтверждения"
                )

            return {"message": "Код подтверждения отправлен на ваш email"}

    except Exception as e:
        logger.error(f"Error in send_login_code: {str(e)}")
        raise


@router.post("/login/verify_code")
async def verify_login_code(data: VerifyCode):
    try:
        async with database.get_session() as session:
            repo = UserRepository(session)
            user = await repo.get_user_by_email(data.email)
            if not user:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пользователь не найден")

            stored_code = await redis_client.get(f"login_code:{user.email}")
            if not stored_code or stored_code != data.code:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный код подтверждения")

            # Удаляем код из Redis
            await redis_client.client.delete(f"login_code:{user.email}")

            # Генерируем JWT токен
            access_token = create_access_token(data={"sub": user.email})

            return {
                "message": "Успешный вход",
                "user_id": user.id,
                "email": user.email,
                "access_token": access_token,
                "token_type": "bearer"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in verify_login_code: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при входе: {str(e)}"
        )