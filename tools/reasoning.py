from registry.registry import tool

@tool(scope="reasoning.deep", risk="read")
def think_harder(reason: str) -> dict:
    """Switch to the stronger model. Call this BEFORE answering when the request needs
    multi-step planning, tricky analysis, long writing, or writing a script."""
    print("THINKING HARDER NOW")
    return {"ok": True, "note": "Now on the stronger model. Continue the task."}