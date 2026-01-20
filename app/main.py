from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.api.routes import router as api_router
from app.config.settings import get_settings
from app.storage.database import init_db
from app.utils.logging_config import setup_logging


# Setup logging
logger = setup_logging()
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    description="Constraint-based scheduling and optimization engine with CSP solvers",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting {settings.app_name}...")
    init_db()
    logger.info("Database initialized")
    logger.info(f"Solver type: {settings.solver_type}")
    logger.info(f"OR-Tools time limit: {settings.ortools_time_limit_seconds}s")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info(f"Shutting down {settings.app_name}...")

app.include_router(api_router, prefix="/api/v1", tags=["scheduling"])


@app.get("/health", tags=["health"])
def health_check():
    """Health check endpoint for monitoring and load balancers."""
    return {"status": "ok", "app": settings.app_name, "version": "1.0.0"}
