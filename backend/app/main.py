"""FastAPI application entry point."""

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import connect_db, close_db, get_database
from scrapers.scheduler import run_all_scrapers
from app.routers import (
    auth,
    profiles,
    universities,
    shortlists,
    applications,
    documents,
    roadmaps,
    analysis,
    employee,
    admin,
    dashboard,
    chatbot,
)

logger = logging.getLogger(__name__)


async def weekly_scraper_scheduler():
    """Background loop that executes scrapers weekly."""
    logger.info("Weekly scraper scheduler loop started.")
    await asyncio.sleep(5)  # Wait briefly for startup completion
    db = get_database()
    while True:
        try:
            logger.info("Checking last scraper execution timestamp...")
            latest_log = await db.scraper_logs.find_one({}, sort=[("created_at", -1)])
            
            should_run = False
            if not latest_log:
                should_run = True
            else:
                from datetime import datetime, timezone
                try:
                    log_time = datetime.fromisoformat(latest_log["created_at"])
                    # Run if log is older than 7 days
                    if (datetime.now(timezone.utc) - log_time).days >= 7:
                        should_run = True
                except Exception:
                    should_run = True
            
            if should_run:
                logger.info("Executing weekly scraper updates...")
                await run_all_scrapers(db)
            else:
                logger.info("Database records are up-to-date. Next scheduler check in 24 hours.")
        except Exception as e:
            logger.error(f"Error occurred in weekly scraper scheduler: {e}")
        
        # Check daily
        await asyncio.sleep(86400)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    await connect_db()
    # Start scheduler loop as an independent background task
    scheduler_task = asyncio.create_task(weekly_scraper_scheduler())
    yield
    scheduler_task.cancel()
    await close_db()


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="AI-Powered Global Education Platform API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all API routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(profiles.router, prefix="/api/v1")
app.include_router(universities.router, prefix="/api/v1")
app.include_router(shortlists.router, prefix="/api/v1")
app.include_router(applications.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(roadmaps.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(employee.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(chatbot.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "tagline": "Your AI-Powered Global Education Partner",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
