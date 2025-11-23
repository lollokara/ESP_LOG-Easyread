import os
import sys
import platform

def get_data_dir(app_name="SerialLens"):
    """
    Returns the platform-specific data directory for the application.
    """
    system = platform.system()

    if system == "Darwin":  # macOS
        base_dir = os.path.expanduser("~/Library/Application Support")
    elif system == "Windows":
        base_dir = os.getenv("APPDATA", os.path.expanduser("~\\AppData\\Roaming"))
    else:  # Linux / Unix
        base_dir = os.getenv("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))

    data_dir = os.path.join(base_dir, app_name)

    if not os.path.exists(data_dir):
        try:
            os.makedirs(data_dir, exist_ok=True)
        except OSError as e:
            print(f"Error creating data directory {data_dir}: {e}")
            # Fallback to local directory if permission denied
            return "."

    return data_dir

def get_db_path(app_name="SerialLens", filename="serial_logs.db"):
    return os.path.join(get_data_dir(app_name), filename)
