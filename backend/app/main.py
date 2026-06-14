"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import connect_db, close_db
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



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    await connect_db()
    yield
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
