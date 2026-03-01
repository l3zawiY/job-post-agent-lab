"""step4_loop.py

Goal-driven agentic loop: process a batch of job files, score each one
against your profile, rank them, and produce two output artifacts
(shortlist.json and best_job_prep.md) — no human intervention required.

New concepts introduced here versus Step 3:
- Python controls a deterministic outer loop (progress tracking)
- State is saved incrementally to state.json  →  resumable if interrupted
- The agent stops only when all work is done (clear stopping condition)
- Tools perform real file writes, not just logging
- No user input required; the system is fully goal-driven

Architecture (5 layers):
  A. Input   — reads profile.txt and all files in jobs/
  B. Reasoning — Claude evaluates each JD using the scoring framework below
  C. Tools   — save_evaluation, write_shortlist, write_prep_pack
  D. State   — state.json keeps intermediate results so the run is resumable
  E. Loop    — Python iterates over unprocessed jobs; Claude handles each one
"""

import asyncio
import json
from pathlib import Path
from typing import Any, Dict

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    AssistantMessage,
    TextBlock,
    tool,
    create_sdk_mcp_server,
)

# ── File paths ────────────────────────────────────────────────────────────────

PROFILE_FILE   = Path("profile.txt")
JOBS_DIR       = Path("jobs")
STATE_FILE     = Path("state.json")
SHORTLIST_FILE = Path("shortlist.json")
PREP_PACK_FILE = Path("best_job_prep.md")

# ── State helpers (pure Python, not tools) ────────────────────────────────────


def load_state() -> dict:
    """Load intermediate evaluations from state.json.

    Returns an empty dict if the file does not exist yet.  The dict maps
    job filenames to their evaluation records so the loop can skip jobs
    that were already processed on a previous run.
    """
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state: dict) -> None:
    """Persist the current state dict to state.json (pretty-printed)."""
    STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ── Tools ─────────────────────────────────────────────────────────────────────
#
# Three tools cover all file I/O.  Their handlers are pure async functions;
# the @tool decorator turns them into MCP-compatible tool definitions that
# ClaudeSDKClient will expose to the model.

@tool(
    name="save_evaluation",
    description=(
        "Save a structured evaluation of one job to state.json. "
        "Call this immediately after evaluating each job description."
    ),
    input_schema={
        # All values are strings so the model never has to worry about
        # JSON-encoding nested objects; we parse scores_json ourselves.
        "job_file":            str,
        "title_guess":         str,
        "summary":             str,
        "top_requirements":    str,
        "strengths_of_fit":    str,
        "risks_or_objections": str,
        # JSON string encoding an object with the 8 dimension scores
        "scores_json":         str,
        # Numeric string e.g. "3.75"
        "overall_score":       str,
        # "Pursue strongly" | "Pursue selectively" | "Low priority" | "Skip"
        "recommendation":      str,
        "notes":               str,
    },
)
async def save_evaluation(args: Dict[str, Any]) -> dict:
    """Append or update one job evaluation inside state.json."""

    job_file = args.get("job_file", "unknown")

    # Parse scores safely — Claude passes a JSON string per the schema
    scores_raw = args.get("scores_json", "{}")
    try:
        scores = json.loads(scores_raw) if isinstance(scores_raw, str) else scores_raw
    except json.JSONDecodeError:
        scores = {}

    try:
        overall_score = float(args.get("overall_score", 0))
    except (ValueError, TypeError):
        overall_score = 0.0

    state = load_state()
    state[job_file] = {
        "job_file":            job_file,
        "title_guess":         args.get("title_guess", ""),
        "summary":             args.get("summary", ""),
        "top_requirements":    args.get("top_requirements", ""),
        "strengths_of_fit":    args.get("strengths_of_fit", ""),
        "risks_or_objections": args.get("risks_or_objections", ""),
        "scores":              scores,
        "overall_score":       overall_score,
        "recommendation":      args.get("recommendation", ""),
        "notes":               args.get("notes", ""),
    }
    save_state(state)

    print(f"[TOOL] save_evaluation  →  '{job_file}' saved (score: {overall_score:.2f})")
    return {
        "content": [
            {"type": "text", "text": f"Saved evaluation for '{job_file}' (overall_score={overall_score:.2f})."}
        ]
    }


@tool(
    name="write_shortlist",
    description=(
        "Write shortlist.json with all evaluated jobs ranked from best to worst. "
        "Call this once — only after all individual jobs have been evaluated."
    ),
    input_schema={
        # JSON array string of filenames ordered best → worst, e.g.
        # '["job3.txt", "job1.txt", "job2.txt"]'
        "ranked_job_files": str,
    },
)
async def write_shortlist(args: Dict[str, Any]) -> dict:
    """Produce shortlist.json from state.json, ordered by the provided ranking."""

    raw = args.get("ranked_job_files", "[]")
    try:
        ranked_files: list = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        ranked_files = []

    state = load_state()

    # Build ordered list; unranked jobs go at the bottom (safety net)
    seen: set = set()
    shortlist: list = []
    for rank, job_file in enumerate(ranked_files, start=1):
        entry = dict(state.get(job_file, {"job_file": job_file}))
        entry["rank"] = rank
        shortlist.append(entry)
        seen.add(job_file)

    extra_rank = len(shortlist) + 1
    for job_file, entry in state.items():
        if job_file not in seen:
            entry = dict(entry)
            entry["rank"] = extra_rank
            shortlist.append(entry)
            extra_rank += 1

    SHORTLIST_FILE.write_text(
        json.dumps(shortlist, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[TOOL] write_shortlist  →  {len(shortlist)} jobs written to {SHORTLIST_FILE}")
    return {
        "content": [
            {"type": "text", "text": f"Wrote shortlist.json with {len(shortlist)} ranked jobs."}
        ]
    }


@tool(
    name="write_prep_pack",
    description=(
        "Write best_job_prep.md — a full interview prep pack for the top-ranked job. "
        "Call this after write_shortlist. The markdown_content field must be the "
        "complete markdown text of the prep pack."
    ),
    input_schema={
        "job_file":         str,
        "markdown_content": str,
    },
)
async def write_prep_pack(args: Dict[str, Any]) -> dict:
    """Write the prep pack markdown to best_job_prep.md."""

    job_file = args.get("job_file", "unknown")
    content  = args.get("markdown_content", "")

    PREP_PACK_FILE.write_text(content, encoding="utf-8")
    print(f"[TOOL] write_prep_pack  →  prep pack for '{job_file}' written to {PREP_PACK_FILE}")
    return {
        "content": [
            {"type": "text", "text": f"Wrote best_job_prep.md for '{job_file}'."}
        ]
    }


# ── Response helper ───────────────────────────────────────────────────────────


async def stream_response(client: ClaudeSDKClient) -> str:
    """Consume the response stream, print assistant text, and return it.

    Tool calls made by the model will trigger our handler functions
    (which print their own [TOOL] lines); text blocks are printed here.
    """
    pieces: list[str] = []
    async for msg in client.receive_response():
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    pieces.append(block.text)
                    print(block.text, end="", flush=True)
    print()
    return "".join(pieces)


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a skeptical job-shortlisting assistant.
Your sole job is to evaluate job descriptions against a candidate profile, \
score them across 8 dimensions, and generate the final output artifacts.

Scoring dimensions (each 1–5):
  sellability            — how likely a recruiter screens this candidate positively
  ownership              — real product ownership vs coordination / admin work
  product_ai_fit         — fit with the candidate's product + AI/analytics background
  domain_fit             — domain match (fintech, SaaS, AI products, data, etc.)
  seniority_fit          — seniority level credibility given the candidate's background
  language_advantage     — English/French bilingual advantage (1 = none, 5 = strong)
  excitement             — genuine role excitement and motivation signal
  tailoring_feasibility  — how easily the resume can be tailored to this role

Weighted overall_score formula:
  sellability × 0.25 + ownership × 0.15 + product_ai_fit × 0.15 +
  domain_fit × 0.10 + seniority_fit × 0.10 + language_advantage × 0.05 +
  excitement × 0.10 + tailoring_feasibility × 0.10

Recommendation labels (pick exactly one):
  "Pursue strongly" | "Pursue selectively" | "Low priority" | "Skip"

Behavior rules:
- Be concise and skeptical. Do not flatter. Do not assume fit.
- Separate true fit from sellability explicitly.
- Flag objections and risks even for high-scoring roles.
- After evaluating each job: call save_evaluation immediately.
- After all jobs are evaluated: call write_shortlist, then write_prep_pack.
"""

# ── Main agentic loop ─────────────────────────────────────────────────────────


async def main() -> None:

    # ── A. Input layer ──────────────────────────────────────────────────────
    if not PROFILE_FILE.exists():
        raise FileNotFoundError("profile.txt not found — create it before running.")
    profile_text = PROFILE_FILE.read_text(encoding="utf-8")

    job_files = sorted(JOBS_DIR.glob("*.txt"))
    if not job_files:
        raise FileNotFoundError(f"No .txt files found in {JOBS_DIR}/")

    print(f"\nFound {len(job_files)} job file(s): {[f.name for f in job_files]}")

    # ── B. State layer (resumability) ───────────────────────────────────────
    state      = load_state()
    processed  = set(state.keys())
    unprocessed = [f for f in job_files if f.name not in processed]

    print(f"Already processed : {len(processed)} | Remaining : {len(unprocessed)}")

    # ── C. Tool registration and session setup ──────────────────────────────
    tools_server = create_sdk_mcp_server(
        name="job_tools",
        tools=[save_evaluation, write_shortlist, write_prep_pack],
    )

    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={"local": tools_server},
        allowed_tools=["save_evaluation", "write_shortlist", "write_prep_pack"],
        permission_mode="bypassPermissions",
    )

    # A single ClaudeSDKClient session is kept open for the entire run so
    # the model retains context from earlier evaluations when it does the
    # final ranking.  This is the "memory" layer that Step 2 introduced.
    async with ClaudeSDKClient(options=options) as client:

        # ── D. Control loop — evaluate each unprocessed job ─────────────────
        for job_file in unprocessed:
            job_text = job_file.read_text(encoding="utf-8")

            print(f"\n{'─' * 60}")
            print(f"Evaluating : {job_file.name}")
            print(f"{'─' * 60}")

            # The prompt gives Claude both the profile and the job description.
            # The system prompt instructs it to call save_evaluation when done.
            await client.query(
                f"CANDIDATE PROFILE:\n{profile_text}\n\n"
                f"JOB FILE: {job_file.name}\n"
                f"JOB DESCRIPTION:\n{job_text}\n\n"
                "Evaluate this job against the profile. Compute all 8 dimension "
                "scores and the weighted overall_score. Then call save_evaluation "
                "with:\n"
                f"  job_file        = '{job_file.name}'\n"
                "  scores_json     = JSON string of the 8 dimension scores\n"
                "  overall_score   = numeric string (e.g. '3.60')\n"
                "  recommendation  = one of the four labels\n"
                "All other fields as described in the tool schema."
            )
            await stream_response(client)

        # ── E. Final outputs — rank and write artifacts ──────────────────────
        # Reload state so we have fresh scores from this run
        state = load_state()

        if not state:
            print("No evaluations found in state.json. Nothing to rank.")
            return

        jobs_summary = "\n".join(
            f"  {e['job_file']}: {e.get('title_guess', '?')} | "
            f"score={e.get('overall_score', 0):.2f} | {e.get('recommendation', '')}"
            for e in state.values()
        )

        print(f"\n{'─' * 60}")
        print("Ranking all jobs and writing final outputs...")
        print(f"{'─' * 60}\n")

        await client.query(
            f"All evaluated jobs:\n{jobs_summary}\n\n"
            "Complete the final two steps in order:\n\n"
            "1. Call write_shortlist with ranked_job_files = a JSON array string "
            "of all job filenames ordered from highest to lowest overall_score.\n\n"
            "2. Call write_prep_pack for the top-ranked job. The markdown_content "
            "must be a detailed, self-contained prep pack in markdown with these "
            "sections:\n"
            "   # [Job title] — [job_file]\n"
            "   ## Why it ranked first\n"
            "   ## Main requirements\n"
            "   ## Why the candidate is credible\n"
            "   ## Likely objections\n"
            "   ## 5 likely interview themes\n"
            "   ## 3–5 story areas to prepare\n"
            "   ## 30-minute prep checklist\n"
            "   ## Questions to ask the interviewer\n"
        )
        await stream_response(client)

    # ── F. Summary ───────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("Agent loop complete.")
    print(f"  {STATE_FILE}      →  {len(state)} job evaluation(s)")
    print(f"  {SHORTLIST_FILE}  →  ranked shortlist")
    print(f"  {PREP_PACK_FILE}  →  prep pack for top job")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted. Run again to resume — progress is saved in state.json.")
