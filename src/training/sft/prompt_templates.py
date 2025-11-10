SYSTEM = (
    "You are an Automation Workflow Generator. "
    "Return ONE JSON object only between <json> and </json>. "
    "Root is {'workflow':{'workflowSteps':[...]}, 'text': <optional>}. "
    "First step must be a trigger. Use only allowed actionTypes. "
    "No comments or extra text."
)

def format_example(inp: str, out_json: str) -> str:
    # Input → Output style; output is canonical JSON string (no newlines if you prefer)
    return (
        f"<system>\n{SYSTEM}\n</system>\n"
        f"<user>\n{inp}\n</user>\n"
        f"<assistant>\n<json>\n{out_json}\n</json>\n"
    )
