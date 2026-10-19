"""Scaffold API cho luồng học tri thức. Chưa được include vào `api/v1/router.py`.

Ingestion, Segmenter/Extractor và persistence chưa được triển khai, nên route trả 501
thay vì giả vờ đã nhận job.
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter(tags=["learning_ai"])


class LearnRequest(BaseModel):
    session_id: str = Field(min_length=1)
    retry_failed: bool = Field(default=False, description="Chạy lại nếu job trước đó failed/partial")


@router.post("/learning-knowledge", response_model=None)
async def submit_learning(req: LearnRequest) -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="learning pipeline is not implemented",
    )
