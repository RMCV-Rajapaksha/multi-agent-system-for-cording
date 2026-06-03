"""
tools/terminal_tools.py
-----------------------
Shell execution tool for the Coding / Testing Agents.
Every command goes through a HITL approval gate before running.
"""

from __future__ import annotations

import re
import subprocess
import sys

# ── path fix so sibling packages resolve when run directly ─────────────────────
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from langchain_core.tools import tool

from ui.terminal_ui import AgentUI

# ── shared UI instance ─────────────────────────────────────────────────────────
ui = AgentUI()

# ── Command timeout (seconds) ──────────────────────────────────────────────────
_TIMEOUT = 60

# ── Patterns that are always blocked, regardless of human approval ─────────────
_DANGEROUS_PATTERNS: list[re.Pattern] = [
    re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f\s+/"),   # rm -rf /
    re.compile(r"\bsudo\b"),
    re.compile(r"\bformat\b", re.IGNORECASE),
    re.compile(r"\bmkfs\b"),
    re.compile(r"\bdd\b.*of=/dev/"),
    re.compile(r"\bshutdown\b"),
    re.compile(r"\breboot\b"),
    re.compile(r"\bhalt\b"),
]


# ══════════════════════════════════════════════════════════════════════════════
# Custom exception — raised when human rejects an action
# ══════════════════════════════════════════════════════════════════════════════

class HumanRejectedError(RuntimeError):
    """Raised when the operator rejects a HITL gate."""


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _is_dangerous(cmd: str) -> bool:
    """Return True if the command matches any dangerous pattern."""
    return any(pat.search(cmd) for pat in _DANGEROUS_PATTERNS)


def _run(cmd: str, cwd: str) -> dict:
    """Execute a shell command and capture output."""
    proc = subprocess.run(
        cmd,
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "exit_code": proc.returncode,
        "stdout":    proc.stdout.strip(),
        "stderr":    proc.stderr.strip(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Tool — run_command
# ══════════════════════════════════════════════════════════════════════════════

@tool
def run_command(command: str, working_dir: str = ".") -> dict:
    """
    Execute a shell command after human approval.

    The operator is shown the exact command and may APPROVE, REJECT, or EDIT
    it before it runs. Dangerous patterns (rm -rf /, sudo, format, mkfs, dd,
    shutdown) are blocked unconditionally.

    Args:
        command:     The shell command to run.
        working_dir: Directory to run the command in (default: current dir).

    Returns:
        dict with keys: exit_code, stdout, stderr, approved_by_human,
                        command_used (may differ from input if EDIT was chosen).

    Raises:
        ValueError:         If the command matches a dangerous pattern.
        HumanRejectedError: If the operator chooses REJECT.
        subprocess.TimeoutExpired: If the command exceeds 60 seconds.
    """
    ui.show_tool_call("run_command", f"{command!r}  (cwd={working_dir!r})")

    # ── Safety check: block dangerous patterns unconditionally ────────────
    if _is_dangerous(command):
        msg = f"BLOCKED: Command matches dangerous pattern -- '{command}'"
        ui.show_error(msg)
        raise ValueError(msg)

    # ── HITL gate ──────────────────────────────────────────────────────────
    details = (
        f"Command    : {command}\n"
        f"Working dir: {working_dir}\n"
        f"Timeout    : {_TIMEOUT}s"
    )
    decision, edited_value = ui.request_approval(
        "SHELL COMMAND", details, allow_edit=True
    )

    if decision == "REJECT":
        raise HumanRejectedError(f"Shell command rejected by operator: {command!r}")

    # Determine the actual command to run
    if decision == "EDIT" and edited_value:
        actual_cmd = edited_value
        ui.console.print(
            f"  [yellow]Command changed by operator:[/] [cyan]{actual_cmd}[/]"
        )
    else:
        actual_cmd = command

    # ── Execute ────────────────────────────────────────────────────────────
    ui.show_step("SYSTEM", f"Running: {actual_cmd}")
    try:
        result = _run(actual_cmd, working_dir)
    except subprocess.TimeoutExpired:
        msg = f"Command timed out after {_TIMEOUT}s: {actual_cmd!r}"
        ui.show_error(msg)
        return {
            "exit_code":         -1,
            "stdout":            "",
            "stderr":            msg,
            "approved_by_human": True,
            "command_used":      actual_cmd,
        }

    # ── Display result ─────────────────────────────────────────────────────
    exit_code = result["exit_code"]
    display = (
        f"Exit code : {exit_code}\n"
        f"--- stdout ---\n{result['stdout'][:600] or '(empty)'}\n"
        f"--- stderr ---\n{result['stderr'][:400] or '(empty)'}"
    )
    if exit_code == 0:
        ui.show_result(display)
    else:
        ui.show_error(display)

    return {
        "exit_code":         exit_code,
        "stdout":            result["stdout"],
        "stderr":            result["stderr"],
        "approved_by_human": True,
        "command_used":      actual_cmd,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Quick test
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    from ui.terminal_ui import AQUA

    ui.console.rule(
        f"[bold {AQUA}]terminal_tools.py  --  Quick Test[/]", style=AQUA
    )
    ui.console.print()
    ui.console.print(
        f"  [cyan]This test will ask for approval before running 'echo Hello'.[/]\n"
    )

    ui.show_step("CODING", "Testing run_command with a safe echo command")

    try:
        result = run_command.invoke({"command": "echo Hello from run_command!", "working_dir": "."})
        ui.show_success(
            f"run_command completed.  exit_code={result['exit_code']}\n"
            f"  stdout: {result['stdout']}"
        )
    except HumanRejectedError as exc:
        ui.show_error(f"Test rejected by operator: {exc}")

    ui.console.print()

    # ── Dangerous pattern block test (no prompt shown) ─────────────────────
    ui.show_step("SYSTEM", "Testing dangerous command blocker (no prompt)")
    try:
        run_command.invoke({"command": "sudo rm -rf /", "working_dir": "."})
    except ValueError as exc:
        ui.show_success(f"Dangerous command correctly blocked:\n  {exc}")

    ui.console.print()
    ui.show_hitl_summary()
    ui.console.rule(f"[bold {AQUA}]Test Complete[/]", style=AQUA)
