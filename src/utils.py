import sys
import os
import ctypes
from ctypes import wintypes

# Windows API for Mutex
kernel32 = ctypes.windll.kernel32
CreateMutexW = kernel32.CreateMutexW
CloseHandle = kernel32.CloseHandle
GetLastError = kernel32.GetLastError
ERROR_ALREADY_EXISTS = 183

class SingleInstance:
    """
    Ensures only one instance of the application is running using a named Mutex.
    """
    def __init__(self, name="Global\\NVFT_Single_Instance_Mutex"):
        self.mutex_name = name
        self.mutex_handle = None
        self.is_already_running = False

    def check(self):
        self.mutex_handle = CreateMutexW(None, False, self.mutex_name)
        if not self.mutex_handle:
            # Should rarely happen unless system is very unstable
            return True 
        
        if GetLastError() == ERROR_ALREADY_EXISTS:
            self.is_already_running = True
            return True
        
        return False

    def release(self):
        if self.mutex_handle:
            CloseHandle(self.mutex_handle)
            self.mutex_handle = None

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    return os.path.join(base_path, relative_path)

def get_app_dir():
    """Returns the directory where the executable or script is located."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    # If running from src/main.py, we want the project root (parent of src)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
