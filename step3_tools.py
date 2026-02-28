"""step3_tools.py

Beginner-friendly example that extends the session-based assistant (Step 2)
to expose two simple local tools via the Claude Agent SDK's tool pattern.

Tools implemented:
- `save_job_analysis`: saves an analysis to `job_notes_store.json`
- `load_saved_analyses`: reads previously saved analyses

The assistant keeps conversation memory while the client is open. Tools are
registered via an in-process MCP server and exposed to the model; the model
may call them when appropriate.

This file is commented heavily to help a beginner understand each step.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# SDK imports: query-style tools are in step1; for tools we use the SDK's
# MCP tool decorator and server creation helpers, plus the session client.
from claude_agent_sdk import (
	ClaudeAgentOptions,
	ClaudeSDKClient,
	AssistantMessage,
	TextBlock,
	tool,
	create_sdk_mcp_server,
	PermissionMode,
)


# -----------------------------
# Local helper functions (not tools)
# -----------------------------

STORE_FILE = Path("job_notes_store.json")


def _read_store() -> list:
	"""Read the JSON store and return a list of analyses.

	If the file does not exist yet, return an empty list.
	"""

	if not STORE_FILE.exists():
		return []
	try:
		return json.loads(STORE_FILE.read_text(encoding="utf-8"))
	except Exception:
		return []


def _write_store(data: list) -> None:
	"""Write the given list to the JSON store (pretty-printed)."""

	STORE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# -----------------------------
# Tool definitions
# -----------------------------

# The `@tool` decorator creates a tool definition the SDK can register with
# an in-process MCP server. The handler must be async and receives a single
# dict-like argument containing the tool inputs.


@tool(
	name="save_job_analysis",
	description="Save a job analysis to a local JSON store",
	input_schema={
		"title": str,
		"summary": str,
		"requirements": str,
		"interview_focus_areas": str,
	},
)
async def save_job_analysis(args: Dict[str, Any]) -> dict:
	"""Save an analysis entry to `job_notes_store.json`.

	The handler is intentionally simple: it appends a dict with a timestamp
	to the JSON file and returns a short text confirmation.  We also print
	on stdout so you can clearly see when the tool runs.
	"""

	title = args.get("title", "(untitled)")
	summary = args.get("summary", "")
	requirements = args.get("requirements", "")
	interview_focus_areas = args.get("interview_focus_areas", "")

	entry = {
		"title": title,
		"summary": summary,
		"requirements": requirements,
		"interview_focus_areas": interview_focus_areas,
		"saved_at": datetime.utcnow().isoformat() + "Z",
	}

	# Read, append, write back
	data = _read_store()
	data.append(entry)
	_write_store(data)

	# Print to stdout to make a clear distinction between assistant output
	# and tool side-effects when running the script interactively.
	print(f"[TOOL] Saved analysis '{title}' to {STORE_FILE}")

	# The tool returns a dict containing 'content' which the SDK will convert
	# into assistant-visible output.  Keep the response human-readable.
	return {"content": [{"type": "text", "text": f"Saved analysis '{title}'."}]}


@tool(
	name="load_saved_analyses",
	description="Load previously saved job analyses from the local JSON store",
	input_schema={},
)
async def load_saved_analyses(args: Dict[str, Any]) -> dict:
	"""Return a human-readable list of saved analyses.

	We also print the number of entries to stdout so you can see the tool
	effect immediately during testing.
	"""

	data = _read_store()
	count = len(data)
	print(f"[TOOL] Loaded {count} saved analyses from {STORE_FILE}")

	if count == 0:
		text = "No saved analyses found."
	else:
		# Build a short, numbered list containing title + timestamp
		lines = [f"{i+1}. {item.get('title','(untitled)')} (saved: {item.get('saved_at')})" for i, item in enumerate(data)]
		text = "Saved analyses:\n" + "\n".join(lines)

	return {"content": [{"type": "text", "text": text}], "analyses": data}


# -----------------------------
# Main session + MCP registration
# -----------------------------


async def print_assistant_text(client: ClaudeSDKClient) -> str:
	"""Print assistant text blocks and return the combined text.

	We print as before for interactive visibility, but also return the full
	assistant output as a string so the script can parse and save it
	programmatically.
	"""

	pieces: list[str] = []
	async for msg in client.receive_response():
		if isinstance(msg, AssistantMessage):
			for block in msg.content:
				if isinstance(block, TextBlock):
					text = block.text
					pieces.append(text)
					print(text, end="")
	print()
	return "".join(pieces)


def parse_analysis(text: str) -> Dict[str, str]:
	"""Simple parser to extract summary, requirements, and interview areas.

	This function uses basic heuristics and is intentionally simple so a
	beginner can read and modify it.
	"""

	lower = text.lower()
	idx_summary = None
	idx_require = None
	idx_interview = None

	markers_summary = ["five-line summary", "five line summary", "summary"]
	markers_require = ["top five requirements", "top five", "top 5", "requirements"]
	markers_interview = ["interview focus", "interview focus areas", "likely interview"]

	for m in markers_summary:
		i = lower.find(m)
		if i != -1:
			idx_summary = i
			break
	for m in markers_require:
		i = lower.find(m)
		if i != -1:
			idx_require = i
			break
	for m in markers_interview:
		i = lower.find(m)
		if i != -1:
			idx_interview = i
			break

	end_summary = idx_require if idx_require is not None else idx_interview
	summary = text[idx_summary:end_summary].strip() if idx_summary is not None else ""

	start_require = idx_require
	end_require = idx_interview
	requirements = text[start_require:end_require].strip() if start_require is not None else ""

	interview = text[idx_interview:].strip() if idx_interview is not None else ""

	if not summary:
		lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
		summary = "\n".join(lines[:5])
	if not requirements:
		req_lines = [ln for ln in text.splitlines() if ln.strip().startswith(("1", "2", "3", "4", "5"))]
		requirements = "\n".join(req_lines[:5]) if req_lines else ""
	if not interview:
		lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
		interview = "\n".join(lines[-5:])

	return {
		"title": "Job Analysis",
		"summary": summary,
		"requirements": requirements,
		"interview_focus_areas": interview,
	}


async def main() -> None:
	# Read the job description the same way as previous steps
	job_text = Path("notes.txt").read_text(encoding="utf-8")

	system_prompt = (
		"You are a concise job-post prep assistant. "
		"You remember what the user already told you in this session. "
		"When it makes sense, you may call tools to save or load analyses."
	)

	# Create an in-process MCP server with our two tools.  This turns our
	# Python functions into callable tools available to the model.
	tools_server = create_sdk_mcp_server(name="local_tools", tools=[save_job_analysis, load_saved_analyses])

	# Tell the client about the MCP server and explicitly allow our tools.
	options = ClaudeAgentOptions(
		system_prompt=system_prompt,
		mcp_servers={"local": tools_server},
		allowed_tools=["save_job_analysis", "load_saved_analyses"],
		permission_mode="bypassPermissions",
	)

	# Open a session client; this keeps conversation memory while it's open.
	async with ClaudeSDKClient(options=options) as client:
		# Turn 1: request analysis of the job description
		print("==> Sending job description to assistant for analysis")
		await client.query(
			"Please analyze the following job description and provide:\n"
			"1) A five-line summary\n"
			"2) The top five requirements\n"
			"3) Three likely interview focus areas\n\n"
			f"{job_text}"
		)
		print("\n--- Assistant analysis ---")
		# capture the assistant text so we can parse and save it later
		analysis_text = await print_assistant_text(client)

		# Simple interactive loop: the user can ask follow-ups, request save,
		# or ask to list saved analyses.  This is a manual loop (no autonomy).
		print("\nYou can now ask follow-ups, say 'save this analysis', ")
		print("or ask 'what analyses have I saved?'. Type 'exit' to quit.")

		while True:
			user_q = input("> ").strip()
			if user_q.lower() in {"exit", "quit"}:
				break

			# If the user asks to save, parse the last assistant analysis and call
			# the local save tool handler directly (no need for the model to
			# format inputs).
			if "save" in user_q.lower() and "analys" in user_q.lower():
				payload = parse_analysis(analysis_text)
				# include a helpful title from the job text (first line)
				payload["title"] = job_text.splitlines()[0].strip() if job_text.splitlines() else payload.get("title")
				# call the async tool handler directly and show its human text
				res = await save_job_analysis.handler(payload)
				print("[SCRIPT] save_job_analysis returned:", res.get("content", [{}])[0].get("text"))
				continue

			# If the user asks to list saved analyses, call the loader tool
			if "what" in user_q.lower() and "saved" in user_q.lower():
				res = await load_saved_analyses.handler({})
				print("[SCRIPT] load_saved_analyses returned:")
				print(res.get("content", [{}])[0].get("text"))
				continue

			# Otherwise forward the user's question to the assistant (memory kept)
			await client.query(user_q)

			# Print assistant output.  If the model chooses to call one of the
			# registered tools, the tool's stdout prints (e.g. "[TOOL] ...")
			# will appear interleaved with assistant content.  Update the
			# analysis_text so subsequent 'save' uses the latest assistant output.
			analysis_text = await print_assistant_text(client)


if __name__ == "__main__":
	try:
		asyncio.run(main())
	except KeyboardInterrupt:
		print("\nGoodbye!")

