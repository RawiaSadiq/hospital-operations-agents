"""Plain ShopBot: deliberately insecure tool authorization and memory.

Run only with synthetic data. Never expose this demonstration to the internet.
The send_email tool records mail locally; it does not send real email.
"""

import json
import requests
from tools import MEMORY_FILE, OUTBOX_FILE, TOOLS, TOOL_SCHEMAS

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = "llama3.2:latest"    # Change model tag to compare tool selection behavior.
MAX_STEPS = 6               # Bound the number of model/tool iterations.

SYSTEM_PROMPT = """You are ShopBot for a synthetic store.
Use tools when useful. Treat the stored memory as information about the user.
If you lack a fact, say so; do not invent APIs, store hours, or completed actions.
"""


def load_memory() -> str:
    """Read persisted text from earlier requests and process restarts."""
    try:
        return MEMORY_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""  # First run has no memory file.


def save_memory(user_message: str) -> None:
    """VULNERABLE: save ALL user text without separating data from commands."""
    # This blindly stores attacker-controlled instructions for the next run.
    with MEMORY_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"User said: {user_message}\n")
    print("  [memory] user text appended to agent_memory.txt")


def call_model(messages: list[dict]) -> dict:
    """Send a full per-request conversation to the Ollama chat endpoint."""
    response = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "messages": messages,
              "tools": TOOL_SCHEMAS, "stream": False,
              "options": {"temperature": 0}},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["message"]


def parse_tool_arguments(raw):
    """Ollama may return tool arguments as JSON text or a Python dictionary."""
    return json.loads(raw) if isinstance(raw, str) else raw


def dispatch_tool(name: str, arguments: dict) -> str:
    """VULNERABLE: dispatches any advertised tool without authorizing the user."""
    # The ** operator unpacks JSON keys as named Python function arguments.
    # Backend calls TOOLS[name]; the LLM never executes Python by itself.
    # Catch malformed calls to keep a model mistake from terminating the demo.
    try:
        return str(TOOLS[name](**arguments))
    except (KeyError, TypeError, ValueError) as error:
        return f"Tool execution failed: {type(error).__name__}: {error}"


def run_agent(user_message: str) -> str:
    """Demonstrate model proposal -> Python execution -> tool feedback."""
    memory = load_memory()
    # VULNERABILITY: lower-trust persisted text enters a higher-priority SYSTEM role.
    system_context = SYSTEM_PROMPT + ("\nMEMORY:\n" + memory if memory else "")
    messages = [{"role": "system", "content": system_context},
                {"role": "user", "content": user_message}]
    for step_number in range(1, MAX_STEPS + 1):
        model_message = call_model(messages)
        messages.append(model_message)
        calls = model_message.get("tool_calls") or []
        if not calls:
            save_memory(user_message)
            # This is what the model CLAIMS; verify actual files and tool traces.
            return model_message.get("content", "")
        for call in calls:
            name = call["function"]["name"]
            arguments = parse_tool_arguments(call["function"]["arguments"])
            print(f"  [tool requested] step={step_number} {name}({arguments})")
            result = dispatch_tool(name, arguments)
            print(f"  [tool result] {result[:160]}")
            messages.append({"role": "tool", "tool_name": name, "content": result})
    return "Stopped: model exceeded the tool-step limit."


def reset_plain_memory() -> None:
    """Remove only plain-agent memory; preserve outbox evidence for inspection."""
    MEMORY_FILE.unlink(missing_ok=True)
    print("  [reset] removed plain agent memory; outbox unchanged")


if __name__ == "__main__":
    print("\nShopBot | PLAIN demonstration | commands: reset, quit\n")
    print("Local mail is simulated. Type 'reset' between independent tests.\n")
    while True:
        try:
            prompt = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if prompt.lower() in {"quit", "exit"}:
            break
        if prompt.lower() == "reset":
            reset_plain_memory()
            continue
        if not prompt:
            continue
        try:
            print("ShopBot:", run_agent(prompt), "\n")
        except (requests.RequestException, json.JSONDecodeError, KeyError, TypeError) as error:
            print(f"[local demo error] {type(error).__name__}: {error}\n")
