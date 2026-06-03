"""
tools/search_tools.py
---------------------
Web search tools for the Research Agent.
Uses DuckDuckGo (no API key) as primary, Tavily as optional fallback.
Read-only operations — no HITL approval needed.
"""

from __future__ import annotations

import os
import sys
import concurrent.futures
from typing import Any

# ── path fix so sibling packages resolve when run directly ─────────────────────
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
from langchain_core.tools import tool

from ui.terminal_ui import AgentUI

load_dotenv()

# ── shared UI instance ─────────────────────────────────────────────────────────
ui = AgentUI()

# ── Tavily client (optional) ───────────────────────────────────────────────────
_tavily_client: Any | None = None
if os.getenv("TAVILY_API_KEY"):
    try:
        from tavily import TavilyClient
        _tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    except Exception:
        _tavily_client = None


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _ddg_search(query: str, max_results: int = 5) -> list[dict]:
    """Run a DuckDuckGo text search and return raw result dicts."""
    from ddgs import DDGS
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))


def _format_ddg_results(results: list[dict]) -> str:
    """Format DuckDuckGo result dicts into a readable string."""
    if not results:
        return "No results found."
    lines: list[str] = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "No title")
        href  = r.get("href",  "")
        body  = r.get("body",  "").strip()[:200]
        lines.append(f"{i}. {title}\n   URL: {href}\n   {body}")
    return "\n\n".join(lines)


def _tavily_search(query: str) -> str:
    """Run a Tavily search (only called when client is available)."""
    if _tavily_client is None:
        return ""
    try:
        resp = _tavily_client.search(query=query, max_results=5)
        results = resp.get("results", [])
        lines: list[str] = []
        for i, r in enumerate(results, 1):
            title   = r.get("title",   "")
            url     = r.get("url",     "")
            content = r.get("content", "").strip()[:200]
            lines.append(f"{i}. {title}\n   URL: {url}\n   {content}")
        return "\n\n".join(lines)
    except Exception as exc:
        return f"[Tavily error: {exc}]"


# ══════════════════════════════════════════════════════════════════════════════
# Tool 1 — web_search
# ══════════════════════════════════════════════════════════════════════════════

@tool
def web_search(query: str) -> str:
    """
    Search the web for a query and return the top 5 results.

    Uses DuckDuckGo as the primary source. If TAVILY_API_KEY is set in .env,
    Tavily results are appended for extra depth. No API key required for
    basic usage.

    Args:
        query: The search query string.

    Returns:
        A formatted string with up to 5 result snippets.
    """
    ui.show_tool_call("web_search", query)

    output_parts: list[str] = []

    # ── DuckDuckGo ─────────────────────────────────────────────────────────
    try:
        ddg_results = _ddg_search(query, max_results=5)
        ddg_text = _format_ddg_results(ddg_results)
        output_parts.append(f"[DuckDuckGo]\n{ddg_text}")
    except Exception as exc:
        output_parts.append(f"[DuckDuckGo error: {exc}]")

    # ── Tavily (optional) ──────────────────────────────────────────────────
    if _tavily_client is not None:
        tav_text = _tavily_search(query)
        if tav_text:
            output_parts.append(f"[Tavily]\n{tav_text}")

    combined = "\n\n" + ("─" * 40) + "\n\n".join(output_parts)
    ui.show_result(combined[:1200])  # cap display length
    return combined


# ══════════════════════════════════════════════════════════════════════════════
# Tool 2 — deep_search
# ══════════════════════════════════════════════════════════════════════════════

@tool
def deep_search(query: str) -> str:
    """
    Run 3 parallel DuckDuckGo searches with query variations and merge results.

    Generates three query variants (original, "best practices", "tutorial") and
    runs them concurrently, then deduplicates and merges all results.

    Args:
        query: The base search query.

    Returns:
        A merged, deduplicated string of search result snippets.
    """
    variants = [
        query,
        f"{query} best practices",
        f"{query} tutorial guide 2024",
    ]

    ui.show_tool_call("deep_search", f"{query!r}  [3 parallel queries]")

    all_results: list[dict] = []
    seen_urls: set[str] = set()

    def _fetch(q: str) -> list[dict]:
        try:
            return _ddg_search(q, max_results=5)
        except Exception:
            return []

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_fetch, v): v for v in variants}
        for fut in concurrent.futures.as_completed(futures):
            for item in fut.result():
                url = item.get("href", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(item)

    combined = _format_ddg_results(all_results[:10])  # top 10 de-duped
    ui.show_result(f"deep_search: {len(all_results)} unique results found.\n\n{combined[:1200]}")
    return combined


# ══════════════════════════════════════════════════════════════════════════════
# Quick test
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    from rich.rule import Rule
    from ui.terminal_ui import AQUA

    ui.console.rule(
        f"[bold {AQUA}]search_tools.py  --  Quick Test[/]", style=AQUA
    )
    ui.console.print()

    # Test 1: basic web search
    ui.show_step("RESEARCH", "Running web_search test")
    result1 = web_search.invoke({"query": "LangGraph multi-agent tutorial 2024"})
    ui.console.print(f"  [dim]Returned {len(result1)} characters[/]\n")

    # Test 2: deep search
    ui.show_step("RESEARCH", "Running deep_search test")
    result2 = deep_search.invoke({"query": "Python code generation with LLM"})
    ui.console.print(f"  [dim]Returned {len(result2)} characters[/]\n")

    ui.show_success("search_tools.py — all tests passed!")
    ui.console.rule(f"[bold {AQUA}]Test Complete[/]", style=AQUA)
