"""
agents/research_agent.py
------------------------
Agent 1 — Research Agent.

Responsibilities:
  1. Web-search best architecture, libraries, pitfalls, and folder structure.
  2. Generate a structured Implementation Guide via Groq LLM.
  3. Handle user comments (regenerate) or EDIT (store human paste directly).
  4. Store final guide + parsed artefacts in AgentState.
  5. HITL gate after every guide generation: APPROVE / REJECT / EDIT.

LLM  : Groq  llama-3.3-70b-versatile
Tools: web_search  (tools/search_tools.py)
UI   : AgentUI     (ui/terminal_ui.py)
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import textwrap
from copy import deepcopy
from pathlib import Path

# ── project root on path ───────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(_ROOT.parent / ".env")       # f:\Projects\multi-agent-system-for-cording\.env
load_dotenv(_ROOT / ".env", override=False)  # fallback: multi-agent-system/.env

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from rich.markdown import Markdown
from rich.panel import Panel

from graph.state import AgentState
from tools.search_tools import web_search
from ui.terminal_ui import AgentUI, AQUA, YELLOW, GREEN, RED, WHITE, DIM_CYAN

# ── shared UI ──────────────────────────────────────────────────────────────────
ui = AgentUI()

# ── LLM setup ─────────────────────────────────────────────────────────────────
_GROQ_MODEL = "llama-3.3-70b-versatile"
_llm = None

def _get_llm():
    """Lazy-initialise the Groq LLM. Returns None if key is missing/invalid."""
    global _llm
    if _llm is not None:
        return _llm
    key = os.getenv("GROQ_API_KEY", "")
    if not key or key == "your_groq_key_here":
        ui.console.print(
            f"  [bold {YELLOW}]WARN:[/] GROQ_API_KEY not set — "
            "running in MOCK mode (no LLM calls)."
        )
        return None
    try:
        from langchain_groq import ChatGroq
        _llm = ChatGroq(model=_GROQ_MODEL, temperature=0.3, api_key=key)
        return _llm
    except Exception as exc:
        ui.show_error(f"Failed to initialise Groq LLM: {exc}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# Guide section template
# ══════════════════════════════════════════════════════════════════════════════

_GUIDE_SYSTEM_PROMPT = textwrap.dedent("""\
    You are a senior software architect. Given a project description and
    web-research results, produce a comprehensive Implementation Guide in
    Markdown with EXACTLY these sections (use the exact headings):

    ## Project Overview
    ## Recommended Libraries
    ## Folder Structure
    ## Implementation Steps
    ## Potential Challenges & Solutions
    ## Estimated Complexity

    Rules:
    - Recommended Libraries: include pip install commands and a one-sentence
      reason for each choice.
    - Folder Structure: render as an ASCII tree.
    - Implementation Steps: numbered, detailed (5-10 steps).
    - Estimated Complexity: rate each component as Low / Medium / High.
    - Be specific, opinionated, and production-ready.
    - If the user has left comments/feedback, incorporate them.
""")


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _extract_folder_structure(guide: str) -> str:
    """Pull the ASCII tree out of the Folder Structure section."""
    match = re.search(
        r"## Folder Structure\s*\n(.*?)(?=\n##|\Z)",
        guide,
        re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def _extract_libraries(guide: str) -> list[str]:
    """Extract Python package specs from the Recommended Libraries section.

    Strategy: a bullet line whose *first* backtick token is a valid package
    name is a library entry. We take only that first token.
    Also captures bare ``pip install <pkg>`` lines.

    Valid package name: 2+ chars, alphanumeric + hyphens/underscores,
    optionally followed by extras [extra] or version specifier >=x.y.
    """
    match = re.search(
        r"## Recommended Libraries\s*\n(.*?)(?=\n##|\Z)",
        guide,
        re.DOTALL,
    )
    if not match:
        return []
    block = match.group(1)

    # Prose words that look like package names but aren't
    _PROSE = {
        "modern", "fast", "simple", "secure", "async", "sync",
        "standard", "library", "python", "support", "using",
        "this", "that", "with", "for", "and", "the",
    }
    # pattern: valid package spec token
    _PKG_RE = re.compile(
        r"^[a-zA-Z][a-zA-Z0-9_\-]+(\[\w+\])?([><=!~]{1,2}[\w\.\*]+)?$"
    )

    libs: list[str] = []
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # ── Format 1: pip install <pkg> [pkg2 ...] ────────────────────────
        if "pip install" in stripped:
            after = stripped[stripped.index("pip install") + 11:].strip()
            # Strip trailing description (after '—', ' - ', or '#')
            for sep in (" — ", " -- ", " - ", " # "):
                if sep in after:
                    after = after[:after.index(sep)]
            for p in after.split():
                p = p.strip("',\"`")
                if p and not p.startswith("-") and _PKG_RE.match(p):
                    libs.append(p)
            continue

        # ── Format 2: bullet whose first `backtick` token is the package ──
        # Strip leading bullet markers
        core = re.sub(r"^[\-\*\+]\s*", "", stripped)
        # The FIRST backtick-wrapped token must be at position 0 of core
        first_bt = re.match(r"`([^`]+)`", core)
        if first_bt:
            token = first_bt.group(1).strip()
            if (
                _PKG_RE.fullmatch(token)
                and token.lower() not in _PROSE
                and len(token) >= 4
            ):
                libs.append(token)

    # De-duplicate while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for p in libs:
        if p not in seen:
            seen.add(p)
            result.append(p)
    return result


def _print_guide(guide: str) -> None:
    """Render the guide as a Rich Markdown panel with Aqua border."""
    ui.console.print(
        Panel(
            Markdown(guide),
            title=f"[bold {AQUA}]Implementation Guide[/]",
            border_style=AQUA,
            expand=True,
            padding=(1, 2),
        )
    )


def _mock_guide(task: str, comments: list[str]) -> str:
    """Return a realistic-looking guide without an LLM (for offline testing)."""
    comment_note = ""
    if comments:
        comment_note = "\n> **User comments incorporated:** " + "; ".join(comments) + "\n"

    return textwrap.dedent(f"""\
        ## Project Overview
        {comment_note}
        Build a production-ready solution for: **{task}**

        This guide covers architecture decisions, library choices, folder
        organisation, and step-by-step implementation instructions.

        ## Recommended Libraries

        - `pip install fastapi>=0.110` — High-performance async web framework
          with automatic OpenAPI docs.
        - `pip install uvicorn[standard]>=0.29` — ASGI server; best pairing
          with FastAPI.
        - `pip install sqlalchemy>=2.0` — Modern async ORM for database access.
        - `pip install alembic>=1.13` — Database migration tool for SQLAlchemy.
        - `pip install python-jose[cryptography]>=3.3` — JWT token creation
          and verification for auth.
        - `pip install passlib[bcrypt]>=1.7` — Secure password hashing.
        - `pip install pydantic>=2.6` — Data validation and settings management.
        - `pip install pytest>=8.0 pytest-asyncio>=0.23` — Async-aware test suite.

        ## Folder Structure

        ```
        project/
        ├── app/
        │   ├── __init__.py
        │   ├── main.py            # FastAPI app factory
        │   ├── core/
        │   │   ├── config.py      # Settings (Pydantic BaseSettings)
        │   │   └── security.py    # JWT + hashing helpers
        │   ├── api/
        │   │   ├── __init__.py
        │   │   └── v1/
        │   │       ├── auth.py    # /auth/register, /auth/login
        │   │       └── users.py   # /users/me, /users/{{id}}
        │   ├── models/
        │   │   └── user.py        # SQLAlchemy User model
        │   ├── schemas/
        │   │   └── user.py        # Pydantic request/response schemas
        │   └── db/
        │       ├── base.py        # declarative_base
        │       └── session.py     # async engine + get_db dependency
        ├── alembic/               # migration scripts
        ├── tests/
        │   ├── conftest.py
        │   ├── test_auth.py
        │   └── test_users.py
        ├── .env
        ├── requirements.txt
        └── README.md
        ```

        ## Implementation Steps

        1. **Scaffold the project** — create the folder structure above and
           initialise a virtual environment.
        2. **Configure settings** — implement `app/core/config.py` using
           Pydantic `BaseSettings` to load DATABASE_URL, SECRET_KEY, etc.
        3. **Set up the database** — create `app/db/session.py` with an async
           SQLAlchemy engine and `get_db` dependency; run `alembic init`.
        4. **Define the User model** — create `app/models/user.py` with id,
           email (unique), hashed_password, is_active, created_at fields.
        5. **Add Pydantic schemas** — UserCreate, UserRead, Token schemas in
           `app/schemas/user.py`.
        6. **Implement security helpers** — `app/core/security.py`: bcrypt
           hashing, JWT creation (`create_access_token`), and verification.
        7. **Build auth endpoints** — `POST /auth/register` and
           `POST /auth/login` returning a Bearer token.
        8. **Build user endpoints** — `GET /users/me` (protected),
           `GET /users/{{id}}` (admin-only).
        9. **Write tests** — use `pytest-asyncio` with an in-memory SQLite
           database; cover happy-paths and error cases.
        10. **Document & containerise** — update README, add a `Dockerfile`
            and `docker-compose.yml` for local development.

        ## Potential Challenges & Solutions

        | Challenge | Solution |
        |-----------|----------|
        | Async SQLAlchemy session management | Use `AsyncSession` with a
          per-request dependency and `expire_on_commit=False` |
        | JWT token refresh | Implement short-lived access tokens (15 min) +
          long-lived refresh tokens (7 days) stored in HttpOnly cookies |
        | Password reset flow | Send signed, time-limited URLs via email
          (use `itsdangerous`) |
        | Database migrations in production | Use `alembic upgrade head` in
          a startup hook or CI/CD step |
        | Test isolation | Reset DB state between tests using transactions
          that are rolled back after each test |

        ## Estimated Complexity

        | Component | Complexity | Notes |
        |-----------|------------|-------|
        | Project scaffold | Low | Boilerplate only |
        | Database layer | Medium | Async SQLAlchemy has nuances |
        | Auth (JWT) | Medium | Standard pattern, library handles crypto |
        | API endpoints | Low | FastAPI makes routing trivial |
        | Tests | Medium | Async test fixtures need care |
        | Containerisation | Low | Standard Dockerfile pattern |
    """)


# ══════════════════════════════════════════════════════════════════════════════
# Core: generate implementation guide
# ══════════════════════════════════════════════════════════════════════════════

async def _generate_guide(task: str, research: str, comments: list[str]) -> str:
    """
    Call the Groq LLM to produce the Implementation Guide.
    Falls back to _mock_guide() when no API key is configured.
    """
    llm = _get_llm()
    if llm is None:
        ui.show_reasoning("No Groq API key — using mock guide generator.")
        return _mock_guide(task, comments)

    comment_block = ""
    if comments:
        comment_block = (
            "\n\nThe user reviewed a previous draft and left these comments:\n"
            + "\n".join(f"  - {c}" for c in comments)
            + "\n\nPlease incorporate all of them in the new guide."
        )

    messages = [
        SystemMessage(content=_GUIDE_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"Project task: {task}\n\n"
                f"Web research results:\n{research}{comment_block}"
            )
        ),
    ]

    ui.show_reasoning("Sending research results to Groq LLM for guide generation…")
    try:
        response = await llm.ainvoke(messages)
        return response.content
    except Exception as exc:
        ui.show_error(f"LLM call failed: {exc}")
        ui.show_reasoning("Falling back to mock guide.")
        return _mock_guide(task, comments)


# ══════════════════════════════════════════════════════════════════════════════
# Core: run web research phase
# ══════════════════════════════════════════════════════════════════════════════

async def _run_research(task: str) -> str:
    """
    Run four targeted web searches and concatenate results.
    Returns a single research blob passed to the LLM.
    """
    queries = [
        f"{task} architecture patterns best practices",
        f"{task} Python libraries 2024 recommended",
        f"{task} common pitfalls mistakes to avoid",
        f"{task} project folder structure Python",
    ]

    results: list[str] = []
    for q in queries:
        ui.show_reasoning(f"Searching: {q!r}")
        try:
            # web_search is a sync LangChain @tool — run in thread pool
            raw = await asyncio.get_event_loop().run_in_executor(
                None, lambda _q=q: web_search.invoke({"query": _q})
            )
            results.append(f"### Query: {q}\n{raw}")
        except Exception as exc:
            ui.show_reasoning(f"Search failed ({exc}) — skipping.")

    return "\n\n---\n\n".join(results)


# ══════════════════════════════════════════════════════════════════════════════
# HITL loop
# ══════════════════════════════════════════════════════════════════════════════

async def _hitl_loop(
    task: str,
    research: str,
    initial_comments: list[str],
) -> tuple[str, list[str]]:
    """
    Generate guide → show to user → loop until APPROVE or EDIT.

    Returns (final_guide, accumulated_comments).
    """
    comments: list[str] = list(initial_comments)
    iteration = 0

    while True:
        iteration += 1
        ui.show_step(
            "RESEARCH",
            f"Generating Implementation Guide (attempt {iteration})…",
        )

        guide = await _generate_guide(task, research, comments)

        ui.console.print()
        _print_guide(guide)
        ui.console.print()

        # ── HITL gate ──────────────────────────────────────────────────────
        decision, edited_value = ui.request_approval(
            "RESEARCH GUIDE",
            "Approve this implementation guide?\n"
            "  APPROVE = accept and hand off to Coding Agent\n"
            "  REJECT  = tell us what to change (guide will be regenerated)\n"
            "  EDIT    = paste your own edited guide directly",
            allow_edit=True,
        )

        if decision == "APPROVE":
            ui.show_success("Implementation Guide approved — moving to Coding Agent.")
            return guide, comments

        elif decision == "EDIT":
            if edited_value and edited_value.strip():
                ui.show_success("Using human-edited guide — skipping regeneration.")
                return edited_value.strip(), comments
            else:
                ui.show_error("Empty edit — falling back to current guide.")
                return guide, comments

        else:  # REJECT
            ui.console.print(
                f"  [{YELLOW}]What should be changed? "
                "(Press Enter when done):[/]"
            )
            feedback = ui.console.input(
                f"  [bold {AQUA}]Feedback > [/]"
            ).strip()
            if feedback:
                comments.append(feedback)
                ui.show_reasoning(f"Feedback noted: {feedback!r} — regenerating…")
            else:
                ui.show_reasoning("No feedback provided — regenerating with same params.")


# ══════════════════════════════════════════════════════════════════════════════
# Public agent entry point
# ══════════════════════════════════════════════════════════════════════════════

async def research_agent(state: AgentState) -> AgentState:
    """
    LangGraph node — Research Agent.

    Reads:  state["task"], state["research_comments"]
    Writes: state["research_guide"], state["folder_structure"],
            state["suggested_libraries"], state["current_agent"],
            state["step_log"], state["hitl_decision"],
            state["hitl_edit_value"], state["messages"]
    """
    new_state: AgentState = deepcopy(state)
    new_state["current_agent"] = "RESEARCH"

    task        = state.get("task", "").strip()
    comments    = list(state.get("research_comments") or [])
    step_log    = list(state.get("step_log") or [])
    messages    = list(state.get("messages") or [])

    if not task:
        new_state["error"] = "Research Agent: task is empty."
        return new_state

    ui.console.rule(
        f"[bold {AQUA}]Research Agent — Starting[/]", style=AQUA
    )
    step_log.append(f"[RESEARCH] Task received: {task!r}")

    # ── Phase 1: web research ──────────────────────────────────────────────
    ui.show_step("RESEARCH", "Phase 1 — Running web research")
    research_blob = await _run_research(task)
    step_log.append("[RESEARCH] Web research completed.")

    # ── Phase 2: HITL guide generation loop ───────────────────────────────
    ui.show_step("RESEARCH", "Phase 2 — Generating Implementation Guide")
    guide, final_comments = await _hitl_loop(task, research_blob, comments)

    # ── Phase 3: parse artefacts out of the guide ─────────────────────────
    folder_structure   = _extract_folder_structure(guide)
    suggested_libraries = _extract_libraries(guide)

    step_log.append(
        f"[RESEARCH] Guide approved. "
        f"Libraries: {suggested_libraries}. "
        f"Comments applied: {final_comments}"
    )

    # ── Update messages (append the guide as an AI turn) ──────────────────
    messages.append(HumanMessage(content=f"Project task: {task}"))
    messages.append(AIMessage(content=guide))

    # ── Write back to state ────────────────────────────────────────────────
    new_state["research_guide"]      = guide
    new_state["research_comments"]   = final_comments
    new_state["folder_structure"]    = folder_structure
    new_state["suggested_libraries"] = suggested_libraries
    new_state["step_log"]            = step_log
    new_state["messages"]            = messages
    new_state["current_agent"]       = "IDLE"
    new_state["error"]               = None
    new_state["hitl_decision"]       = None
    new_state["hitl_edit_value"]     = None
    new_state["pending_approval"]    = None

    ui.console.rule(
        f"[bold {GREEN}]Research Agent — Complete[/]", style=GREEN
    )
    return new_state


# ══════════════════════════════════════════════════════════════════════════════
# Standalone test
# ══════════════════════════════════════════════════════════════════════════════

async def test_research_agent(task: str) -> None:
    """Run the Research Agent standalone with a minimal initial state."""
    from langchain_core.messages import HumanMessage as HM

    ui.console.rule(
        f"[bold {AQUA}]Research Agent — Standalone Test[/]", style=AQUA
    )
    ui.console.print(f"  [bold {AQUA}]Task:[/] {task}\n")

    initial_state: AgentState = {
        "messages":           [HM(content=task)],
        "task":               task,
        "research_guide":     "",
        "research_comments":  [],
        "folder_structure":   "",
        "suggested_libraries": [],
        "generated_files":    {},
        "current_agent":      "IDLE",
        "terminal_output":    [],
        "test_results":       "",
        "final_report":       "",
        "error":              None,
        "step_log":           [],
        "hitl_decision":      None,
        "hitl_edit_value":    None,
        "pending_approval":   None,
    }

    final_state = await research_agent(initial_state)

    # ── Print summary ──────────────────────────────────────────────────────
    ui.console.print()
    ui.console.rule(f"[bold {AQUA}]Final State Summary[/]", style=AQUA)

    ui.console.print(
        f"\n  [bold {AQUA}]Folder Structure:[/]\n"
        + "\n".join(
            f"    {line}"
            for line in (final_state["folder_structure"] or "(none)").splitlines()
        )
    )

    libs = final_state["suggested_libraries"]
    ui.console.print(
        f"\n  [bold {AQUA}]Suggested Libraries ({len(libs)}):[/]  "
        + ",  ".join(libs[:8])
        + ("  …" if len(libs) > 8 else "")
    )

    logs = final_state["step_log"]
    ui.console.print(f"\n  [bold {AQUA}]Step Log ({len(logs)} entries):[/]")
    for entry in logs:
        ui.console.print(f"    [{DIM_CYAN}]{entry}[/]")

    err = final_state.get("error")
    if err:
        ui.show_error(f"Agent returned error: {err}")
    else:
        ui.show_success("Research Agent test completed successfully!")

    ui.console.print()
    ui.show_hitl_summary()
    ui.console.rule(f"[bold {AQUA}]Test Complete[/]", style=AQUA)


if __name__ == "__main__":
    asyncio.run(
        test_research_agent("Build a REST API with user authentication")
    )
