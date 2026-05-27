"""External web search for /web turns (SP3.1: wire Tavily or Brave)."""

from __future__ import annotations

import os
from typing import Any


def web_search(query: str) -> dict[str, Any]:
    """Return search results or an error until a provider is configured."""
    api_key = os.environ.get("WEB_SEARCH_API_KEY", "").strip()
    if not api_key:
        return {"error": "not configured", "query": query}
    return {"error": "provider not implemented", "query": query}
