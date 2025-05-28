from fastapi import Depends
from sqlalchemy.orm import Session
from .core.security import verify_code, get_password_hash
from .db.database import get_db
from .services.auth import UserService

def get_auth_service(db: Session = Depends(get_db)):
    return UserService(db)

def get_code_verifier():
    return verify_code

def get_password_hasher():
    return get_password_hash