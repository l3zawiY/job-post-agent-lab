# step1_query.py
# This script demonstrates the *simplest* way to send a one-shot prompt to
# the Anthropic Claude Agent SDK for Python.  It is deliberately minimal and
# written in a very beginner-friendly style so that someone new to AI agents
# can follow along.
#
# The goal of Step 1 is to:
#  1. load a job description from a local text file (`notes.txt`)
#  2. send a stateless query to Claude using the SDK's `query()` helper
#  3. print the model's analysis (summary, requirements, interview areas)
#
# We do *not* introduce any memory, tools, or user interfaces here.  The
# script is synchronous from the caller's perspective but uses Python
# asynchronous primitives internally because the SDK uses async iterators.

# NOTE: the Anthropic SDK relies on the `claude` CLI being installed and
# authenticated (e.g. via `claude login`) or on appropriate environment
# variables.  If you run this script without logging in you will see
# a "Not logged in" error, which is caught and printed by the code below.

import asyncio
from pathlib import Path

# import the pieces we'll need from the SDK.  `query` is the simple,
# one-shot API; `ClaudeAgentOptions` lets us supply a system prompt and other
# configuration.
from claude_agent_sdk import query, ClaudeAgentOptions


def read_job_description(filename: str) -> str:
	"""Read the job description text from a file.

	Using a separate function makes it easy to replace the source later or add
	error handling without cluttering the main logic.
	"""

	path = Path(filename)
	if not path.exists():
		raise FileNotFoundError(f"Could not find {filename}")
	return path.read_text(encoding="utf-8")


async def main() -> None:
	# load the raw job description from disk
	job_text = read_job_description("notes.txt")

	# this is the "system" prompt that Claude will see; it's not part of the
	# user's question but tells the model what role it should play.
	system_prompt = (
		"You are a concise job-post prep assistant helping a beginner learn AI agents."
	)

	# build the query we will send.  It includes the job description and a
	# numbered list of the exact outputs we want.  Keeping the instructions
	# explicit helps a beginner understand what the model is being asked.
	user_prompt = (
		"Please analyze the following job description.\n\n"
		f"{job_text}\n\n"
		"1. Provide a five-line summary of the role.\n"
		"2. List the top five requirements.\n"
		"3. Suggest three likely interview focus areas.\n"
	)

	options = ClaudeAgentOptions(system_prompt=system_prompt)

	# send the query and print every message we receive.  In the simple
	# stateless pattern the SDK yields messages one after another and then
	# finishes.  Most messages contain a ``content`` field which is a list of
	# "blocks"; each block may have a ``text`` attribute.
	print("==> Sending prompt to Claude (may require you to be logged in)")
	try:
		async for msg in query(prompt=user_prompt, options=options):
			# the message object is a dataclass but we avoid depending on its
			# exact type here, just look for text-containing blocks.
			content = getattr(msg, "content", None)
			if content is None:
				# some message types (like system/init messages) don't include
				# human-readable text.  We ignore them.
				continue

			for block in content:
				# many blocks are TextBlock objects with a .text attribute;
				# others may be strings already.
				text = None
				if hasattr(block, "text"):
					text = getattr(block, "text")
				elif isinstance(block, str):
					text = block
				if text is not None:
					# print without adding extra newlines; the model output
					# may already include its own formatting.
					print(text, end="")
		print("\n==> Finished receiving model output")
	except Exception as e:  # pragma: no cover - runtime environment may differ
		# it's common for beginners to run this before configuring their
		# Claude CLI or providing credentials.  We print a friendly message
		# rather than crashing.
		print("Error during query:", e)


if __name__ == "__main__":
	# asyncio.run is the simplest way to run a top-level async function.
	asyncio.run(main())

