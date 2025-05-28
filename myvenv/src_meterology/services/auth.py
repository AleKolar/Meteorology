from ..core.security import generate_verification_code, save_verification_code
from ..db.repository import UserRepository
from ..schemas.auth import UserCreate


class UserService:
    def __init__(self, db):
        self.repository = UserRepository(db)

    def register_user(self, user_data: UserCreate):
        """Регистрирует нового пользователя и отправляет код подтверждения"""
        # Проверка существования пользователя
        if self.repository.get_user_by_email(user_data.email):
            raise ValueError("Email already registered")

        # Генерация и сохранение кода
        verification_code = generate_verification_code()
        save_verification_code(user_data.email, verification_code)

        # Здесь должна быть отправка кода по email/SMS
        print(f"Код подтверждения для {user_data.email}: {verification_code}")

        return {"message": "Verification code sent", "email": user_data.email}