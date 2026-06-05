"""
ui/terminal_ui.py
-----------------
Rich-based terminal UI for the Multi-Agent LangGraph system.
All output uses an Aqua (#00FFFF) color theme.
"""

from __future__ import annotations

import sys
import time
from typing import Any

# Force UTF-8 output on Windows legacy consoles
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich.align import Align
from rich import box

# ── Theme constants ────────────────────────────────────────────────────────────
AQUA        = "#00FFFF"
DIM_CYAN    = "cyan"
BRIGHT_CYAN = "bright_cyan"
YELLOW      = "yellow"
RED         = "red"
GREEN       = "bright_green"
WHITE       = "white"

# Map agent name -> display label with slot number
_AGENT_LABELS: dict[str, str] = {
    "RESEARCH": "AGENT 1  *  RESEARCH",
    "CODING":   "AGENT 2  *  CODING",
    "TESTING":  "AGENT 3  *  TESTING",
}


class AgentUI:
    """
    Terminal UI controller for the multi-agent pipeline.

    All public methods accept plain strings and handle all Rich markup
    internally so callers never need to know about Rich syntax.
    """

    def __init__(self) -> None:
        self.console = Console(highlight=False)
        # Running log of every HITL gate encountered this session
        self._hitl_log: list[dict] = []

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _header(self, agent_name: str) -> str:
        """Return the display header for an agent."""
        return _AGENT_LABELS.get(agent_name.upper(), f"AGENT  *  {agent_name.upper()}")

    def _rule(self, msg: str = "", style: str = AQUA) -> None:
        self.console.print(Rule(f"[bold {AQUA}]{msg}[/]", style=style))

    # ── Public display methods ─────────────────────────────────────────────────

    def show_step(self, agent_name: str, step_description: str) -> None:
        """
        Print an aqua panel announcing a new agent step.

        Example output:
            +---------- AGENT 1  *  RESEARCH ----------+
            |  Starting web search for requirements     |
            +-------------------------------------------+
        """
        header = self._header(agent_name)
        self.console.print(
            Panel(
                f"[{WHITE}]{step_description}[/]",
                title=f"[bold {AQUA}]{header}[/]",
                border_style=AQUA,
                expand=False,
                padding=(0, 2),
            )
        )

    def show_reasoning(self, thought: str) -> None:
        """Print an agent's internal reasoning in dim cyan italic."""
        self.console.print(
            f"  [dim {DIM_CYAN}][italic]Thought:[/italic]  {thought}[/]"
        )

    def show_tool_call(self, tool_name: str, input: Any) -> None:
        """Show a tool being called in bright cyan with its input."""
        input_str = str(input)
        body = (
            f"[bold {BRIGHT_CYAN}]Tool   :[/]  [bold white]{tool_name}[/]\n"
            f"[bold {BRIGHT_CYAN}]Input  :[/]  [{DIM_CYAN}]{input_str}[/]"
        )
        self.console.print(
            Panel(
                body,
                title=f"[bold {BRIGHT_CYAN}]-- Tool Call --[/]",
                border_style=BRIGHT_CYAN,
                expand=False,
                padding=(0, 2),
            )
        )

    def show_result(self, content: str) -> None:
        """Show agent output / tool result in an aqua-bordered white panel."""
        self.console.print(
            Panel(
                f"[{WHITE}]{content}[/]",
                title=f"[bold {AQUA}]Result[/]",
                border_style=AQUA,
                expand=False,
                padding=(0, 2),
            )
        )

    def show_error(self, error: str) -> None:
        """Print a red error panel."""
        self.console.print(
            Panel(
                f"[bold {RED}]{error}[/]",
                title=f"[bold {RED}]ERROR[/]",
                border_style=RED,
                expand=False,
                padding=(0, 2),
            )
        )

    def show_success(self, message: str) -> None:
        """Print a bright-green success panel with a checkmark."""
        self.console.print(
            Panel(
                f"[bold {GREEN}]  [OK]  {message}[/]",
                title=f"[bold {GREEN}]SUCCESS[/]",
                border_style=GREEN,
                expand=False,
                padding=(0, 2),
            )
        )

    def show_agent_transition(self, from_agent: str, to_agent: str) -> None:
        """
        Print an animated arrow showing agent handoff.

        Example:  RESEARCH  ──────►  CODING
        """
        self._rule()

        arrow_steps = [
            f"[bold {AQUA}]{from_agent.upper()}[/]  [dim {AQUA}]----[/]",
            f"[bold {AQUA}]{from_agent.upper()}[/]  [{AQUA}]--------[/]",
            f"[bold {AQUA}]{from_agent.upper()}[/]  [{AQUA}]------------[/]",
            f"[bold {AQUA}]{from_agent.upper()}[/]  [{AQUA}]------------>  [/][bold {AQUA}]{to_agent.upper()}[/]",
        ]

        for frame in arrow_steps:
            self.console.print(f"  {frame}", end="\r")
            time.sleep(0.18)

        # Print the final stable line
        final = (
            f"  [bold {AQUA}]{from_agent.upper()}[/]"
            f"  [{AQUA}]------------>  [/]"
            f"[bold {AQUA}]{to_agent.upper()}[/]"
        )
        self.console.print(final)
        self._rule()

    # ── HITL gate ──────────────────────────────────────────────────────────────

    def request_approval(
        self,
        action_type: str,
        details: str,
        allow_edit: bool = False,
    ) -> tuple[str, str | None]:
        """
        Human-in-the-Loop approval gate.

        Displays a yellow warning panel describing exactly what is about to
        happen, then blocks until the human types APPROVE, REJECT, or EDIT.

        Parameters
        ----------
        action_type : str
            Category label, e.g. "FILE WRITE", "SHELL COMMAND", "AGENT TRANSITION".
        details : str
            The exact command / path / content the agent wants to execute.
        allow_edit : bool
            When True, offer an EDIT option that lets the human retype the value.

        Returns
        -------
        (decision, edited_value)
            decision       -- "APPROVE" | "REJECT" | "EDIT"
            edited_value   -- the human-supplied replacement string, or None
        """
        options = "APPROVE / REJECT / EDIT" if allow_edit else "APPROVE / REJECT"

        body_lines = [
            f"[bold {YELLOW}]Action Type:[/]  [white]{action_type}[/]",
            "",
            f"[bold {YELLOW}]Details:[/]",
            f"  [white]{details}[/]",
            "",
            f"[{YELLOW}]Options: [bold]{options}[/bold][/]",
        ]
        body = "\n".join(body_lines)

        self.console.print(
            Panel(
                body,
                title=f"[bold {YELLOW}]  !! HUMAN APPROVAL REQUIRED !![/]",
                border_style=YELLOW,
                expand=False,
                padding=(1, 3),
            )
        )

        # ── Prompt loop ────────────────────────────────────────────────────
        valid = {"APPROVE", "REJECT", "EDIT"} if allow_edit else {"APPROVE", "REJECT"}
        decision: str = ""
        edited_value: str | None = None

        while True:
            raw = self.console.input(
                f"[bold {AQUA}]  Your decision > [/]"
            ).strip().upper()

            if raw in valid:
                decision = raw
                break
            self.console.print(
                f"  [bold {RED}]Invalid input.[/] "
                f"[{YELLOW}]Please type one of: {options}[/]"
            )

        # ── If EDIT: capture the replacement value (supports multi-line) ──────
        if decision == "EDIT" and allow_edit:
            self.console.print(
                f"  [{AQUA}]Enter replacement value.[/] "
                f"[{YELLOW}]Type [bold]---END---[/bold] on its own line when finished:[/]"
            )
            lines: list[str] = []
            while True:
                line = self.console.input(f"  [{BRIGHT_CYAN}]> [/]")
                if line.strip() == "---END---":
                    break
                lines.append(line)
            edited_value = "\n".join(lines).strip()

        # ── Visual feedback ────────────────────────────────────────────────
        if decision == "APPROVE":
            self.console.print(
                Panel(
                    f"[bold {GREEN}]  [OK]  Approved -- proceeding.[/]",
                    border_style=GREEN,
                    expand=False,
                )
            )
        elif decision == "REJECT":
            self.console.print(
                Panel(
                    f"[bold {RED}]  [X]  Rejected -- action cancelled.[/]",
                    border_style=RED,
                    expand=False,
                )
            )
        else:  # EDIT
            self.console.print(
                Panel(
                    f"[bold {YELLOW}]  [~]  Value edited by human.[/]",
                    border_style=YELLOW,
                    expand=False,
                )
            )

        # ── Audit trail ────────────────────────────────────────────────────
        log_entry = {
            "action_type":   action_type,
            "details":       details,
            "decision":      decision,
            "edited_value":  edited_value,
            "changed":       edited_value is not None,
        }
        self._hitl_log.append(log_entry)

        return decision, edited_value

    # ── HITL summary table ─────────────────────────────────────────────────────

    def show_hitl_summary(self, decisions: list[dict] | None = None) -> None:
        """
        Print a table of every HITL gate that occurred during this run.

        Parameters
        ----------
        decisions : list[dict] | None
            If None, uses the internal ``_hitl_log`` populated by
            ``request_approval()`` calls.
            Each dict must have keys:
                action_type, details, decision, changed (bool).
        """
        data = decisions if decisions is not None else self._hitl_log

        self._rule("HITL Audit Summary")

        if not data:
            self.console.print(
                f"  [{DIM_CYAN}]No HITL gates were triggered during this run.[/]"
            )
            return

        table = Table(
            box=box.ROUNDED,
            border_style=AQUA,
            header_style=f"bold {AQUA}",
            show_lines=True,
        )
        table.add_column("Step",       style="bold white",   width=6,  justify="center")
        table.add_column("Action",     style=f"{AQUA}",      width=22)
        table.add_column("Details",    style="white",        width=34)
        table.add_column("Decision",   style="bold",         width=10, justify="center")
        table.add_column("Changed?",   style="bold",         width=9,  justify="center")

        decision_color = {
            "APPROVE": GREEN,
            "REJECT":  RED,
            "EDIT":    YELLOW,
        }

        for i, entry in enumerate(data, start=1):
            d = entry.get("decision", "")
            color = decision_color.get(d, WHITE)
            changed_cell = (
                f"[{YELLOW}]YES[/]" if entry.get("changed") else f"[{DIM_CYAN}]no[/]"
            )
            # Truncate long details for display
            detail_display = entry.get("details", "")
            if len(detail_display) > 32:
                detail_display = detail_display[:29] + "..."

            table.add_row(
                str(i),
                entry.get("action_type", ""),
                detail_display,
                f"[{color}]{d}[/]",
                changed_cell,
            )

        self.console.print(
            Panel(
                table,
                title=f"[bold {AQUA}]HITL Gate Log[/]",
                border_style=AQUA,
                expand=False,
                padding=(0, 1),
            )
        )


# ══════════════════════════════════════════════════════════════════════════════
# DEMO  --  run with:  python ui/terminal_ui.py
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    ui = AgentUI()

    # ── Banner ─────────────────────────────────────────────────────────────
    ui.console.rule(
        f"[bold {AQUA}]Multi-Agent LangGraph  --  Terminal UI Demo[/]",
        style=AQUA,
    )
    ui.console.print()

    # ── Step 1: Research agent kicks off ───────────────────────────────────
    ui.show_step("RESEARCH", "Starting web search for project requirements")

    ui.show_reasoning(
        "I need to search for best practices and library options "
        "before proposing a folder structure and stack."
    )

    ui.show_tool_call(
        "web_search",
        "langgraph multi-agent best practices 2024",
    )

    ui.show_result(
        "Found 5 relevant results:\n"
        "  1. LangGraph official docs -- agent patterns\n"
        "  2. Multi-agent coordination with shared state\n"
        "  3. HITL patterns for LLM pipelines\n"
        "  4. LangChain Groq integration guide\n"
        "  5. pytest-cov HTML report generation"
    )

    ui.console.print()

    # ── HITL gate: approve the agent transition ────────────────────────────
    decision, _ = ui.request_approval(
        "AGENT TRANSITION",
        "Move from RESEARCH  -->  CODING?\n"
        "  Research guide is ready. Coding agent will generate files.",
    )

    ui.console.print()

    if decision == "APPROVE":
        # ── Animated transition ────────────────────────────────────────────
        ui.show_agent_transition("RESEARCH", "CODING")
        ui.console.print()

        # ── Step 2: Coding agent begins ────────────────────────────────────
        ui.show_step("CODING", "Generating project files from research guide")

        ui.show_reasoning(
            "Research guide approved. I will scaffold the folder structure "
            "and generate each source file in sequence."
        )

        ui.show_tool_call(
            "write_file",
            "src/main.py  (generating entry-point boilerplate)",
        )

        ui.show_result("src/main.py written -- 42 lines.")

        ui.console.print()

        # ── HITL gate: approve a shell command ────────────────────────────
        decision2, edited = ui.request_approval(
            "SHELL COMMAND",
            "pip install -r requirements.txt",
            allow_edit=True,
        )

        ui.console.print()

        if decision2 in ("APPROVE", "EDIT"):
            cmd = edited if edited else "pip install -r requirements.txt"
            ui.show_step("TESTING", f"Running: {cmd}")
            ui.show_result("All packages installed. Running pytest ...")
            ui.show_success("Research phase complete! All 6 tests passed.")
        else:
            ui.show_error("Shell command rejected by user.")

    else:
        ui.show_error("Transition rejected by user.")

    # ── HITL audit summary ─────────────────────────────────────────────────
    ui.console.print()
    ui.show_hitl_summary()

    ui.console.print()
    ui.console.rule(f"[bold {AQUA}]Demo Complete[/]", style=AQUA)
