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
| 4 | `step4_loop.py` | Agentic loop | (In progress) Claude works toward a goal autonomously without waiting for each instruction. |

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
