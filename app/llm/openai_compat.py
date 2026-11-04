import json
from collections.abc import AsyncIterator

import httpx

from app.llm.types import LLMProvider, LLMRequest, ProviderError, TextChunk, Usage


class OpenAICompatProvider(LLMProvider):
    """Streaming client for OpenAI-compatible /chat/completions endpoints."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = httpx.Timeout(timeout_seconds, connect=5.0)
        self.transport = transport

    async def stream_async(self, request: LLMRequest) -> AsyncIterator[TextChunk]:
        payload = {
            "model": request.model or self.model,
            "messages": [{"role": message.role, "content": message.content} for message in request.messages],
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.status_code >= 400:
                        body = (await response.aread()).decode(errors="replace")[:300]
                        raise ProviderError(
                            f"provider returned {response.status_code}: {body}",
                            status_code=response.status_code,
                            retry_after=_retry_after(response),
                        )

                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            return
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError as error:
                            raise ProviderError("provider returned invalid stream JSON") from error
                        usage = _usage_from_chunk(chunk)
                        if usage is not None:
                            yield TextChunk("", usage=usage)
                        for choice in chunk.get("choices", []):
                            text = (choice.get("delta") or {}).get("content")
                            if text:
                                yield TextChunk(text)
        except ProviderError:
            raise
        except httpx.TimeoutException as error:
            raise ProviderError(f"provider timeout: {error}") from error
        except httpx.TransportError as error:
            raise ProviderError(f"provider connection failed: {error}") from error


def _retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after")
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _usage_from_chunk(chunk: dict) -> Usage | None:
    usage = chunk.get("usage")
    if not usage:
        return None
    return Usage(
        input_tokens=usage.get("prompt_tokens", 0),
        output_tokens=usage.get("completion_tokens", 0),
    )
