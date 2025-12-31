import customtkinter as ctk
import threading
from .utils import resource_path

# Appearance
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

BG_COLOR = "#050509"          
CARD_BG = "#12131a"           
CARD_ALT_BG = "#181924"       
BORDER_COLOR = "#2b2e40"      
ACCENT = "#001d5a"            
ACCENT_DARK = "#001d5a"
DANGER = "#5A0302"
SUCCESS = "#359e3b"
TEXT_MAIN = "#ffffff"
TEXT_MUTED = "#9aa0b5"
SECTION_LABEL = "#7a8098"

class SettingsApp(ctk.CTk):
    def __init__(self, config_manager, gamma_controller, input_manager_ref):
        super().__init__()
        self.config = config_manager
        self.gamma = gamma_controller
        # input_manager is assigned later or passed via wrapper because circular dep if not careful.
        # Ideally: Main creates Config, Gamma, GUI, Input.
        # But Input needs to callback GUI/Gamma.
        # GUI needs to callback Input (to record hotkeys).
        # We will set input_manager via method or pass a wrapper.
        self.input_manager = input_manager_ref
        
        self.attributes("-topmost", self.config.current_settings.get("always_on_top", True))
        self.title("NVFT Control")
        self.geometry("420x650")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.hide_window)
        
        self.configure(fg_color=BG_COLOR)
        
        self.sliders = {}
        self._setup_ui()
        self.update_status_visuals()

    def _setup_ui(self):
        # Grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        self.header_frame = ctk.CTkFrame(self, corner_radius=0, fg_color=BG_COLOR)
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 10))
        
        self.lbl_title = ctk.CTkLabel(self.header_frame, text="Night Vision", font=("Segoe UI", 24, "bold"), text_color=TEXT_MAIN)
        self.lbl_title.pack(side="left")

        self.status_badge = ctk.CTkLabel(self.header_frame, text="OFF", font=("Segoe UI", 12, "bold"), text_color=TEXT_MAIN, fg_color=DANGER, corner_radius=999, width=60, height=24)
        self.status_badge.pack(side="right", pady=4)
        self.status_badge.bind("<Button-1>", lambda e: self.toggle_filter())

        # Scroll Content
        self.scroll_frame = ctk.CTkScrollableFrame(self, corner_radius=16, fg_color=BG_COLOR, border_width=0)
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 8))

        # Luminance
        self._create_section_header("LUMINANCE")
        self.card_luminance = self._create_card(self.scroll_frame, CARD_BG)
        self._create_slider(self.card_luminance, "Brightness", "brightness", 0.0, 1.0, 0.01)
        self._create_slider(self.card_luminance, "Contrast", "contrast", 0.0, 1.0, 0.01)
        self._create_slider(self.card_luminance, "Gamma", "gamma", 0.1, 5.0, 0.1)

        # Colors
        self._create_section_header("COLOR CHANNELS")
        self.card_color = self._create_card(self.scroll_frame, CARD_ALT_BG)
        self._create_slider(self.card_color, "Red Boost", "red_scale", 0.0, 2.0, 0.05)
        self._create_slider(self.card_color, "Green Boost", "green_scale", 0.0, 2.0, 0.05)
        self._create_slider(self.card_color, "Blue Boost", "blue_scale", 0.0, 2.0, 0.05)

        # Presets
        self._create_section_header("PRESETS")
        self.card_presets = self._create_card(self.scroll_frame, CARD_BG)
        self._build_presets_section(self.card_presets)

        # General
        self._create_section_header("GENERAL")
        self.card_general = self._create_card(self.scroll_frame, CARD_BG)
        self._build_general_settings(self.card_general)

    def _create_card(self, parent, color):
        f = ctk.CTkFrame(parent, corner_radius=14, fg_color=color, border_width=1, border_color=BORDER_COLOR)
        f.pack(fill="x", pady=(0, 14))
        return f

    def _create_section_header(self, text):
        lbl = ctk.CTkLabel(self.scroll_frame, text=text, font=("Segoe UI", 11, "bold"), text_color=SECTION_LABEL)
        lbl.pack(anchor="w", padx=4, pady=(8, 6))

    def _create_slider(self, parent, label, setting_key, min_v, max_v, step):
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(fill="x", padx=14, pady=8)
        
        head = ctk.CTkFrame(container, fg_color="transparent")
        head.pack(fill="x", pady=(0, 2))
        
        lbl = ctk.CTkLabel(head, text=label, font=("Segoe UI", 13, "bold"), text_color=TEXT_MAIN)
        lbl.pack(side="left")
        
        val_lbl = ctk.CTkLabel(head, text="0.00", font=("Consolas", 12), text_color=TEXT_MUTED)
        val_lbl.pack(side="right")
        
        slider = ctk.CTkSlider(container, from_=min_v, to=max_v, number_of_steps=int((max_v-min_v)/step), border_width=0, height=18, fg_color="#1f2230", progress_color=ACCENT, button_color="#f5f5f5")
        slider.pack(fill="x", pady=(2, 0))
        
        current_val = self.config.current_settings.get(setting_key, 1.0)
        slider.set(current_val)
        val_lbl.configure(text=f"{current_val:.2f}")

        def on_change(val):
            v = float(val)
            val_lbl.configure(text=f"{v:.2f}")
            self.config.update_setting(setting_key, v)
            if self.gamma.active:
                self.gamma.apply_settings(self.config.current_settings)

        slider.configure(command=on_change)
        
        # Double click reset
        def on_reset(event):
            def_val = self.config.default_settings.get(setting_key, 1.0)
            slider.set(def_val)
            on_change(def_val)
        
        slider.bind("<Double-Button-1>", on_reset)
        self.sliders[setting_key] = {"slider": slider, "label": val_lbl}

    def _build_presets_section(self, parent):
        self.presets_container = ctk.CTkFrame(parent, fg_color=CARD_ALT_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        self.presets_container.pack(fill="x", padx=14, pady=(10, 10))
        self.update_presets_list()
        
        btn_frame = ctk.CTkFrame(parent, fg_color="transparent")
        btn_frame.pack(fill="x", padx=14, pady=(0, 10))
        
        ctk.CTkButton(btn_frame, text="💾 Save Current", font=("Segoe UI", 12, "bold"), fg_color=SUCCESS, corner_radius=8, height=36, command=self.save_preset_dialog).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ctk.CTkButton(btn_frame, text="⚙️ Manage", font=("Segoe UI", 12, "bold"), fg_color=ACCENT, corner_radius=8, height=36, command=self.manage_presets_dialog).pack(side="right", expand=True, fill="x", padx=(4, 0))

    def update_presets_list(self):
        for w in self.presets_container.winfo_children(): w.destroy()
        
        names = self.config.get_preset_names()
        if not names:
            ctk.CTkLabel(self.presets_container, text="No presets saved", text_color=TEXT_MUTED).pack(pady=12)
            return

        for name in names[:5]:
            row = ctk.CTkFrame(self.presets_container, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=4)
            
            ctk.CTkLabel(row, text=name, text_color=TEXT_MAIN, font=("Segoe UI", 12), anchor="w").pack(side="left", fill="x", expand=True)
            
            hk = self.config.presets[name].get("hotkey")
            if hk is None: 
                hk = "No Hotkey"
                
            ent = ctk.CTkEntry(row, width=100, font=("Consolas", 11), corner_radius=6)
            ent.insert(0, hk)
            ent.configure(state="readonly")
            ent.pack(side="right", padx=4)
            ent.bind("<Button-1>", lambda e, n=name, w=ent: self.record_preset_hotkey(n, w))
            
            ctk.CTkButton(row, text="Load", width=50, height=24, fg_color=ACCENT, command=lambda n=name: self.load_preset(n)).pack(side="right")

    def _build_general_settings(self, parent):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=10)
        
        ctk.CTkLabel(row, text="Toggle Shortcut", text_color=TEXT_MAIN).pack(side="left")
        self.main_hk_entry = ctk.CTkEntry(row, width=150, font=("Consolas", 12))
        self.main_hk_entry.pack(side="right")
        self.main_hk_entry.insert(0, self.config.current_settings.get("hotkey", ""))
        self.main_hk_entry.configure(state="readonly")
        self.main_hk_entry.bind("<Button-1>", lambda e: self.record_main_hotkey())
        
        row2 = ctk.CTkFrame(parent, fg_color="transparent")
        row2.pack(fill="x", padx=14, pady=5)
        
        self.autostart_var = ctk.BooleanVar(value=self.config.current_settings.get("autostart", False))
        ctk.CTkCheckBox(row2, text="Launch at startup", variable=self.autostart_var, command=self.toggle_autostart, fg_color=ACCENT).pack(side="left")

        row3 = ctk.CTkFrame(parent, fg_color="transparent")
        row3.pack(fill="x", padx=14, pady=5)
        self.topmost_var = ctk.BooleanVar(value=self.config.current_settings.get("always_on_top", True))
        ctk.CTkCheckBox(row3, text="Always on top", variable=self.topmost_var, command=self.toggle_topmost, fg_color=ACCENT).pack(side="left")

    # --- Actions ---
    
    def toggle_filter(self):
        if self.gamma.active:
            self.gamma.restore()
        else:
            self.gamma.apply_settings(self.config.current_settings)
        self.update_status_visuals()

    def update_status_visuals(self):
        if self.gamma.active:
            self.status_badge.configure(text="ACTIVE", fg_color=SUCCESS)
        else:
            self.status_badge.configure(text="OFF", fg_color=DANGER)

    def load_preset(self, name):
        if name in self.config.presets:
            p = self.config.presets[name]
            # Update settings object
            for k in ["brightness", "contrast", "gamma", "red_scale", "green_scale", "blue_scale"]:
                if k in p: self.config.current_settings[k] = p[k]
            
            # Update Sliders
            for k, w in self.sliders.items():
                val = self.config.current_settings.get(k, 1.0)
                w["slider"].set(val)
                w["label"].configure(text=f"{val:.2f}")
            
            # Apply if active
            if self.gamma.active:
                self.gamma.apply_settings(self.config.current_settings)
            
            # Persist changes
            self.config.save_settings()

    def save_preset_dialog(self):
        d = ctk.CTkInputDialog(text="Name:", title="Save Preset")
        name = d.get_input()
        if name:
            self.config.save_preset(name, self.config.current_settings)
            self.update_presets_list()
            # Register hotkeys again in case new preset needs one (though save_preset preserves old hk)
            if self.input_manager: self.input_manager.register_shortcuts()

    def manage_presets_dialog(self):
        """Mostra finestra per gestire (rinominare/eliminare) preset"""
        preset_names = self.config.get_preset_names()
        
        if preset_names is None:
             preset_names = []
        
        # Crea finestra popup
        manage_window = ctk.CTkToplevel(self)
        manage_window.title("Manage Presets")
        manage_window.geometry("380x450")
        manage_window.resizable(False, False)
        manage_window.configure(fg_color=BG_COLOR)
        manage_window.attributes("-topmost", True)
        
        # Centra la finestra
        manage_window.transient(self)
        manage_window.grab_set()
        
        # Header
        header = ctk.CTkLabel(
            manage_window,
            text="Manage Presets",
            font=("Segoe UI", 20, "bold"),
            text_color=TEXT_MAIN
        )
        header.pack(pady=(20, 10), padx=20)
        
        # Frame scrollabile per lista preset
        scroll_frame = ctk.CTkScrollableFrame(
            manage_window,
            fg_color=CARD_BG,
            corner_radius=12,
            border_width=1,
            border_color=BORDER_COLOR
        )
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        
        def refresh_list():
            for widget in scroll_frame.winfo_children():
                widget.destroy()
            
            current_presets = self.config.get_preset_names()
            
            if not current_presets:
                ctk.CTkLabel(scroll_frame, text="No presets to manage.", text_color=TEXT_MUTED).pack(pady=20)
                return
            
            for preset_name in current_presets:
                preset_frame = ctk.CTkFrame(
                    scroll_frame,
                    fg_color=CARD_ALT_BG,
                    corner_radius=8,
                    border_width=1,
                    border_color=BORDER_COLOR
                )
                preset_frame.pack(fill="x", pady=6, padx=4)
                
                # Nome
                name_lbl = ctk.CTkLabel(
                    preset_frame,
                    text=preset_name,
                    font=("Segoe UI", 13),
                    text_color=TEXT_MAIN,
                    anchor="w"
                )
                name_lbl.pack(side="left", padx=12, pady=10, fill="x", expand=True)
                
                # Bottoni
                btn_container = ctk.CTkFrame(preset_frame, fg_color="transparent")
                btn_container.pack(side="right", padx=8, pady=6)
                
                # Rename
                btn_rename = ctk.CTkButton(
                    btn_container,
                    text="Rename",
                    width=70,
                    height=28,
                    font=("Segoe UI", 11),
                    fg_color=ACCENT,
                    hover_color=ACCENT_DARK,
                    corner_radius=6,
                    command=lambda name=preset_name: rename_preset(name)
                )
                btn_rename.pack(side="left", padx=2)
                
                # Delete
                btn_delete = ctk.CTkButton(
                    btn_container,
                    text="Delete",
                    width=70,
                    height=28,
                    font=("Segoe UI", 11),
                    fg_color=DANGER,
                    hover_color="#450201",
                    corner_radius=6,
                    command=lambda name=preset_name: delete_preset(name)
                )
                btn_delete.pack(side="left", padx=2)
        
        def rename_preset(old_name):
            dialog = ctk.CTkInputDialog(
                text=f"Enter new name for '{old_name}':",
                title="Rename Preset"
            )
            new_name = dialog.get_input()
            
            if new_name and new_name.strip() and new_name.strip() != old_name:
                new_name = new_name.strip()
                if self.config.rename_preset(old_name, new_name):
                    refresh_list()
                    self.update_presets_list()
        
        def delete_preset(preset_name):
            if self.config.delete_preset(preset_name):
                refresh_list()
                self.update_presets_list()
                if self.input_manager: self.input_manager.register_shortcuts()
        
        refresh_list()
        
        # Bottone chiudi
        btn_close = ctk.CTkButton(
            manage_window,
            text="Close",
            font=("Segoe UI", 12, "bold"),
            fg_color=BORDER_COLOR,
            hover_color="#3a3d50",
            corner_radius=8,
            height=36,
            command=manage_window.destroy
        )
        btn_close.pack(pady=(0, 20), padx=20, fill="x")

    def toggle_autostart(self):
        self.config.update_setting("autostart", self.autostart_var.get())
        self.config.save_settings()
        self.config.sync_autostart_registry()

    def toggle_topmost(self):
        val = self.topmost_var.get()
        self.config.update_setting("always_on_top", val)
        self.config.save_settings()
        self.attributes("-topmost", val)

    def record_main_hotkey(self):
        self.main_hk_entry.configure(state="normal")
        self.main_hk_entry.delete(0, "end")
        self.main_hk_entry.insert(0, "Press key...")
        self.main_hk_entry.configure(state="readonly")
        
        self.input_manager.record_hotkey(self._on_main_hotkey_recorded)
        
    def _on_main_hotkey_recorded(self, hotkey):
        # Must run on main thread
        def ui_update():
            if hotkey:
                self.main_hk_entry.configure(state="normal")
                self.main_hk_entry.delete(0, "end")
                self.main_hk_entry.insert(0, hotkey)
                self.main_hk_entry.configure(state="readonly")
                self.input_manager.update_main_hotkey(hotkey)
            else:
                # Cancelled or failed, revert
                current = self.config.current_settings.get("hotkey", "")
                self.main_hk_entry.configure(state="normal")
                self.main_hk_entry.delete(0, "end")
                self.main_hk_entry.insert(0, current)
                self.main_hk_entry.configure(state="readonly")
                # Restore shortcuts since we unregistered them
                self.input_manager.register_shortcuts()
        
        self.after(0, ui_update)

    def record_preset_hotkey(self, name, widget):
        widget.configure(state="normal")
        widget.delete(0, "end")
        widget.insert(0, "...")
        widget.configure(state="readonly")
        self.input_manager.record_hotkey(lambda k: self._on_preset_hotkey_recorded(name, widget, k))

    def _on_preset_hotkey_recorded(self, name, widget, hotkey):
        def ui_update():
            if hotkey:
                widget.configure(state="normal")
                widget.delete(0, "end")
                widget.insert(0, hotkey)
                widget.configure(state="readonly")
                self.input_manager.set_preset_hotkey(name, hotkey)
            else:
                old = self.config.presets[name].get("hotkey", "")
                widget.configure(state="normal")
                widget.delete(0, "end")
                widget.insert(0, old)
                widget.configure(state="readonly")
                # Restore shortcuts since we unregistered them
                self.input_manager.register_shortcuts()
        self.after(0, ui_update)

    def hide_window(self):
        self.withdraw()

    def show_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    # Thread Safe External Calls
    def external_toggle(self):
        self.after(0, self.toggle_filter)
    
    def external_load_preset(self, name):
        self.after(0, lambda: self.load_preset(name))

