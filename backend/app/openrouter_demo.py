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


_INDUSTRY_PAYLOAD: dict[str, Any] = {
    "summary": "[데모] AI 인프라 사이클 expansion. HBM·서버 메모리 수요 강세.",
    "cycle_phase": "expansion",
    "demand_drivers": [
        {
            "text": "빅테크 capex 가이드 상향이 HBM·DRAM 수요 견인.",
            "label": "estimate",
            "citations": [{"source": "news context"}],
        }
    ],
    "supply_constraints": [
        {"text": "TSMC CoWoS 캐파가 HBM 출하 상한.", "label": "opinion", "citations": []}
    ],
    "competitors": [
        {
            "name": "Samsung (005930)",
            "position": "challenger",
            "strength": "종합 메모리 1위, HBM 추격",
            "weakness": "HBM 수익성 SK 대비 낮음",
        },
        {
            "name": "Micron (MU)",
            "position": "challenger",
            "strength": "미국 본토, HBM3E 양산",
            "weakness": "DRAM 점유율 낮음",
        },
    ],
    "market_share_note": "[데모] 정확한 점유율은 외부 자료 확인 필요",
    "risks": [
        {"text": "CXMT 양산 확대 시 레거시 DRAM 가격 하방.", "label": "opinion", "citations": []}
    ],
    "data_caveats": ["[데모 모드] 시장조사기관 정량 자료 미포함."],
}


_MACRO_PAYLOAD: dict[str, Any] = {
    "summary": "[데모] 금리 동결 + 빅테크 capex 상향 — 메모리주 우호.",
    "factors": [
        {
            "label": "Fed Funds Rate",
            "value": "4.50%",
            "trend": "stable",
            "impact_on_asset": "[데모] 멀티플 압력 제한적.",
        },
        {
            "label": "10Y UST",
            "value": "4.20%",
            "trend": "stable",
            "impact_on_asset": "[데모] 할인율 안정.",
        },
    ],
    "fx_view": "[데모] 달러 강세 — 한국 수출주 단기 환산 호재.",
    "capex_cycle": "[데모] 빅테크 4사 capex 가이드 yoy +70%, AI 비중 75%.",
    "correlation_notes": ["[데모] SOX·NVDA 강한 양의 상관."],
    "scenario_bias": "tailwind",
    "data_caveats": ["[데모 모드] FRED 일부 시리즈 미포함."],
}


_SENTIMENT_PAYLOAD: dict[str, Any] = {
    "summary": "[데모] 외인 매수 + 어닝 서프라이즈 — bullish, 단 RSI 과열 동반.",
    "overall_tone": "bullish",
    "consensus_note": "본 분석에서는 미제공 — 미확보",
    "news_signals": [
        {
            "name": "Q1 어닝 서프라이즈",
            "direction": "bullish",
            "strength": "strong",
            "evidence": "[데모] EPS 컨센 상회.",
        }
    ],
    "flow_signals": [
        {
            "name": "외인 매수 전환",
            "direction": "bullish",
            "strength": "moderate",
            "evidence": "[데모] 최근 5거래일 외인 순매수.",
        }
    ],
    "risks": [
        {"text": "[데모] 단기 RSI 70 근접 — 차익 매물.", "label": "opinion", "citations": []}
    ],
    "data_caveats": ["[데모 모드] 컨센서스 데이터 미포함."],
}


_REVIEWER_PAYLOAD: dict[str, Any] = {
    "final_report_markdown": """# {ASSET} 주식 가치 분석 보고서 (DEMO)

> **⚠️ 데모 모드**: 본 보고서는 `OPENROUTER_API_KEY=demo` 설정으로 생성된 고정 응답입니다. 실제 분석이 아닙니다.

## 0. Executive Summary
- 펀더멘털·산업 tailwind + 기술적 정배열 [F][T][I][M], 단기 과열 [T][S].
- Base 적정주가 범위: $880~$1,000.

## 1. 기업 개요
- (컨텍스트 메타 그대로)

## 2. 펀더멘털 [F]
- Fwd PER 30x peer median 28x.

## 3. 기술적 [T]
- MA 완전 정배열, RSI 62.

## 4. 산업·경쟁구도 [I]
- 사이클: expansion. HBM 수요 견조.

## 5. 거시 환경 [M]
- 금리 동결, capex tailwind.

## 6. 시장 심리·수급 [S]
- 외인 매수 + 어닝 서프라이즈. 단기 과열.

## 7. 통합 시나리오
| 시나리오 | 트리거 | 가격 범위 |
|---------|--------|----------|
| Bullish | 데이터센터 +60% YoY, 950 돌파 [F][T] | $980~$1,200 |
| **Base** | 사이클 정상화, capex 유지 [I][M] | **$850~$1,000** |
| Bearish | AI capex 둔화, MA50 이탈 [M][T] | $550~$800 |

## 8. 모니터링
- 다음 분기 데이터센터 가이던스 [F]
- AI capex 가이드 변경 [M]
- ASIC 경쟁 시그널 [I]

## 9. 데이터 일관성 / 미해결 이슈
- 컨센서스 데이터 미확보 [S]

## 10. 면책 조항
본 보고서는 데모 모드 고정 응답이며 어떤 투자 권유도 아닙니다.
""",
    "discrepancies": [],
    "open_questions": [
        "[데모] OpenRouter 실제 호출은 OPENROUTER_API_KEY 설정 후 가능",
    ],
}


def _detect_role(system: str) -> str:
    # Reviewer first (its prompt also contains analyst keywords)
    if "Integrator-Reviewer" in system or "Discrepancy" in system:
        return "reviewer"
    if "Industry Analyst" in system:
        return "industry"
    if "Macro Analyst" in system:
        return "macro"
    if "Sentiment Analyst" in system:
        return "sentiment"
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
    if role == "industry":
        return _INDUSTRY_PAYLOAD
    if role == "macro":
        return _MACRO_PAYLOAD
    if role == "sentiment":
        return _SENTIMENT_PAYLOAD
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
