"""Mod orchestrator. Manages all mod subsystems and their lifecycle."""

import logging
import threading
import time
from core.memory import Memory
from game.game_state import GameState, GameSnapshot
from game import addresses as addr
from game.hud import write_hud

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
        self.on_options_loaded = None  # callback(speed_label, pickup_label, map_label, map_tgt_label)

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
                    self._apply_saved_options()
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

            # Update HUD overlay
            if self._ingame:
                try:
                    write_hud(self.mem, loop_no)
                except Exception as e:
                    log.error("HUD error: %s", e)
                try:
                    self._debug_event_dialog()
                except Exception:
                    pass
                try:
                    self._auto_repair_tick()
                except Exception:
                    pass
                try:
                    self._auto_key_tick()
                except Exception:
                    pass

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

    def _debug_event_dialog(self):
        """Auto-dismiss the Magic Crystal chest dialog (msg 0x8CA)."""
        scene_ptr = self.mem.read_int(addr.DNG_MAIN_SCENE)
        if scene_ptr == 0:
            return
        pine_scene = 0x20000000 + scene_ptr
        clsmes_ptr = self.mem.read_int(pine_scene + addr._SCENE_MSG_CLSMES_OFFSET)
        if clsmes_ptr == 0:
            return
        pine_cls = 0x20000000 + clsmes_ptr
        msg_id = self.mem.read_int(pine_cls + 0x17E4)
        if msg_id == 0x8CA:
            self.mem.write_int(pine_cls + 0x17E4, -1)
            log.info("Auto-dismissed Magic Crystal dialog")

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
        if self.on_options_loaded:
            self.on_options_loaded(speed_label, pickup_label, map_label, map_tgt_label, dng_speed_label)

    def _auto_repair_tick(self):
        """Check if PNACH cave consumed a repair powder, then update inventory."""
        if not self.auto_repair:
            self.mem.write_int(addr.AUTO_REPAIR_FLAG, 0)
            return

        # Check if cave signaled a consumption
        consumed = self.mem.read_int(addr.REPAIR_CONSUMED)
        if consumed != 0:
            self.mem.write_int(addr.REPAIR_CONSUMED, 0)
            item_id = addr.REPAIR_POWDER_MELEE if consumed == 1 else addr.REPAIR_POWDER_RANGED
            slot_name = "melee" if consumed == 1 else "ranged"
            if self._consume_item(item_id):
                log.info("Auto-used Repair Powder (%s)", slot_name)
            else:
                log.warning("Repair powder consumed but item not found in inventory!")

        # Scan inventory for any repair powder and set/clear the flag
        has_melee = self._find_item(addr.REPAIR_POWDER_MELEE) is not None
        has_ranged = self._find_item(addr.REPAIR_POWDER_RANGED) is not None
        self.mem.write_int(addr.AUTO_REPAIR_FLAG, 1 if (has_melee or has_ranged) else 0)

    def _auto_key_tick(self):
        """Set auto-key flag and log when PNACH cave uses a key."""
        self.mem.write_int(addr.AUTO_KEY_FLAG, 1 if self.auto_key else 0)
        if not self.auto_key:
            return
        consumed = self.mem.read_int(addr.KEY_CONSUMED)
        if consumed != 0:
            self.mem.write_int(addr.KEY_CONSUMED, 0)
            log.info("Auto-used dungeon key on door (box %d)", consumed - 1)

    def _find_item(self, item_id):
        """Find inventory slot address containing item_id, or None."""
        base = addr.USER_DATA_MANAGER
        for i in range(addr.INVENTORY_SLOT_COUNT):
            slot = base + i * addr.INVENTORY_SLOT_SIZE
            iid = self.mem.read_short(slot + 2)
            if iid == item_id:
                count = self.mem.read_short(slot + 0x10)
                if count > 0:
                    return slot
        return None

    def _consume_item(self, item_id):
        """Decrement count of item_id in inventory. Returns True if successful."""
        slot = self._find_item(item_id)
        if slot is None:
            return False
        count = self.mem.read_short(slot + 0x10)
        if count <= 1:
            # Last one — zero out the entire slot
            for off in range(0, addr.INVENTORY_SLOT_SIZE, 4):
                self.mem.write_int(slot + off, 0)
        else:
            self.mem.write_short(slot + 0x10, count - 1)
        return True
