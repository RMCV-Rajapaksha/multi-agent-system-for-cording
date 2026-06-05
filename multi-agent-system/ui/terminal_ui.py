"""
ui/terminal_ui.py
-----------------
Rich-based terminal UI for the Multi-Agent LangGraph system.
All output uses an Aqua (#00FFFF) color theme.
"""

from __future__ import annotations

import os
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
from rich.layout import Layout
from rich.live import Live
from rich.align import Align
from rich import box
from rich.progress import Progress, BarColumn, TextColumn

# ── Theme constants ────────────────────────────────────────────────────────────
AQUA        = "#00FFFF"
DIM_CYAN    = "cyan"
BRIGHT_CYAN = "bright_cyan"
YELLOW      = "yellow"
RED         = "red"
GREEN       = "bright_green"
WHITE       = "white"

_AGENT_LABELS: dict[str, str] = {
    "RESEARCH": "AGENT 1  *  RESEARCH",
    "CODING":   "AGENT 2  *  CODING",
    "TESTING":  "AGENT 3  *  TESTING",
}

ASCII_ART = f"""[bold {AQUA}]
  __  __ _   _ _  _____ ___   _   ___ ___ _  _ _____   _____   _____ _____ ___ __  __ 
 |  \\/  | | | | ||_   _|_ _| /_\\ / __| __| \\| |_   _| / __\\ \\ / / __|_   _| __|  \\/  |
 | |\\/| | |_| | |__| |  | | / _ \\ (_ | _|| .` | | |   \\__ \\\\ V /\\__ \\ | | | _|| |\\/| |
 |_|  |_|\\___/|____|_| |___/_/ \\_\\___|___|_|\\_| |_|   |___/ |_| |___/ |_| |___|_|  |_|
[/]"""

class AgentUI:
    """
    Terminal UI controller for the multi-agent pipeline.
    Uses the Singleton pattern to coordinate a unified rich.live display.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized: return
        self._initialized = True
        
        self.console = Console(highlight=False)
        self._hitl_log: list[dict] = []
        
        # Live display state
        self.agent_statuses = {
            "RESEARCH": "IDLE",
            "CODING": "IDLE",
            "TESTING": "IDLE",
        }
        self.active_agent = ""
        self.thoughts: list[str] = []
        self.files: list[dict] = [] # {"filename": str, "lines": int, "status": str}
        self.progress_count = 0
        self.total_steps = 15
        self.start_time = time.time()
        
        # Statistics tracking
        self.files_created = 0
        self.files_skipped = 0
        self.files_rejected = 0
        self.hitl_rejections = 0
        self.hitl_edits = 0
        
        self.live = None

    def start(self):
        """Start the live UI. Safe to call multiple times."""
        if self.live is None:
            self.live = Live(self._generate_layout(), console=self.console, refresh_per_second=4, transient=False)
            self.live.start()

    def stop(self):
        """Stop the live UI safely."""
        if self.live is not None:
            self.live.stop()
            self.live = None

    def update(self):
        """Refresh the live display layout."""
        if self.live is not None:
            self.live.update(self._generate_layout())

    def _generate_layout(self) -> Layout:
        """Construct the live dashboard layout."""
        layout = Layout(name="root")
        layout.split_column(
            Layout(name="header", size=7),
            Layout(name="cards", size=6),
            Layout(name="progress", size=3),
            Layout(name="body")
        )
        layout["body"].split_row(
            Layout(name="reasoning", ratio=2),
            Layout(name="files", ratio=1)
        )
        
        # Header (ASCII Art)
        layout["header"].update(Align.center(ASCII_ART))
        
        # Cards
        cards_grid = Table.grid(expand=True, padding=(0, 2))
        cards_grid.add_column(ratio=1)
        cards_grid.add_column(ratio=1)
        cards_grid.add_column(ratio=1)
        
        def make_card(name, title, capabilities, status):
            color = DIM_CYAN
            if status == "ACTIVE": color = AQUA
            elif status == "WAITING": color = YELLOW
            elif status == "DONE": color = GREEN
            
            content = f"[bold white]{title}[/]\n[{DIM_CYAN}]{capabilities}[/]\n\n[bold {color}]Status: {status}[/]"
            return Panel(content, border_style=color, box=box.ROUNDED)
            
        cards_grid.add_row(
            make_card("RESEARCH", "Agent 1: Research", "Web Search, Architecture, Planning", self.agent_statuses["RESEARCH"]),
            make_card("CODING", "Agent 2: Coding", "File Ops, Env Setup, Python Gen", self.agent_statuses["CODING"]),
            make_card("TESTING", "Agent 3: Testing", "Pytest, Auto-fixing, QA Report", self.agent_statuses["TESTING"])
        )
        layout["cards"].update(cards_grid)
        
        # Progress Bar [Research ■■■□□  Coding □□□□□  Testing □□□□□]
        r_blocks = min(5, max(0, self.progress_count))
        c_blocks = min(5, max(0, self.progress_count - 5))
        t_blocks = min(5, max(0, self.progress_count - 10))
        r_str = "■" * r_blocks + "□" * (5 - r_blocks)
        c_str = "■" * c_blocks + "□" * (5 - c_blocks)
        t_str = "■" * t_blocks + "□" * (5 - t_blocks)
        
        custom_bar = (
            f"[bold {WHITE}]Pipeline Progress:[/]   "
            f"[bold {AQUA}]Research[/] [{AQUA}]{r_str}[/]  "
            f"[bold {AQUA}]Coding[/] [{AQUA}]{c_str}[/]  "
            f"[bold {AQUA}]Testing[/] [{AQUA}]{t_str}[/]"
        )
        layout["progress"].update(Panel(Align.center(custom_bar), box=box.SIMPLE))
        
        # Reasoning Panel (left body)
        # Ensure we always show the latest 15 thoughts
        reasoning_text = "\n".join(self.thoughts[-15:])
        layout["reasoning"].update(Panel(reasoning_text, title=f"[bold {DIM_CYAN}]Live Reasoning[/]", border_style=DIM_CYAN))
        
        # File Creation Table (right body)
        file_table = Table(box=box.SIMPLE, expand=True)
        file_table.add_column("Filename", style="bold white")
        file_table.add_column("Lines", justify="right", style=DIM_CYAN)
        file_table.add_column("Status")
        for f in self.files[-12:]:
            file_table.add_row(f["filename"], str(f["lines"]), f["status"])
            
        layout["files"].update(Panel(file_table, title=f"[bold {WHITE}]File Workspace[/]", border_style=WHITE))
        
        return layout

    def _add_thought(self, text: str):
        self.thoughts.append(text)
        if len(self.thoughts) > 100:
            self.thoughts.pop(0)

    # ── Public display methods ─────────────────────────────────────────────────

    def show_step(self, agent_name: str, step_description: str) -> None:
        """Announce a new agent step."""
        self.start()
        name = agent_name.upper()
        if self.active_agent != name:
            if self.active_agent in self.agent_statuses:
                self.agent_statuses[self.active_agent] = "DONE"
            if name in self.agent_statuses:
                self.agent_statuses[name] = "ACTIVE"
            self.active_agent = name
            
        self.progress_count = min(self.total_steps, self.progress_count + 1)
        self._add_thought(f"[{WHITE}]● {step_description}[/]")
        self.update()

    def show_reasoning(self, thought: str) -> None:
        """Print an agent's internal reasoning."""
        self.start()
        self._add_thought(f"  [dim {DIM_CYAN}]→ {thought}[/]")
        self.update()

    def show_tool_call(self, tool_name: str, input: Any) -> None:
        """Show a tool being called."""
        self.start()
        input_str = str(input).replace("\n", " ")
        self._add_thought(f"  [{BRIGHT_CYAN}]⚡ Tool:[/] {tool_name} [{DIM_CYAN}]({input_str[:60]}...)[/]")
        self.update()

    def show_result(self, content: str) -> None:
        """Show agent output / tool result."""
        self.start()
        clean_content = str(content).replace("\n", " ")
        self._add_thought(f"  [{GREEN}]✓ Result:[/] {clean_content[:80]}...")
        self.update()

    def show_error(self, error: str) -> None:
        """Print an error."""
        self.start()
        clean_error = str(error).replace("\n", " ")
        self._add_thought(f"  [bold {RED}]✗ ERROR:[/] {clean_error}")
        self.update()

    def show_success(self, message: str) -> None:
        """Print a success message."""
        self.start()
        self._add_thought(f"  [bold {GREEN}]★ {message}[/]")
        self.update()

    def show_agent_transition(self, from_agent: str, to_agent: str) -> None:
        """Animated arrow showing agent handoff inside the live thought panel."""
        self.start()
        from_name = from_agent.upper()
        to_name = to_agent.upper()
        
        arrow_steps = [
            f"[bold {AQUA}]{from_name}[/] [dim {AQUA}]----[/]",
            f"[bold {AQUA}]{from_name}[/] [{AQUA}]--------[/]",
            f"[bold {AQUA}]{from_name}[/] [{AQUA}]------------[/]",
            f"[bold {AQUA}]{from_name}[/] [{AQUA}]------------►[/] [bold {AQUA}]{to_name}[/]",
        ]
        
        for frame in arrow_steps:
            self._add_thought(frame)
            self.update()
            time.sleep(0.2)
            if frame != arrow_steps[-1]:
                self.thoughts.pop()

    # ── HITL gate ──────────────────────────────────────────────────────────────

    def request_approval(
        self,
        action_type: str,
        details: str,
        allow_edit: bool = False,
    ) -> tuple[str, str | None]:
        
        if self.active_agent in self.agent_statuses:
            self.agent_statuses[self.active_agent] = "WAITING"
        self.update()
        
        # Stop live rendering to accept input cleanly without mangling the screen
        self.stop()
        
        # Parse details to extract filename and lines
        filename = "unknown"
        lines_count = 0
        is_file_action = "FILE" in action_type
        if is_file_action:
            for line in details.splitlines():
                if "File:" in line or "Path:" in line:
                    filename = line.split(":", 1)[1].strip()
            lines_count = len(details.splitlines())
            risk_text = f"Will write {lines_count} lines to disk"
        else:
            filename = action_type
            risk_text = "System modification"

        # Redesigned HITL Gate Panel
        target_display = filename if filename != "unknown" else str(details).splitlines()[0][:40]
        options_line = "[bold yellow][A] APPROVE[/]   [bold red][R] REJECT[/]"
        if allow_edit:
            options_line += "   [bold cyan][E] EDIT[/]"
            
        panel_content = (
            f"  [bold red]⚠  HUMAN APPROVAL REQUIRED[/]\n"
            f"  [bold white]Action[/]  : {action_type}\n"
            f"  [bold white]Target[/]  : {target_display}\n"
            f"  [bold white]Risk[/]    : {risk_text}\n"
            f"  [dim white]{'─'*50}[/]\n"
            f"  {options_line}\n"
            f"  [white]Type your choice (A, R, E) and press Enter:[/]"
        )
        self.console.print(Panel(panel_content, border_style=YELLOW, expand=False))

        valid = {"A": "APPROVE", "R": "REJECT", "E": "EDIT", "APPROVE": "APPROVE", "REJECT": "REJECT", "EDIT": "EDIT"}
        if not allow_edit:
            valid.pop("E", None)
            valid.pop("EDIT", None)
            
        decision: str = ""
        edited_value: str | None = None

        while True:
            raw = self.console.input(f"  [bold {AQUA}]> [/]").strip().upper()
            if raw in valid:
                decision = valid[raw]
                break
            self.console.print(f"  [bold {RED}]Invalid choice.[/]")

        # Multi-line edit prompt
        if decision == "EDIT" and allow_edit:
            self.hitl_edits += 1
            self.console.print(f"  [{AQUA}]Enter replacement value. Type [bold]---END---[/bold] on its own line when finished:[/]")
            input_lines = []
            while True:
                line = self.console.input(f"  [{BRIGHT_CYAN}]> [/]")
                if line.strip() == "---END---":
                    break
                input_lines.append(line)
            edited_value = "\n".join(input_lines).strip()
            if is_file_action:
                lines_count = len(input_lines)
                
        # Small Receipt
        t_str = time.strftime("%H:%M:%S")
        if decision == "APPROVE":
            self.console.print(f"  [bold {GREEN}]✓ Human approved {action_type} → {target_display} at {t_str}[/]\n")
            if is_file_action: self.files_created += 1
        elif decision == "REJECT":
            self.hitl_rejections += 1
            self.console.print(f"  [bold {RED}]✗ Human rejected {action_type} → {target_display} at {t_str}[/]\n")
            if is_file_action: self.files_rejected += 1
        else:
            self.console.print(f"  [bold {YELLOW}]✎ Human edited {action_type} → {target_display} at {t_str}[/]\n")
            if is_file_action: self.files_created += 1
            
        # Update Files Table
        if is_file_action and filename != "unknown":
            status_symbol = f"[{GREEN}]✓[/]" if decision == "APPROVE" else (f"[{RED}]✗[/]" if decision == "REJECT" else f"[{YELLOW}]✎[/]")
            self.files.append({"filename": os.path.basename(filename), "lines": lines_count, "status": status_symbol})

        log_entry = {
            "agent": self.active_agent or "SYSTEM",
            "action_type": action_type,
            "decision": decision,
            "edited": edited_value is not None,
            "time": t_str
        }
        self._hitl_log.append(log_entry)

        if self.active_agent in self.agent_statuses:
            self.agent_statuses[self.active_agent] = "ACTIVE"
            
        self.start()
        return decision, edited_value

    def show_hitl_summary(self, decisions: list[dict] | None = None) -> None:
        """Show the final tables when the pipeline finishes."""
        self.stop()
        
        data = decisions if decisions is not None else self._hitl_log
        
        self.console.print("\n")
        
        # 1. Final HITL Audit Table
        table = Table(box=box.ROUNDED, border_style=AQUA, header_style=f"bold {AQUA}", expand=False)
        table.add_column("#", justify="right", width=4)
        table.add_column("Agent", style="bold white", width=12)
        table.add_column("Action", style=DIM_CYAN)
        table.add_column("Decision", justify="center")
        table.add_column("Edited?", justify="center")
        table.add_column("Time", justify="center")

        decision_color = {"APPROVE": GREEN, "REJECT": RED, "EDIT": YELLOW}

        for i, entry in enumerate(data, start=1):
            d = entry.get("decision", "")
            color = decision_color.get(d, WHITE)
            changed_cell = f"[{YELLOW}]Yes[/]" if entry.get("edited") else f"[{DIM_CYAN}]No[/]"
            
            table.add_row(
                str(i),
                entry.get("agent", "SYSTEM"),
                entry.get("action_type", ""),
                f"[{color}]{d}[/]",
                changed_cell,
                entry.get("time", "")
            )

        self.console.print(Panel(table, title=f"[bold {AQUA}]Final HITL Audit Table[/]", border_style=AQUA, expand=False))
        self.console.print("\n")
        
        # 2. Final Summary Panel
        elapsed = time.time() - self.start_time
        mins, secs = divmod(int(elapsed), 60)
        time_str = f"{mins}m {secs}s"
        
        # Check if any rejections occurred to mark FAILED
        overall_status = f"[{RED}]✗ FAILED[/]" if self.hitl_rejections > 0 else f"[{GREEN}]✓ PASSED[/]"
        
        summary_content = (
            f"[bold white]Total Time Taken:[/]     [{AQUA}]{time_str}[/]\n"
            f"[bold white]Files Stats:[/]          [{GREEN}]{self.files_created} created[/]  [dim white]| {self.files_skipped} skipped | {self.files_rejected} rejected[/]\n"
            f"[bold white]HITL Gates Triggered:[/] [{AQUA}]{len(data)}[/]  [dim white]| Rejections: {self.hitl_rejections} | Edits: {self.hitl_edits}[/]\n\n"
            f"[bold white]Overall Status:[/]       {overall_status}"
        )
        self.console.print(Panel(summary_content, title=f"[bold {AQUA}]Final Execution Summary[/]", border_style=AQUA, expand=False))


# ══════════════════════════════════════════════════════════════════════════════
# DEMO  --  run with:  python ui/terminal_ui.py
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    ui = AgentUI()
    ui.start()
    
    ui.show_step("RESEARCH", "Starting web search for project requirements")
    ui.show_reasoning("I need to search for best practices and library options.")
    ui.show_tool_call("web_search", "langgraph multi-agent best practices 2024")
    time.sleep(1.5)
    ui.show_result("Found 5 relevant results.")
    time.sleep(1.5)
    
    decision, _ = ui.request_approval("AGENT TRANSITION", "Move from RESEARCH --> CODING?", allow_edit=False)
    
    if decision == "APPROVE":
        ui.show_agent_transition("RESEARCH", "CODING")
        ui.show_step("CODING", "Generating project files")
        ui.show_reasoning("Research guide approved. Scaffolding folder structure.")
        time.sleep(1)
        
        # Simulate file generation
        ui.request_approval("CREATE FILE", "File: output/generated_code/main.py\nprint('hello')\nprint('world')", allow_edit=True)
        ui.show_result("src/main.py written.")
        time.sleep(1)
        
        ui.show_step("TESTING", "Running tests...")
        ui.show_reasoning("Executing pytest test suite.")
        time.sleep(1.5)
        ui.show_success("Research phase complete! All tests passed.")
        time.sleep(1.5)
        
    ui.show_hitl_summary()
