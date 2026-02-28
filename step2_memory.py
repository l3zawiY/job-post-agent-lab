import asyncio
from pathlib import Path

# The SDK provides two high-level interfaces: `query()` for stateless one-
# shot prompts (used in step1) and `ClaudeSDKClient` for session-based
# interactions.  We're importing the latter here along with a few helper
# classes that let us inspect messages later.
from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    AssistantMessage,  # type of message sent by the assistant
    TextBlock,         # blocks containing human-readable text
)


def read_job_description(filename: str) -> str:
    path = Path(filename)
    if not path.exists():
        raise FileNotFoundError(f"Could not find {filename}")
    # read() returns a Python string containing the entire file contents
    return path.read_text(encoding="utf-8")


async def print_assistant_text(client: ClaudeSDKClient) -> None:
    """Helper that pulls messages from the client and prints any text.

    The client streams messages back from Claude; they are not all plain text,
    so we look for AssistantMessage instances containing TextBlock objects.
    This keeps the example simple while still demonstrating how the client
    works.
    """

    async for msg in client.receive_response():
        # messages can be SystemMessage, AssistantMessage, ResultMessage, etc.
        if isinstance(msg, AssistantMessage):
            # the assistant's response is a list of content blocks
            for block in msg.content:
                if isinstance(block, TextBlock):
                    # print without adding extra newline; the model text may
                    # already include formatting
                    print(block.text, end="")
    # make sure we end with a newline after the assistant finishes
    print()


async def main() -> None:
    # Step 2 reads the same job description as before.
    job_text = read_job_description("notes.txt")

    # The system prompt now emphasizes that the assistant *will* remember
    # previous turns during this session.  "Memory" in this context simply
    # means the conversation history that ClaudeSDKClient keeps internally
    # while it's open.  When the script exits, that history is discarded.
    system_prompt = (
        "You are a concise job-post prep assistant. "
        "You remember what the user already told you in this session. "
        "Ask at most one clarifying question when necessary."
    )

    # We still pass options to the client so that the system prompt takes
    # effect.
    options = ClaudeAgentOptions(system_prompt=system_prompt)

    # `ClaudeSDKClient` is an async context manager; opening it launches a
    # connection to the CLI/backend and it stays open until we exit the block.
    # While it's open the client keeps track of all messages we send and all
    # responses we receive – this is what we mean by "memory" in Step 2.
    async with ClaudeSDKClient(options=options) as client:
        # Turn 1: we send the job description and ask for an initial analysis.
        # This message is stored internally so it's available to later turns.
        await client.query(
            "Here is the job description we will work with in this session:\n\n"
            f"{job_text}\n\n"
            "First, give a 5-line summary and top 5 requirements."
        )
        await print_assistant_text(client)

        # Now we enter a simple REPL loop where the user can ask follow-up
        # questions.  Because the `client` has kept the earlier message in
        # memory, the assistant can refer back to it automatically.
        print("\nType a follow-up question (or type 'exit'):\n")
        while True:
            user_q = input("> ").strip()
            if user_q.lower() in {"exit", "quit"}:
                # exit the loop and let the client close, which frees resources
                break

            # send whatever the user typed; ClaudeSDKClient will include the
            # previous conversation history automatically.
            await client.query(user_q)
            await print_assistant_text(client)


if __name__ == "__main__":
    asyncio.run(main())