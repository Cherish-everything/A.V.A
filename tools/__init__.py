# tools/__init__.py
import importlib
import pkgutil


def load_all_tools():
    """Imports every file in tools/ (skipping names that start with _). Importing runs the @tool decorators."""
    for m in pkgutil.iter_modules(__path__):
        if not m.name.startswith("_"):
            importlib.import_module(f"{__name__}.{m.name}")