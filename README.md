# job-post-agent-lab

A personal learning lab for building AI agents step by step using the [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk).

**Goal:** go from a simple one-shot API call to a fully autonomous agentic loop — one concept at a time.

**Rule:** start simple, test each step, then add one new capability.

---

## Learning Journey

| Step | File | Concept | What it does |
|------|------|---------|--------------|
| 1 | `step1_query.py` | One-shot call | Sends a job description to Claude, gets a single analysis back. No memory, no tools. |
| 2 | `step2_memory.py` | Session memory | Opens a session so Claude remembers what was said earlier in the same run. |
| 3 | `step3_tools.py` | Tools | Gives Claude two local tools: save an analysis to JSON, or load previously saved ones. |
| 4 | `step4_loop.py` | Agentic loop | Claude works autonomously through a batch of job files, scores each one, ranks them, and writes a prep pack — no hand-holding required. |

---

## Step 4 — Agentic Loop (deep dive)

### What it does

Instead of waiting for a human after each step, the agent runs a deterministic loop from start to finish and stops only when all work is done.

### Strategy

```mermaid
flowchart TD
    A([Start]) --> B[Load profile.txt]
    B --> C[Discover jobs/]
    C --> D[Load state.json]
    D --> E{Unprocessed\njobs remaining?}
    E -->|Yes| F[Read next job file]
    F --> G[Claude evaluates JD\nvs profile — 8 dimensions]
    G --> H[save_evaluation\n→ state.json]
    H --> E
    E -->|No| I[Rank all evaluations]
    I --> J[write_shortlist\n→ shortlist.json]
    J --> K[write_prep_pack\n→ best_job_prep.md]
    K --> L([Done])
```

This gives you: iterative progress, resumability, and a clear stopping condition.

### Architecture (5 layers)

```mermaid
flowchart LR
    subgraph A["A · Input"]
        A1[profile.txt]
        A2["jobs/*.txt"]
    end
    subgraph B["B · Reasoning"]
        B1["Claude scores each JD\nacross 8 dimensions"]
    end
    subgraph C["C · Tools"]
        C1[save_evaluation]
        C2[write_shortlist]
        C3[write_prep_pack]
    end
    subgraph D["D · State"]
        D1[("state.json\n(checkpoint)")]
    end
    subgraph E["E · Control Loop"]
        E1["Python outer loop\n(deterministic)"]
    end

    A --> E1
    E1 --> B1
    B1 --> C1
    C1 --> D1
    D1 -->|"resume check\nnext run"| E1
    C2 --> shortlist.json
    C3 --> best_job_prep.md
```

### Agentic patterns — why Python-orchestrated?

Two valid designs exist. This project uses the first one deliberately.

```mermaid
flowchart TB
    subgraph PO["Python-Orchestrated — what Step 4 builds"]
        direction LR
        P1["Python\ndecides next job"] --> P2["Claude\nevaluates it"]
        P2 --> P3["Tool: save_evaluation\n→ state.json"]
        P3 --> P1
    end

    subgraph PT["Pure Tool-Driven — Claude drives everything"]
        direction LR
        C1["Claude"] -->|"calls"| T1["load_jobs"]
        T1 --> C1
        C1 -->|"calls"| T2["save_evaluation"]
        T2 --> C1
        C1 -->|"calls"| T3["write_shortlist"]
    end

    PO -->|"chose this\nreason: deterministic + resumable"| WHY["Design decision"]
    PT -->|"more autonomous\nbut harder to control\nand debug"| WHY
```

| | Python-orchestrated | Pure tool-driven |
|---|---|---|
| Who drives the loop | Python | Claude |
| Resumability | Easy — Python tracks state | Harder — depends on Claude |
| Predictability | High | Lower |
| Autonomy | Medium | High |
| Best for | Batch jobs, reliability | Open-ended tasks |

### Output files

| File | Description |
|------|-------------|
| `state.json` | Intermediate scores per job (resumability checkpoint) |
| `shortlist.json` | Ranked list of all evaluated jobs |
| `best_job_prep.md` | Full interview prep pack for the top-ranked job |

### What's missing — the eval layer

Building the agent is step one. Knowing if its outputs are correct is step two. This is called **evaluation**, and it is the hardest skill in agent engineering.

```mermaid
flowchart TD
    A["state.json\nClaude's scores"] --> B["Pick 3 jobs manually"]
    B --> C["You score each\ndimension 1–5"]
    B --> D["Claude's scores\nfrom state.json"]
    C --> E["Compare gap\nper dimension"]
    D --> E
    E --> F{"Systematic bias?"}
    F -->|"Claude too generous"| G["Tighten\nsystem prompt"]
    F -->|"Specific dimension off"| H["Refine the\nscoring rubric"]
    F -->|"Weights feel wrong"| I["Adjust\ndimension weights"]
    G --> J["Re-run agent"]
    H --> J
    I --> J
    J --> A
```

Without this loop, you have a confident system that may be consistently wrong. Most beginners skip it. Don't.

---

## Setup

**Prerequisites:**
- Python 3.10+
- Claude Code CLI installed and authenticated (`claude` in your PATH)

**Install dependencies:**
```bash
python -m venv .venv
source .venv/bin/activate   # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**Set your API key:**
```bash
cp .env.example .env
# then edit .env and add your key
```

**Add a job description:**

Create a `notes.txt` file in the project root and paste any job posting into it.

---

## Running each step

```bash
python step1_query.py   # one-shot analysis
python step2_memory.py  # interactive session with memory
python step3_tools.py   # session with save/load tools
```

Type `exit` or press `Ctrl+C` to quit any interactive step.
