# 🔄 Workflows

> **Back to** [Documentation Hub](README.md)

---

## What Is a Workflow?

A workflow is the **sequence of steps** the system follows from the moment you type a project description to the moment the code is ready and tested.

This document explains every stage of that journey.

---

## End-to-End Workflow

Here is the full picture — from your first input to the finished project:

```mermaid
flowchart TD
    START(["👤 User starts main.py\n and enters project description"])

    R1["Research Agent\n🔍 Runs 4 web searches"]
    R2["Groq LLM\n📝 Generates Implementation Guide"]
    H1{{"⚠ HITL Gate 1\nResearch Guide Review"}}

    C1["Coding Agent\n📁 Creates folder structure"]
    H2{{"⚠ HITL Gate 2\nFolder Structure"}}
    C2["Coding Agent\n📦 pip install packages"]
    H3{{"⚠ HITL Gate 3\nPackage Installation"}}
    C3["Coding Agent\n💻 Generates code files"]
    H4{{"⚠ HITL Gate 4\nEach File Preview"}}
    C4["Coding Agent\n▶ Runs the project"]
    H5{{"⚠ HITL Gate 5\nRun Project"}}

    T1["Testing Agent\n🔬 Analyzes codebase"]
    T2["Testing Agent\n✍ Writes test files"]
    H6{{"⚠ HITL Gate 6\nTest File Plan"}}
    T3["Testing Agent\n🧪 Runs pytest"]
    H7{{"⚠ HITL Gate 7\nRun Tests"}}
    T4["Testing Agent\n📄 Writes QA report"]
    H8{{"⚠ HITL Gate 8\nFinal Report"}}

    END(["✅ Pipeline Complete\nCode + Tests + Report\nin output/"])

    START --> R1 --> R2 --> H1
    H1 -->|"APPROVE / EDIT"| C1
    H1 -->|"REJECT + feedback"| R1

    C1 --> H2
    H2 -->|"APPROVE"| C2
    H2 -->|"REJECT"| STOP1["Pipeline stops"]
    C2 --> H3
    H3 -->|"APPROVE"| C3
    C3 --> H4
    H4 -->|"APPROVE each file"| C4
    C4 --> H5

    H5 -->|"APPROVE"| T1
    H5 -->|"REJECT"| STOP2["Pipeline stops"]
    T1 --> T2 --> H6
    H6 -->|"APPROVE"| T3
    T3 --> H7
    H7 -->|"APPROVE"| T4
    T4 --> H8
    H8 -->|"APPROVE"| END
    H8 -->|"REJECT"| T1
```

---

## User Request Lifecycle

Let's trace what happens when you type: *"Build a FastAPI REST API with JWT authentication"*

### Phase 1: Research (approx. 30-60 seconds)

```mermaid
sequenceDiagram
    participant U as 👤 You
    participant UI as 🖥️ Terminal UI
    participant R as 🔍 Research Agent
    participant W as 🌐 Web (DuckDuckGo)
    participant L as 🧠 Groq LLM

    U->>UI: Types project description
    UI->>R: Passes task string
    R->>W: Search: "FastAPI JWT architecture patterns"
    W-->>R: Top 5 results
    R->>W: Search: "FastAPI libraries 2024 recommended"
    W-->>R: Top 5 results
    R->>W: Search: "FastAPI common pitfalls mistakes"
    W-->>R: Top 5 results
    R->>W: Search: "FastAPI project folder structure Python"
    W-->>R: Top 5 results
    R->>L: "Here is the task + all search results. Generate a guide."
    L-->>R: Returns Implementation Guide (Markdown)
    R->>UI: Displays guide on screen
    UI-->>U: ⚠ "APPROVE / REJECT / EDIT this guide?"
```

### Phase 2: Coding (approx. 1-3 minutes)

```mermaid
sequenceDiagram
    participant U as 👤 You
    participant UI as 🖥️ Terminal UI
    participant C as 🖊️ Coding Agent
    participant FS as 📁 Filesystem
    participant PY as 🐍 Python/pip

    UI-->>C: Guide approved
    C->>UI: Shows proposed folder tree
    UI-->>U: ⚠ "CREATE folder structure?"
    U-->>C: APPROVE
    C->>FS: mkdir app/, app/core/, app/api/, etc.
    C->>UI: Shows package list
    UI-->>U: ⚠ "Install: fastapi, uvicorn, sqlalchemy...?"
    U-->>C: APPROVE
    C->>PY: pip install fastapi uvicorn sqlalchemy...
    loop For each file
        C->>UI: Shows file preview (first 30 lines)
        UI-->>U: ⚠ "CREATE FILE main.py?"
        U-->>C: APPROVE
        C->>FS: Writes file to output/generated_code/
    end
    C->>PY: python app/main.py (5s timeout)
```

### Phase 3: Testing (approx. 30-60 seconds)

```mermaid
sequenceDiagram
    participant U as 👤 You
    participant UI as 🖥️ Terminal UI
    participant T as 🧪 Testing Agent
    participant FS as 📁 Filesystem
    participant PT as 🧪 pytest

    T->>FS: Reads all generated files
    T->>UI: "Will create tests/test_main.py with 5 test cases"
    UI-->>U: ⚠ "APPROVE test plan?"
    U-->>T: APPROVE
    T->>FS: Writes test files
    UI-->>U: ⚠ "RUN pytest?"
    U-->>T: APPROVE
    T->>PT: pytest output/generated_code/tests/ -v --cov
    PT-->>T: Results (pass/fail + coverage %)
    T->>UI: Shows QA Report preview
    UI-->>U: ⚠ "APPROVE final report?"
    U-->>T: APPROVE
    T->>FS: Saves FINAL_REPORT.md
```

---

## Approval Process

Every HITL (Human In The Loop) gate works the same way:

```mermaid
stateDiagram-v2
    [*] --> ShowPanel : Agent proposes action
    ShowPanel --> WaitingForInput : Display ⚠ panel with details
    WaitingForInput --> Approved : User types APPROVE (or A)
    WaitingForInput --> Rejected : User types REJECT (or R)
    WaitingForInput --> Editing : User types EDIT (or E)
    Approved --> Receipt : Print ✓ receipt with timestamp
    Rejected --> Receipt : Print ✗ receipt
    Editing --> MultiLineInput : User pastes replacement content
    MultiLineInput --> WaitForEnd : Reads lines until ---END---
    WaitForEnd --> Receipt : Print ✎ receipt
    Receipt --> [*] : Resume pipeline
```

### What you type

| Input | Meaning |
|-------|---------|
| `APPROVE` or `A` | Go ahead — run this action |
| `REJECT` or `R` | Do not run this — skip or stop |
| `EDIT` or `E` | I want to change it — show me the input prompt |

### Multi-line EDIT

When you choose `EDIT`, you can paste multiple lines. Type `---END---` on its own line to finish:

```
> EDIT
Enter replacement value. Type ---END--- on its own line when finished:
> from fastapi import FastAPI
> app = FastAPI()
> 
> @app.get("/")
> def root():
>     return {"message": "Hello"}
> ---END---

✎ Human edited CREATE FILE → main.py at 14:32:01
```

---

## Error Handling

```mermaid
flowchart TD
    Run["Project runs"] --> Check{Exit code?}
    Check -->|"0 = Success"| OK["✅ Continue to Testing"]
    Check -->|"Non-zero = Crash"| Err["Show error output"]
    Err --> Fix["LLM proposes fix"]
    Fix --> Gate{{"⚠ HITL: Approve fix?"}}
    Gate -->|"APPROVE"| Apply["Apply fix\nRetry (max 3 times)"]
    Gate -->|"REJECT"| Stop["Stop run loop\nProceed to next step"]
    Apply --> Run
    Apply -->|"Attempt 3 fails"| Stop
```

The system tries up to **3 automatic fixes** before giving up. You approve each fix before it is applied.

---

## Key Takeaways

> - There are **8+ HITL gates** in a typical pipeline run
> - You can `EDIT` any proposed content — you are always in control
> - The pipeline can **go backwards** (e.g., REJECT the guide → regenerate)
> - If the project crashes, the system tries to **auto-fix** it (with your permission)
> - All output is written to `output/generated_code/` — nothing else is touched

---

**Next:** [Folder Structure →](folder-structure.md)
