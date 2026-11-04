import json
from tools import load_all_tools
from registry.registry import TOOLS, all_schemas

load_all_tools()
print("Registered:", list(TOOLS))
print(json.dumps(all_schemas({"calendar.read"}), indent=2))