import ctypes
import math
from ctypes import windll, byref, Structure, c_int, c_ushort, POINTER, c_wchar, WINFUNCTYPE

# Windows GDI Structures
class RAMP(Structure):
    _fields_ = [("Red", c_ushort * 256), ("Green", c_ushort * 256), ("Blue", c_ushort * 256)]

class RECT(Structure):
    _fields_ = [("left", c_int), ("top", c_int), ("right", c_int), ("bottom", c_int)]

class MONITORINFOEX(Structure):
    _fields_ = [
        ("cbSize", c_int),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", c_int),
        ("szDevice", c_wchar * 32)
    ]

windll.gdi32.CreateDCW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_void_p]
windll.gdi32.CreateDCW.restype = ctypes.c_void_p
windll.gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
windll.gdi32.SetDeviceGammaRamp.argtypes = [ctypes.c_void_p, POINTER(RAMP)]
windll.gdi32.GetDeviceGammaRamp.argtypes = [ctypes.c_void_p, POINTER(RAMP)]
MonitorEnumProc = WINFUNCTYPE(c_int, ctypes.c_void_p, ctypes.c_void_p, POINTER(RECT), c_int)

class GammaController:
    def __init__(self):
        self.original_ramp = RAMP()
        self.active = False
        
        # Save initial state
        dc = self._get_monitor_dc()
        if dc:
            if not windll.gdi32.GetDeviceGammaRamp(dc, byref(self.original_ramp)):
                self._fill_linear_ramp(self.original_ramp)
            windll.gdi32.DeleteDC(dc)
        else:
            self._fill_linear_ramp(self.original_ramp)

    def _get_primary_monitor_name(self):
        primary_name = []

        def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
            mon_info = MONITORINFOEX()
            mon_info.cbSize = ctypes.sizeof(MONITORINFOEX)
            if windll.user32.GetMonitorInfoW(hMonitor, byref(mon_info)):
                if mon_info.dwFlags & 1:  # MONITORINFOF_PRIMARY
                    primary_name.append(mon_info.szDevice)
                    return 0
            return 1

        windll.user32.EnumDisplayMonitors(None, None, MonitorEnumProc(callback), 0)
        return primary_name[0] if primary_name else None

    def _get_monitor_dc(self):
        device_name = self._get_primary_monitor_name()
        if device_name:
            return windll.gdi32.CreateDCW(None, device_name, None, None)
        return windll.gdi32.CreateDCW("DISPLAY", None, None, None)

    def _fill_linear_ramp(self, ramp_struct):
        for i in range(256):
            val = int((i / 255.0) * 65535)
            ramp_struct.Red[i] = ramp_struct.Green[i] = ramp_struct.Blue[i] = val

    def restore(self):
        dc = self._get_monitor_dc()
        if dc:
            windll.gdi32.SetDeviceGammaRamp(dc, byref(self.original_ramp))
            windll.gdi32.DeleteDC(dc)
        self.active = False

    def apply_settings(self, settings):
        """
        Apply gamma ramp based on settings dict.
        keys: brightness, contrast, gamma, red_scale, green_scale, blue_scale
        """
        try:
            b_input = float(settings.get("brightness", 0.53))
            c_input = float(settings.get("contrast", 0.85))
            gamma_val = max(0.1, float(settings.get("gamma", 2.4)))
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

                new_ramp.Red[i] = int(max(0, min(65535, val * 65535 * r_scale)))
                new_ramp.Green[i] = int(max(0, min(65535, val * 65535 * g_scale)))
                new_ramp.Blue[i] = int(max(0, min(65535, val * 65535 * b_scale)))

            dc = self._get_monitor_dc()
            if dc:
                windll.gdi32.SetDeviceGammaRamp(dc, byref(new_ramp))
                windll.gdi32.DeleteDC(dc)
                self.active = True
                return True
        except Exception as e:
            print(f"Error applying gamma: {e}")
            return False
        return False
