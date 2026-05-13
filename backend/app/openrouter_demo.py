"""Offline demo client that returns canned JSON responses.

Activated when `OPENROUTER_API_KEY == "demo"`. Lets users exercise the full
pipeline (fetcher → agents → reviewer → SSE → UI) without paying for or
configuring real OpenRouter calls.

The client sniffs the system prompt to decide which agent is asking and
returns a tiny, schema-valid payload tailored to that role.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from app.openrouter import ChatResult

logger = logging.getLogger(__name__)


_FUND_PAYLOAD: dict[str, Any] = {
    "summary": "[데모 모드] 데이터센터 매출이 견조하나 단기 멀티플이 정점 부근이라 판단된다.",
    "financial_trend": [
        {
            "period": "2026Q1",
            "revenue": 44_000_000_000,
            "operating_income": 29_000_000_000,
            "net_income": 24_000_000_000,
            "eps": 0.95,
            "op_margin": 0.66,
        }
    ],
    "valuation_metrics": [
        {"metric": "PER (TTM)", "value": 50.0, "peer_median": 28.0, "note": "[데모]"},
        {"metric": "PBR", "value": 35.0, "peer_median": None, "note": None},
    ],
    "key_drivers": [
        {
            "text": "데이터센터 매출 yoy +110% (데모 데이터).",
            "label": "fact",
            "citations": [{"source": "demo", "date_ref": "2026Q1"}],
        }
    ],
    "risks": [
        {
            "text": "ASIC 경쟁 심화에 따른 GPU ASP 압박 가능성.",
            "label": "opinion",
            "citations": [],
        }
    ],
    "scenarios": [
        {
            "name": "bullish",
            "triggers": ["FY26 데이터센터 +60% YoY"],
            "assumptions": ["Fwd PER 35x"],
            "target_range_low": 1050.0,
            "target_range_high": 1200.0,
            "probability_qualitative": "medium",
            "rationale": "[데모] 멀티플 유지 + 매출 성장.",
        },
        {
            "name": "base",
            "triggers": ["FY26 데이터센터 +35% YoY"],
            "assumptions": ["Fwd PER 30x"],
            "target_range_low": 880.0,
            "target_range_high": 1000.0,
            "probability_qualitative": "medium",
            "rationale": "[데모] 사이클 정상화.",
        },
        {
            "name": "bearish",
            "triggers": ["AI capex 둔화"],
            "assumptions": ["Fwd PER 22x"],
            "target_range_low": 550.0,
            "target_range_high": 700.0,
            "probability_qualitative": "low",
            "rationale": "[데모] 멀티플 압축.",
        },
    ],
    "data_caveats": ["[데모 모드] 실제 LLM 호출이 아닌 고정 응답."],
}


_TECH_PAYLOAD: dict[str, Any] = {
    "summary": "[데모 모드] 정배열 유지 + RSI 62 — 단기 과열 직전.",
    "trend": "MA20 > MA50 > MA200 완전 정배열. 추세 강도 양호.",
    "moving_averages": {"ma20": 890.0, "ma50": 850.0, "ma200": 700.0},
    "momentum": "RSI 62 (과매수 임박), MACD 양전환 유지, 다이버전스 없음.",
    "levels": [
        {"kind": "support", "price": 850.0, "rationale": "MA50 수렴"},
        {"kind": "support", "price": 700.0, "rationale": "MA200"},
        {"kind": "resistance", "price": 950.0, "rationale": "전 고점"},
    ],
    "scenarios": [
        {
            "name": "bullish",
            "triggers": ["950 돌파 + 평균 이상 거래량"],
            "assumptions": ["RSI 70 미만 유지"],
            "target_range_low": 980.0,
            "target_range_high": 1050.0,
            "probability_qualitative": "medium",
            "rationale": "[데모] 전 고점 돌파 시 1차 1,000.",
        },
        {
            "name": "base",
            "triggers": ["850~950 박스권"],
            "assumptions": ["변동성 일상 수준"],
            "target_range_low": 850.0,
            "target_range_high": 950.0,
            "probability_qualitative": "high",
            "rationale": "[데모] 박스 유지.",
        },
        {
            "name": "bearish",
            "triggers": ["MA50 하향 이탈"],
            "assumptions": ["거래량 동반 매도"],
            "target_range_low": 700.0,
            "target_range_high": 800.0,
            "probability_qualitative": "low",
            "rationale": "[데모] MA200까지 후퇴 가능.",
        },
    ],
    "data_caveats": [
        "[데모 모드] 실제 LLM 호출이 아닌 고정 응답.",
        "기술적 분석은 후행 지표 기반이며 거시·이벤트 충격에 무력화될 수 있음.",
    ],
}


_REVIEWER_PAYLOAD: dict[str, Any] = {
    "final_report_markdown": """# {ASSET} 주식 가치 분석 보고서 (DEMO)

> **⚠️ 데모 모드**: 본 보고서는 `OPENROUTER_API_KEY=demo` 설정으로 생성된 고정 응답입니다. 실제 분석이 아닙니다.

## 0. Executive Summary
- 펀더멘털 [F]: 데이터센터 매출 견조, 멀티플은 정점 부근.
- 기술적 [T]: 정배열 + 과열 직전.
- Base 적정주가 범위: $880~$1,000.

## 1. 펀더멘털 [F]
- 2026Q1 매출 $44B (op margin 66%).
- Fwd PER 30x peer median 28x.

## 2. 기술적 [T]
- MA 완전 정배열, RSI 62.
- 지지 850/700, 저항 950.

## 3. 통합 시나리오
| 시나리오 | 트리거 | 가격 범위 |
|---------|--------|----------|
| Bullish | 데이터센터 +60% YoY, 950 돌파 | $980~$1,200 |
| **Base** | 사이클 정상화, 박스권 | **$850~$1,000** |
| Bearish | AI capex 둔화, MA50 이탈 | $550~$800 |

## 4. 모니터링
- 다음 분기 데이터센터 가이던스
- AI capex 가이드 변경
- ASIC 경쟁 시그널

## 5. 면책 조항
본 보고서는 데모 모드 고정 응답이며 어떤 투자 권유도 아닙니다.
""",
    "discrepancies": [],
    "open_questions": [
        "[데모] OpenRouter 실제 호출은 OPENROUTER_API_KEY 설정 후 가능",
    ],
}


def _detect_role(system: str) -> str:
    if "Integrator-Reviewer" in system or "통합" in system or "Discrepancy" in system:
        return "reviewer"
    if "Technical Analyst" in system:
        return "technical"
    if "Fundamental Analyst" in system:
        return "fundamental"
    return "unknown"


def _payload_for(role: str, asset_hint: str = "ASSET") -> dict[str, Any]:
    if role == "fundamental":
        return _FUND_PAYLOAD
    if role == "technical":
        return _TECH_PAYLOAD
    if role == "reviewer":
        payload = json.loads(json.dumps(_REVIEWER_PAYLOAD))
        payload["final_report_markdown"] = payload["final_report_markdown"].replace(
            "{ASSET}", asset_hint
        )
        return payload
    # Unknown role — return a minimal echo so callers don't crash
    return {"summary": "demo response", "data_caveats": ["unknown role in demo mode"]}


def _asset_from_user(user_prompt: str) -> str:
    # Heuristic: look for "Ticker: `XYZ`" or "Asset: XYZ"
    import re

    m = re.search(r"\*\*Ticker\*\*:\s*`([^`]+)`", user_prompt)
    if m:
        return m.group(1)
    m = re.search(r"Asset.*?:\s*([A-Z0-9.\-]{1,12})", user_prompt)
    if m:
        return m.group(1)
    return "ASSET"


class DemoOpenRouterClient:
    """Drop-in replacement for `OpenRouterClient` returning canned data."""

    def __init__(self, default_model: str = "demo/canned") -> None:
        self._default_model = default_model

    @property
    def default_model(self) -> str:
        return self._default_model

    async def chat(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
        json_mode: bool = False,
        json_schema: dict | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> ChatResult:
        # Pretend to take a moment — keeps SSE timeline visible in the UI.
        await asyncio.sleep(0.25)
        role = _detect_role(system)
        asset = _asset_from_user(user)
        payload = _payload_for(role, asset)
        content = json.dumps(payload, ensure_ascii=False)
        chosen_model = model or self._default_model
        # Roughly approximate token counts so the UI shows non-zero values.
        prompt_tokens = max(1, len(system) // 4 + len(user) // 4)
        completion_tokens = max(1, len(content) // 4)
        return ChatResult(
            content=content,
            model=chosen_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            finish_reason="stop",
            raw=None,
        )

    async def chat_stream(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        result = await self.chat(system=system, user=user, model=model)
        # Yield in a handful of chunks so streaming consumers also work.
        text = result.content
        chunk = max(64, len(text) // 8)
        for i in range(0, len(text), chunk):
            await asyncio.sleep(0.05)
            yield text[i : i + chunk]

    async def echo_test(self, model: str | None = None) -> ChatResult:
        return ChatResult(
            content="pong (demo)", model=model or self._default_model, total_tokens=1
        )

    async def close(self) -> None:
        return None
