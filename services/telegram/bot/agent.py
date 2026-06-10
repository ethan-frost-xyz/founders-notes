"""OpenRouter vault agent: agentic retrieval loop + synthesis (Telegram Librarian)."""

from __future__ import annotations

from agent_core import (
    EMPTY_SYNTHESIS,
    MAX_TOOL_ROUNDS,
    SEARCH_BUDGET_NUDGE,
    TurnResult,
    VaultAgent,
    search_budget_nudge as _search_budget_nudge,
)
from agent_tools import (
    build_trace_summary,
    execute_tool,
    openrouter_tools,
    tool_result_content as _tool_result_content,
)

__all__ = [
    "EMPTY_SYNTHESIS",
    "MAX_TOOL_ROUNDS",
    "SEARCH_BUDGET_NUDGE",
    "TurnResult",
    "VaultAgent",
    "_search_budget_nudge",
    "_tool_result_content",
    "build_trace_summary",
    "execute_tool",
    "openrouter_tools",
]
