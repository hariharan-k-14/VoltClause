from collections.abc import AsyncIterator, Iterable, Iterator

from app.llm.types import LLMProvider, LLMRequest, ProviderError, TextChunk, Usage


class FakeProvider(LLMProvider):
    """Deterministic provider for local development and tests."""

    def __init__(
        self,
        chunks: Iterable[str] = ("Hello", " from the fake provider."),
        usage: Usage | None = None,
        error: ProviderError | None = None,
    ) -> None:
        self._chunks = tuple(chunks)
        self._usage = usage or Usage(
            input_tokens=0,
            output_tokens=len(self._chunks),
            estimated=True,
        )
        self._error = error
        self.calls = 0

    def stream(self, request: LLMRequest) -> Iterator[TextChunk]:
        self.calls += 1
        if self._error is not None:
            raise self._error
        for chunk in self._chunks:
            yield TextChunk(chunk)
        if self._chunks:
            yield TextChunk("", usage=self._usage)

    async def stream_async(self, request: LLMRequest) -> AsyncIterator[TextChunk]:
        for chunk in self.stream(request):
            yield chunk
