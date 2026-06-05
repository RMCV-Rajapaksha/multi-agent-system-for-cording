import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

from graph.orchestrator import run_pipeline
from ui.terminal_ui import AgentUI, AQUA, DIM_CYAN

# Load .env explicitly if available
_ROOT = Path(__file__).resolve().parent
load_dotenv(_ROOT / ".env")

async def main():
    ui = AgentUI()
    
    # Aqua welcome banner
    ui.console.rule(f"[bold {AQUA}]Multi-Agent System for Coding[/]", style=AQUA)
    ui.console.print(f"  [bold {AQUA}]Welcome to the Autonomous LangGraph Coding Pipeline![/]\n")
    
    # Ask: "What project do you want to build?"
    task = ui.console.input(f"  [bold {AQUA}]What project do you want to build? > [/]").strip()
    
    if not task:
        ui.show_error("No project specified. Exiting.")
        return

    ui.console.print()
    
    # Run the orchestrator pipeline
    try:
        final_state = await run_pipeline(task)
    except Exception as e:
        ui.show_error(f"Pipeline crashed fatally: {e}")
        return

    # Print step log
    step_log = final_state.get("step_log", [])
    if step_log:
        ui.console.rule(f"[bold {AQUA}]Execution Step Log[/]", style=AQUA)
        for entry in step_log:
            ui.console.print(f"    [{DIM_CYAN}]{entry}[/]")
        ui.console.print()

    # Call ui.show_hitl_summary to print the full table of every human decision
    ui.show_hitl_summary()
    
    ui.console.rule(f"[bold {AQUA}]Session Complete[/]", style=AQUA)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSession aborted by user.")
