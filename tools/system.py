import sys
import subprocess
import time
import shutil
import platform
from pathlib import Path
from datetime import datetime
from registry.registry import tool

EXTENSIONS = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".heic", ".avif", ".webp"},
    "Videos": {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv"},
    "Documents": {".pdf", ".docx", ".doc", ".txt", ".xlsx", ".xls", ".pptx", ".ppt", ".csv", ".md"},
    }

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
        return f"Failed to route interface protocols: {str(e)}"\
        
@tool(scope="files.organize", risk="read")
def file_organize(target_path: str = "") -> str:
    """
    Safely navigates the downloads folder and sorts files/folders:
    - Folders and .zip files go into a separate folder called 'Folders'.
    - Loose files are sorted into Recent/Older folders categorized by extension.
    """
    raw_path = r"C:\Users\Cherish\Downloads\test"
    path = Path(raw_path)
    
    if not path.exists():
        print("Download not found")
        return "Download folder not found."

    one_month_ago = time.time() - (30 * 24 * 60 * 60) # in seconds
    current_run_date = datetime.now().strftime("%m-%y")
    folders_dir_name = "Folders"
    
    moved = 0

    for item in path.iterdir():
        if item.name == folders_dir_name:
            continue

        # Move folders and .zip into /Folders
        if item.is_dir() or item.suffix.lower() == ".zip" or item.name.startswith("."):
            target = path / folders_dir_name
            target.mkdir(parents=True, exist_ok=True)
            dest = target / item.name
            
            try:
                if item.resolve() == target.resolve():
                    continue
                shutil.move(str(item), str(dest))
                moved += 1
            except Exception:
                pass
            continue

        # Recent vs Older -> Categories
        try:
            file_mod_time = item.stat().st_mtime
            age_folder = f"Recent Files {current_run_date}" if file_mod_time > one_month_ago else f"Older Files {current_run_date}"

            file_ext = item.suffix.lower()
            category_folder = "Others"
            for category, ext_list in EXTENSIONS.items():
                if file_ext in ext_list:
                    category_folder = category
                    break

            target_dir = path / age_folder / category_folder
            target_dir.mkdir(parents=True, exist_ok=True)

            destination = target_dir / item.name
            if destination.exists():
                destination = target_dir / f"{item.stem}_{int(file_mod_time)}{item.suffix}"

            shutil.move(str(item), str(destination))
            moved += 1
        except Exception:
            pass

    return f"Successfully organized. Total items moved: {moved}"

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