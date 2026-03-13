"""Mod orchestrator. Manages all mod subsystems and their lifecycle."""

import logging
import threading
import time
from core.memory import Memory
from game.game_state import GameState, GameSnapshot
from game import addresses as addr

log = logging.getLogger(__name__)


class ModManager:
    """Orchestrates all mod subsystems based on game state."""

    def __init__(self, mem: Memory, state: GameState):
        self.mem = mem
        self.state = state
        self._running = False
        self._thread = None
        self._ingame = False
        self._mods_started = False
        self.fast_start = False
        self.widescreen = False

        self.all_mods = []

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._main_loop, daemon=True, name="ModManager")
        self._thread.start()

    def stop(self):
        self._running = False
        for mod in self.all_mods:
            mod.stop()
        if self._thread:
            self._thread.join(timeout=3)

    def stop_nowait(self):
        self._running = False
        for mod in self.all_mods:
            mod._running = False

    def _main_loop(self):
        log.info("Mod manager started")

        while self._running:
            self.state.poll()
            snap = self.state.snapshot

            if not snap.connected or not snap.dc2_detected:
                if self._mods_started:
                    self._stop_mods()
                time.sleep(1)
                continue

            if not snap.flags.pnach_active:
                time.sleep(0.5)
                continue

            # Set mod flag so PNACH knows we're running
            self.mem.write_int(addr.MOD_FLAG, 1)
            self.mem.write_int(addr.FAST_START_FLAG, 1 if self.fast_start else 0)
            self.mem.write_int(addr.WIDESCREEN_FLAG, 1 if self.widescreen else 0)

            loop_no = snap.loop_no

            # Detect entering in-game (dungeon or town)
            if not self._ingame and loop_no in (addr.Mode.DUNGEON, addr.Mode.TOWN):
                # Wait for load to finish — keep checking until loop stabilizes
                time.sleep(2)
                loop_no = self.mem.read_int(addr.LOOP_NO)
                if loop_no not in (addr.Mode.DUNGEON, addr.Mode.TOWN):
                    continue  # was transient, not actually in-game yet

                if loop_no == addr.Mode.TOWN and self.mem.read_byte(addr.ENHANCED_MOD_SAVE_FLAG) != 1:
                    # New game — first time entering town, stamp the save
                    self.mem.write_byte(addr.ENHANCED_MOD_SAVE_FLAG, 1)
                    log.info("New game detected, set enhanced save flag")

                if self.mem.read_byte(addr.ENHANCED_MOD_SAVE_FLAG) == 1:
                    log.info("Entering in-game (loop=%d), starting mods", loop_no)
                    self._start_mods()
                    self._ingame = True
                else:
                    log.warning("Not a Reforged save file — mods disabled for this session.")
                    self._ingame = True  # mark as in-game so we don't keep checking

            # Detect returning to title
            if self._ingame and loop_no in (addr.Mode.TITLE, addr.Mode.EXIT):
                log.info("Returned to title/exit")
                self._stop_mods()
                self._ingame = False

            time.sleep(0.001)

        self.mem.write_int(addr.MOD_FLAG, 0)

    def _start_mods(self):
        if self._mods_started:
            return
        for mod in self.all_mods:
            mod.start()
        self._mods_started = True

    def _stop_mods(self):
        for mod in self.all_mods:
            mod.stop()
        self._mods_started = False
        self._ingame = False
