# 📁 Folder Structure

> **Back to** [Documentation Hub](README.md)

---

## Complete Repository Tree

```text
multi-agent-system/                     ← Project root
│
├── 📄 main.py                          ← Entry point. Run this to start the pipeline
├── 📄 requirements.txt                 ← Python packages to install
├── 📄 setup.py                         ← Optional setup/installation script
├── 📄 README.md                        ← Top-level project description
├── 📄 .env.example                     ← Template for your API keys (copy → .env)
├── 📄 .env                             ← YOUR API keys (never commit this!)
│
├── 📂 agents/                          ← The three AI agents
│   ├── 📄 research_agent.py            ← Agent 1: researches and plans
│   ├── 📄 coding_agent.py              ← Agent 2: generates code
│   └── 📄 testing_agent.py            ← Agent 3: writes and runs tests
│
├── 📂 graph/                           ← LangGraph orchestration
│   ├── 📄 orchestrator.py             ← Wires agents into a StateGraph
│   └── 📄 state.py                    ← Defines AgentState (shared data)
│
├── 📂 tools/                           ← Reusable tools for agents
│   ├── 📄 search_tools.py             ← web_search() and deep_search()
│   ├── 📄 terminal_tools.py           ← run_command() with safety checks
│   └── 📄 filesystem_tools.py        ← create_file(), create_directory()
│
├── 📂 ui/                              ← Terminal user interface
│   └── 📄 terminal_ui.py              ← AgentUI class (Rich live dashboard)
│
├── 📂 output/                          ← Everything the system generates
│   ├── 📂 generated_code/             ← ⚠ SANDBOX: all AI-written code goes here
│   │   ├── app/                       ← Your generated project (example)
│   │   ├── tests/
│   │   └── requirements.txt
│   └── 📂 test_reports/              ← pytest HTML reports and FINAL_REPORT.md
│
├── 📂 docs/                            ← 📚 You are here — all documentation
│   ├── 📄 README.md
│   ├── 📄 project-overview.md
│   ├── 📄 system-architecture.md
│   ├── 📄 agent-architecture.md
│   ├── 📄 workflows.md
│   ├── 📄 folder-structure.md
│   ├── 📄 installation.md
│   ├── 📄 configuration.md
│   ├── 📄 api-documentation.md
│   ├── 📄 database.md
│   ├── 📄 deployment.md
│   ├── 📄 security.md
│   ├── 📄 troubleshooting.md
│   ├── 📄 developer-guide.md
│   └── 📄 glossary.md
│
└── 📂 venv/                            ← Python virtual environment (do not edit)
```

---

## Important Files Explained

### `main.py` — The Entry Point

This is the **only file you need to run**. It:
1. Loads environment variables from `.env`
2. Creates the `AgentUI` instance
3. Asks you for the project description
4. Calls `run_pipeline(task)` in `graph/orchestrator.py`
5. Prints the step log and HITL audit table at the end

```python
# Simplified view of main.py
async def main():
    ui = AgentUI()
    task = ui.console.input("What project do you want to build? > ")
    final_state = await run_pipeline(task)
    ui.show_hitl_summary()
```

### `graph/state.py` — The Shared Notebook

All agents read from and write to this single Python `TypedDict`. Think of it as the **shared whiteboard** the team uses. See [Agent Architecture](agent-architecture.md) for the full list of fields.

### `tools/filesystem_tools.py` — The Safe File Writer

```text
_SANDBOX = output/generated_code/
```

This file defines `_SANDBOX` — the **only folder the AI can write to**. If any agent tries to write a file outside this folder (e.g., to `C:\Windows`), the system raises an error and blocks it.

### `.env.example` — API Key Template

```env
# Required: Groq API key for LLM inference
GROQ_API_KEY=your_groq_key_here

# Optional: Tavily API key for web search (Research agent)
TAVILY_API_KEY=your_tavily_key_here
```

Copy this to `.env` and fill in your real keys. **Never commit `.env` to Git** — it is in `.gitignore`.

---

## Folder Responsibilities

| Folder | What lives here | Who uses it |
|--------|----------------|-------------|
| `agents/` | The three AI agent scripts | Orchestrator, developers |
| `graph/` | LangGraph wiring and shared state | All agents via import |
| `tools/` | Reusable LangChain tools | Individual agents |
| `ui/` | The Rich terminal dashboard | All agents via singleton |
| `output/generated_code/` | **AI-generated project files** | Coding Agent (writes), Testing Agent (reads) |
| `output/test_reports/` | pytest HTML reports and QA report | Testing Agent (writes) |
| `docs/` | All project documentation | Developers and users |
| `venv/` | Python virtual environment | Python runtime |

---

## Why This Structure?

### Separation of Concerns

Each folder has **one clear job**:
- `agents/` = intelligence and decision making
- `tools/` = safe primitive operations
- `graph/` = coordination and state
- `ui/` = what you see on screen
- `output/` = what gets generated (sandboxed)

### Safety by Design

The `output/generated_code/` sandbox means the AI can **never** accidentally modify your own project files. Even if the LLM generates code that tries to overwrite `main.py`, the filesystem tool will block it.

---

## Key Takeaways

> - Run `main.py` to start everything
> - All AI-generated code lands in `output/generated_code/` — nowhere else
> - Your API keys go in `.env` (never commit it!)
> - `graph/state.py` is the central data store — all agents share it

---

**Next:** [Installation Guide →](installation.md)
