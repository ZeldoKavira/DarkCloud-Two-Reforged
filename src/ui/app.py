"""Main application window with mod status dashboard."""

import logging
import tkinter as tk
from tkinter import ttk
from game.game_state import GameState, GameSnapshot
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

        self.root = tk.Tk()
        from core.version import get_version
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

        self._build_ui()
        self.state.on_update(self._on_state_update)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        header = ttk.Frame(self.root)
        header.pack(fill=tk.X, padx=10, pady=(10, 5))
        ttk.Label(header, text="Dark Cloud 2 Reforged", style="Header.TLabel").pack(side=tk.LEFT)
        self.status_dot = tk.Label(header, text="●", font=("Helvetica", 16), bg=BG, fg=RED)
        self.status_dot.pack(side=tk.RIGHT, padx=5)
        self.status_label = ttk.Label(header, text="Connecting...", style="Status.TLabel")
        self.status_label.pack(side=tk.RIGHT)

        container = ttk.Frame(self.root)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        canvas = tk.Canvas(container, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=canvas.yview)
        self._scroll_frame = ttk.Frame(canvas)
        self._scroll_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self._scroll_frame, anchor="nw")
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

        sf = self._scroll_frame
        content = ttk.Frame(sf)
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

        self._fast_start_var = tk.BooleanVar(value=False)
        tk.Checkbutton(self.flags_panel, text="Fast Start Game", variable=self._fast_start_var,
                        command=self._toggle_fast_start, bg=BG_PANEL, fg=FG,
                        selectcolor=BG, activebackground=BG_PANEL, activeforeground=FG,
                        font=("Helvetica", 10)).pack(anchor=tk.W, padx=10, pady=(0, 5))

        self.dng_panel = self._panel(right, "Dungeon")
        self.dng_fields = self._add_fields(self.dng_panel, [
            "Status",
        ])

        self.title_panel = self._panel(right, "Title Screen")
        self.title_fields = self._add_fields(self.title_panel, [
            "TitleInfo Ptr", "TitleInfo[0]", "TitleInfo[1]", "Cursor (+8)", "TitlePhase",
            "Instr@0x2A0134",
        ])

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
        self.manager.fast_start = self._fast_start_var.get()

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
