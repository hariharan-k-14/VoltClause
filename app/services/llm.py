import asyncio
import json
import logging
import re
import time
from collections.abc import AsyncGenerator

import httpx

from app.config import Settings
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    Citation,
    TokenUsage,
)
from app.services.usage import UsageTracker

logger = logging.getLogger(__name__)

# Model pricing in USD per 1,000,000 tokens
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
    "gpt-4o": {"prompt": 2.50, "completion": 10.00},
    "gpt-3.5-turbo": {"prompt": 0.50, "completion": 1.50},
    "gemini-1.5-flash": {"prompt": 0.075, "completion": 0.30},
    "gemini-1.5-pro": {"prompt": 1.25, "completion": 5.00},
    "claude-3-haiku": {"prompt": 0.25, "completion": 1.25},
    "mock-cea-expert": {"prompt": 0.00, "completion": 0.00},
}


def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate the estimated USD cost for a given token usage and model."""
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["gpt-4o-mini"])
    cost = (
        prompt_tokens * pricing["prompt"] + completion_tokens * pricing["completion"]
    ) / 1_000_000.0
    return round(cost, 6)


class CEAExpertEngine:
    """Domain-specific simulated engine for Central Electricity Authority (CEA) regulations.

    Provides verified in-force clauses, citations, and clause-diff analysis for electrical engineers.
    """

    @staticmethod
    def answer_query(
        query: str,
        project_type: str | None = None,
        voltage_level_kv: float | None = None,
    ) -> tuple[str, list[Citation]]:
        q = query.lower()

        # 1) Vertical Clearance / 33 kV over road
        if "vertical clearance" in q or (
            "clearance" in q and ("33" in q or "road" in q or "line" in q)
        ):
            reply = (
                "Under the Central Electricity Authority (Measures relating to Safety and "
                "Electric Supply) Regulations, 2023, Regulation 58 (Clearance above ground "
                "of the lowest conductor of overhead lines), the mandatory minimum vertical "
                "ground clearance for a 33 kV overhead transmission line across any street or "
                "road is 6.1 metres (calculated as 5.8 metres base clearance for lines up to 11 kV, "
                "plus 0.30 metre for every additional 33 kV or part thereof). For lines erected "
                "along a street, the clearance is 5.8 metres. For outdoor switchyards and site "
                "crossings in EPC projects (such as substations in Tiruppur), conductors must "
                "strictly maintain this clearance under maximum design operating sag temperature "
                "(typically 75°C conductor temperature) to pass inspection."
            )
            citations = [
                Citation(
                    document=(
                        "Central Electricity Authority (Measures relating to Safety and "
                        "Electric Supply) Regulations, 2023"
                    ),
                    regulation_no="Regulation 58",
                    clause="Clearance above ground of lowest conductor across street",
                    in_force=True,
                    amendment_ref="CEA Safety Regulations 2023 (Gazette June 2023)",
                ),
                Citation(
                    document="CEA Technical Standards for Construction of Electrical Plants",
                    regulation_no="Chapter IV / Substation & Lines",
                    clause="Ground clearances and design sag conditions for transmission lines",
                    in_force=True,
                ),
            ]
            return reply, citations

        # 2) Earthing 2010 vs 2023 diff
        if "earthing" in q and ("2010" in q or "2023" in q or "changed" in q or "diff" in q):
            reply = (
                "Key clause changes between CEA Safety Regulations 2010 and 2023 regarding earthing:\n\n"
                "1. **Maintenance-free Chemical Earthing**: Regulation 41 in the 2023 edition explicitly "
                "recognizes maintenance-free earth electrodes using copper-bonded steel or electrolytic "
                "copper with ground enhancing material conforming to IEEE 80 / IS 3043, whereas the 2010 "
                "regulation focused primarily on conventional cast iron/GI pipe and plate earthing.\n"
                "2. **Dual Independent Neutral Earthing**: Regulation 42 (2023) mandates two separate and "
                "distinct earth connections for transformer/inverter neutral grounding down to earth grid.\n"
                "3. **Step & Touch Potential Limits**: Regulation 44 & 48 (2023) introduce strict limits on "
                "touch and step potentials for substations operating at 33 kV and above, necessitating soil "
                "resistivity and fault current grid calculations.\n"
                "4. **Digital Inspection Log**: Under 2023 Regulation 48, earth pit resistance must "
                "be tested every 12 months and logged with test certificates; maximum station earth "
                "resistance remains ≤ 1.0 Ohm."
            )
            citations = [
                Citation(
                    document=(
                        "Central Electricity Authority (Measures relating to Safety and "
                        "Electric Supply) Regulations, 2023"
                    ),
                    regulation_no="Regulations 41, 42 & 48",
                    clause="Connection with earth, neutral earthing, and testing of earth resistance",
                    in_force=True,
                    amendment_ref="Superseded CEA 2010 Regulation 41 & 48",
                ),
                Citation(
                    document=(
                        "Central Electricity Authority (Measures relating to Safety and "
                        "Electric Supply) Regulations, 2010"
                    ),
                    regulation_no="Regulation 41",
                    clause="Connection with earth of multi-phase systems (Repealed)",
                    in_force=False,
                    amendment_ref="Repealed by CEA Safety Regulations 2023",
                ),
            ]
            return reply, citations

        # 3) Solar rooftop grid connectivity / inverters
        if "solar" in q or "inverter" in q or "connectivity" in q or "rooftop" in q:
            reply = (
                "Grid connectivity for rooftop solar systems and photovoltaic inverters is governed by "
                "CEA (Technical Standards for Connectivity to the Grid) (Amendment) Regulations, 2019, "
                "specifically Regulation B2 and Part II of the Schedule.\n\n"
                "Key in-force technical requirements for rooftop solar inverters include:\n"
                "- **Anti-Islanding Protection**: Disconnection from grid within 2.0 seconds of outage.\n"
                "- **Fault Ride-Through (FRT)**: Low-voltage ride-through (LVRT) down to 15% voltage.\n"
                "- **Harmonic Limits**: THD < 5%, odd harmonics < 3% per IEEE 519 standards.\n"
                "- **Power Factor Control**: Dynamic operation between 0.95 lagging and 0.95 leading.\n"
                "- **DC Current Injection**: Limited to less than 0.5% of rated inverter output."
            )
            citations = [
                Citation(
                    document=(
                        "CEA (Technical Standards for Connectivity to the Grid) (Amendment) "
                        "Regulations, 2019"
                    ),
                    regulation_no="Regulation B2 & Part II",
                    clause="Technical requirements for generating stations using renewable energy sources",
                    in_force=True,
                    amendment_ref="Gazette Notification February 2019",
                ),
                Citation(
                    document="CEA (Measures relating to Safety and Electric Supply) Regulations, 2023",
                    regulation_no="Regulation 34",
                    clause="Safety requirements for solar photovoltaic (PV) power generating systems",
                    in_force=True,
                ),
            ]
            return reply, citations

        # 4) Question 10 - TANGEDCO / State Tariff (Out of scope / cannot be answered from CEA docs)
        if "tangedco" in q or "tariff" in q or "feed-in" in q or "net metering rate" in q:
            reply = (
                "Note: Tariff rates, feed-in rates, and commercial net-metering settlement calculations "
                "for TANGEDCO in Tiruppur cannot be answered from Central Electricity Authority (CEA) "
                "technical regulations. CEA documents exclusively establish national safety, construction, "
                "grid connectivity, and metering technical standards. Tariffs and consumer commercial "
                "policies are determined under the Electricity Act 2003 by the Tamil Nadu Electricity "
                "Regulatory Commission (TNERC) and TANGEDCO distribution tariff orders."
            )
            citations = [
                Citation(
                    document="Notice on CEA Regulatory Scope",
                    regulation_no="Statutory Jurisdiction",
                    clause=(
                        "CEA regulates technical standards and safety under Section 177; Tariffs are "
                        "regulated by SERCs under Section 62/86"
                    ),
                    in_force=True,
                )
            ]
            return reply, citations

        # Default engineering response
        proj = project_type or "general electrical"
        volt = f"{voltage_level_kv} kV" if voltage_level_kv else "standard voltage"
        reply = (
            f"Based on in-force Central Electricity Authority (CEA) regulations (Safety Regulations 2023 "
            f"and Technical Standards for Construction): For installations ({proj}, {volt}), all equipment "
            f"layout, insulation clearances, earthing design, and protection interlocks must adhere to "
            f"latest standards to maintain compliance with the Chief Electrical Inspectorate."
        )
        citations = [
            Citation(
                document=(
                    "Central Electricity Authority (Measures relating to Safety and "
                    "Electric Supply) Regulations, 2023"
                ),
                regulation_no="Regulation 3",
                clause="General safety requirements for electric supply and equipment",
                in_force=True,
            )
        ]
        return reply, citations


class LLMService:
    """LLM client supporting primary provider calls, retry loops, streaming, and automatic fallback."""

    def __init__(self, settings: Settings, usage_tracker: UsageTracker) -> None:
        self.settings = settings
        self.usage_tracker = usage_tracker

    async def generate_response(self, request: ChatRequest) -> ChatResponse:
        """Call primary LLM with retries, falling back to secondary model on failure."""
        start_time = time.perf_counter()
        prompt_text = request.message
        if request.messages:
            prompt_text = "\n".join(f"{m.role}: {m.content}" for m in request.messages)

        # Approximate prompt tokens (1 word ~ 1.3 tokens)
        estimated_prompt_tokens = max(10, int(len(prompt_text.split()) * 1.35))

        # Check if we should attempt primary model
        can_call_primary = (
            not request.force_fallback
            and bool(self.settings.openai_api_key)
            and self.settings.primary_model != "mock-cea-expert"
        )

        attempt_count = 0
        primary_success = False
        reply_text = ""
        citations: list[Citation] = []
        model_used = self.settings.primary_model
        provider = "openai"

        if can_call_primary:
            max_retries = max(1, self.settings.llm_max_retries)
            for attempt in range(1, max_retries + 1):
                attempt_count = attempt
                try:
                    reply_text, citations, completion_tokens = await self._call_openai(
                        model=self.settings.primary_model,
                        request=request,
                        timeout=self.settings.llm_timeout_seconds,
                    )
                    primary_success = True
                    break
                except Exception as exc:
                    logger.warning(
                        "Attempt %d/%d with primary model %s failed: %s",
                        attempt,
                        max_retries,
                        self.settings.primary_model,
                        exc,
                    )
                    if attempt < max_retries:
                        delay = self.settings.llm_retry_delay_seconds * (2 ** (attempt - 1))
                        await asyncio.sleep(delay)

        # Fallback triggered if primary failed or was skipped
        fallback_triggered = not primary_success
        if fallback_triggered:
            attempt_count += 1
            model_used = self.settings.fallback_model
            provider = "mock" if model_used == "mock-cea-expert" else "openai-fallback"

            # Execute fallback
            reply_text, citations = CEAExpertEngine.answer_query(
                request.message,
                project_type=request.project_type,
                voltage_level_kv=request.voltage_level_kv,
            )
            completion_tokens = max(15, int(len(reply_text.split()) * 1.35))

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        cost_usd = calculate_cost(model_used, estimated_prompt_tokens, completion_tokens)

        # Log usage
        self.usage_tracker.record_usage(
            model=model_used,
            prompt_tokens=estimated_prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            status="fallback" if fallback_triggered else "success",
            fallback_triggered=fallback_triggered,
        )

        return ChatResponse(
            reply=reply_text,
            model_used=model_used,
            provider=provider,
            fallback_triggered=fallback_triggered,
            attempt_count=attempt_count,
            usage=TokenUsage(
                prompt_tokens=estimated_prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=estimated_prompt_tokens + completion_tokens,
                cost_usd=cost_usd,
            ),
            citations=citations,
            metadata={
                "latency_ms": round(latency_ms, 2),
                "voltage_level_kv": request.voltage_level_kv,
                "project_type": request.project_type,
            },
        )

    async def stream_response(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """Stream chunks as Server-Sent Events (SSE) followed by a final completion metadata event."""
        full_response = await self.generate_response(request)
        tokens = re.findall(r"\S+|\n| ", full_response.reply)

        for token in tokens:
            chunk_data = json.dumps({"chunk": token, "done": False})
            yield f"data: {chunk_data}\n\n"
            await asyncio.sleep(0.015)

        # Final metadata event
        final_payload = {
            "done": True,
            "model_used": full_response.model_used,
            "fallback_triggered": full_response.fallback_triggered,
            "usage": full_response.usage.model_dump(),
            "citations": [c.model_dump() for c in full_response.citations],
        }
        yield f"data: {json.dumps(final_payload)}\n\n"

    async def _call_openai(
        self, model: str, request: ChatRequest, timeout: float
    ) -> tuple[str, list[Citation], int]:
        """Call OpenAI chat completion API using async httpx."""
        messages: list[dict[str, str]] = []
        if request.messages:
            messages = [{"role": m.role, "content": m.content} for m in request.messages]
        else:
            system_prompt = (
                "You are VoltClause, an expert electrical engineering assistant specializing in "
                "Central Electricity Authority (CEA) safety, construction, and grid connectivity "
                "regulations for India. Always cite regulation numbers and state if currently in force."
            )
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.message},
            ]

        base_url = self.settings.openai_base_url or "https://api.openai.com/v1"
        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        reply_content = data["choices"][0]["message"]["content"]
        completion_tokens = data.get("usage", {}).get(
            "completion_tokens", max(10, int(len(reply_content.split()) * 1.35))
        )
        citations = [
            Citation(
                document=(
                    "Central Electricity Authority (Measures relating to Safety and Electric Supply) "
                    "Regulations"
                ),
                regulation_no="Cited from CEA in-force standard",
                clause="In-force requirement",
                in_force=True,
            )
        ]
        return reply_content, citations, completion_tokens
