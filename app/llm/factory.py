from app.config import Settings
from app.llm.fake import FakeProvider
from app.llm.openai_compat import OpenAICompatProvider
from app.llm.reliable import AsyncReliableLLM
from app.llm.types import LLMProvider


def create_provider(settings: Settings) -> AsyncReliableLLM:
    primary = _create_provider(
        settings.llm_provider,
        settings.llm_base_url,
        settings.llm_api_key,
        settings.llm_model,
    )
    fallback = None
    if settings.llm_fallback_model:
        fallback = OpenAICompatProvider(
            settings.llm_fallback_base_url or settings.llm_base_url,
            settings.llm_fallback_api_key or settings.llm_api_key,
            settings.llm_fallback_model,
            settings.llm_timeout_seconds,
        )
    return AsyncReliableLLM(
        primary,
        fallback=fallback,
        primary_retries=settings.llm_max_retries,
        fallback_retries=1,
    )


def _create_provider(
    provider_name: str,
    base_url: str,
    api_key: str,
    model: str,
) -> LLMProvider:
    if provider_name == "fake":
        return FakeProvider()
    if provider_name == "openai_compat":
        return OpenAICompatProvider(base_url, api_key, model)
    raise ValueError(f"unknown LLM_PROVIDER: {provider_name}")
