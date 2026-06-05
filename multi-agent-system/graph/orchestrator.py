"""
graph/orchestrator.py
---------------------
LangGraph StateGraph that wires the 3 agents together using proper
interrupt() / Command(resume=...) mechanics with MemorySaver checkpointing.
"""

from __future__ import annotations

import asyncio
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

from graph.state import AgentState
from agents.research_agent import research_agent
from agents.coding_agent import coding_agent
from agents.testing_agent import testing_agent
from ui.terminal_ui import AgentUI, AQUA, YELLOW, GREEN, RED

ui = AgentUI()

# ══════════════════════════════════════════════════════════════════════════════
# Interrupt Nodes — these PAUSE the graph and hand control back to the runner
# ══════════════════════════════════════════════════════════════════════════════

def await_guide(state: AgentState) -> dict:
    """Pause graph for human review of the Research Guide."""
    ui.show_step("SYSTEM", "Graph paused: Awaiting review of Research Guide")
    guide = state.get("research_guide", "No guide generated.")
    interrupt({
        "gate": "RESEARCH GUIDE",
        "details": guide,
        "allow_edit": True,
        "action_desc": (
            "APPROVE → hand off to Coding Agent\n"
            "REJECT  → provide feedback and regenerate\n"
            "EDIT    → paste your own guide directly"
        ),
    })
    return {}


def await_run(state: AgentState) -> dict:
    """Pause graph before running tests."""
    ui.show_step("SYSTEM", "Graph paused: Awaiting approval to run the project")
    interrupt({
        "gate": "RUN PROJECT",
        "details": (
            "The Coding Agent has finished generating all files.\n"
            "Approve to hand off to the Testing Agent."
        ),
        "allow_edit": False,
        "action_desc": (
            "APPROVE → pass to Testing Agent\n"
            "REJECT  → abort the pipeline"
        ),
    })
    return {}


def await_report(state: AgentState) -> dict:
    """Pause graph for human review of the Final QA Report."""
    ui.show_step("SYSTEM", "Graph paused: Awaiting review of Final QA Report")
    report = state.get("final_report", "No report generated yet.")
    interrupt({
        "gate": "FINAL REPORT REVIEW",
        "details": report[:800],
        "allow_edit": True,
        "action_desc": (
            "APPROVE → mark pipeline as complete\n"
            "EDIT    → adjust the report manually\n"
            "REJECT  → run the Testing Agent again"
        ),
    })
    return {}


def error_handler(state: AgentState) -> dict:
    """Handle fatal errors or user rejections."""
    err = state.get("error") or "Operation aborted by user."
    ui.show_error(f"Pipeline aborted: {err}")
    return {"current_agent": "ERROR"}


def complete(state: AgentState) -> dict:
    """Print the final success summary."""
    ui.show_success(
        "Pipeline complete! All agents finished successfully."
    )
    return {"current_agent": "COMPLETE"}


# ══════════════════════════════════════════════════════════════════════════════
# Conditional edge routers — read hitl_decision set by the runner
# ══════════════════════════════════════════════════════════════════════════════

def route_after_guide(state: AgentState) -> str:
    decision = (state.get("hitl_decision") or "").upper()
    if decision in ("APPROVE", "EDIT"):
        return "coding"
    return "research"          # REJECT → regenerate


def route_after_run(state: AgentState) -> str:
    decision = (state.get("hitl_decision") or "").upper()
    if decision == "APPROVE":
        return "testing"
    return "error_handler"


def route_after_report(state: AgentState) -> str:
    decision = (state.get("hitl_decision") or "").upper()
    if decision in ("APPROVE", "EDIT"):
        return "complete"
    return "testing"           # REJECT → run tests again


# ══════════════════════════════════════════════════════════════════════════════
# Graph construction
# ══════════════════════════════════════════════════════════════════════════════

_workflow = StateGraph(AgentState)

_workflow.add_node("research",      research_agent)
_workflow.add_node("await_guide",   await_guide)
_workflow.add_node("coding",        coding_agent)
_workflow.add_node("await_run",     await_run)
_workflow.add_node("testing",       testing_agent)
_workflow.add_node("await_report",  await_report)
_workflow.add_node("error_handler", error_handler)
_workflow.add_node("complete",      complete)

_workflow.add_edge(START, "research")
_workflow.add_edge("research", "await_guide")

_workflow.add_conditional_edges(
    "await_guide", route_after_guide,
    {"coding": "coding", "research": "research"},
)

_workflow.add_edge("coding", "await_run")

_workflow.add_conditional_edges(
    "await_run", route_after_run,
    {"testing": "testing", "error_handler": "error_handler"},
)

_workflow.add_edge("testing", "await_report")

_workflow.add_conditional_edges(
    "await_report", route_after_report,
    {"complete": "complete", "testing": "testing"},
)

_workflow.add_edge("error_handler", END)
_workflow.add_edge("complete", END)

_memory = MemorySaver()
graph = _workflow.compile(checkpointer=_memory)


# ══════════════════════════════════════════════════════════════════════════════
# Public runner
# ══════════════════════════════════════════════════════════════════════════════

async def run_pipeline(task: str) -> AgentState:
    """
    Stream the graph from start to finish, pausing at every interrupt()
    node to collect human decisions via AgentUI.request_approval().
    """
    thread_id = "pipeline-run"
    config = {"configurable": {"thread_id": thread_id}}

    initial_input: AgentState | None = {
        "messages": [],
        "task": task,
        "research_guide": "",
        "research_comments": [],
        "folder_structure": "",
        "suggested_libraries": [],
        "generated_files": {},
        "current_agent": "IDLE",
        "terminal_output": [],
        "test_results": "",
        "final_report": "",
        "error": None,
        "step_log": [],
        "hitl_decision": None,
        "hitl_edit_value": None,
        "pending_approval": None,
    }

    while True:
        # ── stream until the graph pauses or finishes ──────────────────────
        input_to_send = initial_input  # None after the first pass
        async for _event in graph.astream(input_to_send, config, stream_mode="updates"):
            pass                       # agents print their own rich UI

        # After the stream drains, check the graph's checkpoint state
        snapshot = graph.get_state(config)

        # ── finished? ──────────────────────────────────────────────────────
        if not snapshot.next:
            return snapshot.values

        # ── interrupted? ───────────────────────────────────────────────────
        interrupts_found = False
        for task_obj in snapshot.tasks:
            if not task_obj.interrupts:
                continue
            interrupts_found = True

            payload  = task_obj.interrupts[0].value
            gate     = payload.get("gate", "APPROVAL REQUIRED")
            details  = payload.get("details", "")
            allow_ed = payload.get("allow_edit", False)
            desc     = payload.get("action_desc", "")

            # Build the detail string shown in the Rich panel
            display_details = f"{desc}\n\n{details}" if desc else details

            # Show the panel and collect the decision
            decision, edited = ui.request_approval(gate, display_details, allow_edit=allow_ed)

            # Build the state patch
            updates: dict = {
                "hitl_decision":   decision,
                "hitl_edit_value": edited,
            }

            if gate == "RESEARCH GUIDE":
                if decision == "EDIT" and edited:
                    updates["research_guide"] = edited
                elif decision == "REJECT":
                    feedback = ui.console.input(
                        f"  [bold {AQUA}]What should be changed? > [/]"
                    ).strip()
                    existing = list(snapshot.values.get("research_comments") or [])
                    existing.append(feedback)
                    updates["research_comments"] = existing
                    updates["hitl_decision"] = "REJECT"

            elif gate == "FINAL REPORT REVIEW":
                if decision == "EDIT" and edited:
                    updates["final_report"] = edited

            # Patch the checkpoint state
            graph.update_state(config, updates, as_node=task_obj.name)

            # Resume from the interrupt — passes `True` as the interrupt's
            # return value and re-enters the graph at the paused node
            initial_input = Command(resume=True)
            break   # handle one interrupt per loop iteration

        if not interrupts_found:
            # No interrupt found but graph still has next nodes — safety exit
            ui.show_error("Graph stalled — no interrupt found but not finished.")
            return graph.get_state(config).values
