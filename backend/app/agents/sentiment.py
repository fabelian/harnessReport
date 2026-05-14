"""Sentiment analyst — produces a `SentimentOutput` from `AnalysisData`."""
from __future__ import annotations

from app.agents.base import AgentRun, BaseAgent, OnStep
from app.schemas.data import AnalysisData
from app.schemas.outputs import SentimentOutput
from app.utils.markdown import render_full_context


class SentimentAgent(BaseAgent):
    role = "sentiment"
    output_schema = SentimentOutput
    system_prompt_path = "system/sentiment.md"
    methodology_paths = ("methodology/sentiment.md", "methodology/citations.md")

    def build_user_prompt(self, data: AnalysisData) -> str:  # type: ignore[override]
        return render_full_context(data)

    async def run(
        self,
        data: AnalysisData,
        *,
        model: str | None = None,
        on_step: OnStep | None = None,
    ) -> AgentRun:
        user_prompt = self.build_user_prompt(data)
        output, result, retried = await self._call_and_parse(
            user_prompt=user_prompt, model=model, on_step=on_step
        )
        return self._build_run(self.role, output, result, retried)
