import PyInstaller.__main__
import os
import sys
from PyInstaller.utils.hooks import collect_data_files

# Define the application name
APP_NAME = "ESP32_Monitor"

# Determine separator for path
sep = os.pathsep

# Collect NiceGUI static files
# This returns a list of tuples (source, dest)
# We need to format them as 'source:dest' for the args list
datas = collect_data_files('nicegui')
add_data_args = [f'--add-data={src}{sep}{dest}' for src, dest in datas]

# Basic PyInstaller arguments
args = [
    'main.py',                        # Your main script
    '--name=%s' % APP_NAME,           # Name of the executable
    '--onefile',                      # Package into a single executable
    '--windowed',                     # No console window (Mac/Windows)
    '--clean',                        # Clean cache
    '--add-data=requirements.txt:.',  # Add any data files if needed
] + add_data_args + [
    # NiceGUI / Starlette / Uvicorn hidden imports
    # These are often missed by PyInstaller's auto-analysis
    '--hidden-import=uvicorn.logging',
    '--hidden-import=uvicorn.loops',
    '--hidden-import=uvicorn.loops.auto',
    '--hidden-import=uvicorn.protocols',
    '--hidden-import=uvicorn.protocols.http',
    '--hidden-import=uvicorn.protocols.http.auto',
    '--hidden-import=uvicorn.protocols.websockets',
    '--hidden-import=uvicorn.protocols.websockets.auto',
    '--hidden-import=uvicorn.lifespan.on',
    '--hidden-import=nicegui',
    '--hidden-import=pyserial',

    # Mac specific optimizations
    # '--target-architecture=universal2', # Removed: Causes issues with Anaconda/Single-arch Python
]

if __name__ == '__main__':
    print("Building Mac App...")
    PyInstaller.__main__.run(args)
    print("Build Complete. Check the 'dist' folder.")
