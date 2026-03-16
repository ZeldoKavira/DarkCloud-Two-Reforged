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

        # Load saved settings
        self.manager.fast_start = settings.get("fast_start") or False
        self.manager.widescreen = settings.get("widescreen") or False
        self.manager.auto_repair = settings.get("auto_repair") or False

        self.root = tk.Tk()
        from core.version import get_version
        from game.dialog import Dialog
        self.dialog = Dialog(state.mem, self.root)
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

        if snap.loop_no == 1:
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

    def _test_dialog(self):
        """Inject row 16 + start poll."""
        import struct
        try:
            ptr = self.state.mem.read_int(0x203781B0)
            if ptr == 0:
                log.info("Options not open"); return
            pine = 0x20000000 + ptr
            obf = self.state.mem.read_int(0x20378198)
            if obf == 0: return
            op = 0x20000000 + obf
            count = self.state.mem.read_short(op + 0x68)
            if count <= 33:
                self._inject_row16(pine, op, count)
            self._pine = pine
            self._poll_fix()
            log.info("Injected + poll active")
        except Exception as e:
            log.error("Failed: %s", e)

    def _poll_fix(self):
        """Poll to update cursor/rect positions for injected option rows.

        The PNACH cave (10-cursor-fix) hooks after FormStep and writes
        cursor + rect form positions from flag memory at 0x01F70B60-0x01F70B78.
        This poll computes the correct positions from the selected button's
        screen coordinates and writes them to the flag area.

        Also updates the label text Y position at 0x01F80044 for the draw cave.

        Flag memory layout (0x01F70B60+):
          +0x00 (0xB60): cursor form target X (float, 0=disabled)
          +0x04 (0xB64): cursor form target Y (float)
          +0x08 (0xB68): rect form target X (float)
          +0x0C (0xB6C): rect form target Y (float)
          +0x10 (0xB70): rect part[0] PS2 addr (for size fix)
          +0x14 (0xB74): rect part width (float)
          +0x18 (0xB78): rect part height (float)
        """
        import struct
        try:
            # Bail if options screen closed (CMenuOptionPtr == 0)
            menu_opt_ptr = self.state.mem.read_int(addr.CMENU_OPTION_PTR)
            if menu_opt_ptr == 0:
                return

            pine_opt = self._pine  # PINE addr of CMenuOption
            cursor_row = self.state.mem.read_int(pine_opt + 0x374)

            if cursor_row >= 16:
                # --- Read selected button's position ---
                sub_selection = self.state.mem.read_int(pine_opt + 0x37C)
                btn_ptr_offset = 0x164 + cursor_row * 0xC + sub_selection * 4
                btn_ps2 = self.state.mem.read_int(pine_opt + btn_ptr_offset)
                if not btn_ps2:
                    self.root.after(200, self._poll_fix)
                    return

                pine_btn = 0x20000000 + btn_ps2
                btn_x = struct.unpack('f', struct.pack('I', self.state.mem.read_int(pine_btn + 0x1C)))[0]
                btn_y = struct.unpack('f', struct.pack('I', self.state.mem.read_int(pine_btn + 0x20)))[0]

                # --- Read OptionButtonForm base position (scrolls with the list) ---
                obf_ps2 = self.state.mem.read_int(addr.OPTION_BUTTON_FORM)
                pine_obf = 0x20000000 + obf_ps2
                obf_x = struct.unpack('f', struct.pack('I', self.state.mem.read_int(pine_obf + 0x0C)))[0]
                obf_y = struct.unpack('f', struct.pack('I', self.state.mem.read_int(pine_obf + 0x10)))[0]

                # --- Compute screen position of selected button ---
                btn_screen_x = obf_x + btn_x
                btn_screen_y = obf_y + btn_y

                # --- Cursor form position (spinning arrow, offset -50,-3 from button) ---
                cursor_target_x = btn_screen_x - 50.0
                cursor_target_y = btn_screen_y - 3.0

                # --- Rect form position (dashed rectangle, offset -2,-2 from button) ---
                rect_target_x = btn_screen_x - 2.0
                rect_target_y = btn_screen_y - 2.0

                # --- Write cursor/rect targets to cave flag area ---
                pack_f = lambda f: struct.unpack('I', struct.pack('f', f))[0]
                FLAG_BASE = 0x21F70B60
                self.state.mem.write_int(FLAG_BASE + 0x00, pack_f(cursor_target_x))
                self.state.mem.write_int(FLAG_BASE + 0x04, pack_f(cursor_target_y))
                self.state.mem.write_int(FLAG_BASE + 0x08, pack_f(rect_target_x))
                self.state.mem.write_int(FLAG_BASE + 0x0C, pack_f(rect_target_y))

                # --- Write rect part addr + size for the cave to fix SetWakuWH ---
                mci_ps2 = self.state.mem.read_int(addr.MENU_COMMON_INFO)
                pine_mci = 0x20000000 + mci_ps2
                rect_form_ps2 = self.state.mem.read_int(pine_mci + 0x13C)
                pine_rect_form = 0x20000000 + rect_form_ps2
                rect_part0_ps2 = self.state.mem.read_int(pine_rect_form + 0x6C)
                self.state.mem.write_int(FLAG_BASE + 0x10, rect_part0_ps2)
                self.state.mem.write_int(FLAG_BASE + 0x14, pack_f(50.0))   # rect width
                self.state.mem.write_int(FLAG_BASE + 0x18, pack_f(16.0))   # rect height

                # --- Update label text Y to track the button row ---
                LABEL_BASE = 0x21F80000
                self.state.mem.write_int(LABEL_BASE + 0x40, 86)                # label X
                self.state.mem.write_int(LABEL_BASE + 0x44, int(btn_screen_y) + 2)  # label Y
            else:
                # Cursor on a native row — disable cave override
                self.state.mem.write_int(0x21F70B60, 0)

            self.root.after(200, self._poll_fix)
        except Exception as e:
            log.error("Options poll error: %s", e)

    def _inject_row16(self, pine, op, old_count):
        import struct
        old_ptr = self.state.mem.read_int(op + 0x6C)
        cave = 0x21F72000
        old_pp = 0x20000000 + old_ptr
        for i in range(0, old_count * 0x48, 4):
            self.state.mem.write_int(cave + i, self.state.mem.read_int(old_pp + i))
        src = cave
        tex_ptr = self.state.mem.read_int(src + 0x14)
        tex_idx = self.state.mem.read_byte(src + 0x18)
        src_w = self.state.mem.read_int(src + 0x24)
        src_h = self.state.mem.read_int(src + 0x28)
        flags = self.state.mem.read_byte(src + 0x19)
        ablend = self.state.mem.read_byte(src + 0x1A)
        new_count = old_count + 2
        for b in range(2):
            a = cave + (old_count + b) * 0x48
            for i in range(0, 0x48, 4):
                self.state.mem.write_int(a + i, 0)
            self.state.mem.write_byte(a + 0x04, 1)
            self.state.mem.write_byte(a + 0x05, 1)
            bright = 0x80 if b == 0 else 0x40
            for off in [0x07, 0x08, 0x09]:
                self.state.mem.write_byte(a + off, bright)
            self.state.mem.write_byte(a + 0x0A, 0x80)
            self.state.mem.write_int(a + 0x14, tex_ptr)
            self.state.mem.write_byte(a + 0x18, tex_idx)
            self.state.mem.write_byte(a + 0x19, flags)
            self.state.mem.write_byte(a + 0x1A, ablend)
            x = 230.0 + b * 60.0
            self.state.mem.write_int(a + 0x1C, struct.unpack('I', struct.pack('f', x))[0])
            self.state.mem.write_int(a + 0x20, struct.unpack('I', struct.pack('f', 384.0))[0])
            self.state.mem.write_int(a + 0x24, src_w)
            self.state.mem.write_int(a + 0x28, src_h)
        new_ps2 = cave - 0x20000000
        self.state.mem.write_int(op + 0x6C, new_ps2)
        self.state.mem.write_short(op + 0x68, new_count)
        p33 = new_ps2 + old_count * 0x48
        self.state.mem.write_int(pine + 0x224, p33)
        self.state.mem.write_int(pine + 0x228, p33 + 0x48)
        self.state.mem.write_int(pine + 0x22C, 0)

        # Write name strings at 0x01F70A40 (safe from auto-repair cave at 0x01F70B00)
        names_base = 0x21F70A40
        for b, name in enumerate([b"INDEX160\x00\x00\x00\x00", b"INDEX161\x00\x00\x00\x00"]):
            na = names_base + b * 16
            for i, ch in enumerate(name):
                self.state.mem.write_byte(na + i, ch)
            # Set name_ptr on the part
            part_addr = cave + (old_count + b) * 0x48
            self.state.mem.write_int(part_addr, (na - 0x20000000))  # PS2 addr
        self.state.mem.write_int(pine + 0x114 + 16 * 4, 2)
        v = struct.unpack('I', struct.pack('f', 17.0))[0]
        self.state.mem.write_int(0x203769F8, v)
        self.state.mem.write_int(0x203769FC, v)
        log.info("Row 16 injected (count %d→%d)", old_count, new_count)
        # Verify: read back the last 2 parts' names
        for b in range(2):
            pa = cave + (old_count + b) * 0x48
            np = self.state.mem.read_int(pa)  # name_ptr (PS2 addr)
            if np:
                npp = 0x20000000 + np
                name = ''.join(chr(self.state.mem.read_byte(npp + i)) for i in range(10)
                               if self.state.mem.read_byte(npp + i) != 0)
                log.info("  part[%d] name='%s' name_ptr=0x%08X", old_count + b, name, np)
            else:
                log.info("  part[%d] name_ptr=NULL", old_count + b)
        # Write label text at 0x01F80000
        label = b"Run Speed\x00\x00\x00\x00\x00\x00\x00"
        for i, ch in enumerate(label):
            self.state.mem.write_byte(0x21F80000 + i, ch)
        # Write label X/Y position (near the button row)
        # The label should be to the left of the buttons
        # Buttons are at screen X ~316, label should be around X=100
        # Y should match the button Y
        self.state.mem.write_int(0x21F80040, 86)
        self.state.mem.write_int(0x21F80044, 200)
        log.info("Draw flag set, label at 0x01F80000, X=86 Y=200")

    def _on_close(self):
        self.manager.stop_nowait()
        self.state.mem.disconnect()
        self.root.destroy()

    def run(self):
        self.manager.start()
        # Periodic no-op so Tkinter yields to signal handlers (Ctrl+C)
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
