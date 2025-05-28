import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from passlib.context import CryptContext
import jwt
from datetime import datetime, timedelta
import random
from .config import settings
import aiosmtplib

from .redis import redis_client

# Инициализация компонентов безопасности
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

logger = logging.getLogger(__name__)


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

async def save_verification_code(email: str, code: str):
    expiration_seconds = settings.CODE_EXPIRATION_SECONDS
    await redis_client.setex(email, expiration_seconds, code)

async def get_verification_code(email: str):
    return await redis_client.get(email)

async def delete_verification_code(email: str):
    await redis_client.client.delete(email)


# Отправляет email с кодом подтверждения
async def send_verification_email(email: str, code: str) -> bool:
    """Асинхронно отправляет email с кодом подтверждения"""
    if not all([
        settings.EMAIL_HOST,
        settings.EMAIL_PORT,
        settings.EMAIL_HOST_USER,
        settings.EMAIL_HOST_PASSWORD
    ]):
        logger.error("Email settings are incomplete. Cannot send verification email.")
        return False

    try:
        # Создание сообщения
        message = MIMEMultipart("alternative")
        message["From"] = settings.EMAIL_HOST_USER
        message["To"] = email
        message["Subject"] = "Код подтверждения для регистрации"

        expiration_minutes = settings.CODE_EXPIRATION_SECONDS // 60

        text = f"""  
        Добрый день!  
        Ваш код подтверждения для регистрации: {code}  
        Код действителен в течение {expiration_minutes} минут.  
        С уважением,  
        Команда {settings.APP_NAME}  
        """

        html = f"""  
        <html>  
          <body style="font-family: Arial, sans-serif; line-height: 1.6;">  
            <div style="max-width: 600px; margin: 20px auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 5px;">  
              <p>Добрый день!</p>  
              <p>Ваш код подтверждения: <strong style="font-size: 18px;">{code}</strong></p>  
              <p>Код действителен {expiration_minutes} минут.</p>  
              <p>С уважением,<br>Команда <strong>{settings.APP_NAME}</strong></p>  
            </div>  
          </body>  
        </html>  
        """

        message.attach(MIMEText(text, "plain", "utf-8"))
        message.attach(MIMEText(html, "html", "utf-8"))

        # Упрощенное создание SMTP-клиента
        smtp = aiosmtplib.SMTP(
            hostname=settings.EMAIL_HOST,
            port=settings.EMAIL_PORT,
            use_tls=settings.EMAIL_USE_SSL
        )

        await smtp.connect()
        if not settings.EMAIL_USE_SSL:
            await smtp.starttls()  # Явный STARTTLS

        await smtp.login(
            settings.EMAIL_HOST_USER,
            settings.EMAIL_HOST_PASSWORD
        )
        await smtp.send_message(message)
        await smtp.quit()
        return True

    except Exception as e:
        logger.error(f"Ошибка отправки email: {str(e)}", exc_info=True)
        return False
