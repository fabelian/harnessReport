"""Output schemas emitted by each analyst agent.

Designed for OpenRouter's `response_format=json_object` mode plus client-side
Pydantic validation. Kept deliberately flat — no Unions, only basic types and
lists — so weaker open-weight models can comply.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# --- shared ------------------------------------------------------------------

Label = Literal["fact", "estimate", "opinion"]
ScenarioName = Literal["bullish", "base", "bearish"]


class Citation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    source: str
    url: str | None = None
    date_ref: str | None = None  # ISO date or quarter label


class Claim(BaseModel):
    """A single labeled statement with optional citations."""

    model_config = ConfigDict(extra="ignore")
    text: str
    label: Label
    citations: list[Citation] = Field(default_factory=list)


class Scenario(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: ScenarioName
    triggers: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    target_range_low: float | None = None
    target_range_high: float | None = None
    probability_qualitative: Literal["low", "medium", "high"] | None = None
    rationale: str | None = None


# --- fundamental -------------------------------------------------------------


class FinancialTrendRow(BaseModel):
    model_config = ConfigDict(extra="ignore")
    period: str
    revenue: float | None = None
    operating_income: float | None = None
    net_income: float | None = None
    eps: float | None = None
    op_margin: float | None = None


class ValuationMetric(BaseModel):
    model_config = ConfigDict(extra="ignore")
    metric: str  # "PER (TTM)", "PBR", "EV/EBITDA", ...
    value: float | None = None
    peer_median: float | None = None
    note: str | None = None


class FundamentalOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    summary: str
    financial_trend: list[FinancialTrendRow] = Field(default_factory=list)
    valuation_metrics: list[ValuationMetric] = Field(default_factory=list)
    key_drivers: list[Claim] = Field(default_factory=list)
    risks: list[Claim] = Field(default_factory=list)
    scenarios: list[Scenario] = Field(default_factory=list)
    data_caveats: list[str] = Field(default_factory=list)


# --- technical ---------------------------------------------------------------


class Level(BaseModel):
    model_config = ConfigDict(extra="ignore")
    kind: Literal["support", "resistance"]
    price: float
    rationale: str | None = None


class TechnicalOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    summary: str
    trend: str
    moving_averages: dict[str, float | None] = Field(default_factory=dict)
    momentum: str
    levels: list[Level] = Field(default_factory=list)
    scenarios: list[Scenario] = Field(default_factory=list)
    data_caveats: list[str] = Field(default_factory=list)


# --- reviewer ----------------------------------------------------------------


class Discrepancy(BaseModel):
    model_config = ConfigDict(extra="ignore")
    metric: str
    values: list[str] = Field(default_factory=list)
    resolution: str | None = None


class ReviewerOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    final_report_markdown: str
    discrepancies: list[Discrepancy] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    used_model: str | None = None


# --- industry ----------------------------------------------------------------


class CompetitorRow(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    position: str | None = None  # e.g. "leader", "challenger", "follower"
    strength: str | None = None
    weakness: str | None = None


class IndustryOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    summary: str
    cycle_phase: str  # e.g. "early-recovery", "expansion", "peak", "downturn"
    demand_drivers: list[Claim] = Field(default_factory=list)
    supply_constraints: list[Claim] = Field(default_factory=list)
    competitors: list[CompetitorRow] = Field(default_factory=list)
    market_share_note: str | None = None
    risks: list[Claim] = Field(default_factory=list)
    data_caveats: list[str] = Field(default_factory=list)


# --- macro -------------------------------------------------------------------


class MacroFactor(BaseModel):
    model_config = ConfigDict(extra="ignore")
    label: str  # e.g. "Fed Funds Rate", "10Y UST"
    value: str | None = None  # human-readable, may include unit
    trend: str | None = None  # "rising" / "falling" / "stable"
    impact_on_asset: str | None = None


class MacroOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    summary: str
    factors: list[MacroFactor] = Field(default_factory=list)
    fx_view: str | None = None  # e.g. KRW/USD commentary
    capex_cycle: str | None = None
    correlation_notes: list[str] = Field(default_factory=list)
    scenario_bias: str | None = None  # "tailwind" / "neutral" / "headwind"
    data_caveats: list[str] = Field(default_factory=list)


# --- sentiment ---------------------------------------------------------------


class SentimentSignal(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    direction: Literal["bullish", "neutral", "bearish"]
    strength: Literal["weak", "moderate", "strong"] | None = None
    evidence: str | None = None


class SentimentOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    summary: str
    overall_tone: Literal["bullish", "neutral", "bearish"]
    consensus_note: str | None = None  # 12M target / earnings estimates if available
    news_signals: list[SentimentSignal] = Field(default_factory=list)
    flow_signals: list[SentimentSignal] = Field(default_factory=list)
    risks: list[Claim] = Field(default_factory=list)
    data_caveats: list[str] = Field(default_factory=list)


__all__ = [
    "Citation",
    "Claim",
    "Scenario",
    "FinancialTrendRow",
    "ValuationMetric",
    "FundamentalOutput",
    "Level",
    "TechnicalOutput",
    "CompetitorRow",
    "IndustryOutput",
    "MacroFactor",
    "MacroOutput",
    "SentimentSignal",
    "SentimentOutput",
    "Discrepancy",
    "ReviewerOutput",
]
