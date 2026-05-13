"""Integrator-reviewer — merges analyst outputs into a final markdown report."""
from __future__ import annotations

from app.agents.base import AgentRun, BaseAgent
from app.schemas.data import AnalysisData
from app.schemas.outputs import (
    FundamentalOutput,
    IndustryOutput,
    MacroOutput,
    ReviewerOutput,
    SentimentOutput,
    TechnicalOutput,
)
from app.utils.markdown import render_agent_outputs_for_reviewer


class ReviewerAgent(BaseAgent):
    role = "reviewer"
    output_schema = ReviewerOutput
    system_prompt_path = "system/reviewer.md"
    methodology_paths = ("methodology/citations.md",)

    # Reviewer produces a longer markdown report
    default_max_tokens: int = 8192

    def build_user_prompt(  # type: ignore[override]
        self,
        data: AnalysisData,
        fundamental: FundamentalOutput | None,
        technical: TechnicalOutput | None,
        industry: IndustryOutput | None = None,
        macro: MacroOutput | None = None,
        sentiment: SentimentOutput | None = None,
    ) -> str:
        return render_agent_outputs_for_reviewer(
            data, fundamental, technical, industry, macro, sentiment
        )

    async def run(
        self,
        data: AnalysisData,
        fundamental: FundamentalOutput | None,
        technical: TechnicalOutput | None,
        industry: IndustryOutput | None = None,
        macro: MacroOutput | None = None,
        sentiment: SentimentOutput | None = None,
        *,
        model: str | None = None,
    ) -> AgentRun:
        user_prompt = self.build_user_prompt(
            data, fundamental, technical, industry, macro, sentiment
        )
        output, result, retried = await self._call_and_parse(
            user_prompt=user_prompt, model=model
        )
        # Stamp the model name back into the structured output for traceability.
        if isinstance(output, ReviewerOutput) and not output.used_model:
            output = output.model_copy(update={"used_model": result.model})
        return self._build_run(self.role, output, result, retried)
