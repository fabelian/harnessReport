"""Load prompt markdown files from `app/prompts/` with simple caching."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class PromptNotFound(FileNotFoundError):
    """Raised when a referenced prompt file does not exist."""


@lru_cache(maxsize=64)
def load(relative_path: str) -> str:
    """Read a prompt markdown file relative to `app/prompts/`.

    Example: `load("system/fundamental.md")`
    """
    path = (PROMPTS_DIR / relative_path).resolve()
    if not path.is_file():
        raise PromptNotFound(f"prompt not found: {relative_path} (looked at {path})")
    if PROMPTS_DIR not in path.parents and path != PROMPTS_DIR:
        # Defensive — prevent path-traversal escapes via "../"
        raise PromptNotFound(f"prompt path escapes prompts dir: {relative_path}")
    return path.read_text(encoding="utf-8")


def compose(system_path: str, *methodology_paths: str) -> str:
    """Concatenate a system prompt with one or more methodology references."""
    system = load(system_path)
    sections = [system]
    for mp in methodology_paths:
        sections.append("\n\n---\n\n# Methodology Reference: " + mp + "\n\n" + load(mp))
    return "\n".join(sections)
