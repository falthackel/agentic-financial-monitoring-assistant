"""
Terminal chat for the agent: reads the user's input and prints answers.

Quit: press ESC while waiting for input, or type 'exit'.
"""

import agent
import trace_log

try:
    import msvcrt  # built into Windows, used to detect the ESC key
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False  # not Windows: fall back to plain input() + Ctrl+C


def ask(question: str) -> str:
    """Send one question (for manual testing outside chat mode)."""
    if not agent.has_history():
        trace_log.start_session()
    print(f"\n>> You: {question}")
    answer = agent.run_request(question)
    print(f"\n>> Agent:\n{answer}")
    return answer


# ---------------------------------------------------------
# Input that lets the user press ESC to quit (Windows, via msvcrt)
# ---------------------------------------------------------
def _read_line_with_esc(prompt: str = ""):
    """
    Read one line of input. Return None if the user presses ESC (meaning
    they want to quit). Outside Windows (no msvcrt), fall back to plain
    input(); use Ctrl+C to quit.
    """
    if not HAS_MSVCRT:
        try:
            return input(prompt)
        except (EOFError, KeyboardInterrupt):
            return None

    print(prompt, end="", flush=True)
    buffer = []
    while True:
        ch = msvcrt.getwch()
        if ch == "\x1b":  # ESC
            print()
            return None
        elif ch in ("\r", "\n"):
            print()
            return "".join(buffer)
        elif ch == "\x08":  # backspace
            if buffer:
                buffer.pop()
                print("\b \b", end="", flush=True)
        else:
            buffer.append(ch)
            print(ch, end="", flush=True)


# ---------------------------------------------------------
# Interactive chat mode
# ---------------------------------------------------------
def chat():
    trace_log.start_session()

    print("=" * 60)
    print("Asset Price Assistant")
    print("Examples: 'market summary today', 'what is the SGD to TWD rate?'")
    print("Press ESC at any time to quit (or type 'exit')")
    print("Type 'reset' to start a new conversation")
    print(f"This session's log (all requests) is saved to: {trace_log.LOG_FILE}")
    print("=" * 60)

    while True:
        question = _read_line_with_esc("\nYou: ")

        if question is None:
            print("\n[ESC pressed] Closing the program. Goodbye!")
            break

        question = question.strip()
        if not question:
            continue
        if question.lower() in ("exit", "quit", "bye", "esc"):
            print("Goodbye!")
            break
        if question.lower() in ("reset", "clear"):
            agent.reset_conversation()
            print("[Conversation reset: earlier context is forgotten]")
            continue

        answer = agent.run_request(question)
        print(f"\nAgent:\n{answer}")
