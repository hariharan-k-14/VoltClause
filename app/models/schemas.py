from typing import Any

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(..., description="Role of the author, e.g. 'user', 'assistant', 'system'")
    content: str = Field(..., description="Content of the message")


class ChatRequest(BaseModel):
    message: str = Field(..., description="User question or electrical specification query")
    messages: list[ChatMessage] | None = Field(default=None, description="Optional full conversation history")
    project_type: str | None = Field(
        default=None, description="Project domain: rooftop_solar, substation, transmission_line"
    )
    voltage_level_kv: float | None = Field(
        default=None, description="System voltage level in kV, e.g. 11, 33, 66, 110, 230"
    )
    stream: bool = Field(default=False, description="Enable Server-Sent Events token streaming")
    force_fallback: bool = Field(
        default=False, description="Force fallback model execution for resilience testing"
    )
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)


class Citation(BaseModel):
    document: str = Field(..., description="CEA regulation or gazette document title")
    regulation_no: str = Field(..., description="Regulation number, e.g. 'Regulation 58'")
    clause: str | None = Field(default=None, description="Specific clause or title")
    in_force: bool = Field(default=True, description="Whether this version is currently in force")
    amendment_ref: str | None = Field(
        default=None, description="Gazette notification amendment reference if applicable"
    )


class TokenUsage(BaseModel):
    prompt_tokens: int = Field(..., description="Tokens in the prompt")
    completion_tokens: int = Field(..., description="Tokens generated in the completion")
    total_tokens: int = Field(..., description="Total tokens consumed")
    cost_usd: float = Field(..., description="Estimated cost in USD")


class ChatResponse(BaseModel):
    reply: str = Field(..., description="Technical answer quoting valid CEA clauses")
    model_used: str = Field(..., description="The model that produced the answer")
    provider: str = Field(..., description="LLM provider: openai, gemini, or mock")
    fallback_triggered: bool = Field(..., description="True if primary model failed and fallback was used")
    attempt_count: int = Field(..., description="Number of attempts before success")
    usage: TokenUsage = Field(..., description="Token usage and dollar cost for this call")
    citations: list[Citation] = Field(
        default_factory=list, description="CEA regulation citations backing the response"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class UsageLogEntry(BaseModel):
    id: str
    timestamp: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    latency_ms: float
    status: str
    fallback_triggered: bool


class ModelUsageSummary(BaseModel):
    requests: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


class UsageStatsResponse(BaseModel):
    total_requests: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_cost_usd: float
    breakdown_by_model: dict[str, ModelUsageSummary]
    recent_logs: list[UsageLogEntry]
