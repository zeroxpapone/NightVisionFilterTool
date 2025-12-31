import keyboard
import threading
import time

class InputManager:
    def __init__(self, config_manager, toggle_callback, preset_callback=None):
        self.config = config_manager
        self.toggle_cb = toggle_callback
        self.preset_cb = preset_callback
        self.main_hotkey = self.config.current_settings.get("hotkey")
        self.is_recording = False
        
        # Initial registration
        self.register_shortcuts()

    def register_shortcuts(self):
        """Unregister old and register new shortcuts."""
        if self.is_recording:
            return

        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        
        # Main Toggle
        if self.main_hotkey:
            try:
                # suppress=False ensures the key event is passed to other apps (like games)
                keyboard.add_hotkey(self.main_hotkey, self._on_toggle, suppress=False)
            except Exception as e:
                print(f"Failed to register main hotkey '{self.main_hotkey}': {e}")

        # Presets
        for name, data in self.config.presets.items():
            if isinstance(data, dict):
                hk = data.get("hotkey")
                if hk:
                    try:
                        # Capture name in lambda default arg to avoid closure scope issues
                        keyboard.add_hotkey(hk, lambda n=name: self._on_preset(n), suppress=False)
                    except Exception as e:
                        print(f"Failed to register hotkey '{hk}' for preset {name}: {e}")

    def _on_toggle(self):
        if self.toggle_cb:
            self.toggle_cb()

    def _on_preset(self, preset_name):
        if self.preset_cb:
            self.preset_cb(preset_name)

    def update_main_hotkey(self, new_hotkey):
        if not new_hotkey: return
        self.main_hotkey = new_hotkey
        self.config.update_setting("hotkey", new_hotkey)
        self.config.save_settings()
        self.register_shortcuts()

    def set_preset_hotkey(self, preset_name, new_hotkey):
        if preset_name in self.config.presets:
            self.config.presets[preset_name]["hotkey"] = new_hotkey
            self.config.save_presets()
            self.register_shortcuts()

    # --- NEW RECORDING LOGIC ---

    def record_hotkey(self, callback_success):
        """
        Starts a manual recording session.
        Unregisters everything first.
        listens to raw events.
        Finalizes when all keys are released.
        """
        if self.is_recording:
            return

        self.is_recording = True
        
        # Unhook everything to prevent triggers during recording
        try:
            keyboard.unhook_all_hotkeys()
        except:
            pass

        threading.Thread(target=self._recording_worker, args=(callback_success,), daemon=True).start()

    def _recording_worker(self, callback):
        pressed_keys = set()
        max_combo = set()
        recording_started = False
        
        while True:
            # Read event BLOCKING, but suppress it so F10 doesn't trigger Menu Bar
            e = keyboard.read_event(suppress=True)
            
            # Filter unknown names
            if not e.name: continue

            if e.event_type == keyboard.KEY_DOWN:
                if not recording_started:
                    recording_started = True
                
                pressed_keys.add(e.name.lower())
                
                if len(pressed_keys) > len(max_combo):
                    max_combo.clear()
                    max_combo.update(pressed_keys)
                
            elif e.event_type == keyboard.KEY_UP:
                if e.name.lower() in pressed_keys:
                    pressed_keys.remove(e.name.lower())
                
                if recording_started and len(pressed_keys) == 0:
                    break
        
        self.is_recording = False
        
        # Process result
        if max_combo:
            # Sort keys to make stable string
            # Order: modifiers first, then others
            modifiers = {'ctrl', 'shift', 'alt', 'windows', 'cmd', 'command', 'option', 'right ctrl', 'left ctrl', 'right shift', 'left shift', 'right alt', 'left alt', 'right windows', 'left windows'}
            
            # Simplify modifiers (left ctrl -> ctrl)? 
            # keyboard library usually normalizes names in 'e.name' but sometimes distinguishes sides.
            # For simplicity, we keep what we got but sort nicely.
            
            mods_found = []
            keys_found = []
            
            for k in max_combo:
                # Normalize common names
                lk = k.replace("left ", "").replace("right ", "")
                if lk in modifiers or k in modifiers:
                    mods_found.append(lk)
                else:
                    keys_found.append(k)
            
            # Validation: Block pure modifiers
            if not keys_found:
                 # User pressed only Ctrl or Alt. Invalid.
                 print("Invalid hotkey: Modifiers only.")
                 callback(None)
                 return

            # Construct string
            # keyboard library expects "ctrl+alt+a"
            final_combo = "+".join(sorted(set(mods_found)) + sorted(keys_found))
            callback(final_combo)
        else:
            callback(None)
