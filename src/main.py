import sys
import threading
import pystray
from PIL import Image, ImageDraw
import os

from .utils import SingleInstance, resource_path
from .config import ConfigManager
from .gamma import GammaController
from .input_manager import InputManager
from .gui import SettingsApp

def create_tray_icon():
    # Try loading from file or create programmatically
    # In original it was 'icon.png' in root.
    icon_path = resource_path("icon.png")
    if os.path.exists(icon_path):
        return Image.open(icon_path)
    
    # Fallback
    img = Image.new('RGB', (64, 64), (255, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([20, 20, 44, 44], fill=(255, 255, 255))
    return img

import socket

LOCAL_PORT = 65432

def try_send_toggle():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.1)
        sock.sendto(b"TOGGLE", ("127.0.0.1", LOCAL_PORT))
        sock.close()
    except Exception:
        pass

def start_ipc_listener(app):
    def server():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Bind only to localhost to match original and be safer
            sock.bind(("127.0.0.1", LOCAL_PORT))
            while True:
                data, _ = sock.recvfrom(1024)
                if data == b"TOGGLE":
                    # Run on main thread
                    app.external_toggle()
        except OSError:
            # Port busy (maybe another app?). We just silently fail listening feature
            # but allow the app to run normally (unlike original behavior).
            print(f"IPC Port {LOCAL_PORT} busy. Remote toggle disabled.")
        except Exception as e:
            print(f"IPC Error: {e}")
            
    t = threading.Thread(target=server, daemon=True)
    t.start()

def main():
    # 1. Single Instance Check
    instance = SingleInstance()
    if instance.check():
        # Already running? Send toggle command then exit
        try_send_toggle()
        sys.exit(0)

    # 2. Initialize Components
    config = ConfigManager()
    gamma = GammaController()
    
    # 3. Initialize GUI (Hidden initially if needed, but usually we show it on start unless args say min)
    app = SettingsApp(config, gamma, None) 
    
    # 4. Initialize Input Manager
    input_mgr = InputManager(
        config, 
        toggle_callback=app.external_toggle,
        preset_callback=app.external_load_preset
    )
    app.input_manager = input_mgr # Link back

    # 5. Start IPC Listener (New Feature)
    start_ipc_listener(app)

    # 6. Tray Icon
    def on_open(icon, item):
        app.show_window()

    def on_exit(icon, item):
        config.save_settings()
        gamma.restore()
        icon.stop()
        os._exit(0)

    tray_icon = pystray.Icon(
        "NVFT",
        create_tray_icon(),
        menu=pystray.Menu(
            pystray.MenuItem("Settings", on_open, default=True),
            pystray.MenuItem("Exit", on_exit)
        )
    )
    
    def tray_thread():
        tray_icon.run()
    
    threading.Thread(target=tray_thread, daemon=True).start()

    # 7. Run App
    app.withdraw()
    
    try:
        app.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        gamma.restore()
        instance.release()

if __name__ == "__main__":
    main()
