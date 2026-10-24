import re

PATTERNS = [
    (r"\bsk-[A-Za-z0-9_-]{12,}\b", "[REDACTED_API_KEY]"),
    (r"\bgh[pousr]_[A-Za-z0-9_]{12,}\b", "[REDACTED_TOKEN]"),
    (r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/-]{12,}", r"\1 [REDACTED]"),
    (r"(?i)((?:api[_-]?key|password|secret|token)\s*[:=]\s*)[\"']?[^\s,\"'}]{6,}", r"\1[REDACTED]"),
]


def redact(text: str) -> str:
    for pattern, replacement in PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text


def visible_messages(record, selected_tool=False):
    """Version-isolated adapter: never read reasoning or instruction records."""
    if record.get("type") == "response_item":
        p = record.get("payload", {})
        if p.get("type") == "message" and p.get("role") in ("user", "assistant"):
            if not isinstance(p.get("content"), list):
                raise ValueError("Unsupported Codex message format; capture paused before advancing its checkpoint.")
            parts = [c.get("text", "") for c in p.get("content", [])
                     if c.get("type") in ("input_text", "output_text", "text")]
            if parts:
                return [(p["role"], redact("\n".join(parts)))]
        if p.get("type") in ("function_call_output", "custom_tool_call_output"):
            output = p.get("output", "")
            if selected_tool and isinstance(output, str) and not ('"retrieval_id"' in output and '"guidance"' in output):
                return [("tool", redact(output[:4000]))]
    return []
