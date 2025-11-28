import ctypes
import json
import threading
import time
import math
import os
import socket
import sys
from ctypes import windll, byref, Structure, c_void_p, c_int, c_ushort, POINTER, c_wchar_p, c_wchar, WINFUNCTYPE

# Librerie esterne
import keyboard
import pystray
from PIL import Image, ImageDraw

# --- CONFIGURAZIONE ---
CONFIG_FILE = "settings.json"
ICON_FILE = "icon.png" # Il nome del tuo file icona
HOTKEY = "ctrl+f10"
LOCAL_PORT = 65432 

# DEFAULT SETTINGS
DEFAULT_SETTINGS = {
    "brightness": 0.53,
    "contrast": 0.85,
    "gamma": 2.4,
    "red_scale": 1.0,
    "green_scale": 1.0,
    "blue_scale": 1.0
}

# --- STRUTTURE WINDOWS API ---
class RAMP(Structure):
    _fields_ = [("Red", c_ushort * 256),
                ("Green", c_ushort * 256),
                ("Blue", c_ushort * 256)]

class RECT(Structure):
    _fields_ = [("left", c_int), ("top", c_int), ("right", c_int), ("bottom", c_int)]

class MONITORINFOEX(Structure):
    _fields_ = [("cbSize", c_int),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", c_int),
                ("szDevice", c_wchar * 32)]

# Definizioni DLL
windll.gdi32.CreateDCW.argtypes = [c_wchar_p, c_wchar_p, c_wchar_p, c_void_p]
windll.gdi32.CreateDCW.restype = c_void_p
windll.gdi32.DeleteDC.argtypes = [c_void_p]
windll.gdi32.DeleteDC.restype = c_int
windll.gdi32.SetDeviceGammaRamp.argtypes = [c_void_p, POINTER(RAMP)]
windll.gdi32.SetDeviceGammaRamp.restype = c_int
windll.gdi32.GetDeviceGammaRamp.argtypes = [c_void_p, POINTER(RAMP)]
windll.gdi32.GetDeviceGammaRamp.restype = c_int

MonitorEnumProc = WINFUNCTYPE(c_int, c_void_p, c_void_p, POINTER(RECT), c_int)

# --- FUNZIONI DI SISTEMA ---
def resource_path(relative_path):
    """ Ottiene il percorso assoluto alla risorsa, funzionante per dev e per PyInstaller onefile """
    try:
        # PyInstaller crea una cartella temporanea in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_primary_monitor_name():
    primary_name = []
    def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
        mon_info = MONITORINFOEX()
        mon_info.cbSize = ctypes.sizeof(MONITORINFOEX)
        if windll.user32.GetMonitorInfoW(hMonitor, byref(mon_info)):
            if mon_info.dwFlags & 1: 
                primary_name.append(mon_info.szDevice)
                return 0 
        return 1
    windll.user32.EnumDisplayMonitors(None, None, MonitorEnumProc(callback), 0)
    return primary_name[0] if primary_name else None

def get_monitor_dc():
    device_name = get_primary_monitor_name()
    if device_name:
        return windll.gdi32.CreateDCW(None, device_name, None, None)
    return windll.gdi32.CreateDCW("DISPLAY", None, None, None)

def create_linear_ramp():
    ramp = RAMP()
    for i in range(256):
        val = int((i / 255.0) * 65535)
        ramp.Red[i] = val
        ramp.Green[i] = val
        ramp.Blue[i] = val
    return ramp

def check_and_create_config():
    if not os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(DEFAULT_SETTINGS, f, indent=4)
        except: pass

# --- GESTIONE COMUNICAZIONE LOCALE ---
def try_send_command_to_existing_instance():
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_socket.settimeout(0.1)
        client_socket.sendto(b"TOGGLE", ("127.0.0.1", LOCAL_PORT))
        client_socket.close()
        return True
    except Exception:
        return False

def start_command_listener(state_obj):
    def listener():
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            server_socket.bind(("127.0.0.1", LOCAL_PORT))
            while True:
                data, addr = server_socket.recvfrom(1024)
                if data == b"TOGGLE":
                    state_obj.toggle()
        except Exception as e:
            print(f"Listener error: {e}")
    t = threading.Thread(target=listener, daemon=True)
    t.start()

# --- GESTIONE STATO ---
class DisplayState:
    def __init__(self):
        self.active = False
        self.original_ramp = RAMP()
        
        dc = get_monitor_dc()
        if dc:
            if not windll.gdi32.GetDeviceGammaRamp(dc, byref(self.original_ramp)):
                self.original_ramp = create_linear_ramp()
            windll.gdi32.DeleteDC(dc)
        else:
            self.original_ramp = create_linear_ramp()

    def restore_defaults(self):
        dc = get_monitor_dc()
        if dc:
            windll.gdi32.SetDeviceGammaRamp(dc, byref(self.original_ramp))
            windll.gdi32.DeleteDC(dc)
        self.active = False

    def apply_custom_settings(self):
        try:
            settings = DEFAULT_SETTINGS.copy()
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    file_settings = json.load(f)
                    settings.update(file_settings)
            
            b_input = float(settings["brightness"])
            c_input = float(settings["contrast"])
            gamma_val = float(settings["gamma"])
            if gamma_val < 0.1: gamma_val = 0.1

            r_scale = float(settings.get("red_scale", 1.0))
            g_scale = float(settings.get("green_scale", 1.0))
            b_scale = float(settings.get("blue_scale", 1.0))

            brightness_offset = b_input - 0.5
            contrast_gain = c_input * 2.0

            new_ramp = RAMP()
            
            for i in range(256):
                val = i / 255.0
                val = math.pow(val, 1.0 / gamma_val)
                val = val + brightness_offset
                val = (val - 0.5) * contrast_gain + 0.5
                val = max(0.0, min(1.0, val))

                new_ramp.Red[i]   = int(max(0, min(65535, val * 65535 * r_scale)))
                new_ramp.Green[i] = int(max(0, min(65535, val * 65535 * g_scale)))
                new_ramp.Blue[i]  = int(max(0, min(65535, val * 65535 * b_scale)))

            dc = get_monitor_dc()
            if dc:
                windll.gdi32.SetDeviceGammaRamp(dc, byref(new_ramp))
                self.active = True
                windll.gdi32.DeleteDC(dc)

        except Exception as e:
            self.restore_defaults()

    def toggle(self):
        if self.active:
            self.restore_defaults()
        else:
            self.apply_custom_settings()

state = DisplayState()

# --- GUI ---
def create_image():
    # Cerca l'icona personalizzata (dentro l'exe o nella cartella)
    icon_path = resource_path(ICON_FILE)
    
    if os.path.exists(icon_path):
        try:
            return Image.open(icon_path)
        except Exception:
            pass # Se fallisce, usa il default sotto
            
    # Fallback: Quadrato rosso
    img = Image.new('RGB', (64, 64), (255, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([20, 20, 44, 44], fill=(255, 255, 255))
    return img

def on_exit(icon, item):
    state.restore_defaults()
    icon.stop()
    os._exit(0)

def setup_tray():
    return pystray.Icon("NVFT", create_image(), menu=pystray.Menu(
        pystray.MenuItem("Toggle (CTRL+F10)", lambda i, it: state.toggle()),
        pystray.MenuItem("Exit", on_exit)
    ))

def hotkey_handler():
    state.toggle()
    time.sleep(0.2)

def main():
    test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        test_socket.bind(("127.0.0.1", LOCAL_PORT))
        test_socket.close()
    except OSError:
        try_send_command_to_existing_instance()
        sys.exit(0)

    check_and_create_config()
    start_command_listener(state)
    keyboard.add_hotkey(HOTKEY, hotkey_handler)
    setup_tray().run()

if __name__ == "__main__":
    main()