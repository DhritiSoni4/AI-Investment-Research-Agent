from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.research_sessions import router as research_sessions_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(
    research_sessions_router, prefix="/research-sessions", tags=["research-sessions"]
)
