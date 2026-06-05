# ⚙️ Installation Guide

> **Back to** [Documentation Hub](README.md)

---

## Prerequisites

Before you start, make sure you have these installed on your computer:

| Tool | Version | How to check | Download |
|------|---------|--------------|----------|
| Python | 3.10 or higher | `python --version` | [python.org](https://python.org) |
| pip | Comes with Python | `pip --version` | — |
| Git | Any recent version | `git --version` | [git-scm.com](https://git-scm.com) |

You also need:
- A **Groq API key** (free at [console.groq.com](https://console.groq.com)) for the LLM
- Optionally: a **Tavily API key** (free tier available at [tavily.com](https://tavily.com)) for enhanced web search

> **No API key?** No problem! The system runs in **MOCK mode** without any keys. It skips real LLM calls and uses pre-written example outputs. This is great for testing the UI and workflow.

---

## Step 1: Clone the Repository

Open your terminal and run:

```bash
git clone https://github.com/RMCV-Rajapaksha/multi-agent-system-for-cording.git
cd multi-agent-system-for-cording/multi-agent-system
```

---

## Step 2: Create a Virtual Environment

A virtual environment keeps this project's packages separate from the rest of your computer. This is strongly recommended.

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` appear at the start of your terminal prompt. That means it worked!

---

## Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs all required packages. Here is what gets installed:

| Package | Version | Purpose |
|---------|---------|---------|
| `langgraph` | ≥0.2.0 | AI pipeline orchestration |
| `langchain` | ≥0.3.0 | AI tool framework |
| `langchain-groq` | ≥0.2.0 | Groq LLM connector |
| `langchain-community` | ≥0.3.0 | Community tools |
| `ddgs` | ≥1.0.0 | DuckDuckGo web search (free) |
| `tavily-python` | ≥0.3.0 | Tavily search (optional) |
| `rich` | ≥13.0.0 | Beautiful terminal UI |
| `pytest` | ≥8.0.0 | Running tests |
| `pytest-cov` | ≥5.0.0 | Test coverage reports |
| `pytest-html` | ≥4.0.0 | HTML test reports |
| `python-dotenv` | ≥1.0.0 | Loading `.env` files |

---

## Step 4: Configure API Keys

Copy the example environment file:

**Windows:**
```powershell
copy .env.example .env
```

**macOS / Linux:**
```bash
cp .env.example .env
```

Open `.env` in any text editor and fill in your keys:

```env
# Required for LLM calls
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Optional: for enhanced web search
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

> 🔒 **Important:** Never share your `.env` file or commit it to Git. It is already in `.gitignore`.

---

## Step 5: Run the System

```bash
python main.py
```

You should see the Aqua-colored welcome banner appear, followed by a prompt:

```
────────── Multi-Agent System for Coding ──────────
  Welcome to the Autonomous LangGraph Coding Pipeline!

  What project do you want to build? >
```

Type your project description and press Enter. The pipeline will start!

---

## Example First Run

Try this prompt to test everything works:

```
What project do you want to build? > Build a simple Python script that converts Celsius to Fahrenheit
```

This is a small enough task that MOCK mode will handle it quickly, letting you see all the HITL gates in action.

---

## Verifying Installation

To test the tools individually:

```bash
# Test search tools (no API key needed — uses DuckDuckGo)
python tools/search_tools.py

# Test the terminal tools (will ask for one approval)
python tools/terminal_tools.py

# Test the Research Agent alone
python agents/research_agent.py

# Test the Coding Agent alone
python agents/coding_agent.py
```

---

## Troubleshooting Installation

| Problem | Solution |
|---------|----------|
| `python: command not found` | Use `python3` instead of `python` |
| `pip: command not found` | Use `pip3` instead |
| `ModuleNotFoundError: No module named 'langgraph'` | Make sure your venv is activated and run `pip install -r requirements.txt` again |
| `UnicodeEncodeError` on Windows | The code adds a UTF-8 fix automatically, but you may need to set `PYTHONIOENCODING=utf-8` in PowerShell |
| SSL errors with DuckDuckGo | This sometimes happens on corporate networks — try using a personal network or Tavily instead |

For more help, see [Troubleshooting](troubleshooting.md).

---

## Key Takeaways

> - Python 3.10+ is required
> - Create a virtual environment before installing packages
> - Copy `.env.example` → `.env` and add your Groq API key
> - The system works **without any API keys** in MOCK mode
> - Run `python main.py` to start

---

**Next:** [Configuration Guide →](configuration.md)
