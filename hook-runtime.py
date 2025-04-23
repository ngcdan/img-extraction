
# Runtime hook for PyInstaller
import os
import sys
import importlib.util

# Add missing modules to sys.modules
missing_modules = [
    'win32api', 'win32con', 'win32gui', 'ctypes.wintypes'
]

for module in missing_modules:
    try:
        if importlib.util.find_spec(module) and module not in sys.modules:
            __import__(module)
            print(f"Runtime hook: Successfully imported {module}")
    except (ImportError, ModuleNotFoundError):
        print(f"Runtime hook: Module {module} not available")
