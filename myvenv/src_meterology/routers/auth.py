from fastapi import APIRouter, Depends, HTTPException, status
from ..schemas.auth import UserCreate, VerifyCode, Token
from ..dependencies import get_auth_service, get_code_verifier
from ..core.security import create_access_token
from ..services.auth import UserService

router = APIRouter()


@router.post("/register", response_model=dict)
async def register(
        user: UserCreate,
        auth_service: UserService = Depends(get_auth_service)
):
    try:
        return auth_service.register_user(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/verify-login", response_model=Token)
async def verify_login(
        verification: VerifyCode,
        code_verifier=Depends(get_code_verifier)
):
    if not code_verifier(verification.email, verification.code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid verification code"
        )

    access_token = create_access_token(data={"sub": verification.email})
    return {"access_token": access_token, "token_type": "bearer"}