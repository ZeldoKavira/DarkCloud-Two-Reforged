"""Main application window with mod status dashboard."""

import logging
import tkinter as tk
from tkinter import ttk
from core import settings
from game.game_state import GameState, GameSnapshot
from game import addresses as addr
from mods.manager import ModManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

BG = "#1a1a2e"
BG_PANEL = "#16213e"
FG = "#e0e0e0"
FG_DIM = "#888888"
ACCENT = "#0f3460"
GREEN = "#4ecca3"
ORANGE = "#f0a500"
RED = "#e74c3c"


class App:
    def __init__(self, state: GameState):
        self.state = state
        self.manager = ModManager(state.mem, state)
        self.manager.on_options_loaded = self._on_options_loaded
        self.manager.on_early_texture_patch = self._early_texture_patch
        self._opts_injected = False
        self._custom_rows = []
        self._last_opt_vals = {}
        self._btn_uvs = []
        self._btn_part_addrs = {}  # (row_i, btn_idx) -> PINE addr
        self._last_desc = ""

        # Load saved settings
        self.manager.fast_start = settings.get("fast_start") or False
        self.manager.widescreen = settings.get("widescreen") or False
        self.manager.auto_repair = settings.get("auto_repair") or False
        self.manager.auto_key = settings.get("auto_key") or False

        self.root = tk.Tk()
        from core.version import get_version
        from game.dialog import Dialog
        self.dialog = Dialog(state.mem, self.root)
        self.manager.dialog = self.dialog
        self.root.title(f"Dark Cloud 2 Reforged {get_version()}")
        self.root.geometry("720x500")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=BG_PANEL)
        style.configure("TLabel", background=BG, foreground=FG, font=("Helvetica", 10))
        style.configure("Header.TLabel", background=BG, foreground=FG, font=("Helvetica", 14, "bold"))
        style.configure("Sub.TLabel", background=BG_PANEL, foreground=FG, font=("Helvetica", 10))
        style.configure("Dim.TLabel", background=BG_PANEL, foreground=FG_DIM, font=("Helvetica", 9))
        style.configure("Status.TLabel", background=BG, foreground=GREEN, font=("Helvetica", 11, "bold"))
        style.configure("TNotebook", background=BG)
        style.configure("TNotebook.Tab", background=ACCENT, foreground=FG, padding=(10, 4))
        style.map("TNotebook.Tab", background=[("selected", BG_PANEL)])

        self._build_ui()
        self.state.on_update(self._on_state_update)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        # Header
        header = ttk.Frame(self.root)
        header.pack(fill=tk.X, padx=10, pady=(10, 5))
        ttk.Label(header, text="Dark Cloud 2 Reforged", style="Header.TLabel").pack(side=tk.LEFT)
        self.status_dot = tk.Label(header, text="●", font=("Helvetica", 16), bg=BG, fg=RED)
        self.status_dot.pack(side=tk.RIGHT, padx=5)
        self.status_label = ttk.Label(header, text="Connecting...", style="Status.TLabel")
        self.status_label.pack(side=tk.RIGHT)

        # Tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self._build_data_tab()
        self._build_settings_tab()
        self.notebook.select(1)  # default to Settings tab

        # Log area
        log_frame = ttk.Frame(self.root)
        log_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=(0, 10))
        ttk.Label(log_frame, text="Log", style="Header.TLabel").pack(anchor=tk.W)
        self.log_text = tk.Text(
            log_frame, height=6, bg="#0d1117", fg="#8b949e",
            font=("Courier", 9), state=tk.DISABLED, wrap=tk.WORD,
            borderwidth=1, relief=tk.SOLID,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self._log_handler = TextHandler(self.log_text, self.root)
        logging.getLogger().addHandler(self._log_handler)

    def _build_data_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Data")

        canvas = tk.Canvas(tab, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        scroll_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mousewheel(event):
            canvas.yview_scroll(-3 if (event.num == 4 or event.delta > 0) else 3, "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", _on_mousewheel)
        canvas.bind_all("<Button-5>", _on_mousewheel)

        def _on_canvas_resize(event):
            canvas.itemconfig(canvas.find_all()[0], width=event.width)
        canvas.bind("<Configure>", _on_canvas_resize)

        content = ttk.Frame(scroll_frame)
        content.pack(fill=tk.BOTH, expand=True)
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)

        left = ttk.Frame(content)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        self.conn_panel = self._panel(left, "Connection")
        self.conn_fields = self._add_fields(self.conn_panel, [
            "PCSX2", "PINE Status", "Game ID", "DC2 Detected",
        ])

        self.game_panel = self._panel(left, "Game State")
        self.game_fields = self._add_fields(self.game_panel, [
            "Loop", "Now Mode", "Menu Mode", "Paused", "Play Time", "In Battle", "Battle Count",
        ])

        right = ttk.Frame(content)
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        self.player_panel = self._panel(right, "Player")
        self.player_fields = self._add_fields(self.player_panel, [
            "Character", "Gilda",
        ])

        self.flags_panel = self._panel(right, "Mod Flags")
        self.flags_fields = self._add_fields(self.flags_panel, [
            "PNACH", "Mod Flag", "Enhanced Save",
        ])

        self.dng_panel = self._panel(right, "Dungeon")
        self.dng_fields = self._add_fields(self.dng_panel, [
            "Status",
        ])

        self.title_panel = self._panel(right, "Title Screen")
        self.title_fields = self._add_fields(self.title_panel, [
            "TitleInfo Ptr", "TitleInfo[0]", "TitleInfo[1]", "Cursor (+8)", "TitlePhase",
            "Instr@0x2A0134",
        ])

    def _build_settings_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Settings")

        canvas = tk.Canvas(tab, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        scroll_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_canvas_resize(event):
            canvas.itemconfig(canvas.find_all()[0], width=event.width)
        canvas.bind("<Configure>", _on_canvas_resize)

        inner = ttk.Frame(scroll_frame, style="Panel.TFrame")
        inner.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(inner, text="Game Options", background=ACCENT, foreground=FG,
                  font=("Helvetica", 10, "bold"), padding=(8, 3)).pack(fill=tk.X)

        # Debug — at top for quick testing
        debug = ttk.Frame(inner, style="Panel.TFrame")
        debug.pack(fill=tk.X, padx=8, pady=8)
        tk.Button(debug, text="Test Inject", command=self._test_dialog,
                  bg=ACCENT, fg=FG, font=("Helvetica", 10)).pack(anchor=tk.W)
        tk.Button(debug, text="Dump Message Table", command=self._dump_msg_table,
                  bg=ACCENT, fg=FG, font=("Helvetica", 10)).pack(anchor=tk.W, pady=(4, 0))

        opts = ttk.Frame(inner, style="Panel.TFrame")
        opts.pack(fill=tk.X, padx=8, pady=8)

        self._fast_start_var = tk.BooleanVar(value=self.manager.fast_start)
        tk.Checkbutton(opts, text="Fast Start Game", variable=self._fast_start_var,
                       command=self._toggle_fast_start, bg=BG_PANEL, fg=FG,
                       selectcolor=BG, activebackground=BG_PANEL, activeforeground=FG,
                       font=("Helvetica", 10)).pack(anchor=tk.W, pady=2)
        ttk.Label(opts, text="Skip intro and go straight to the menu on boot",
                  style="Dim.TLabel").pack(anchor=tk.W, padx=20)

        self._widescreen_var = tk.BooleanVar(value=self.manager.widescreen)
        tk.Checkbutton(opts, text="Widescreen 16:9", variable=self._widescreen_var,
                       command=self._toggle_widescreen, bg=BG_PANEL, fg=FG,
                       selectcolor=BG, activebackground=BG_PANEL, activeforeground=FG,
                       font=("Helvetica", 10)).pack(anchor=tk.W, pady=(8, 2))
        ttk.Label(opts, text="Enable Widescreen",
                  style="Dim.TLabel").pack(anchor=tk.W, padx=20)

        self._auto_repair_var = tk.BooleanVar(value=self.manager.auto_repair)
        tk.Checkbutton(opts, text="Auto Repair Powder", variable=self._auto_repair_var,
                       command=self._toggle_auto_repair, bg=BG_PANEL, fg=FG,
                       selectcolor=BG, activebackground=BG_PANEL, activeforeground=FG,
                       font=("Helvetica", 10)).pack(anchor=tk.W, pady=(8, 2))
        ttk.Label(opts, text="Automatically use repair powder when a weapon is about to break",
                  style="Dim.TLabel").pack(anchor=tk.W, padx=20)

        self._auto_key_var = tk.BooleanVar(value=self.manager.auto_key)
        tk.Checkbutton(opts, text="Auto Use Dungeon Key", variable=self._auto_key_var,
                       command=self._toggle_auto_key, bg=BG_PANEL, fg=FG,
                       selectcolor=BG, activebackground=BG_PANEL, activeforeground=FG,
                       font=("Helvetica", 10)).pack(anchor=tk.W, pady=(8, 2))
        ttk.Label(opts, text="Automatically use key on locked doors when pressing X",
                  style="Dim.TLabel").pack(anchor=tk.W, padx=20)

        self._synth_hud_var = tk.BooleanVar(value=settings.get("synth_hud") is not False)
        tk.Checkbutton(opts, text="Show Synthesis Points", variable=self._synth_hud_var,
                       command=self._toggle_synth_hud, bg=BG_PANEL, fg=FG,
                       selectcolor=BG, activebackground=BG_PANEL, activeforeground=FG,
                       font=("Helvetica", 10)).pack(anchor=tk.W, pady=(8, 2))
        ttk.Label(opts, text="Display pending synthesis points on weapon icons",
                  style="Dim.TLabel").pack(anchor=tk.W, padx=20)

        self._gift_box_var = tk.BooleanVar(value=settings.get("gift_box_hud") or False)
        tk.Checkbutton(opts, text="Show Gift Box Contents", variable=self._gift_box_var,
                       command=self._toggle_gift_box, bg=BG_PANEL, fg=FG,
                       selectcolor=BG, activebackground=BG_PANEL, activeforeground=FG,
                       font=("Helvetica", 10)).pack(anchor=tk.W, pady=(8, 2))
        ttk.Label(opts, text="Reveal item names in clown chest boxes",
                  style="Dim.TLabel").pack(anchor=tk.W, padx=20)

        self._start_map_var = tk.BooleanVar(value=False)
        tk.Checkbutton(opts, text="Start With Map", variable=self._start_map_var,
                       command=self._toggle_start_map, bg=BG_PANEL, fg=FG,
                       selectcolor=BG, activebackground=BG_PANEL, activeforeground=FG,
                       font=("Helvetica", 10)).pack(anchor=tk.W, pady=(8, 2))
        ttk.Label(opts, text="Automatically reveal the dungeon map on each floor",
                  style="Dim.TLabel").pack(anchor=tk.W, padx=20)

        self._start_crystal_var = tk.BooleanVar(value=False)
        tk.Checkbutton(opts, text="Start With Crystal", variable=self._start_crystal_var,
                       command=self._toggle_start_crystal, bg=BG_PANEL, fg=FG,
                       selectcolor=BG, activebackground=BG_PANEL, activeforeground=FG,
                       font=("Helvetica", 10)).pack(anchor=tk.W, pady=(8, 2))
        ttk.Label(opts, text="Automatically place the magic crystal on each floor",
                  style="Dim.TLabel").pack(anchor=tk.W, padx=20)

        # Town speed
        speed_row = ttk.Frame(opts, style="Panel.TFrame")
        speed_row.pack(anchor=tk.W, pady=(8, 2))
        tk.Label(speed_row, text="Town Speed", bg=BG_PANEL, fg=FG,
                 font=("Helvetica", 10)).pack(side=tk.LEFT)
        self._speed_var = tk.StringVar(value=settings.get("run_speed") or "1x (Default)")
        speed_menu = ttk.Combobox(speed_row, textvariable=self._speed_var,
                                  values=list(addr.SPEED_OPTIONS.keys()),
                                  state="readonly", width=14)
        speed_menu.pack(side=tk.LEFT, padx=(8, 0))
        speed_menu.bind("<<ComboboxSelected>>", lambda e: self._set_run_speed())
        ttk.Label(opts, text="Movement speed in town areas",
                  style="Dim.TLabel").pack(anchor=tk.W, padx=20)

        # Dungeon speed
        dng_speed_row = ttk.Frame(opts, style="Panel.TFrame")
        dng_speed_row.pack(anchor=tk.W, pady=(8, 2))
        tk.Label(dng_speed_row, text="Dungeon Speed", bg=BG_PANEL, fg=FG,
                 font=("Helvetica", 10)).pack(side=tk.LEFT)
        self._dng_speed_var = tk.StringVar(value=settings.get("dng_speed") or "1x (Default)")
        dng_speed_menu = ttk.Combobox(dng_speed_row, textvariable=self._dng_speed_var,
                                      values=list(addr.SPEED_DNG_OPTIONS.keys()),
                                      state="readonly", width=14)
        dng_speed_menu.pack(side=tk.LEFT, padx=(8, 0))
        dng_speed_menu.bind("<<ComboboxSelected>>", lambda e: self._set_dng_speed())
        ttk.Label(opts, text="Movement speed in dungeon floors",
                  style="Dim.TLabel").pack(anchor=tk.W, padx=20)

        # Pickup radius
        pickup_row = ttk.Frame(opts, style="Panel.TFrame")
        pickup_row.pack(anchor=tk.W, pady=(8, 2))
        tk.Label(pickup_row, text="Pickup Radius", bg=BG_PANEL, fg=FG,
                 font=("Helvetica", 10)).pack(side=tk.LEFT)
        self._pickup_var = tk.StringVar(value=settings.get("pickup_radius") or "1x (Default)")
        pickup_menu = ttk.Combobox(pickup_row, textvariable=self._pickup_var,
                                   values=list(addr.PICKUP_RADIUS_OPTIONS.keys()),
                                   state="readonly", width=14)
        pickup_menu.pack(side=tk.LEFT, padx=(8, 0))
        pickup_menu.bind("<<ComboboxSelected>>", lambda e: self._set_pickup_radius())
        ttk.Label(opts, text="Multiply item pickup collection range",
                  style="Dim.TLabel").pack(anchor=tk.W, padx=20)

        # Map position
        map_row = ttk.Frame(opts, style="Panel.TFrame")
        map_row.pack(anchor=tk.W, pady=(8, 2))
        tk.Label(map_row, text="Large Map Position", bg=BG_PANEL, fg=FG,
                 font=("Helvetica", 10)).pack(side=tk.LEFT)
        self._map_pos_var = tk.StringVar(value=settings.get("map_position") or "Center (Default)")
        map_menu = ttk.Combobox(map_row, textvariable=self._map_pos_var,
                                values=list(addr.MINIMAP_POS_OPTIONS.keys()),
                                state="readonly", width=18)
        map_menu.pack(side=tk.LEFT, padx=(8, 0))
        map_menu.bind("<<ComboboxSelected>>", lambda e: self._set_map_position())
        ttk.Label(opts, text="Move the large dungeon minimap on screen",
                  style="Dim.TLabel").pack(anchor=tk.W, padx=20)

        # Map position (targeting)
        map_tgt_row = ttk.Frame(opts, style="Panel.TFrame")
        map_tgt_row.pack(anchor=tk.W, pady=(8, 2))
        tk.Label(map_tgt_row, text="Map Position (Targeting)", bg=BG_PANEL, fg=FG,
                 font=("Helvetica", 10)).pack(side=tk.LEFT)
        self._map_tgt_var = tk.StringVar(value=settings.get("map_position_target") or "Center (Default)")
        map_tgt_menu = ttk.Combobox(map_tgt_row, textvariable=self._map_tgt_var,
                                    values=list(addr.MINIMAP_POS_OPTIONS.keys()),
                                    state="readonly", width=18)
        map_tgt_menu.pack(side=tk.LEFT, padx=(8, 0))
        map_tgt_menu.bind("<<ComboboxSelected>>", lambda e: self._set_map_position_target())
        ttk.Label(opts, text="Map position when locked onto a monster",
                  style="Dim.TLabel").pack(anchor=tk.W, padx=20)

    # --- helpers ---

    def _panel(self, parent, title):
        frame = ttk.Frame(parent, style="Panel.TFrame")
        frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(frame, text=title, background=ACCENT, foreground=FG,
                  font=("Helvetica", 10, "bold"), padding=(8, 3)).pack(fill=tk.X)
        inner = ttk.Frame(frame, style="Panel.TFrame")
        inner.pack(fill=tk.X, padx=8, pady=4)
        return inner

    def _add_fields(self, parent, labels):
        fields = {}
        for label in labels:
            row = ttk.Frame(parent, style="Panel.TFrame")
            row.pack(fill=tk.X, pady=1)
            ttk.Label(row, text=label, style="Dim.TLabel", width=18, anchor=tk.W).pack(side=tk.LEFT)
            val = ttk.Label(row, text="—", style="Sub.TLabel", anchor=tk.W)
            val.pack(side=tk.LEFT, fill=tk.X, expand=True)
            fields[label] = val
        return fields

    def _on_state_update(self, snap: GameSnapshot):
        self.root.after(0, self._update_ui, snap)

    def _update_ui(self, snap: GameSnapshot):
        if not snap.connected:
            self.status_label.config(text=snap.error or "Disconnected")
            self.status_dot.config(fg=RED)
        elif not snap.dc2_detected:
            self.status_label.config(text=snap.error or "Waiting for Dark Cloud 2")
            self.status_dot.config(fg=ORANGE)
        elif snap.loop_no == 3:
            self.status_label.config(text="Title Screen")
            self.status_dot.config(fg=ORANGE)
        else:
            self.status_label.config(text=snap.loop_name)
            self.status_dot.config(fg=GREEN)
            self._apply_run_speed()
            self._apply_dng_speed()
            self._apply_pickup_radius()
            self._apply_map_position()

        emu_names = {0: "Running", 1: "Paused", 2: "Shutdown"}
        self._set(self.conn_fields, "PCSX2", "Connected" if snap.connected else "Disconnected",
                  GREEN if snap.connected else RED)
        self._set(self.conn_fields, "PINE Status", emu_names.get(snap.emu_status, "?"),
                  GREEN if snap.emu_status == 0 else ORANGE)
        self._set(self.conn_fields, "DC2 Detected", "Yes" if snap.dc2_detected else "No",
                  GREEN if snap.dc2_detected else RED)
        self._set(self.conn_fields, "Game ID", snap.error if snap.error else "SCUS-97213")

        self._set(self.game_fields, "Loop", f"{snap.loop_no} — {snap.loop_name}")
        self._set(self.game_fields, "Now Mode", str(snap.now_mode))
        self._set(self.game_fields, "Menu Mode", str(snap.menu_mode))
        self._set_bool(self.game_fields, "Paused", snap.paused)
        self._set(self.game_fields, "Play Time", str(snap.play_time))
        self._set_bool(self.game_fields, "In Battle", snap.battle.in_battle)
        self._set(self.game_fields, "Battle Count", str(snap.battle.battle_count))

        p = snap.player
        self._set(self.player_fields, "Character", f"{p.character_name} ({p.character_id})")
        self._set(self.player_fields, "Gilda", f"{p.gilda:,}")

        self._set_bool(self.flags_fields, "PNACH", snap.flags.pnach_active)
        self._set_bool(self.flags_fields, "Mod Flag", snap.flags.mod_active)
        self._set_bool(self.flags_fields, "Enhanced Save", snap.flags.enhanced_save)

        if snap.loop_no == 2:
            self._set(self.dng_fields, "Status", str(snap.dungeon.status))
        else:
            self._set(self.dng_fields, "Status", "—")

        t = snap.title
        if snap.loop_no == 3:
            self._set(self.title_fields, "TitleInfo Ptr", f"0x{t.title_info_ptr:08X}")
            self._set(self.title_fields, "TitleInfo[0]", str(t.title_info_0))
            self._set(self.title_fields, "TitleInfo[1]", str(t.title_info_1))
            self._set(self.title_fields, "Cursor (+8)", str(t.title_info_8))
            self._set(self.title_fields, "TitlePhase", str(t.title_phase))
            self._set(self.title_fields, "Instr@0x2A0134", f"0x{t.instr_002a0134:08X}")
        else:
            for key in self.title_fields:
                self._set(self.title_fields, key, "—")

    def _set(self, fields, key, text, color=FG):
        if key in fields:
            fields[key].config(text=text, foreground=color)

    def _set_bool(self, fields, key, val):
        self._set(fields, key, "Yes" if val else "No", GREEN if val else FG_DIM)

    def _toggle_fast_start(self):
        val = self._fast_start_var.get()
        self.manager.fast_start = val
        settings.set("fast_start", val)

    def _toggle_widescreen(self):
        val = self._widescreen_var.get()
        self.manager.widescreen = val
        settings.set("widescreen", val)

    def _toggle_auto_repair(self):
        val = self._auto_repair_var.get()
        self.manager.auto_repair = val
        settings.set("auto_repair", val)
        self.state.mem.write_byte(addr.OPTION_SAVE_AUTO_REPAIR, 1 if val else 0)

    def _toggle_auto_key(self):
        val = self._auto_key_var.get()
        self.manager.auto_key = val
        settings.set("auto_key", val)
        self.state.mem.write_byte(addr.OPTION_SAVE_AUTO_KEY, 1 if val else 0)

    def _toggle_synth_hud(self):
        val = self._synth_hud_var.get()
        settings.set("synth_hud", val)
        self.state.mem.write_byte(addr.OPTION_SAVE_SYNTH_HUD, 0 if val else 1)

    def _toggle_gift_box(self):
        val = self._gift_box_var.get()
        settings.set("gift_box_hud", val)
        self.state.mem.write_byte(addr.OPTION_SAVE_GIFT_BOX, 0 if val else 1)

    def _toggle_start_map(self):
        val = self._start_map_var.get()
        self.state.mem.write_byte(addr.OPTION_SAVE_START_MAP, 1 if val else 0)

    def _toggle_start_crystal(self):
        val = self._start_crystal_var.get()
        self.state.mem.write_byte(addr.OPTION_SAVE_START_CRYSTAL, 1 if val else 0)

    def _set_run_speed(self):
        label = self._speed_var.get()
        settings.set("run_speed", label)
        idx = list(addr.SPEED_OPTIONS.keys()).index(label)
        try:
            self.state.mem.write_byte(addr.OPTION_SAVE_RUN_SPEED, idx)
        except Exception:
            pass
        self._apply_run_speed()

    def _set_dng_speed(self):
        label = self._dng_speed_var.get()
        settings.set("dng_speed", label)
        idx = list(addr.SPEED_DNG_OPTIONS.keys()).index(label)
        try:
            self.state.mem.write_byte(addr.OPTION_SAVE_DNG_SPEED, idx)
        except Exception:
            pass
        self._apply_dng_speed()

    def _apply_dng_speed(self):
        dng_label = self._dng_speed_var.get()
        dng_upper = addr.SPEED_DNG_OPTIONS.get(dng_label, 0x3F80)
        if dng_upper == 0x3F80:
            return
        try:
            self.state.mem.write_int(addr.SPEED_INSTR_DNG, 0x3C020000 | dng_upper)
        except Exception:
            pass

    def _on_options_loaded(self, speed_label, pickup_label, map_label, map_tgt_label, dng_speed_label):
        self._speed_var.set(speed_label)
        settings.set("run_speed", speed_label)
        self._dng_speed_var.set(dng_speed_label)
        settings.set("dng_speed", dng_speed_label)
        self._apply_dng_speed()
        self._pickup_var.set(pickup_label)
        settings.set("pickup_radius", pickup_label)
        self._map_pos_var.set(map_label)
        settings.set("map_position", map_label)
        self._map_tgt_var.set(map_tgt_label)
        settings.set("map_position_target", map_tgt_label)
        # Sync toggle checkboxes from save data
        self._auto_repair_var.set(self.manager.auto_repair)
        self._auto_key_var.set(self.manager.auto_key)
        self._synth_hud_var.set(settings.get("synth_hud") is not False)
        self._start_map_var.set(self.manager.mem.read_byte(addr.OPTION_SAVE_START_MAP) == 1)
        self._start_crystal_var.set(self.manager.mem.read_byte(addr.OPTION_SAVE_START_CRYSTAL) == 1)

    def _apply_run_speed(self):
        label = self._speed_var.get()
        upper16 = addr.SPEED_OPTIONS.get(label, 0x40a0)
        dng_label = self._dng_speed_var.get()
        dng_upper = addr.SPEED_DNG_OPTIONS.get(dng_label, 0x3F80)
        try:
            # Town
            if upper16 != 0x40a0:
                instr = addr.speed_lui(upper16)
                if self.state.mem.read_int(addr.SPEED_INSTR_MAIN) != instr:
                    self.state.mem.write_int(addr.SPEED_INSTR_MAIN, instr)
        except Exception:
            pass

    def _set_pickup_radius(self):
        label = self._pickup_var.get()
        settings.set("pickup_radius", label)
        idx = list(addr.PICKUP_RADIUS_OPTIONS.keys()).index(label)
        try:
            self.state.mem.write_byte(addr.OPTION_SAVE_PICKUP_RADIUS, idx)
        except Exception:
            pass
        self._apply_pickup_radius()

    def _apply_pickup_radius(self):
        label = self._pickup_var.get()
        upper16 = addr.PICKUP_RADIUS_OPTIONS.get(label, 0x41a0)
        if upper16 == 0x41a0:
            return
        instr = addr.pickup_radius_lui(upper16)
        try:
            cur = self.state.mem.read_int(addr.PICKUP_RADIUS_INSTR)
            if cur != instr:
                self.state.mem.write_int(addr.PICKUP_RADIUS_INSTR, instr)
                log.info("Pickup radius → %s", label)
        except Exception:
            pass

    def _set_map_position(self):
        label = self._map_pos_var.get()
        settings.set("map_position", label)
        idx = list(addr.MINIMAP_POS_OPTIONS.keys()).index(label)
        try:
            self.state.mem.write_byte(addr.OPTION_SAVE_MAP_POS, idx)
        except Exception:
            pass
        self._apply_map_position()

    def _set_map_position_target(self):
        label = self._map_tgt_var.get()
        settings.set("map_position_target", label)
        idx = list(addr.MINIMAP_POS_OPTIONS.keys()).index(label)
        try:
            self.state.mem.write_byte(addr.OPTION_SAVE_MAP_POS_TARGET, idx)
        except Exception:
            pass
        self._apply_map_position()

    def _is_locked_on(self):
        """Check if player is locked onto a monster."""
        try:
            chara_ptr = self.state.mem.read_int(addr.MAIN_CHARA)
            if chara_ptr == 0:
                return False
            pine_chara = 0x20000000 + chara_ptr
            return self.state.mem.read_short(pine_chara + addr.LOCKON_OFFSET) != 0
        except Exception:
            return False

    def _apply_map_position(self):
        if self._is_locked_on():
            label = self._map_tgt_var.get()
        else:
            label = self._map_pos_var.get()
        vals = addr.MINIMAP_POS_OPTIONS.get(label)
        if not vals:
            return
        x13, y13, x2, y2 = vals
        try:
            # Site 1: li v0, X → 0x2402XXYY; li v1, Y → 0x2403XXYY
            self._patch_li(addr.MINIMAP_LG_X1, 0x2402, x13)
            self._patch_li(addr.MINIMAP_LG_Y1, 0x2403, y13)
            # Site 2 (Sphida): li v1, X → 0x2403XXYY; li v0, Y → 0x2402XXYY
            self._patch_li(addr.MINIMAP_LG_X2, 0x2403, x2)
            self._patch_li(addr.MINIMAP_LG_Y2, 0x2402, y2)
            # Site 3: li v0, X → 0x2402XXYY; li v1, Y → 0x2403XXYY
            self._patch_li(addr.MINIMAP_LG_X3, 0x2402, x13)
            self._patch_li(addr.MINIMAP_LG_Y3, 0x2403, y13)
        except Exception:
            pass

    def _patch_li(self, pine_addr, opcode_hi, imm16):
        """Patch a `li reg, imm16` instruction if it differs."""
        instr = (opcode_hi << 16) | imm16
        cur = self.state.mem.read_int(pine_addr)
        if cur != instr:
            self.state.mem.write_int(pine_addr, instr)

    def _dump_msg_table(self):
        try:
            import json, os
            clsmes = 0x21E94AC0
            buf_ptr = self.state.mem.read_int(clsmes + 0x21D4)
            pine_buf = 0x20000000 + buf_ptr
            count = self.state.mem.read_short(pine_buf)
            log.info("Dumping %d messages from 0x%08X...", count, buf_ptr)

            messages = {}
            for i in range(count):
                msg_id = self.state.mem.read_short(pine_buf + 4 + i * 4)
                text_off = self.state.mem.read_short(pine_buf + 6 + i * 4)
                text_addr = pine_buf + (count + text_off + 1) * 2
                shorts = []
                for j in range(500):
                    s = self.state.mem.read_short(text_addr + j * 2)
                    shorts.append(s)
                    if s == 0xFF01:
                        break
                messages[f"0x{msg_id:04X}"] = {
                    "entry": i,
                    "text_offset": text_off,
                    "raw_shorts": [f"0x{s:04X}" for s in shorts],
                }

            out = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))), "dev-files", "msg-table-dump.json")
            with open(out, 'w') as f:
                json.dump(messages, f, indent=2)
            log.info("Dumped %d messages to %s", count, out)
        except Exception as e:
            log.error("Dump failed: %s", e)

    # Known button texture indices
    BTN_TEX = {
        114: "ON",       115: "OFF",
        116: "Normal",   117: "Fast",
        118: "Stereo",   119: "Mono",
        120: "Small",    121: "Large",
        122: "1",        123: "2",        124: "3",
        125: "Normal2",  126: "Reverse",
    }

    def _test_dialog(self):
        """Scan scene struct for fish pointer arrays."""
        try:
            mem = self.state.mem
            sgi = mem.read_int(0x21F59E30)
            if not sgi:
                return
            pine_scene = 0x20000000 + sgi
            # The scene is a CScene. The fishing code gets a character via
            # GetCharacter(scene, scene+0x2E50). Let's read that.
            char_idx = mem.read_int(pine_scene + 0x2E50)
            log.info("Scene=0x%08X char_idx=0x%08X", sgi, char_idx)
            # Scan scene for arrays of 2+ consecutive valid pointers
            for off in range(0, 0x3000, 4):
                count = 0
                for i in range(8):
                    try:
                        v = mem.read_int(pine_scene + off + i * 4)
                        if 0x100000 < v < 0x2000000:
                            count += 1
                        else:
                            break
                    except:
                        break
                if count >= 2:
                    # Read first pointer and check if it looks like a CAquaFish
                    p0 = mem.read_int(pine_scene + off)
                    pp = 0x20000000 + p0
                    # CAquaFish has vtable as first field
                    vt = mem.read_int(pp)
                    log.info("  Scene+0x%04X: %d ptrs, first=0x%08X vt=0x%08X", off, count, p0, vt)
                    if count >= 2:
                        off += count * 4  # skip past this array
        except Exception as e:
            log.error("Test failed: %s", e)

    def _on_answer(self, choice):
        self.dialog.show("You chose: " + ("Yes" if choice else "No"), duration=10, mode=0)
        import time; time.sleep(3)
        self.dialog.show("You chose: " + ("Yes" if choice else "No"), duration=10, mode=4)

    def _options_auto_poll(self):
        """Auto-detect options screen and inject custom rows."""
        try:
            mci = self.state.mem.read_int(addr.MENU_COMMON_INFO)
            if mci != 0:
                page = self.state.mem.read_int(0x20000000 + mci + 0x54)
                if page == 7 and not self._opts_injected:
                    log.info("Options page detected, auto-injecting...")
                    self._options_inject()
                elif page != 7 and self._opts_injected:
                    self._opts_injected = False
                    self.state.mem.write_int(0x21F70B60, 0)
                    self.state.mem.write_int(0x21F70B70, 0)
                    # Restore original help text
                    if self._last_desc and hasattr(self, '_help_text_addr') and hasattr(self, '_orig_help_text'):
                        for i, s in enumerate(self._orig_help_text):
                            self.state.mem.write_short(self._help_text_addr + i * 2, s)
                        self.state.mem.write_int(self._help_msg_ptr + 0x17E4, -1)
                        self._last_desc = ""
        except Exception:
            pass
        self.root.after(500, self._options_auto_poll)

    def _options_inject(self):
        """Inject custom rows into the options screen and start the cursor poll."""
        try:
            ptr = self.state.mem.read_int(addr.CMENU_OPTION_PTR)
            if ptr == 0: return
            pine = 0x20000000 + ptr
            obf = self.state.mem.read_int(addr.OPTION_BUTTON_FORM)
            if obf == 0: return
            op = 0x20000000 + obf
            count = self.state.mem.read_short(op + 0x68)
            if count <= 33:
                self._inject_custom_rows(pine, op, count)
            else:
                # Rows already injected, but re-inject textures (may have been reloaded)
                self._reinject_btn_textures()
            self._pine = pine
            self._opts_injected = True
            self._last_opt_vals = {}
            # Find help message text address for description swapping
            self._orig_help_text = [
                0x0023,0x0047,0x0040,0x004D,0x0046,0x0044,0xFF02,0x0052,0x0044,0x0053,
                0x0053,0x0048,0x004D,0x0046,0x0052,0xFF02,0x0056,0x0048,0x0053,0x0047,
                0xFF02,0xFD06,0xFF02,0x0041,0x0054,0x0053,0x0053,0x004E,0x004D,0x000E,
                0xFF02,0x0025,0x004D,0x0043,0xFF02,0x0056,0x0048,0x0053,0x0047,0xFF02,
                0xFD08,0xFF02,0x0041,0x0054,0x0053,0x0053,0x004E,0x004D,0x000E,0xFF00,
                0x0032,0x0044,0x0053,0x0054,0x0051,0x004D,0xFF02,0x0053,0x004E,0xFF02,
                0x004E,0x0051,0x0048,0x0046,0x0048,0x004D,0x0040,0x004B,0xFF02,0x0052,
                0x0044,0x0053,0x0053,0x0048,0x004D,0x0046,0x0052,0xFF02,0x0056,0x0048,
                0x0053,0x0047,0xFF02,0xFD09,0xFF02,0x0041,0x0054,0x0053,0x0053,0x004E,
                0x004D,0x000E,0xFF01,0xFF00,
            ]
            try:
                self._help_msg_ptr = 0x20000000 + self.state.mem.read_int(0x21ECCA40 + 3 * 4)
                self._help_msg_orig_id = self.state.mem.read_int(self._help_msg_ptr + 0x17E4)
                buf_ptr = self.state.mem.read_int(self._help_msg_ptr + 0x21D4)
                pine_buf = 0x20000000 + buf_ptr
                count = self.state.mem.read_short(pine_buf)
                for i in range(count):
                    msg_id = self.state.mem.read_short(pine_buf + 4 + i * 4)
                    if msg_id == self._help_msg_orig_id:
                        text_off = self.state.mem.read_short(pine_buf + 6 + i * 4)
                        self._help_text_addr = pine_buf + (count + text_off + 1) * 2
                        break
            except Exception as e:
                log.error("Help msg setup: %s", e)
            self._options_cursor_poll()
            log.info("Options: auto-injected %d custom rows", len(self._custom_rows))
        except Exception as e:
            log.error("Options inject failed: %s", e)

    def _options_cursor_poll(self):
        """Fast poll (200ms) for cursor/label position updates."""
        import struct
        pack_f = lambda f: struct.unpack('I', struct.pack('f', f))[0]
        read_f = lambda a: struct.unpack('f', struct.pack('I', self.state.mem.read_int(a)))[0]
        def get_btn_addr(row_i, b):
            """Get PINE address for button part, using Python dict for overlapping rows."""
            game_row = 16 + row_i
            if 0x164 + game_row * 0xC >= 0x254:  # overlaps native config_ptrs
                return self._btn_part_addrs.get((row_i, b), 0)
            ps2 = self.state.mem.read_int(pine_opt + 0x164 + game_row * 0xC + b * 4)
            return (0x20000000 + ps2) if ps2 else 0
        try:
            if self.state.mem.read_int(addr.CMENU_OPTION_PTR) == 0:
                self._opts_injected = False
                return
            pine_opt = self._pine
            cursor_row = self.state.mem.read_int(pine_opt + 0x374)

            # Update clip bounds
            clip_ps2 = self.state.mem.read_int(0x20378148)  # LocalMenuClipForm
            if clip_ps2:
                pc = 0x20000000 + clip_ps2
                cy = int(read_f(pc + 0x10))
                ch = self.state.mem.read_short(pc + 0x06)
                self.state.mem.write_int(0x21F8004C, cy)
                self.state.mem.write_int(0x21F80050, cy + ch - 24)

            # Write form-relative label Y (cave adds form Y every frame for smooth gliding)
            obf_ps2 = self.state.mem.read_int(addr.OPTION_BUTTON_FORM)
            pine_obf = 0x20000000 + obf_ps2
            obf_y = read_f(pine_obf + 0x10)
            self.state.mem.write_int(0x21F80054, int(obf_y))  # form Y for cave
            for row_i, row in enumerate(self._custom_rows):
                label_base = 0x21F80000 + row_i * 0x80
                pb = get_btn_addr(row_i, 0)
                if pb:
                    btn_rel_y = read_f(pb + 0x20)
                    self.state.mem.write_int(label_base + 0x44, int(btn_rel_y) + 2)  # form-relative Y

            if cursor_row >= 16:
                row_i_c = cursor_row - 16
                sub_selection = self.state.mem.read_int(pine_opt + 0x37C)
                # Clamp sub_selection for rows without max_toggle in struct
                if row_i_c < len(self._custom_rows):
                    max_btn = self._custom_rows[row_i_c]["buttons"]
                    if sub_selection >= max_btn:
                        sub_selection = max_btn - 1
                        self.state.mem.write_int(pine_opt + 0x37C, sub_selection)
                    elif sub_selection < 0:
                        sub_selection = 0
                        self.state.mem.write_int(pine_opt + 0x37C, 0)
                pine_btn = get_btn_addr(row_i_c, sub_selection)
                if pine_btn:
                    btn_x = read_f(pine_btn + 0x1C)
                    btn_y = read_f(pine_btn + 0x20)
                    obf_ps2 = self.state.mem.read_int(addr.OPTION_BUTTON_FORM)
                    pine_obf = 0x20000000 + obf_ps2
                    bsx = read_f(pine_obf + 0x0C) + btn_x
                    bsy = read_f(pine_obf + 0x10) + btn_y
                    FLAG_BASE = 0x21F70B60
                    def i32(v): return int(v) & 0xFFFFFFFF
                    self.state.mem.write_int(FLAG_BASE + 0x00, i32(bsx - 50))
                    self.state.mem.write_int(FLAG_BASE + 0x04, i32(bsy - 3))
                    self.state.mem.write_int(FLAG_BASE + 0x08, i32(bsx - 2))
                    self.state.mem.write_int(FLAG_BASE + 0x0C, i32(bsy - 3))
                    mci_ps2 = self.state.mem.read_int(addr.MENU_COMMON_INFO)
                    if mci_ps2 == 0:
                        self.root.after(16, self._options_cursor_poll)
                        return
                    pine_mci = 0x20000000 + mci_ps2
                    rect_form_ps2 = self.state.mem.read_int(pine_mci + 0x13C)
                    if rect_form_ps2 == 0:
                        self.root.after(16, self._options_cursor_poll)
                        return
                    pine_rect_form = 0x20000000 + rect_form_ps2
                    rect_part0_ps2 = self.state.mem.read_int(pine_rect_form + 0x6C)
                    self.state.mem.write_int(FLAG_BASE + 0x10, rect_part0_ps2)
                    import struct as st
                    btn_w_px = st.unpack('f', st.pack('I', self.state.mem.read_int(pine_btn + 0x24)))[0]
                    self.state.mem.write_int(FLAG_BASE + 0x14, pack_f(btn_w_px - 6.0))
                    self.state.mem.write_int(FLAG_BASE + 0x18, pack_f(16.0))
                    # Write max_buttons for sub_selection clamp (for rows with overlapping max_toggle)
                    self.state.mem.write_int(0x21F70B7C, self._custom_rows[row_i_c]["buttons"])
            else:
                self.state.mem.write_int(0x21F70B60, 0)
                self.state.mem.write_int(0x21F70B7C, 0)

            # Swap help message description for custom rows
            if hasattr(self, '_help_text_addr'):
                if cursor_row >= 16:
                    ri = cursor_row - 16
                    desc = self._custom_rows[ri].get("desc", "") if ri < len(self._custom_rows) else ""
                else:
                    desc = ""
                if desc:
                    if self._last_desc != desc:
                        from game.dialog import encode
                        self._encoded_desc = encode(desc)
                        max_len = len(self._orig_help_text)
                        if len(self._encoded_desc) > max_len:
                            log.error("Description too long (%d/%d shorts): %s", len(self._encoded_desc), max_len, desc[:60])
                            self._encoded_desc = self._encoded_desc[:max_len - 2] + [0xFF01, 0xFF00]
                        for i in range(max_len):
                            self.state.mem.write_short(
                                self._help_text_addr + i * 2,
                                self._encoded_desc[i] if i < len(self._encoded_desc) else 0)
                        # Force re-render: set to -1 now, restore next cycle
                        self.state.mem.write_int(self._help_msg_ptr + 0x17E4, -1)
                        self._desc_pending_restore = True
                        self._last_desc = desc
                    elif hasattr(self, '_desc_pending_restore') and self._desc_pending_restore:
                        self.state.mem.write_int(self._help_msg_ptr + 0x17E4, self._help_msg_orig_id)
                        self._desc_pending_restore = False
                elif self._last_desc:
                    if hasattr(self, '_orig_help_text'):
                        for i, s in enumerate(self._orig_help_text):
                            self.state.mem.write_short(self._help_text_addr + i * 2, s)
                        self.state.mem.write_int(self._help_msg_ptr + 0x17E4, -1)
                        self._desc_pending_restore = True
                    self._last_desc = ""
                elif hasattr(self, '_desc_pending_restore') and self._desc_pending_restore:
                    self.state.mem.write_int(self._help_msg_ptr + 0x17E4, self._help_msg_orig_id)
                    self._desc_pending_restore = False
            for row_i, row in enumerate(self._custom_rows):
                game_row = 16 + row_i
                cfg_addr = self._config_base_pine + row_i * 4
                new_val = self.state.mem.read_int(cfg_addr)
                old_val = self._last_opt_vals.get(row_i)
                if old_val is not None and new_val != old_val:
                    log.info("%s changed to %d", row["label"], new_val)
                    row["on_change"](new_val)
                self._last_opt_vals[row_i] = new_val
                # Always update button highlights
                for b in range(row["buttons"]):
                    pa = get_btn_addr(row_i, b)
                    if pa:
                        bright = 0x80 if b == new_val else 0x40
                        for off in [0x07, 0x08, 0x09]:
                            self.state.mem.write_byte(pa + off, bright)

            self.root.after(16, self._options_cursor_poll)
        except Exception as e:
            log.error("Options poll error: %s", e, exc_info=True)

    def _inject_custom_rows(self, pine, op, old_count):
        """Inject multiple custom option rows into the options screen."""
        import struct
        pack_f = lambda f: struct.unpack('I', struct.pack('f', f))[0]

        self._custom_rows = [
            {"label": "Run Speed (Town)",              "buttons": 3,
             "btn_tex": [127, 128, 129], "btn_text": [],
             "init": self._init_run_speed,
             "on_change": self._on_run_speed_change,
             "desc": "Mutiplies movement speed in town areas."},
            {"label": "Run Speed (Dungeon)",           "buttons": 3,
             "btn_tex": [127, 128, 129], "btn_text": [],
             "init": self._init_dng_speed,
             "on_change": self._on_dng_speed_change,
             "desc": "Mutiplies movement speed in dungeons."},
            {"label": "Auto Use Repair Powder",        "buttons": 2,
             "btn_tex": [0, 1], "btn_text": [],
             "init": lambda: 0 if self.manager.auto_repair else 1,
             "on_change": self._on_auto_repair_change,
             "desc": "Auto-Uses Repair Powder when weapons break{n}if the appropriate repair powder is available."},
            {"label": "Auto Insert Dungeon Keys",      "buttons": 2,
             "btn_tex": [0, 1], "btn_text": [],
             "init": lambda: 0 if self.manager.auto_key else 1,
             "on_change": self._on_auto_key_change,
             "desc": "Auto-use keys on locked doors when pressing {sq}."},
            {"label": "Map Pos.",                      "buttons": 3,
             "btn_tex": [130, 131, 132], "btn_text": [],
             "init": self._init_map_pos,
             "on_change": self._on_map_pos_change,
             "desc": "Offsets large map position during normal gameplay."},
            {"label": "Map Pos. (Targeting Enemy)",    "buttons": 3,
             "btn_tex": [130, 131, 132], "btn_text": [],
             "init": self._init_map_tgt,
             "on_change": self._on_map_tgt_change,
             "desc": "Offsets large map position while targeting an enemy{n}to move it out of the way."},
            {"label": "Pickup Radius",                 "buttons": 3,
             "btn_tex": [127, 133, 134], "btn_text": [],
             "init": self._init_pickup,
             "on_change": self._on_pickup_change,
             "desc": "Adjust item, experience, etc pickup range."},
            {"label": "Fast Pickup",                   "buttons": 2,
             "btn_tex": [0, 1], "btn_text": [],
             "init": lambda: 0 if self.state.mem.read_byte(addr.OPTION_SAVE_FAST_PICKUP) != 1 else 1,
             "on_change": self._on_fast_pickup_change,
             "desc": "Items become pickupable almost instantly after{n}dropping instead of the normal delay."},
            {"label": "Skip Dung Entry Cutscenes",     "buttons": 2,
             "btn_tex": [0, 1], "btn_text": [],
             "init": lambda: 0 if self.state.mem.read_byte(addr.OPTION_SAVE_AUTO_SKIP_EVENT) != 1 else 1,
             "on_change": self._on_auto_skip_event_change,
             "desc": "Automatically skip the dungeon floor entry cutscene."},
            {"label": "Skip All Cutscenes",            "buttons": 2,
             "btn_tex": [1, 0], "btn_text": [],
             "init": lambda: 1 if self.state.mem.read_byte(addr.OPTION_SAVE_SKIP_ALL_EVENTS) == 1 else 0,
             "on_change": self._on_skip_all_events_change,
             "desc": "Automatically skip all in-game cutscenes and events."},
            {"label": "Show Medal HUD",                 "buttons": 2,
             "btn_tex": [0, 1], "btn_text": [],
             "init": lambda: 0 if settings.get("dungeon_hud") is not False else 1,
             "on_change": self._on_dungeon_hud_change,
             "desc": "Show dungeon floor medal requirements and completion{n}status on screen."},
            {"label": "Fishing HUD",                   "buttons": 2,
             "btn_tex": [0, 1], "btn_text": [],
             "init": lambda: 0 if settings.get("fishing_hud") is not False else 1,
             "on_change": self._on_fishing_hud_change,
             "desc": "Show fish info, pond contents, and fishing status{n}while fishing."},
            {"label": "Fast Bite",                     "buttons": 2,
             "btn_tex": [0, 1], "btn_text": [],
             "init": lambda: 0 if settings.get("fast_bite") is not False else 1,
             "on_change": self._on_fast_bite_change,
             "desc": "Fish bite much faster when casting."},
            {"label": "Show Synth Points HUD",        "buttons": 2,
             "btn_tex": [0, 1], "btn_text": [],
             "init": lambda: 0 if settings.get("synth_hud") is not False else 1,
             "on_change": self._on_synth_hud_change,
             "desc": "Show pending synthesis points on weapon icons."},
            {"label": "Show Gift Box Items",           "buttons": 2,
             "btn_tex": [0, 1], "btn_text": [],
             "init": lambda: 0 if settings.get("gift_box_hud") is not False else 1,
             "on_change": self._on_gift_box_change,
             "desc": "Show item names in clown chest boxes and guarantee{n}you receive the item you select."},
            {"label": "Open Chests Near Enemies",     "buttons": 2,
             "btn_tex": [0, 1], "btn_text": [],
             "init": lambda: 0 if self.state.mem.read_byte(addr.OPTION_SAVE_CHEST_NEAR_ENEMY) != 1 else 1,
             "on_change": self._on_chest_enemy_change,
             "desc": "Allow opening treasure chests when enemies{n}are nearby."},
            {"label": "Start With Map",                "buttons": 2,
             "btn_tex": [1, 0], "btn_text": [],
             "init": lambda: 1 if self.state.mem.read_byte(addr.OPTION_SAVE_START_MAP) == 1 else 0,
             "on_change": self._on_start_map_change,
             "desc": "Automatically reveal the dungeon map on each floor."},
            {"label": "Start With Crystal",            "buttons": 2,
             "btn_tex": [1, 0], "btn_text": [],
             "init": lambda: 1 if self.state.mem.read_byte(addr.OPTION_SAVE_START_CRYSTAL) == 1 else 0,
             "on_change": self._on_start_crystal_change,
             "desc": "Automatically place the magic crystal on each floor."},
            {"label": "JP Prices",                     "buttons": 2,
             "btn_tex": [1, 0], "btn_text": [],
             "init": lambda: 1 if self.manager.jp_prices else 0,
             "on_change": self._on_jp_prices_change,
             "desc": "Use Japanese version prices.{n}Name-Change Ticket: 10 medals. Improved Bomb sell: 500."},
            {"label": "Debug Menu",                    "buttons": 2,
             "btn_tex": [1, 0], "btn_text": [],
             "init": lambda: 1 if self.state.mem.read_int(0x20376FB8) == 1 else 0,
             "on_change": self._on_debug_menu_change,
             "desc": "Enable the game's built-in debug menu."},
            {"label": "Idea HUD",                      "buttons": 2,
             "btn_tex": [0, 1], "btn_text": [],
             "init": lambda: 0 if self.state.mem.read_byte(addr.OPTION_SAVE_IDEA_HUD) != 1 else 1,
             "on_change": self._on_idea_hud_change,
             "desc": "Show nearby uncollected photo ideas on screen."},
            {"label": "Show Idea Names",               "buttons": 2,
             "btn_tex": [1, 0], "btn_text": [],
             "init": lambda: 1 if self.state.mem.read_byte(addr.OPTION_SAVE_IDEA_NAMES) == 1 else 0,
             "on_change": self._on_idea_names_change,
             "desc": "List the names of nearby uncollected ideas{n}below the idea count."},
        ]
        num_rows = len(self._custom_rows)
        total_new_parts = sum(r["buttons"] for r in self._custom_rows)

        # Copy existing parts to cave
        cave = 0x21F72000
        old_pp = 0x20000000 + self.state.mem.read_int(op + 0x6C)
        for i in range(0, old_count * 0x48, 4):
            self.state.mem.write_int(cave + i, self.state.mem.read_int(old_pp + i))

        # Read template button properties from native row 0 parts
        # Part 0 = INDEX00 (ON button), Part 1 = INDEX01 (OFF button)
        btn_templates = []
        for ti in range(2):
            p = cave + ti * 0x48
            ptype = self.state.mem.read_byte(p + 0x06)
            btn_templates.append({
                "tex_ptr": self.state.mem.read_int(p + 0x14),
                "tex_idx": self.state.mem.read_byte(p + 0x18),
                "flags": self.state.mem.read_byte(p + 0x19),
                "ablend": self.state.mem.read_byte(p + 0x1A),
                "w": self.state.mem.read_int(p + 0x24),
                "h": self.state.mem.read_int(p + 0x28),
                "type": ptype,
            })

        # Inject custom button texture patch (must happen before row setup)
        self._inject_btn_textures(cave, btn_templates)

        part_idx = old_count
        names_base = cave + (old_count + total_new_parts) * 0x48
        name_idx = 0

        # Config values go right after all label data
        config_base_ps2 = 0x01F80000 + num_rows * 0x80
        config_base_pine = 0x20000000 + config_base_ps2
        self._config_base_pine = config_base_pine

        for row_i, row in enumerate(self._custom_rows):
            game_row = 16 + row_i
            row["config_ps2"] = config_base_ps2 + row_i * 4
            init_val = row["init"]()
            self.state.mem.write_int(config_base_pine + row_i * 4, init_val)

            for b in range(row["buttons"]):
                a = cave + part_idx * 0x48
                for i in range(0, 0x48, 4):
                    self.state.mem.write_int(a + i, 0)
                tex_idx = row["btn_tex"][b]
                if tex_idx < len(btn_templates):
                    tmpl = btn_templates[tex_idx]
                else:
                    tmpl = btn_templates[0]
                self.state.mem.write_byte(a + 0x04, 1)  # enabled
                self.state.mem.write_byte(a + 0x05, 1)  # visible
                self.state.mem.write_byte(a + 0x06, tmpl["type"])  # part type
                bright = 0x80 if b == init_val else 0x40
                for off in [0x07, 0x08, 0x09]:
                    self.state.mem.write_byte(a + off, bright)
                self.state.mem.write_byte(a + 0x0A, 0x80)  # alpha
                self.state.mem.write_int(a + 0x14, tmpl["tex_ptr"])
                self.state.mem.write_byte(a + 0x18, tex_idx if tex_idx >= 127 else tmpl["tex_idx"])
                self.state.mem.write_byte(a + 0x19, tmpl["flags"])
                self.state.mem.write_byte(a + 0x1A, tmpl["ablend"])
                # Get button size and position
                if tex_idx >= 127:
                    btn_w = float(self._btn_uvs[tex_idx - 127]["w"])
                    btn_h = float(self._btn_uvs[tex_idx - 127]["h"])
                    x = 230.0 + b * (btn_w + 4.0)
                else:
                    btn_w = None  # use template raw values
                    x = 230.0 + b * 60.0
                y = 384.0 + row_i * 24.0
                self.state.mem.write_int(a + 0x1C, pack_f(x))
                self.state.mem.write_int(a + 0x20, pack_f(y))
                if btn_w is not None:
                    self.state.mem.write_int(a + 0x24, pack_f(btn_w))
                    self.state.mem.write_int(a + 0x28, pack_f(btn_h))
                else:
                    self.state.mem.write_int(a + 0x24, tmpl["w"])
                    self.state.mem.write_int(a + 0x28, tmpl["h"])

                # Name string: INDEX{game_row}{b}
                name = f"INDEX{game_row}{b}".encode() + b"\x00" * 4
                na = names_base + name_idx * 16
                for i, ch in enumerate(name[:12]):
                    self.state.mem.write_byte(na + i, ch)
                self.state.mem.write_int(a, na - 0x20000000)  # name_ptr
                name_idx += 1

                # Wire button pointer in CMenuOption (skip if overlaps native config_ptrs)
                btn_ptr_off = 0x164 + game_row * 0xC + b * 4
                part_ps2 = a - 0x20000000
                if btn_ptr_off < 0x254:  # safe, no overlap
                    self.state.mem.write_int(pine + btn_ptr_off, part_ps2)
                # Always store in Python for poll access
                self._btn_part_addrs[(row_i, b)] = a
                part_idx += 1
            # Clear unused button pointers (only if safe)
            for b in range(row["buttons"], 3):
                btn_ptr_off = 0x164 + game_row * 0xC + b * 4
                if btn_ptr_off < 0x254:
                    self.state.mem.write_int(pine + btn_ptr_off, 0)

            # Set max toggle value
            mt_off = 0x114 + game_row * 4
            self.state.mem.write_int(pine + mt_off, row["buttons"])
            # Set config pointer (always safe for rows 16-22, lands in +0x294-0x2AC)
            self.state.mem.write_int(pine + 0x254 + game_row * 4, row["config_ps2"])


        # Update form parts count and pointer
        new_count = old_count + total_new_parts
        new_ps2 = cave - 0x20000000
        self.state.mem.write_int(op + 0x6C, new_ps2)
        self.state.mem.write_short(op + 0x68, new_count)

        # Set config_option_num to include new rows
        total_rows = 16 + num_rows
        v = struct.unpack('I', struct.pack('f', float(total_rows)))[0]
        self.state.mem.write_int(0x203769F8, v)
        self.state.mem.write_int(0x203769FC, v)

        # Write label strings (0x01F80000 + row_i * 0x80) and count
        # Write button text strings and zero unused slots
        self.state.mem.write_int(0x21F80058, num_rows)
        for row_i, row in enumerate(self._custom_rows):
            label_base = 0x21F80000 + row_i * 0x80
            label = row["label"].encode() + b"\x00" * 4
            for i, ch in enumerate(label[:36]):
                self.state.mem.write_byte(label_base + i, ch)
            self.state.mem.write_int(label_base + 0x40, 86)  # label X
            # Zero button text area first
            for i in range(0x24, 0x34):
                self.state.mem.write_byte(label_base + i, 0)
            # Write button text strings (only if btn_text provided)
            for b, txt in enumerate(row.get("btn_text", [])):
                txt_off = 0x24 + b * 8
                txt_bytes = txt.encode() + b"\x00" * 4
                for i, ch in enumerate(txt_bytes[:8]):
                    self.state.mem.write_byte(label_base + txt_off + i, ch)

        # Pre-write rect part addr + size
        mci_ps2 = self.state.mem.read_int(addr.MENU_COMMON_INFO)
        if mci_ps2:
            pine_mci = 0x20000000 + mci_ps2
            rect_form_ps2 = self.state.mem.read_int(pine_mci + 0x13C)
            if rect_form_ps2:
                pine_rect_form = 0x20000000 + rect_form_ps2
                rect_part0_ps2 = self.state.mem.read_int(pine_rect_form + 0x6C)
                self.state.mem.write_int(0x21F70B70, rect_part0_ps2)
                self.state.mem.write_int(0x21F70B74, pack_f(50.0))
                self.state.mem.write_int(0x21F70B78, pack_f(16.0))

        log.info("Injected %d custom rows (%d parts, count %d→%d)",
                 num_rows, total_new_parts, old_count, new_count)

    def _init_run_speed(self):
        cur = self.state.mem.read_int(addr.SPEED_INSTR_MAIN)
        speed_map = {0x40A0: 0, 0x40F0: 1, 0x4120: 2}  # 1x, 1.5x, 2x
        for upper, idx in speed_map.items():
            if cur == addr.speed_lui(upper):
                return idx
        return 0

    def _on_run_speed_change(self, val):
        speed_map = {0: 0x40A0, 1: 0x40F0, 2: 0x4120}
        upper16 = speed_map.get(val, 0x40A0)
        instr = addr.speed_lui(upper16)
        self.state.mem.write_int(addr.SPEED_INSTR_MAIN, instr)
        labels = {0: "1x (Default)", 1: "1.5x", 2: "2x"}
        if val in labels:
            self._speed_var.set(labels[val])
            settings.set("run_speed", labels[val])

    def _on_auto_repair_change(self, val):
        enabled = val == 0
        self.manager.auto_repair = enabled
        settings.set("auto_repair", enabled)
        self._auto_repair_var.set(enabled)
        self.state.mem.write_byte(addr.AUTO_REPAIR_FLAG, 1 if enabled else 0)
        self.state.mem.write_byte(addr.OPTION_SAVE_AUTO_REPAIR, 1 if enabled else 0)

    def _init_dng_speed(self):
        cur = self.state.mem.read_int(addr.SPEED_INSTR_DNG)
        speed_map = {0x3F80: 0, 0x3FC0: 1, 0x4000: 2}  # 1x, 1.5x, 2x
        for upper, idx in speed_map.items():
            if cur == (0x3C020000 | upper):
                return idx
        return 0

    def _on_dng_speed_change(self, val):
        speed_map = {0: "1x (Default)", 1: "1.5x", 2: "2x"}
        upper_map = {0: 0x3F80, 1: 0x3FC0, 2: 0x4000}
        upper16 = upper_map.get(val, 0x3F80)
        self.state.mem.write_int(addr.SPEED_INSTR_DNG, 0x3C020000 | upper16)
        label = speed_map.get(val, "1x (Default)")
        self._dng_speed_var.set(label)
        settings.set("dng_speed", label)
        idx = list(addr.SPEED_DNG_OPTIONS.keys()).index(label)
        self.state.mem.write_byte(addr.OPTION_SAVE_DNG_SPEED, idx)

    def _on_auto_key_change(self, val):
        enabled = val == 0
        self.manager.auto_key = enabled
        settings.set("auto_key", enabled)
        self._auto_key_var.set(enabled)
        self.state.mem.write_byte(addr.OPTION_SAVE_AUTO_KEY, 1 if enabled else 0)

    def _init_map_pos(self):
        label = self._map_pos_var.get()
        pos_map = {"Center (Default)": 0, "Center-Left": 1, "Center-Right": 2}
        return pos_map.get(label, 0)

    def _on_map_pos_change(self, val):
        labels = {0: "Center (Default)", 1: "Center-Left", 2: "Center-Right"}
        label = labels.get(val, "Center (Default)")
        self._map_pos_var.set(label)
        settings.set("map_position", label)
        idx = list(addr.MINIMAP_POS_OPTIONS.keys()).index(label)
        self.state.mem.write_byte(addr.OPTION_SAVE_MAP_POS, idx)
        self._apply_map_position()

    def _init_map_tgt(self):
        label = self._map_tgt_var.get()
        pos_map = {"Center (Default)": 0, "Center-Left": 1, "Center-Right": 2}
        return pos_map.get(label, 0)

    def _on_map_tgt_change(self, val):
        labels = {0: "Center (Default)", 1: "Center-Left", 2: "Center-Right"}
        label = labels.get(val, "Center (Default)")
        self._map_tgt_var.set(label)
        settings.set("map_position_target", label)
        idx = list(addr.MINIMAP_POS_OPTIONS.keys()).index(label)
        self.state.mem.write_byte(addr.OPTION_SAVE_MAP_POS_TARGET, idx)
        self._apply_map_position()

    def _init_pickup(self):
        label = self._pickup_var.get()
        pickup_map = {"1x (Default)": 0, "2x": 1, "5x": 2}
        return pickup_map.get(label, 0)

    def _on_pickup_change(self, val):
        keys = list(addr.PICKUP_RADIUS_OPTIONS.keys())
        vals = list(addr.PICKUP_RADIUS_OPTIONS.values())
        if val >= len(keys):
            val = 0
        label = keys[val]
        self._pickup_var.set(label)
        settings.set("pickup_radius", label)
        self.state.mem.write_byte(addr.OPTION_SAVE_PICKUP_RADIUS, val)
        instr = addr.pickup_radius_lui(vals[val])
        try:
            self.state.mem.write_int(addr.PICKUP_RADIUS_INSTR, instr)
        except Exception:
            pass

    def _on_fast_pickup_change(self, val):
        enabled = val == 0
        self.state.mem.write_byte(addr.OPTION_SAVE_FAST_PICKUP, 0 if enabled else 1)
        for a, fast, orig in addr.PICKUP_DELAY_PATCHES:
            self.state.mem.write_int(a, fast if enabled else orig)

    def _on_auto_skip_event_change(self, val):
        self.state.mem.write_byte(addr.OPTION_SAVE_AUTO_SKIP_EVENT, 0 if val == 0 else 1)

    def _on_skip_all_events_change(self, val):
        self.state.mem.write_byte(addr.OPTION_SAVE_SKIP_ALL_EVENTS, 1 if val == 0 else 0)

    def _on_dungeon_hud_change(self, val):
        enabled = val == 0
        settings.set("dungeon_hud", enabled)
        self.state.mem.write_byte(addr.OPTION_SAVE_DUNGEON_HUD, 0 if enabled else 1)
        if not enabled:
            self.state.mem.write_int(addr.HUD_FLAG, 0)

    def _on_fishing_hud_change(self, val):
        settings.set("fishing_hud", val == 0)

    def _on_fast_bite_change(self, val):
        enabled = val == 0
        settings.set("fast_bite", enabled)
        # Patch GetUkiWaitTime base wait: 0xF0 (240) vs 0x1E (30)
        self.state.mem.write_int(0x20302D80, 0x2411001E if enabled else 0x241100F0)

    def _on_synth_hud_change(self, val):
        enabled = val == 0
        settings.set("synth_hud", enabled)
        self._synth_hud_var.set(enabled)
        self.state.mem.write_byte(addr.OPTION_SAVE_SYNTH_HUD, 0 if enabled else 1)

    def _on_start_map_change(self, val):
        enabled = val == 1
        self.state.mem.write_byte(addr.OPTION_SAVE_START_MAP, 1 if enabled else 0)
        self._start_map_var.set(enabled)

    def _on_start_crystal_change(self, val):
        enabled = val == 1
        self.state.mem.write_byte(addr.OPTION_SAVE_START_CRYSTAL, 1 if enabled else 0)
        self._start_crystal_var.set(enabled)

    def _on_gift_box_change(self, val):
        enabled = val == 0
        settings.set("gift_box_hud", enabled)
        self._gift_box_var.set(enabled)
        self.state.mem.write_byte(addr.OPTION_SAVE_GIFT_BOX, 0 if enabled else 1)

    def _on_debug_menu_change(self, val):
        self.state.mem.write_int(0x20376FB8, 1 if val == 1 else 0)

    def _on_idea_hud_change(self, val):
        self.state.mem.write_byte(addr.OPTION_SAVE_IDEA_HUD, 0 if val == 0 else 1)

    def _on_idea_names_change(self, val):
        self.state.mem.write_byte(addr.OPTION_SAVE_IDEA_NAMES, 1 if val == 1 else 0)

    def _on_jp_prices_change(self, val):
        enabled = val == 1
        self.manager.jp_prices = enabled
        self.manager._shop_patched = False
        self.state.mem.write_byte(addr.OPTION_SAVE_JP_PRICES, 1 if enabled else 0)

    def _on_chest_enemy_change(self, val):
        enabled = val == 0
        self.state.mem.write_byte(addr.OPTION_SAVE_CHEST_NEAR_ENEMY, 0 if enabled else 1)
        self.state.mem.write_int(addr.CHEST_ENEMY_CHECK,
                                 0x00000000 if enabled else addr.CHEST_ENEMY_CHECK_ORIG)

    def _inject_btn_textures(self, cave, btn_templates):
        """Write custom button texture patch and create TexGetInfo entries."""
        import os, json, struct, sys
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
        else:
            base = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..')
        tex_dir = os.path.join(base, 'Textures', 'OptionsMenu')
        patch_path = os.path.join(tex_dir, 'btn_patch.bin')
        meta_path = os.path.join(tex_dir, 'btn_patch_meta.json')
        if not os.path.exists(patch_path):
            log.warning("No button texture patch found")
            return
        with open(patch_path, 'rb') as f:
            self._btn_patch_data = f.read()
        with open(meta_path) as f:
            meta = json.load(f)

        self._write_btn_patch()

        # Create TexGetInfo entries
        mp = self.state.mem.read_int(0x20377940)
        pine_mp = 0x20000000 + mp
        tgi_base = self.state.mem.read_int(pine_mp + 0x10)
        src_tgi = 0x20000000 + tgi_base + 114 * 0x20

        for i, btn in enumerate(meta["buttons"]):
            idx = 127 + i
            dst = 0x20000000 + tgi_base + idx * 0x20
            for off in range(0, 0x20, 4):
                self.state.mem.write_int(dst + off, self.state.mem.read_int(src_tgi + off))
            self.state.mem.write_int(dst + 0x00, btn["x"])
            self.state.mem.write_int(dst + 0x04, btn["y"])
            self.state.mem.write_int(dst + 0x08, btn["w"])
            self.state.mem.write_int(dst + 0x0C, btn["h"])

        self._btn_uvs = meta["buttons"]
        log.info("Injected %d custom button textures (%d pixels)",
                 len(meta["buttons"]), len(self._btn_patch_data) // 5)

    def _write_btn_patch(self):
        """Write the sparse texture patch to EE RAM."""
        import struct
        patch = self._btn_patch_data
        # Read pixel data address from native button's mgCTexture
        obf = self.state.mem.read_int(addr.OPTION_BUTTON_FORM)
        if obf == 0:
            base = 0x21B73F60  # fallback
        else:
            parts_ptr = self.state.mem.read_int(0x20000000 + obf + 0x6C)
            tex_ptr = self.state.mem.read_int(0x20000000 + parts_ptr + 0x14)
            pixel_addr = self.state.mem.read_int(0x20000000 + tex_ptr + 0x50)
            base = 0x20000000 + pixel_addr
        log.info("Texture atlas base: 0x%08X", base)
        i = 0
        while i < len(patch):
            tag = chr(patch[i])
            if tag == 'F':
                off, val = struct.unpack_from('<II', patch, i + 1)
                self.state.mem.write_int(base + off, val)
                i += 9
            elif tag == 'B':
                off, val = struct.unpack_from('<IB', patch, i + 1)
                self.state.mem.write_byte(base + off, val)
                i += 6

    def _early_texture_patch(self):
        """Patch button atlas early (before menu opens) so GS upload includes our data."""
        try:
            self._load_btn_patch()
            self._write_btn_patch()
            log.info("Early texture patch applied")
        except Exception as e:
            log.error("Early texture patch failed: %s", e)

    def _load_btn_patch(self):
        """Load patch data from disk if not already loaded."""
        if hasattr(self, '_btn_patch_data'):
            return
        import os, sys
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
        else:
            base = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..')
        tex_dir = os.path.join(base, 'Textures', 'OptionsMenu')
        with open(os.path.join(tex_dir, 'btn_patch.bin'), 'rb') as f:
            self._btn_patch_data = f.read()

    def _reinject_btn_textures(self):
        """Re-apply texture patch (atlas may have been reloaded)."""
        if hasattr(self, '_btn_patch_data'):
            self._write_btn_patch()

    def _on_close(self):
        self.manager.stop_nowait()
        self.state.mem.disconnect()
        self.root.destroy()

    def run(self):
        self.manager.start()
        self._options_auto_poll()
        def _poll():
            self.root.after(500, _poll)
        _poll()
        self.root.mainloop()


class TextHandler(logging.Handler):
    def __init__(self, widget, root):
        super().__init__()
        self.widget = widget
        self.root = root
        self.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S"))

    def emit(self, record):
        msg = self.format(record) + "\n"
        try:
            self.root.after(0, self._append, msg)
        except Exception:
            pass

    def _append(self, msg):
        self.widget.config(state=tk.NORMAL)
        self.widget.insert(tk.END, msg)
        self.widget.see(tk.END)
        lines = int(self.widget.index("end-1c").split(".")[0])
        if lines > 200:
            self.widget.delete("1.0", f"{lines - 200}.0")
        self.widget.config(state=tk.DISABLED)
