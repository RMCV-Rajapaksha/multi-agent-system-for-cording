#!/usr/bin/env python3
"""
Multi-Agent LangGraph System — Project Setup Script
Uses the Rich library for beautiful terminal output (Windows-safe).
"""

import os
import sys
import subprocess
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Bootstrap Rich ──────────────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.tree import Tree
    from rich.rule import Rule
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

AQUA = "#00FFFF"

# ── Console helpers ─────────────────────────────────────────────────────────────
if RICH_AVAILABLE:
    console = Console(highlight=False)

    def aqua_panel(title: str, body: str, border_style: str = AQUA) -> None:
        console.print(Panel(body, title=f"[bold {AQUA}]{title}[/]",
                            border_style=border_style, expand=False))

    def step_rule(msg: str) -> None:
        console.rule(f"[bold {AQUA}]{msg}[/]")

    def ok(msg: str) -> None:
        console.print(f"  [bold green]OK[/]  {msg}")

    def info(msg: str) -> None:
        console.print(f"  [bold {AQUA}]>>[/]  {msg}")

    def err(msg: str) -> None:
        console.print(f"  [bold red]ERR[/] {msg}")

else:
    def aqua_panel(title, body, border_style=AQUA):
        border = "-" * 53
        print(f"\n+{border}+")
        print(f"|  {title:<51}|")
        print(f"|{'-'*53}|")
        for line in body.splitlines():
            print(f"|  {line:<51}|")
        print(f"+{border}+\n")

    def step_rule(msg):
        print(f"\n{'='*20} {msg} {'='*20}")

    def ok(msg):   print(f"  [OK]  {msg}")
    def info(msg): print(f"  [>>]  {msg}")
    def err(msg):  print(f"  [ERR] {msg}")


# ══════════════════════════════════════════════════════════════════════
# STEP 1 — Folder structure
# ══════════════════════════════════════════════════════════════════════
def step1_folder_structure() -> Path:
    step_rule("STEP 1 -- Create Folder Structure")

    base = Path(__file__).parent  # multi-agent-system/

    folders = [
        base / "agents",
        base / "tools",
        base / "graph",
        base / "ui",
        base / "output" / "generated_code",
        base / "output" / "test_reports",
    ]

    created = []
    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)
        gitkeep = folder / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()
        created.append(str(folder.relative_to(base.parent)))

    body = "\n".join(f"  [DIR]  {p}" for p in created)
    aqua_panel("Folders Created", body)
    ok("All directories created (with .gitkeep placeholders).")
    return base


# ══════════════════════════════════════════════════════════════════════
# STEP 2 — requirements.txt
# ══════════════════════════════════════════════════════════════════════
def step2_requirements(base: Path) -> None:
    step_rule("STEP 2 -- requirements.txt")

    req_path = base / "requirements.txt"
    if not req_path.exists():
        err("requirements.txt not found.")
        sys.exit(1)

    packages = req_path.read_text(encoding="utf-8").strip().splitlines()
    body = "\n".join(f"  * {p}" for p in packages if p.strip())
    aqua_panel("requirements.txt -- packages", body)
    ok(f"requirements.txt verified at {req_path}")


# ══════════════════════════════════════════════════════════════════════
# STEP 3 — .env.example
# ══════════════════════════════════════════════════════════════════════
def step3_env_example(base: Path) -> None:
    step_rule("STEP 3 -- .env.example")

    env_src = base / ".env.example"
    if not env_src.exists():
        err(".env.example not found.")
        sys.exit(1)

    body = env_src.read_text(encoding="utf-8").strip()
    aqua_panel(".env.example", body)
    ok(".env.example verified.")


# ══════════════════════════════════════════════════════════════════════
# STEP 4 — Human-in-the-Loop approval
# ══════════════════════════════════════════════════════════════════════
def step4_approval() -> bool:
    step_rule("STEP 4 -- HUMAN-IN-THE-LOOP Approval")

    approval_lines = [
        "  APPROVAL REQUIRED -- Package Installation",
        "",
        "  The following packages will be installed:",
        "    langgraph, langchain, langchain-groq,",
        "    langchain-community, duckduckgo-search,",
        "    tavily-python, rich, pytest, pytest-cov,",
        "    pytest-html, python-dotenv",
        "",
        "  Type  APPROVE  to continue",
        "  Type  REJECT   to cancel",
    ]

    if RICH_AVAILABLE:
        body = Text("\n".join(approval_lines))
        console.print(
            Panel(
                body,
                title="[bold yellow]  !! ACTION REQUIRED !![/]",
                border_style="yellow",
                expand=False,
                padding=(1, 2),
            )
        )
        console.print()
        answer = console.input(f"[bold {AQUA}]  Your choice > [/]").strip().upper()
    else:
        border = "-" * 53
        print(f"\n+{border}+")
        print(f"|  !! APPROVAL REQUIRED -- Package Installation !!   |")
        print(f"|{'-'*53}|")
        for line in approval_lines[2:]:
            print(f"|{line:<53}|")
        print(f"+{border}+\n")
        answer = input("  Your choice > ").strip().upper()

    if answer == "APPROVE":
        ok("Approval received -- proceeding with installation.")
        return True
    else:
        if RICH_AVAILABLE:
            console.print(
                Panel("[bold red]  Installation cancelled.[/]",
                      border_style="red", expand=False)
            )
        else:
            print("\n  Installation cancelled.\n")
        return False


# ══════════════════════════════════════════════════════════════════════
# STEP 5 — pip install
# ══════════════════════════════════════════════════════════════════════
def step5_pip_install(base: Path) -> None:
    step_rule("STEP 5 -- pip install -r requirements.txt")

    req_path = base / "requirements.txt"
    cmd = [sys.executable, "-m", "pip", "install", "-r", str(req_path)]

    info(f"Running: {' '.join(cmd)}")
    if RICH_AVAILABLE:
        console.print()

    result = subprocess.run(cmd, text=True, capture_output=False)

    if result.returncode == 0:
        ok("All packages installed successfully.")
    else:
        err(f"pip exited with code {result.returncode}.")
        sys.exit(result.returncode)


# ══════════════════════════════════════════════════════════════════════
# STEP 6 — Folder tree
# ══════════════════════════════════════════════════════════════════════
def step6_tree(base: Path) -> None:
    step_rule("STEP 6 -- Final Project Tree")

    if RICH_AVAILABLE:
        def build_tree(directory: Path, tree: Tree) -> None:
            try:
                entries = sorted(directory.iterdir(),
                                 key=lambda p: (p.is_file(), p.name.lower()))
            except PermissionError:
                return
            for entry in entries:
                if entry.name.startswith(".") and entry.name != ".env.example":
                    continue
                if entry.is_dir():
                    branch = tree.add(f"[bold cyan]{entry.name}/[/]")
                    build_tree(entry, branch)
                else:
                    tree.add(f"[green]{entry.name}[/]")

        tree = Tree(
            f"[bold {AQUA}]{base.name}/[/]",
            guide_style=AQUA,
        )
        build_tree(base, tree)

        console.print(
            Panel(tree, title=f"[bold {AQUA}]Project Structure[/]",
                  border_style=AQUA, expand=False)
        )
    else:
        print("\n  Project tree:\n")
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in sorted(dirs) if not d.startswith(".")]
            level = len(Path(root).relative_to(base).parts)
            indent = "    " * (level + 1)
            print(f"{indent}[DIR] {Path(root).name}/")
            for f in sorted(files):
                print(f"{indent}      {f}")


# ══════════════════════════════════════════════════════════════════════
# SUCCESS SUMMARY
# ══════════════════════════════════════════════════════════════════════
def success_summary() -> None:
    step_rule("Setup Complete")

    summary = (
        f"[bold green]Multi-Agent LangGraph System -- Ready![/]\n\n"
        f"  [bold {AQUA}]Agents   :[/] Research  |  Coding  |  Testing\n"
        f"  [bold {AQUA}]Stack    :[/] LangGraph + LangChain + Groq\n\n"
        f"  [bold {AQUA}]Next Steps:[/]\n"
        f"    1.  Copy  .env.example  =>  .env\n"
        f"    2.  Fill in your GROQ_API_KEY (and optionally TAVILY_API_KEY)\n"
        f"    3.  Build your agents in  agents/\n"
        f"    4.  Wire the graph in    graph/\n"
        f"    5.  Add tools in         tools/\n"
    )

    if RICH_AVAILABLE:
        console.print(
            Panel(summary, title="[bold green]  SUCCESS[/]",
                  border_style="green", expand=False, padding=(1, 2))
        )
    else:
        print("\n  SUCCESS -- Multi-Agent LangGraph System is Ready!")
        print("  Next: copy .env.example -> .env, add your API key, build agents.\n")


# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════
def main() -> None:
    if RICH_AVAILABLE:
        console.rule(f"[bold {AQUA}]Multi-Agent LangGraph -- Project Setup[/]", style=AQUA)
    else:
        print("\n" + "=" * 55)
        print("   Multi-Agent LangGraph -- Project Setup")
        print("=" * 55)

    base = step1_folder_structure()
    step2_requirements(base)
    step3_env_example(base)

    approved = step4_approval()
    if not approved:
        sys.exit(0)

    step5_pip_install(base)
    step6_tree(base)
    success_summary()


if __name__ == "__main__":
    main()
