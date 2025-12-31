import json
import os
import winreg
import sys
import shutil
from .utils import get_app_dir

APP_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_RUN_NAME = "NVFT"

class ConfigManager:
    def __init__(self):
        # Use LocalAppData for persistence
        self.app_dir = os.path.join(os.environ["LOCALAPPDATA"], "NVFT")
        if not os.path.exists(self.app_dir):
            os.makedirs(self.app_dir)

        self.config_file = os.path.join(self.app_dir, "settings.json")
        self.presets_file = os.path.join(self.app_dir, "presets.json")
        
        self.default_settings = {
            "brightness": 0.53,
            "contrast": 0.85,
            "gamma": 2.4,
            "red_scale": 1.0,
            "green_scale": 1.0,
            "blue_scale": 1.0,
            "hotkey": "ctrl+f10",
            "autostart": False,
            "always_on_top": True
        }
        
        self.current_settings = self.default_settings.copy()
        self.presets = {}
        
        # Migrate if needed
        self._migrate_old_config()
        
        self.load_settings()
        self.load_presets()
        
        # Sync autostart status with registry
        self.sync_autostart_registry()

    def _migrate_old_config(self):
        """Migrate settings from old executable directory if they exist and new ones don't."""
        old_dir = get_app_dir()
        old_settings = os.path.join(old_dir, "settings.json")
        old_presets = os.path.join(old_dir, "presets.json")
        
        if not os.path.exists(self.config_file) and os.path.exists(old_settings):
            try:
                shutil.copy2(old_settings, self.config_file)
            except Exception as e:
                print(f"Failed to migrate settings: {e}")
                
        if not os.path.exists(self.presets_file) and os.path.exists(old_presets):
            try:
                shutil.copy2(old_presets, self.presets_file)
            except Exception as e:
                print(f"Failed to migrate presets: {e}")

    def load_settings(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    # Update curr settings with loaded data, keeping defaults for missing keys
                    self.current_settings.update(data)
            except Exception as e:
                print(f"Error loading settings: {e}")
        else:
            self.save_settings()

    def save_settings(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.current_settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def update_setting(self, key, value):
        self.current_settings[key] = value

    def load_presets(self):
        if os.path.exists(self.presets_file):
            try:
                with open(self.presets_file, 'r') as f:
                    self.presets = json.load(f)
            except Exception as e:
                print(f"Error loading presets: {e}")
                self.presets = {}
        else:
            self.presets = {}

    def save_presets(self):
        try:
            with open(self.presets_file, 'w') as f:
                json.dump(self.presets, f, indent=4)
        except Exception as e:
            print(f"Error saving presets: {e}")

    def save_preset(self, name, current_values):
        """Save current active values as a preset"""
        preset_data = current_values.copy()
        
        # Remove 'hotkey' from the copy, because 'current_values' normally includes the GLOBAL hotkey
        # We don't want the global hotkey to become the preset hotkey by default.
        for key in ["hotkey", "autostart", "always_on_top"]:
            if key in preset_data:
                del preset_data[key]
        
        # Preserve existing hotkey if updating an existing preset
        old_data = self.presets.get(name)
        if isinstance(old_data, dict) and "hotkey" in old_data:
            preset_data["hotkey"] = old_data["hotkey"]
        else:
            preset_data["hotkey"] = None
        
        self.presets[name] = preset_data
        self.save_presets()

    def delete_preset(self, name):
        if name in self.presets:
            del self.presets[name]
            self.save_presets()
            return True
        return False

    def rename_preset(self, old_name, new_name):
        if old_name in self.presets and new_name not in self.presets:
            self.presets[new_name] = self.presets.pop(old_name)
            self.save_presets()
            return True
        return False

    def get_preset_names(self):
        return sorted(self.presets.keys())

    # --- Autostart / Registry Logic ---

    def sync_autostart_registry(self):
        enabled = self.current_settings.get("autostart", False)
        self.set_autostart(enabled)

    def set_autostart(self, enabled: bool):
        exe_path = sys.executable
        # If running as script, use python.exe, but we really want the script path for persistence?
        # Actually for scripts standard practice is hard. Assuming compiled exe for end users via PyInstaller
        # If frozen, sys.executable is the app.exe
        
        if getattr(sys, 'frozen', False):
             target = sys.executable
        else:
            # If running as script, we can't easily auto-start without a bat file or similar.
            # We will point to pythonw.exe + script path
            # But arguments in Run key are tricky.
            # For this context, we will point to the python executable and assume the user knows
            # or best effort:
            target = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
            
            # NOTE: For development, this might not work perfectly if dependencies are not found 
            # but we fixed the CWD issue in get_app_dir so it might work.
            
            # However, simpler to just point to the entry script if possible.
            # Let's fallback to current behavior but robust
            pass

        # Windows Run Key expects simple path or "Path" "Args"
        # We will use the proper path derived above.
        
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, APP_RUN_KEY, 0, winreg.KEY_ALL_ACCESS)
        except FileNotFoundError:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, APP_RUN_KEY)

        if enabled:
            # If we are in dev mode (not frozen), we construct a command
            if not getattr(sys, 'frozen', False):
                 # e.g. "C:\Python\pythonw.exe" "C:\Apps\NVFT\src\main.py"
                 # We need to ensure we run main.py
                 script_path = os.path.join(get_app_dir(), "src", "main.py")
                 cmd = f'"{sys.executable.replace("python.exe", "pythonw.exe")}" "{script_path}"'
            else:
                cmd = f'"{sys.executable}"'

            winreg.SetValueEx(key, APP_RUN_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, APP_RUN_NAME)
            except FileNotFoundError:
                pass

        winreg.CloseKey(key)

