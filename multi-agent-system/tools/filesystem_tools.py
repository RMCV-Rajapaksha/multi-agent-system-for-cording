"""
tools/filesystem_tools.py
-------------------------
File-system tools for the Coding Agent.
All write operations go through a HITL approval gate.
All generated files are sandboxed inside ./output/generated_code/.
"""

from __future__ import annotations

import difflib
import sys
from pathlib import Path

# ── path fix so sibling packages resolve when run directly ─────────────────────
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from langchain_core.tools import tool

from ui.terminal_ui import AgentUI

# ── shared UI instance ─────────────────────────────────────────────────────────
ui = AgentUI()

# ── Write sandbox — all generated files must live here ────────────────────────
_SANDBOX = (
    Path(__file__).resolve().parents[1] / "output" / "generated_code"
)
_SANDBOX.mkdir(parents=True, exist_ok=True)

# ── Preview line count for CREATE FILE gate ───────────────────────────────────
_PREVIEW_LINES = 20


# ══════════════════════════════════════════════════════════════════════════════
# Custom exception
# ══════════════════════════════════════════════════════════════════════════════

class HumanRejectedError(RuntimeError):
    """Raised when the operator rejects a HITL gate."""


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _safe_path(path: str) -> Path:
    """
    Resolve `path` inside the sandbox and verify it doesn't escape.

    Raises ValueError if the resolved path is outside ./output/generated_code/.
    """
    resolved = (_SANDBOX / path).resolve()
    try:
        resolved.relative_to(_SANDBOX.resolve())
    except ValueError:
        raise ValueError(
            f"Path escape attempt blocked.\n"
            f"  Requested : {path}\n"
            f"  Resolved  : {resolved}\n"
            f"  Sandbox   : {_SANDBOX}"
        )
    return resolved


def _content_preview(content: str, n: int = _PREVIEW_LINES) -> str:
    """Return the first `n` lines of content with a truncation notice."""
    lines = content.splitlines()
    preview = "\n".join(lines[:n])
    if len(lines) > n:
        preview += f"\n... ({len(lines) - n} more lines not shown)"
    return preview


def _unified_diff(old: str, new: str, path: str) -> str:
    """Return a unified diff string between old and new content."""
    diff_lines = list(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"CURRENT: {path}",
            tofile=f"NEW:     {path}",
            lineterm="",
        )
    )
    if not diff_lines:
        return "(no differences)"
    return "".join(diff_lines[:80])  # cap at 80 diff lines for display


# ══════════════════════════════════════════════════════════════════════════════
# Tool 1 — create_file  (HITL required)
# ══════════════════════════════════════════════════════════════════════════════

@tool
def create_file(path: str, content: str) -> str:
    """
    Create a new file inside the sandboxed output/generated_code/ directory.

    Requires human approval. Shows the first 20 lines of content before writing.
    Will NOT overwrite an existing file — use overwrite_file for that.

    Args:
        path:    Relative path within generated_code/ (e.g. "src/main.py").
        content: The full file content to write.

    Returns:
        A confirmation string with the absolute path written.

    Raises:
        FileExistsError:    If the file already exists (use overwrite_file).
        HumanRejectedError: If the operator rejects.
        ValueError:         If the path escapes the sandbox.
    """
    ui.show_tool_call("create_file", path)

    target = _safe_path(path)

    if target.exists():
        raise FileExistsError(
            f"File already exists: {target}\n"
            "Use overwrite_file() to replace it."
        )

    # ── HITL gate ──────────────────────────────────────────────────────────
    preview = _content_preview(content)
    details = (
        f"File path  : {target}\n"
        f"Size       : {len(content)} chars  /  {len(content.splitlines())} lines\n"
        f"\n-- First {_PREVIEW_LINES} lines --\n"
        f"{preview}"
    )
    decision, _ = ui.request_approval("CREATE FILE", details)

    if decision == "REJECT":
        raise HumanRejectedError(f"File creation rejected by operator: {path!r}")

    # ── Write ──────────────────────────────────────────────────────────────
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")

    msg = f"Created: {target}  ({len(content.splitlines())} lines)"
    ui.show_success(msg)
    return msg


# ══════════════════════════════════════════════════════════════════════════════
# Tool 2 — read_file  (no approval — read-only)
# ══════════════════════════════════════════════════════════════════════════════

@tool
def read_file(path: str) -> str:
    """
    Read a file from the sandboxed output/generated_code/ directory.

    Read-only — no human approval required.

    Args:
        path: Relative path within generated_code/.

    Returns:
        The full file content as a string.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError:        If the path escapes the sandbox.
    """
    ui.show_tool_call("read_file", path)

    target = _safe_path(path)
    if not target.exists():
        raise FileNotFoundError(f"File not found: {target}")

    content = target.read_text(encoding="utf-8", errors="replace")
    ui.show_result(f"Read {len(content.splitlines())} lines from {target.name}")
    return content


# ══════════════════════════════════════════════════════════════════════════════
# Tool 3 — list_directory  (no approval — read-only)
# ══════════════════════════════════════════════════════════════════════════════

@tool
def list_directory(path: str = ".") -> str:
    """
    List contents of a directory inside the sandboxed generated_code/ folder.

    Read-only — no human approval required.

    Args:
        path: Relative path within generated_code/ (default: root of sandbox).

    Returns:
        A formatted directory listing string.

    Raises:
        NotADirectoryError: If the path is not a directory.
        ValueError:         If the path escapes the sandbox.
    """
    ui.show_tool_call("list_directory", path)

    target = _safe_path(path)
    if not target.is_dir():
        raise NotADirectoryError(f"Not a directory: {target}")

    entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name))
    if not entries:
        result = "(empty directory)"
    else:
        lines = []
        for e in entries:
            kind = "[DIR] " if e.is_dir() else "[FILE]"
            size = f"  {e.stat().st_size:>8} B" if e.is_file() else ""
            lines.append(f"  {kind} {e.name}{size}")
        result = "\n".join(lines)

    ui.show_result(f"Listing: {target}\n{result}")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# Tool 4 — create_directory  (HITL required)
# ══════════════════════════════════════════════════════════════════════════════

@tool
def create_directory(path: str) -> str:
    """
    Create a directory inside the sandboxed output/generated_code/ folder.

    Requires human approval.

    Args:
        path: Relative path within generated_code/ (e.g. "src/utils").

    Returns:
        A confirmation string.

    Raises:
        HumanRejectedError: If the operator rejects.
        ValueError:         If the path escapes the sandbox.
    """
    ui.show_tool_call("create_directory", path)

    target = _safe_path(path)

    # ── HITL gate ──────────────────────────────────────────────────────────
    details = f"Directory path: {target}"
    decision, _ = ui.request_approval("CREATE DIRECTORY", details)

    if decision == "REJECT":
        raise HumanRejectedError(f"Directory creation rejected by operator: {path!r}")

    target.mkdir(parents=True, exist_ok=True)
    msg = f"Directory created: {target}"
    ui.show_success(msg)
    return msg


# ══════════════════════════════════════════════════════════════════════════════
# Tool 5 — overwrite_file  (HITL required — higher risk)
# ══════════════════════════════════════════════════════════════════════════════

@tool
def overwrite_file(path: str, content: str) -> str:
    """
    Overwrite an existing file inside the sandboxed output/generated_code/ dir.

    Higher-risk operation: shows a unified diff of old vs new content and
    requires human approval before replacing the file.

    Args:
        path:    Relative path within generated_code/.
        content: The new file content.

    Returns:
        A confirmation string.

    Raises:
        FileNotFoundError:  If the file does not yet exist (use create_file).
        HumanRejectedError: If the operator rejects.
        ValueError:         If the path escapes the sandbox.
    """
    ui.show_tool_call("overwrite_file", path)

    target = _safe_path(path)

    if not target.exists():
        raise FileNotFoundError(
            f"Cannot overwrite — file does not exist: {target}\n"
            "Use create_file() to create it first."
        )

    old_content = target.read_text(encoding="utf-8", errors="replace")
    diff_text   = _unified_diff(old_content, content, str(target.name))

    # ── HITL gate ──────────────────────────────────────────────────────────
    details = (
        f"File path  : {target}\n"
        f"Old size   : {len(old_content)} chars  /  {len(old_content.splitlines())} lines\n"
        f"New size   : {len(content)} chars  /  {len(content.splitlines())} lines\n"
        f"\n-- Unified Diff --\n"
        f"{diff_text}"
    )
    decision, _ = ui.request_approval("OVERWRITE FILE -- DESTRUCTIVE", details)

    if decision == "REJECT":
        raise HumanRejectedError(f"File overwrite rejected by operator: {path!r}")

    target.write_text(content, encoding="utf-8")
    msg = f"Overwritten: {target}  ({len(content.splitlines())} lines)"
    ui.show_success(msg)
    return msg


# ══════════════════════════════════════════════════════════════════════════════
# Quick test
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    from ui.terminal_ui import AQUA

    ui.console.rule(
        f"[bold {AQUA}]filesystem_tools.py  --  Quick Test[/]", style=AQUA
    )
    ui.console.print(
        f"  [cyan]Sandbox:[/] {_SANDBOX}\n"
        f"  All files will be written inside that directory.\n"
    )

    # ── 1. Create directory ────────────────────────────────────────────────
    ui.show_step("CODING", "Test 1 — create_directory")
    try:
        create_directory.invoke({"path": "test_demo/src"})
    except HumanRejectedError as e:
        ui.show_error(str(e))

    ui.console.print()

    # ── 2. Create file ─────────────────────────────────────────────────────
    ui.show_step("CODING", "Test 2 — create_file")
    sample_code = (
        '"""Sample module generated by the Coding Agent."""\n\n'
        "def greet(name: str) -> str:\n"
        '    """Return a friendly greeting."""\n'
        '    return f"Hello, {name}! Built by the multi-agent system."\n\n\n'
        'if __name__ == "__main__":\n'
        '    print(greet("World"))\n'
    )
    try:
        create_file.invoke({"path": "test_demo/src/hello.py", "content": sample_code})
    except (HumanRejectedError, FileExistsError) as e:
        ui.show_error(str(e))

    ui.console.print()

    # ── 3. Read file ───────────────────────────────────────────────────────
    ui.show_step("CODING", "Test 3 — read_file (no approval needed)")
    try:
        content = read_file.invoke({"path": "test_demo/src/hello.py"})
        ui.console.print(f"  [dim cyan]Content snippet:[/] {content[:80]!r}")
    except FileNotFoundError as e:
        ui.show_error(str(e))

    ui.console.print()

    # ── 4. List directory ──────────────────────────────────────────────────
    ui.show_step("CODING", "Test 4 — list_directory (no approval needed)")
    try:
        list_directory.invoke({"path": "test_demo/src"})
    except NotADirectoryError as e:
        ui.show_error(str(e))

    ui.console.print()

    # ── 5. Overwrite file ──────────────────────────────────────────────────
    ui.show_step("CODING", "Test 5 — overwrite_file (diff shown, HITL required)")
    updated_code = sample_code.replace(
        "Hello, {name}!",
        "Greetings, {name}! (v2)",
    )
    try:
        overwrite_file.invoke({"path": "test_demo/src/hello.py", "content": updated_code})
    except (HumanRejectedError, FileNotFoundError) as e:
        ui.show_error(str(e))

    ui.console.print()

    # ── HITL audit summary ─────────────────────────────────────────────────
    ui.show_hitl_summary()
    ui.console.rule(f"[bold {AQUA}]Test Complete[/]", style=AQUA)
