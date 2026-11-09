# registry/registry.py
import inspect
from dataclasses import dataclass
from typing import Callable

TOOLS = {}  # name -> Tool


@dataclass
class Tool:
    name: str
    fn: Callable
    description: str
    scope: str
    risk: str
    triggers: tuple = ()

def tool(scope, risk="read", triggers=()):
    def wrap(fn):
        TOOLS[fn.__name__] = Tool(name=fn.__name__, fn=fn, description=inspect.getdoc(fn) or "",
                                  scope=scope, risk=risk, triggers=tuple(triggers))
        return fn
    return wrap


PY_TO_JSON = {str: "string", int: "integer", float: "number", bool: "boolean"}


def to_llm_schema(t):
    props, required = {}, []
    for name, p in inspect.signature(t.fn).parameters.items():
        props[name] = {"type": PY_TO_JSON.get(p.annotation, "string")}
        if p.default is inspect.Parameter.empty:
            required.append(name)
    return {
        "type": "function",
        "function": {
            "name": t.name,
            "description": t.description,
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }


def all_schemas(allowed_scopes):
    return [to_llm_schema(t) for t in TOOLS.values() if t.scope in allowed_scopes]