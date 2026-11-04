# registry/permissions.py
from dataclasses import dataclass, field
from registry.registry import TOOLS, to_llm_schema


@dataclass
class Grant:
    source: str                      # "chat" or "script"
    scopes: set = field(default_factory=set)

    def allows(self, scope: str) -> bool:
        return "*" in self.scopes or scope in self.scopes


# Chat can use everything ("*"). Scripts get a small, explicit set per run.
CHAT_GRANT = Grant("chat", {"*"})


def script_grant(scopes) -> Grant:
    return Grant("script", set(scopes))


def schemas_for(grant: Grant) -> list:
    """LLM tool schemas for only the tools this grant is allowed to use."""
    return [to_llm_schema(t) for t in TOOLS.values() if grant.allows(t.scope)]