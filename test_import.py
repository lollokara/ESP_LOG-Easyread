import sys
import os
print(f"CWD: {os.getcwd()}")
print(f"Path: {sys.path}")
try:
    import serial_manager
    print("Import successful")
except ImportError as e:
    print(f"Import failed: {e}")
