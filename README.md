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

```
1. Load profile.txt
2. Load all job files from jobs/
3. Load existing state.json (so the run is resumable)
4. Find unprocessed jobs
5. For each unprocessed job:
   - Read the job description
   - Evaluate it against the profile
   - Assign dimension scores
   - Save result to state.json
6. Rank all evaluated jobs
7. Write shortlist.json
8. Select the best job
9. Generate best_job_prep.md
10. Stop
```

This gives you: iterative progress, resumability, and a clear stopping condition.

### Architecture (5 layers)

| Layer | What it does |
|-------|-------------|
| **A. Input** | Reads `profile.txt` and all files in `jobs/` |
| **B. Reasoning** | Claude evaluates each JD using a scoring framework |
| **C. Tools** | Custom tools handle: load profile, load jobs, save evaluation, load state, write shortlist, write prep pack |
| **D. State** | `state.json` stores intermediate evaluations — makes the run resumable if interrupted |
| **E. Control loop** | Keeps going until all jobs are processed and final artifacts are written |

### Output files

| File | Description |
|------|-------------|
| `state.json` | Intermediate scores per job (resumability checkpoint) |
| `shortlist.json` | Ranked list of all evaluated jobs |
| `best_job_prep.md` | Full interview prep pack for the top-ranked job |

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
