import asyncio
from typing import Annotated, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt

from graph.state import AgentState
from agents.research_agent import research_agent
from agents.coding_agent import coding_agent
from agents.testing_agent import testing_agent
from ui.terminal_ui import AgentUI, AQUA, YELLOW, GREEN, RED

ui = AgentUI()

# ══════════════════════════════════════════════════════════════════════════════
# Interrupt Nodes
# ══════════════════════════════════════════════════════════════════════════════

def await_guide(state: AgentState):
    """Pause graph for human review of the Research Guide."""
    ui.show_step("SYSTEM", "Graph paused: Awaiting review of Research Guide")
    details = state.get("research_guide", "No guide generated.")
    
    # We yield an interrupt with the payload for the main loop to display
    decision_payload = interrupt({
        "gate": "RESEARCH GUIDE",
        "details": details,
        "allow_edit": True,
        "action_desc": "Approve to start coding, Reject to regenerate, Edit to manually adjust."
    })
    
    # When resumed, the main loop has already updated the state, so we just return
    return {}


def await_run(state: AgentState):
    """Pause graph before the first run/tests."""
    ui.show_step("SYSTEM", "Graph paused: Awaiting approval to execute project")
    
    # If the user rejects, we can handle it via the error_handler
    decision_payload = interrupt({
        "gate": "RUN PROJECT",
        "details": "Ready to execute the generated code and run tests.",
        "allow_edit": False,
        "action_desc": "Approve to execute the generated system, Reject to abort."
    })
    
    return {}


def await_report(state: AgentState):
    """Pause graph for human review of the Final QA Report."""
    ui.show_step("SYSTEM", "Graph paused: Awaiting review of Final QA Report")
    
    decision_payload = interrupt({
        "gate": "WRITE FINAL REPORT",
        "details": state.get("final_report", "No report generated."),
        "allow_edit": True,
        "action_desc": "Approve to finish, Edit to tweak report, Reject to run more tests."
    })
    
    return {}


def error_handler(state: AgentState):
    """Handle fatal errors or rejections."""
    err = state.get("error") or "Operation aborted by user."
    ui.show_error(f"Graph aborted: {err}")
    return {"current_agent": "ERROR"}


def complete(state: AgentState):
    """Print final success summary."""
    ui.show_success("Pipeline execution complete! All agents finished successfully.")
    return {"current_agent": "COMPLETE"}


# ══════════════════════════════════════════════════════════════════════════════
# Edge Routers
# ══════════════════════════════════════════════════════════════════════════════

def route_after_guide(state: AgentState) -> str:
    decision = state.get("hitl_decision")
    if decision == "APPROVE" or decision == "EDIT":
        return "coding"
    # If REJECT, go back to research
    return "research"

def route_after_run(state: AgentState) -> str:
    decision = state.get("hitl_decision")
    if decision == "APPROVE":
        return "testing"
    return "error_handler"

def route_after_report(state: AgentState) -> str:
    decision = state.get("hitl_decision")
    if decision == "APPROVE" or decision == "EDIT":
        return "complete"
    return "testing"

# ══════════════════════════════════════════════════════════════════════════════
# Graph Construction
# ══════════════════════════════════════════════════════════════════════════════

workflow = StateGraph(AgentState)

# Nodes
workflow.add_node("research", research_agent)
workflow.add_node("await_guide", await_guide)
workflow.add_node("coding", coding_agent)
workflow.add_node("await_run", await_run)
workflow.add_node("testing", testing_agent)
workflow.add_node("await_report", await_report)
workflow.add_node("error_handler", error_handler)
workflow.add_node("complete", complete)

# Edges
workflow.add_edge(START, "research")
workflow.add_edge("research", "await_guide")

workflow.add_conditional_edges(
    "await_guide",
    route_after_guide,
    {"coding": "coding", "research": "research"}
)

workflow.add_edge("coding", "await_run")

workflow.add_conditional_edges(
    "await_run",
    route_after_run,
    {"testing": "testing", "error_handler": "error_handler"}
)

workflow.add_edge("testing", "await_report")

workflow.add_conditional_edges(
    "await_report",
    route_after_report,
    {"complete": "complete", "testing": "testing"}
)

workflow.add_edge("error_handler", END)
workflow.add_edge("complete", END)

# Compile with memory saver
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)


# ══════════════════════════════════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════════════════════════════════

async def run_pipeline(task: str) -> AgentState:
    """Creates the state, streams events, and handles interrupts."""
    
    thread_id = "run-1"
    config = {"configurable": {"thread_id": thread_id}}
    
    initial_state = {
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
    
    # Helper to stream the graph
    async def process_stream():
        async for event in app.astream(initial_state, config, stream_mode="updates"):
            # We don't necessarily need to print everything here since agents print their own UI.
            # We could look for agent transitions:
            pass

    # The main execution loop
    while True:
        await process_stream()
        
        state_snapshot = app.get_state(config)
        
        # If there are no next nodes, the graph has finished!
        if not state_snapshot.next:
            return state_snapshot.values
            
        # If the graph is paused at an interrupt
        if state_snapshot.tasks:
            for t in state_snapshot.tasks:
                if t.interrupts:
                    payload = t.interrupts[0].value
                    
                    gate = payload.get("gate", "APPROVAL REQUIRED")
                    details = payload.get("details", "")
                    allow_edit = payload.get("allow_edit", False)
                    desc = payload.get("action_desc", "")
                    
                    if desc:
                        details = f"{desc}\n\n{details}"
                        
                    # 1. Call AgentUI.request_approval
                    decision, edited = ui.request_approval(gate, details, allow_edit=allow_edit)
                    
                    # If edited, we might want to apply the edit directly to the state depending on the gate
                    updates = {"hitl_decision": decision, "hitl_edit_value": edited}
                    
                    # Apply specific state modifications based on gate before resuming
                    if gate == "RESEARCH GUIDE" and decision == "EDIT" and edited:
                        updates["research_guide"] = edited
                    elif gate == "RESEARCH GUIDE" and decision == "REJECT":
                        feedback = ui.console.input(f"  [bold {AQUA}]Feedback > [/]")
                        current_comments = state_snapshot.values.get("research_comments", [])
                        current_comments.append(feedback)
                        updates["research_comments"] = current_comments
                    elif gate == "WRITE FINAL REPORT" and decision == "EDIT" and edited:
                        updates["final_report"] = edited
                        
                    # 2. Call graph.update_state
                    app.update_state(config, updates)
                    
                    # 3. Resume the graph by passing the value to the interrupt
                    initial_state = None # To prevent re-initialising the state in the next loop
                    
                    from langgraph.types import Command
                    await app.ainvoke(Command(resume=True), config)
                    
                    break # Break out of task loop, continue the while loop
