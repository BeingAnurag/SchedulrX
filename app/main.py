from fastapi import FastAPI

from app.api.routes import router as api_router
from app.config.settings import get_settings
from app.storage.database import init_db


settings = get_settings()
app = FastAPI(title=settings.app_name, debug=settings.debug)

# Initialize database on startup
init_db()

app.include_router(api_router)


@app.get("/health")
def health_check():
    return {"status": "ok", "app": settings.app_name}
