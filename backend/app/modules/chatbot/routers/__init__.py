from fastapi import APIRouter

from app.modules.chatbot.routers.chat import router as chat_router
from app.modules.chatbot.routers.workspace import router as workspace_router

router = APIRouter()
router.include_router(chat_router)
router.include_router(workspace_router)

__all__ = ["router"]
