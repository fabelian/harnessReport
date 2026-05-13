"""Verify prompt files load correctly and contain the structural anchors agents rely on."""
from __future__ import annotations

import pytest

from app.utils.prompt_loader import PromptNotFound, compose, load


def test_load_system_prompts() -> None:
    for name in ["system/fundamental.md", "system/technical.md", "system/reviewer.md"]:
        text = load(name)
        assert len(text) > 200, f"prompt {name} is suspiciously short"
        # All system prompts must instruct JSON-only output
        assert "JSON" in text or "json" in text


def test_load_methodology_files() -> None:
    for name in [
        "methodology/citations.md",
        "methodology/valuation.md",
        "methodology/technical.md",
    ]:
        text = load(name)
        assert len(text) > 100


def test_compose_concatenates_with_separator() -> None:
    text = compose("system/fundamental.md", "methodology/valuation.md")
    assert "Methodology Reference: methodology/valuation.md" in text


def test_missing_prompt_raises() -> None:
    with pytest.raises(PromptNotFound):
        load("system/does_not_exist.md")
