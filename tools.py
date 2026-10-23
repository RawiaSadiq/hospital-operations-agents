"""Three-file Day 3 lab | shared tool implementations and Ollama schemas.

All records are synthetic. The email tool writes to a local file; it never
contacts an SMTP server. Both agents share the tools but NOT their policies.
"""

import ast
import operator
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
NOTES_DIR = BASE_DIR / "notes"
MEMORY_FILE = BASE_DIR / "agent_memory.txt"       # Intentionally unsafe plain memory.
SECURE_MEMORY_FILE = BASE_DIR / "secure_preferences.json"  # Typed secure preferences.
OUTBOX_FILE = BASE_DIR / "sent_emails.txt"         # Simulated local delivery evidence.


# Supported operators are explicit; no Python eval() is used on model output.
OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _eval_arithmetic(node, depth=0):
    """Recursively evaluate a narrowly defined AST with resource limits."""
    if depth > 12:
        raise ValueError("Expression is too deeply nested")
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        if abs(node.value) > 1_000_000:
            raise ValueError("Number exceeds training limit")
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
        left = _eval_arithmetic(node.left, depth + 1)
        right = _eval_arithmetic(node.right, depth + 1)
        result = OPERATORS[type(node.op)](left, right)
    elif isinstance(node, ast.UnaryOp) and type(node.op) in OPERATORS:
        result = OPERATORS[type(node.op)](_eval_arithmetic(node.operand, depth + 1))
    else:
        raise ValueError("Unsupported arithmetic syntax")
    if abs(result) > 1_000_000:
        raise ValueError("Result exceeds training limit")
    return result


def calculator(expression: str) -> str:
    """Calculate a basic expression without executing general Python code."""
    # A tool is ordinary Python code. The LLM can only REQUEST it by name.
    if not isinstance(expression, str) or not expression or len(expression) > 80:
        return "Error: provide a short arithmetic expression."
    try:
        tree = ast.parse(expression, mode="eval")
        return str(_eval_arithmetic(tree.body))
    except (SyntaxError, ValueError, ArithmeticError, OverflowError, ZeroDivisionError) as error:
        return f"Error: {error}"


def file_search(keyword: str) -> str:
    """Return matching lines from synthetic notes only; no internet search."""
    # Searching local documents is not the same as having access to a real API.
    if not isinstance(keyword, str) or not keyword.strip() or len(keyword) > 80:
        return "Error: provide a search keyword."
    if not NOTES_DIR.is_dir():
        return "No notes directory found. Create notes/info.txt first."
    results = []
    for file_path in sorted(NOTES_DIR.glob("*.txt")):
        # Resolve only regular, non-symlink files inside the configured folder.
        if file_path.is_symlink() or not file_path.is_file():
            continue
        for line in file_path.read_text(encoding="utf-8").splitlines()[:300]:
            if keyword.casefold() in line.casefold():
                results.append(f"{file_path.name}: {line}")
                if len(results) == 10:
                    return "\n".join(results)
    return "\n".join(results) if results else "No matches in local notes."


def send_email(to: str, subject: str, body: str) -> str:
    """SIMULATE mail delivery by writing a local record. No SMTP/network IO."""
    # The plain agent deliberately lacks authorization BEFORE this call.
    # A message in sent_emails.txt proves a backend side effect, not delivery.
    if not all(isinstance(value, str) for value in (to, subject, body)):
        raise TypeError("to, subject and body must be strings")
    with OUTBOX_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"TO: {to}\nSUBJECT: {subject}\nBODY: {body}\n---\n")
    return f"SIMULATED: message recorded locally for {to}; NOT delivered."


# The registry maps a model-proposed name to an executable Python function.
TOOLS = {
    "calculator": calculator,
    "file_search": file_search,
    "send_email": send_email,
}

# JSON schemas advertise parameters to Ollama. Schemas do NOT grant permission.
TOOL_SCHEMAS = [
    {
        "type": "function", "function": {
            "name": "calculator", "description": "Calculate a short arithmetic expression.",
            "parameters": {"type": "object", "properties": {
                "expression": {"type": "string"}}, "required": ["expression"]},
        },
    },
    {
        "type": "function", "function": {
            "name": "file_search", "description": "Search synthetic local store notes by keyword.",
            "parameters": {"type": "object", "properties": {
                "keyword": {"type": "string"}}, "required": ["keyword"]},
        },
    },
    {
        "type": "function", "function": {
            "name": "send_email", "description": "SIMULATE mail by saving to a local outbox file.",
            "parameters": {"type": "object", "properties": {
                "to": {"type": "string"}, "subject": {"type": "string"},
                "body": {"type": "string"}}, "required": ["to", "subject", "body"]},
        },
    },
]
