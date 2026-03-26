"""Mod orchestrator. Manages all mod subsystems and their lifecycle."""

import logging
import threading
import time
from core.memory import Memory
from core import settings
from game.game_state import GameState, GameSnapshot
from game import addresses as addr
from game.hud import write_hud
from game.fishing_hud import write_fishing_hud
from game import render
from game.idea_hud import tick as idea_hud_tick
from game.invention import tick as invention_tick
from mods import auto_repair, auto_key, event_skip, map_reveal, jp_prices

render.register("idea_hud", idea_hud_tick)

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
        self.auto_repair = False
        self.auto_key = False
        self.jp_prices = False
        self.invent_dim = True
        self.on_options_loaded = None
        self.on_early_texture_patch = None
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

            # On title screen with fast start, default cursor to Continue (once)
            if loop_no == addr.Mode.TITLE and self.fast_start:
                if not getattr(self, '_title_cursor_set', False):
                    ti_ptr = self.mem.read_int(addr.TITLE_INFO_PTR)
                    if ti_ptr != 0:
                        self.mem.write_short(0x20000000 + ti_ptr + 8, 1)
                        self._title_cursor_set = True
            else:
                self._title_cursor_set = False

            # Detect entering in-game (dungeon or town)
            if not self._ingame and loop_no in (addr.Mode.DUNGEON, addr.Mode.TOWN):
                time.sleep(2)
                loop_no = self.mem.read_int(addr.LOOP_NO)
                if loop_no not in (addr.Mode.DUNGEON, addr.Mode.TOWN):
                    continue

                if loop_no == addr.Mode.TOWN and self.mem.read_byte(addr.ENHANCED_MOD_SAVE_FLAG) != 1:
                    self.mem.write_byte(addr.ENHANCED_MOD_SAVE_FLAG, 1)
                    self.mem.write_byte(addr.OPTION_SAVE_RUN_SPEED, 1)
                    self.mem.write_byte(addr.OPTION_SAVE_PICKUP_RADIUS, 1)
                    self.mem.write_byte(addr.OPTION_SAVE_MAP_POS_TARGET, 4)
                    self.mem.write_byte(addr.OPTION_SAVE_AUTO_REPAIR, 1)
                    self.mem.write_byte(addr.OPTION_SAVE_AUTO_KEY, 1)
                    log.info("New game detected, set defaults")

                if self.mem.read_byte(addr.ENHANCED_MOD_SAVE_FLAG) == 1:
                    log.info("Entering in-game (loop=%d), starting mods", loop_no)
                    self._apply_saved_options()
                    self._start_mods()
                    self._ingame = True
                    if self.on_early_texture_patch:
                        self.on_early_texture_patch()
                else:
                    log.warning("Not a Reforged save file — mods disabled for this session.")
                    self._ingame = True

            # Detect returning to title
            if self._ingame and loop_no in (addr.Mode.TITLE, addr.Mode.EXIT):
                log.info("Returned to title/exit")
                self._stop_mods()
                self._ingame = False

            if self._ingame:
                hud_counter = getattr(self, '_hud_counter', 0) + 1
                self._hud_counter = hud_counter
                if hud_counter % 5 == 0:
                    try:
                        auto_key.tick(self.mem, self.auto_key, getattr(self, 'dialog', None))
                    except Exception:
                        pass
                    try:
                        auto_repair.tick(self.mem, self.auto_repair)
                    except Exception:
                        pass
                    try:
                        if self.invent_dim:
                            invention_tick(self.mem)
                    except Exception:
                        pass
                    try:
                        event_skip.tick(self.mem)
                    except Exception:
                        pass
                    try:
                        render.tick(self.mem, loop_no)
                    except Exception:
                        pass
                if hud_counter % 50 == 0:
                    try:
                        fishing_active = False
                        if settings.get("fishing_hud") is not False:
                            fishing_active = write_fishing_hud(self.mem, loop_no)
                        if not fishing_active:
                            if settings.get("dungeon_hud") is not False:
                                write_hud(self.mem, loop_no)
                            else:
                                self.mem.write_int(addr.HUD_FLAG, 0)
                    except Exception as e:
                        log.error("HUD error: %s", e)
                    try:
                        map_reveal.tick(self.mem)
                    except Exception:
                        pass
                    try:
                        jp_prices.tick(self.mem, self.jp_prices)
                    except Exception:
                        pass
                if hud_counter % 30 == 0:
                    try:
                        from game.hud import write_gift_box_hud
                        write_gift_box_hud(self.mem, None)
                    except Exception:
                        pass

            time.sleep(0.016)

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

    def _apply_saved_options(self):
        """Read saved option bytes and sync UI dropdowns."""
        speed_keys = list(addr.SPEED_OPTIONS.keys())
        dng_speed_keys = list(addr.SPEED_DNG_OPTIONS.keys())
        pickup_keys = list(addr.PICKUP_RADIUS_OPTIONS.keys())
        map_keys = list(addr.MINIMAP_POS_OPTIONS.keys())

        speed_idx = self.mem.read_byte(addr.OPTION_SAVE_RUN_SPEED)
        dng_speed_idx = self.mem.read_byte(addr.OPTION_SAVE_DNG_SPEED)
        pickup_idx = self.mem.read_byte(addr.OPTION_SAVE_PICKUP_RADIUS)
        map_idx = self.mem.read_byte(addr.OPTION_SAVE_MAP_POS)
        map_tgt_idx = self.mem.read_byte(addr.OPTION_SAVE_MAP_POS_TARGET)

        speed_label = speed_keys[speed_idx] if speed_idx < len(speed_keys) else speed_keys[0]
        dng_speed_label = dng_speed_keys[dng_speed_idx] if dng_speed_idx < len(dng_speed_keys) else dng_speed_keys[0]
        pickup_label = pickup_keys[pickup_idx] if pickup_idx < len(pickup_keys) else pickup_keys[0]
        map_label = map_keys[map_idx] if map_idx < len(map_keys) else map_keys[0]
        map_tgt_label = map_keys[map_tgt_idx] if map_tgt_idx < len(map_keys) else map_keys[0]

        log.info("Loaded saved options — town_speed=%s, dng_speed=%s, pickup=%s, map=%s, map_target=%s",
                 speed_label, dng_speed_label, pickup_label, map_label, map_tgt_label)

        self.auto_repair = self.mem.read_byte(addr.OPTION_SAVE_AUTO_REPAIR) == 1
        self.auto_key = self.mem.read_byte(addr.OPTION_SAVE_AUTO_KEY) == 1
        self.jp_prices = self.mem.read_byte(addr.OPTION_SAVE_JP_PRICES) == 1
        self.invent_dim = self.mem.read_byte(addr.OPTION_SAVE_INVENT_DIM) != 1
        dungeon_hud = self.mem.read_byte(addr.OPTION_SAVE_DUNGEON_HUD) != 1
        synth_hud = self.mem.read_byte(addr.OPTION_SAVE_SYNTH_HUD) != 1
        settings.set("auto_repair", self.auto_repair)
        settings.set("auto_key", self.auto_key)
        settings.set("dungeon_hud", dungeon_hud)
        settings.set("synth_hud", synth_hud)
        gift_box = self.mem.read_byte(addr.OPTION_SAVE_GIFT_BOX) != 1
        settings.set("gift_box_hud", gift_box)

        if settings.get("fast_bite") is not False:
            self.mem.write_int(0x20302D80, 0x2411001E)

        if self.mem.read_byte(addr.OPTION_SAVE_CHEST_NEAR_ENEMY) != 1:
            self.mem.write_int(addr.CHEST_ENEMY_CHECK, 0x00000000)

        if self.mem.read_byte(addr.OPTION_SAVE_FISH_NEAR_ENEMY) != 1:
            self.mem.write_int(addr.FISH_ENEMY_CHECK, 0x00000000)

        if self.mem.read_byte(addr.OPTION_SAVE_FAST_PICKUP) != 1:
            for a, fast, orig in addr.PICKUP_DELAY_PATCHES:
                self.mem.write_int(a, fast)

        # Buildup helper runtime flag
        self.mem.write_int(addr.BUILDUP_HELPER_FLAG,
                           0 if self.mem.read_byte(addr.OPTION_SAVE_BUILDUP_HELPER) == 1 else 1)

        # Buildup name reveal
        if self.mem.read_byte(addr.OPTION_SAVE_BUILDUP_NAMES) != 1:
            self.mem.write_int(addr.BUILDUP_NAME_CHECK, addr.BUILDUP_NAME_CHECK_SHOW)

        if self.on_options_loaded:
            self.on_options_loaded(speed_label, pickup_label, map_label, map_tgt_label, dng_speed_label)
