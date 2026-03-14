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

        # Load saved settings
        self.manager.fast_start = settings.get("fast_start") or False
        self.manager.widescreen = settings.get("widescreen") or False

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

        inner = ttk.Frame(tab, style="Panel.TFrame")
        inner.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(inner, text="Game Options", background=ACCENT, foreground=FG,
                  font=("Helvetica", 10, "bold"), padding=(8, 3)).pack(fill=tk.X)

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

        # Run speed
        speed_row = ttk.Frame(opts, style="Panel.TFrame")
        speed_row.pack(anchor=tk.W, pady=(8, 2))
        tk.Label(speed_row, text="Run Speed", bg=BG_PANEL, fg=FG,
                 font=("Helvetica", 10)).pack(side=tk.LEFT)
        self._speed_var = tk.StringVar(value=settings.get("run_speed") or "1x (Default)")
        speed_menu = ttk.Combobox(speed_row, textvariable=self._speed_var,
                                  values=list(addr.SPEED_OPTIONS.keys()),
                                  state="readonly", width=14)
        speed_menu.pack(side=tk.LEFT, padx=(8, 0))
        speed_menu.bind("<<ComboboxSelected>>", lambda e: self._set_run_speed())
        ttk.Label(opts, text="Multiply character movement speed",
                  style="Dim.TLabel").pack(anchor=tk.W, padx=20)

        # Debug
        debug = ttk.Frame(inner, style="Panel.TFrame")
        debug.pack(fill=tk.X, padx=8, pady=8)
        tk.Button(debug, text="Test Dialog (msg 0x66)", command=self._test_dialog,
                  bg=ACCENT, fg=FG, font=("Helvetica", 10)).pack(anchor=tk.W)
        tk.Button(debug, text="Dump Message Table", command=self._dump_msg_table,
                  bg=ACCENT, fg=FG, font=("Helvetica", 10)).pack(anchor=tk.W, pady=(4, 0))

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

    def _set_run_speed(self):
        label = self._speed_var.get()
        settings.set("run_speed", label)
        self._apply_run_speed()

    def _apply_run_speed(self):
        label = self._speed_var.get()
        upper16 = addr.SPEED_OPTIONS.get(label, 0x40a0)
        if upper16 == 0x40a0:
            return  # default, no patch needed
        instr = addr.speed_lui(upper16)
        try:
            cur = self.state.mem.read_int(addr.SPEED_INSTR_MAIN)
            if cur != instr:
                self.state.mem.write_int(addr.SPEED_INSTR_MAIN, instr)
                log.info("Run speed → %s", label)
        except Exception:
            pass

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
        self.dialog.ask("Do you want a DC2 mod?", callback=self._on_answer)

    def _on_answer(self, choice):
        self.dialog.show("You chose: " + ("Yes" if choice else "No"), duration=10)

    def _on_close(self):
        self.manager.stop_nowait()
        self.state.mem.disconnect()
        self.root.destroy()

    def run(self):
        self.manager.start()
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
