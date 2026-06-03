"""
graph/state.py
--------------
Shared state schema for the Multi-Agent LangGraph system.
All three agents (Research, Coding, Testing) read from and write to this state.
"""

from __future__ import annotations

from typing import TypedDict
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """
    Central state object that flows through every node in the LangGraph.

    Fields
    ------
    messages : list[BaseMessage]
        Full conversation history (HumanMessage, AIMessage, ToolMessage …).

    task : str
        The user's original project request — never mutated after ingestion.

    research_guide : str
        High-level implementation plan produced by the Research Agent.

    research_comments : list[str]
        Human edits or review comments applied to the research guide
        during a HITL gate (populated when the user chooses EDIT).

    folder_structure : str
        Directory layout proposed by the Research Agent, e.g.:
            my_project/
            ├── src/
            └── tests/

    suggested_libraries : list[str]
        Python packages the Research Agent recommends installing,
        e.g. ["fastapi>=0.110", "sqlalchemy>=2.0"].

    generated_files : dict[str, str]
        Mapping of  { relative_file_path -> full_file_content }
        populated incrementally by the Coding Agent.

    current_agent : str
        Name of the agent currently executing, one of:
        "RESEARCH" | "CODING" | "TESTING" | "IDLE".

    terminal_output : list[str]
        Accumulated stdout / stderr lines captured from every shell
        command run by any agent.

    test_results : str
        Raw pytest output (or equivalent) produced by the Testing Agent.

    final_report : str
        Human-readable summary written at the end of a successful run.

    error : str | None
        Set to a non-None string when any agent encounters a fatal error;
        None while the pipeline is healthy.

    step_log : list[str]
        Free-form reasoning trace — each agent appends one entry per
        decision, tool call, or HITL interaction.

    hitl_decision : str | None
        The most recent human decision at a HITL gate:
        "APPROVE" | "REJECT" | "EDIT" | None (not yet decided).

    hitl_edit_value : str | None
        When hitl_decision == "EDIT", holds the human-supplied replacement
        value; None otherwise.

    pending_approval : dict | None
        Describes the item currently waiting at a HITL gate:
        {
            "action_type": str,   # e.g. "FILE WRITE"
            "details":     str,   # exact command / path / snippet
            "allow_edit":  bool,  # whether the EDIT option is offered
        }
        None when no gate is active.
    """

    # ── Conversation ──────────────────────────────────────────────────────
    messages: list[BaseMessage]

    # ── Task definition ───────────────────────────────────────────────────
    task: str

    # ── Research Agent outputs ────────────────────────────────────────────
    research_guide: str
    research_comments: list[str]
    folder_structure: str
    suggested_libraries: list[str]

    # ── Coding Agent outputs ──────────────────────────────────────────────
    generated_files: dict[str, str]

    # ── Runtime tracking ──────────────────────────────────────────────────
    current_agent: str
    terminal_output: list[str]

    # ── Testing Agent outputs ─────────────────────────────────────────────
    test_results: str

    # ── Final summary ─────────────────────────────────────────────────────
    final_report: str

    # ── Error handling ────────────────────────────────────────────────────
    error: str | None

    # ── Observability ─────────────────────────────────────────────────────
    step_log: list[str]

    # ── Human-in-the-Loop (HITL) ──────────────────────────────────────────
    hitl_decision: str | None
    hitl_edit_value: str | None
    pending_approval: dict | None
