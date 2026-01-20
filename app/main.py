from fastapi import FastAPI

from app.api.routes import router as api_router
from app.config.settings import get_settings


settings = get_settings()
app = FastAPI(title=settings.app_name, debug=settings.debug)
app.include_router(api_router)


@app.get("/health")
def health_check():
    return {"status": "ok", "app": settings.app_name}
