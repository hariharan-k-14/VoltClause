from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, Query
from fastapi.responses import StreamingResponse

from app.config import Settings, get_settings
from app.models.schemas import ChatRequest, ChatResponse, UsageStatsResponse
from app.services.llm import LLMService
from app.services.usage import UsageTracker

app = FastAPI(
    title="VoltClause API",
    description="CEA safety and technical clause validation, clause diffing, and LLM research agent.",
    version="0.2.0",
)


@lru_cache
def get_usage_tracker() -> UsageTracker:
    settings = get_settings()
    return UsageTracker(log_file=settings.usage_log_file)


def get_llm_service(
    settings: Annotated[Settings, Depends(get_settings)],
    usage_tracker: Annotated[UsageTracker, Depends(get_usage_tracker)],
) -> LLMService:
    return LLMService(settings=settings, usage_tracker=usage_tracker)


SettingsDep = Annotated[Settings, Depends(get_settings)]
LLMServiceDep = Annotated[LLMService, Depends(get_llm_service)]
UsageTrackerDep = Annotated[UsageTracker, Depends(get_usage_tracker)]


@app.get("/health")
def health(settings: SettingsDep) -> dict:
    """Liveness check: process is up. Must be fast and must not call the LLM or DB."""
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}


@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    llm_service: LLMServiceDep,
):
    """Query CEA regulations with structured answer, citations, fallback model, and cost tracking."""
    if request.stream:
        return StreamingResponse(
            llm_service.stream_response(request),
            media_type="text/event-stream",
        )
    return await llm_service.generate_response(request)


@app.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    llm_service: LLMServiceDep,
):
    """Server-Sent Events (SSE) streaming endpoint for real-time token delivery."""
    return StreamingResponse(
        llm_service.stream_response(request),
        media_type="text/event-stream",
    )


@app.get("/usage", response_model=UsageStatsResponse)
def get_usage(
    usage_tracker: UsageTrackerDep,
    limit: int = Query(default=50, ge=1, le=500),
) -> UsageStatsResponse:
    """Retrieve cumulative token consumption, estimated USD cost, and per-model breakdown."""
    return usage_tracker.get_stats(limit=limit)


@app.post("/usage/reset")
def reset_usage(usage_tracker: UsageTrackerDep) -> dict:
    """Reset tracked usage metrics and logs (useful for test suites and dev environments)."""
    usage_tracker.reset()
    return {"status": "ok", "message": "Usage tracking metrics reset"}
