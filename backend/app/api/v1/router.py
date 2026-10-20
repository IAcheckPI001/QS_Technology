from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.core.config import Settings, settings
from app.modules.chatbot.router import router as chatbot_router
from app.modules.learning_ai.router import router as learning_router


def build_api_router(config: Settings) -> APIRouter:
    router = APIRouter()
    router.include_router(health_router)
    router.include_router(chatbot_router)
    # Chưa có xác thực: chỉ public khi được bật rõ ràng.
    if config.learning_api_enabled:
        router.include_router(learning_router)
    return router


api_router = build_api_router(settings)
