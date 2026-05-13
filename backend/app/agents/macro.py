"""Macro analyst — produces a `MacroOutput` from `AnalysisData`."""
from __future__ import annotations

from app.agents.base import AgentRun, BaseAgent
from app.schemas.data import AnalysisData
from app.schemas.outputs import MacroOutput
from app.utils.markdown import render_full_context


class MacroAgent(BaseAgent):
    role = "macro"
    output_schema = MacroOutput
    system_prompt_path = "system/macro.md"
    methodology_paths = ("methodology/macro.md", "methodology/citations.md")

    def build_user_prompt(self, data: AnalysisData) -> str:  # type: ignore[override]
        return render_full_context(data)

    async def run(
        self,
        data: AnalysisData,
        *,
        model: str | None = None,
    ) -> AgentRun:
        user_prompt = self.build_user_prompt(data)
        output, result, retried = await self._call_and_parse(
            user_prompt=user_prompt, model=model
        )
        return self._build_run(self.role, output, result, retried)
