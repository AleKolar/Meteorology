from fastapi import FastAPI
from myvenv.src_meterology.core.config import settings
from myvenv.src_meterology.routers import auth


app = FastAPI(title=settings.APP_NAME)
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])

@app.on_event("startup")
async def startup():
    # Инициализация подключений
    pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
