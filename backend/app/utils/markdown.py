"""Render `AnalysisData` and agent outputs into prompt-friendly markdown.

Goals:
- Compact (fits in ~8k tokens for an MVP run)
- Numeric — agents should grep specific values out of these tables
- Clearly labeled provenance (every section names its source)
"""
from __future__ import annotations

import json
from typing import Any

from app.schemas.data import AnalysisData
from app.schemas.outputs import (
    FundamentalOutput,
    IndustryOutput,
    MacroOutput,
    SentimentOutput,
    TechnicalOutput,
)


def _fmt_num(v: float | int | None, *, pct: bool = False, decimals: int = 2) -> str:
    if v is None:
        return "n/a"
    if pct:
        return f"{v * 100:.{decimals}f}%"
    if abs(v) >= 1_000_000_000:
        return f"{v / 1_000_000_000:.{decimals}f}B"
    if abs(v) >= 1_000_000:
        return f"{v / 1_000_000:.{decimals}f}M"
    return f"{v:.{decimals}f}"


def _table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return f"_(no rows)_\n"
    sep = "|".join(["---"] * len(headers))
    head_line = "| " + " | ".join(headers) + " |"
    sep_line = "|" + sep + "|"
    body_lines = ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join([head_line, sep_line, *body_lines]) + "\n"


def render_asset_block(data: AnalysisData) -> str:
    a = data.asset
    parts = [
        f"**Ticker**: `{a.ticker}`",
        f"**Name**: {a.name or 'n/a'}",
        f"**Exchange**: {a.exchange or 'n/a'}",
        f"**Currency**: {a.currency or 'n/a'}",
        f"**Sector / Industry**: {a.sector or 'n/a'} / {a.industry or 'n/a'}",
        f"**Country**: {a.country or 'n/a'}",
        f"**Market Cap**: {_fmt_num(a.market_cap)}",
        f"**As-of Date**: {data.as_of_date.isoformat()}",
    ]
    return "\n".join(parts) + "\n"


def render_prices_block(data: AnalysisData) -> str:
    if data.prices is None:
        return "_Price data unavailable._\n"
    p = data.prices
    s = p.summary
    ind = p.indicators
    sub = [
        "### Price Summary",
        f"- As-of close: **{_fmt_num(s.as_of_close)}**",
        f"- 52w high / low: {_fmt_num(s.period_high_52w)} / {_fmt_num(s.period_low_52w)}",
        "- Returns: "
        + ", ".join(
            f"{label}={_fmt_num(value, pct=True)}"
            for label, value in [
                ("1m", s.return_1m),
                ("3m", s.return_3m),
                ("6m", s.return_6m),
                ("YTD", s.return_ytd),
                ("1y", s.return_1y),
            ]
        ),
        f"- Avg volume (30d): {_fmt_num(s.avg_volume_30d)}",
        "",
        "### Latest Indicators",
        "| MA20 | MA50 | MA200 | RSI14 | MACD | MACD signal | MACD hist | BB upper | BB middle | BB lower | ATR14 |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
        "| "
        + " | ".join(
            _fmt_num(v)
            for v in [
                ind.ma20,
                ind.ma50,
                ind.ma200,
                ind.rsi14,
                ind.macd,
                ind.macd_signal,
                ind.macd_hist,
                ind.bb_upper,
                ind.bb_middle,
                ind.bb_lower,
                ind.atr14,
            ]
        )
        + " |",
        "",
        "### Recent OHLCV (last 20 sessions)",
    ]
    rows = [
        [
            pt.date.isoformat(),
            _fmt_num(pt.open),
            _fmt_num(pt.high),
            _fmt_num(pt.low),
            _fmt_num(pt.close),
            f"{pt.volume:,}",
        ]
        for pt in p.points[-20:]
    ]
    sub.append(
        _table(["date", "open", "high", "low", "close", "volume"], rows)
    )
    if p.note:
        sub.append(f"_Note: {p.note}_")
    return "\n".join(sub) + "\n"


def render_fundamentals_block(data: AnalysisData) -> str:
    if data.fundamentals is None:
        return "_Fundamentals unavailable._\n"
    f = data.fundamentals
    lines = ["### Quarterly Income (recent 4)"]
    rows = [
        [
            q.period,
            _fmt_num(q.revenue),
            _fmt_num(q.operating_income),
            _fmt_num(q.net_income),
            _fmt_num(q.eps, decimals=3),
            _fmt_num(q.op_margin, pct=True),
        ]
        for q in f.quarters
    ]
    lines.append(
        _table(["period", "revenue", "op_income", "net_income", "eps", "op_margin"], rows)
    )
    if f.annuals:
        lines.append("### Annual Income (recent 3)")
        ann_rows = [
            [
                a.period,
                _fmt_num(a.revenue),
                _fmt_num(a.operating_income),
                _fmt_num(a.net_income),
                _fmt_num(a.eps, decimals=3),
                _fmt_num(a.op_margin, pct=True),
            ]
            for a in f.annuals
        ]
        lines.append(
            _table(
                ["period", "revenue", "op_income", "net_income", "eps", "op_margin"],
                ann_rows,
            )
        )
    r = f.ratios
    lines.append("### Key Ratios (latest from yfinance.info)")
    ratio_rows = [
        ["PE Trailing", _fmt_num(r.pe_trailing)],
        ["PE Forward", _fmt_num(r.pe_forward)],
        ["PBR", _fmt_num(r.pb)],
        ["EV/EBITDA", _fmt_num(r.ev_ebitda)],
        ["EV/Sales", _fmt_num(r.ev_sales)],
        ["ROE", _fmt_num(r.roe, pct=True)],
        ["Debt/Equity", _fmt_num(r.debt_to_equity)],
        ["Current Ratio", _fmt_num(r.current_ratio)],
        ["Dividend Yield", _fmt_num(r.dividend_yield, pct=True)],
        ["Payout Ratio", _fmt_num(r.payout_ratio, pct=True)],
    ]
    lines.append(_table(["metric", "value"], ratio_rows))

    lines.append(
        f"_Cash: {_fmt_num(f.cash)} | Total Debt: {_fmt_num(f.total_debt)}_"
    )
    if f.note:
        lines.append(f"_Note: {f.note}_")
    return "\n".join(lines) + "\n"


def render_news_block(data: AnalysisData) -> str:
    if data.news is None or not data.news.items:
        if data.news and data.news.note:
            return f"_News unavailable: {data.news.note}_\n"
        return "_No news returned._\n"
    lines = [f"_Provider: {data.news.provider}_"]
    for item in data.news.items[:20]:
        date_str = item.published_at.isoformat() if item.published_at else "n/a"
        src = item.source or "?"
        url = item.url or ""
        lines.append(f"- [{date_str}] **{src}**: {item.title}  \n  {url}")
        if item.summary:
            # one-line snippet
            snippet = item.summary.strip().replace("\n", " ")
            if len(snippet) > 200:
                snippet = snippet[:200] + "…"
            lines.append(f"  _{snippet}_")
    return "\n".join(lines) + "\n"


def render_macro_block(data: AnalysisData) -> str:
    if data.macro is None or data.macro.provider == "none":
        note = (data.macro.note if data.macro else "macro unavailable")
        return f"_Macro unavailable: {note}_\n"
    m = data.macro
    rows: list[list[str]] = []
    for ind in [m.fed_funds_rate, m.ust_10y, m.dxy, m.vix]:
        if ind is None:
            continue
        rows.append(
            [
                ind.label,
                ind.latest_date.isoformat() if ind.latest_date else "n/a",
                _fmt_num(ind.latest_value, decimals=2),
                _fmt_num(ind.change_3m, decimals=2),
                _fmt_num(ind.change_6m, decimals=2),
            ]
        )
    return _table(["indicator", "as_of", "latest", "Δ3m", "Δ6m"], rows) + "\n"


def render_errors_block(data: AnalysisData) -> str:
    if not data.errors:
        return ""
    return "_Data fetch errors:_\n" + "\n".join(f"- {err}" for err in data.errors) + "\n"


def render_full_context(data: AnalysisData) -> str:
    """The full markdown payload passed to an analyst agent."""
    sections = [
        "# Analysis Context",
        f"**Asset**: {data.asset.ticker} ({data.asset.name or '?'})",
        "",
        "## Asset Metadata",
        render_asset_block(data),
        "## Price Series",
        render_prices_block(data),
        "## Fundamentals",
        render_fundamentals_block(data),
        "## Recent News",
        render_news_block(data),
        "## Macro Snapshot",
        render_macro_block(data),
        render_errors_block(data),
    ]
    return "\n".join(sections)


def render_agent_outputs_for_reviewer(
    data: AnalysisData,
    fundamental: FundamentalOutput | None,
    technical: TechnicalOutput | None,
    industry: IndustryOutput | None = None,
    macro: MacroOutput | None = None,
    sentiment: SentimentOutput | None = None,
) -> str:
    """Bundle the analyst JSON outputs (as a single context block) for the reviewer."""
    sections: list[str] = ["# Upstream Agent Outputs"]
    for label, model in [
        ("Fundamental", fundamental),
        ("Technical", technical),
        ("Industry", industry),
        ("Macro", macro),
        ("Sentiment", sentiment),
    ]:
        sections.append(f"## {label} Output (JSON)")
        sections.append("```json")
        sections.append(model.model_dump_json(indent=2) if model else "null")
        sections.append("```")
        sections.append("")
    sections.append("# Original Data Context")
    sections.append(render_full_context(data))
    return "\n".join(sections)


def safe_json_loads(text: str) -> Any:
    """Tolerant JSON parser — strips common LLM artifacts like code fences."""
    s = text.strip()
    if s.startswith("```"):
        # Drop first fence line
        s = s.split("\n", 1)[1] if "\n" in s else s
        if s.endswith("```"):
            s = s.rsplit("```", 1)[0]
        s = s.strip()
    # Some models prefix 'json' label after fence
    if s.lower().startswith("json"):
        s = s[4:].lstrip(":\n ")
    return json.loads(s)
