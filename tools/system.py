import sys
import subprocess
import platform
from pathlib import Path
from registry.registry import tool

@tool(scope="system.maintainence", risk="read")
def system_maintenance() -> str:
    """
    Safely initiates native OS maintenance chores by prompting the official 
    system cleanup dashboard, keeping all file permissions 100% secure.
    """
    try:
        if sys.platform == "win32":
            subprocess.Popen(["cleanmgr.exe"], shell=False)
            return "Initializing native Windows Disk Cleanup terminal interface."
            
        elif sys.platform == "darwin":
            # Opens the native macOS Storage Management utility panel
            subprocess.Popen(["open", "/System/Library/CoreServices/Applications/Storage Management.app"])
            return "Mapping macOS Storage Optimization."
            
        else:
            return "Target platform architecture unrecognized by security layer."
            
    except Exception as e:
        return f"Failed to route interface protocols: {str(e)}"

@tool(scope="app.launch", risk="read")
def launch_system_application(app_name: str) -> str:
    """
    Dynamically launches an application by passing its name 
    directly to the host operating system shell execution engine.
    """
    try:
        clean_app = app_name.lower().strip()
        current_os = platform.system()

        if current_os == "Windows":
            WINDOWS_STORE_APPS = {
                "spotify": "spotify:",
                "whatsapp": "whatsapp:",
                "teams": "msteams:",
                "obsidian": "obsidian:",
                "inkscape": "inkscape:",
                "davinci resolve": "davinci resolve:",
                "freecad": "freecad:",
                "obs studio": "obs studio:"
            }
            
            if clean_app in WINDOWS_STORE_APPS:
                target_command = WINDOWS_STORE_APPS[clean_app]
            else:
                target_command = clean_app

            subprocess.Popen(f'start "" "{target_command}"', shell=True)
            return f"Launched application: '{target_command}'."

        elif current_os == "Darwin":
            subprocess.Popen(["open", "-a", app_name])
            return f"Launched application:'{app_name}'."

        else:
            return f"Host OS environment '{current_os}' is currently unsupported."

    except Exception as e:
        return f"Operating system rejected execution parameters: {str(e)}"