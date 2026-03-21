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
        self.on_early_texture_patch = None  # callback to patch textures early

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
                # Wait for load to finish — keep checking until loop stabilizes
                time.sleep(2)
                loop_no = self.mem.read_int(addr.LOOP_NO)
                if loop_no not in (addr.Mode.DUNGEON, addr.Mode.TOWN):
                    continue  # was transient, not actually in-game yet

                if loop_no == addr.Mode.TOWN and self.mem.read_byte(addr.ENHANCED_MOD_SAVE_FLAG) != 1:
                    # New game — stamp save and write defaults
                    self.mem.write_byte(addr.ENHANCED_MOD_SAVE_FLAG, 1)
                    self.mem.write_byte(addr.OPTION_SAVE_RUN_SPEED, 1)       # 1.5x
                    self.mem.write_byte(addr.OPTION_SAVE_PICKUP_RADIUS, 1)   # 2x
                    self.mem.write_byte(addr.OPTION_SAVE_MAP_POS_TARGET, 4)  # Center-Right
                    self.mem.write_byte(addr.OPTION_SAVE_AUTO_REPAIR, 1)     # on
                    self.mem.write_byte(addr.OPTION_SAVE_AUTO_KEY, 1)        # on
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
                    self._ingame = True  # mark as in-game so we don't keep checking

            # Detect returning to title
            if self._ingame and loop_no in (addr.Mode.TITLE, addr.Mode.EXIT):
                log.info("Returned to title/exit")
                self._stop_mods()
                self._ingame = False

            # Update HUD overlay
            if self._ingame:
                hud_counter = getattr(self, '_hud_counter', 0) + 1
                self._hud_counter = hud_counter
                if hud_counter % 50 == 0:
                    try:
                        # Fishing HUD takes priority when active
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
                    self._auto_key_tick()
                except Exception:
                    pass
                if hud_counter % 50 == 0:
                    try:
                        self._start_floor_tick()
                    except Exception:
                        pass
                try:
                    self._auto_repair_tick()
                except Exception:
                    pass
                if hud_counter % 30 == 0:
                    try:
                        from game.hud import write_gift_box_hud
                        write_gift_box_hud(self.mem, None)
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

        # Load toggle options from save data
        self.auto_repair = self.mem.read_byte(addr.OPTION_SAVE_AUTO_REPAIR) == 1
        self.auto_key = self.mem.read_byte(addr.OPTION_SAVE_AUTO_KEY) == 1
        dungeon_hud = self.mem.read_byte(addr.OPTION_SAVE_DUNGEON_HUD) != 1  # 0=on (default)
        synth_hud = self.mem.read_byte(addr.OPTION_SAVE_SYNTH_HUD) != 1
        settings.set("auto_repair", self.auto_repair)
        settings.set("auto_key", self.auto_key)
        settings.set("dungeon_hud", dungeon_hud)
        settings.set("synth_hud", synth_hud)
        gift_box = self.mem.read_byte(addr.OPTION_SAVE_GIFT_BOX) != 1
        settings.set("gift_box_hud", gift_box)

        # Apply fast bite patch if enabled
        if settings.get("fast_bite") is not False:
            self.mem.write_int(0x20302D80, 0x2411001E)

        if self.on_options_loaded:
            self.on_options_loaded(speed_label, pickup_label, map_label, map_tgt_label, dng_speed_label)

    def _auto_repair_tick(self):
        """Check if PNACH cave consumed a repair powder, then update inventory."""
        if not self.auto_repair:
            if getattr(self, '_repair_flag_set', False):
                self.mem.write_int(addr.AUTO_REPAIR_FLAG, 0)
                self._repair_flag_set = False
            return

        consumed = self.mem.read_int(addr.REPAIR_CONSUMED)
        if consumed != 0:
            self.mem.write_int(addr.REPAIR_CONSUMED, 0)
            item_id = addr.REPAIR_POWDER_MELEE if consumed == 1 else addr.REPAIR_POWDER_RANGED
            cached = getattr(self, '_repair_slot_cache', {}).get(item_id)
            if cached is not None:
                iid = self.mem.read_short(cached + 2)
                count = self.mem.read_short(cached + 0x10)
                if iid == item_id and count > 0:
                    self.mem.write_short(cached + 0x10, count - 1)
                    log.info("Auto-used Repair Powder (%s)", "melee" if consumed == 1 else "ranged")
                    if count - 1 <= 0:
                        self._repair_needs_scan = True
                else:
                    self._repair_needs_scan = True
            else:
                self._repair_needs_scan = True

        if getattr(self, '_repair_needs_scan', True):
            cache = {}
            melee_slot = self._find_item(addr.REPAIR_POWDER_MELEE)
            ranged_slot = self._find_item(addr.REPAIR_POWDER_RANGED)
            if melee_slot: cache[addr.REPAIR_POWDER_MELEE] = melee_slot
            if ranged_slot: cache[addr.REPAIR_POWDER_RANGED] = ranged_slot
            self._repair_slot_cache = cache
            self.mem.write_int(addr.AUTO_REPAIR_FLAG, 1 if cache else 0)
            self._repair_flag_set = bool(cache)
            self._repair_needs_scan = False

    def _start_floor_tick(self):
        """Reveal map / place crystal on new dungeon floors."""
        ptr = self.mem.read_int(addr.NOW_FLOOR_INFO_PTR)
        if ptr == 0:
            self._last_floor_ptr_sf = None
            return
        if ptr == getattr(self, '_last_floor_ptr_sf', None):
            return
        self._last_floor_ptr_sf = ptr
        PINE = 0x20000000
        log.info("New floor detected (ptr=0x%X)", ptr)
        scene_ptr = self.mem.read_int(0x2037729C)  # DngMainScene
        if scene_ptr == 0:
            return
        scene = PINE + scene_ptr
        flags = self.mem.read_int(scene + 0x2FF4)
        if self.mem.read_byte(addr.OPTION_SAVE_START_MAP) == 1:
            flags |= 1
            self._reveal_map()
        if self.mem.read_byte(addr.OPTION_SAVE_START_CRYSTAL) == 1:
            flags |= 2
        self.mem.write_int(scene + 0x2FF4, flags)

    def _reveal_map(self):
        """Replicate MinimapAllVisible — set all map cells visible."""
        PINE = 0x20000000
        automap = PINE + 0x01EA0480
        w = self.mem.read_short(automap + 0x1B8)
        h = self.mem.read_short(automap + 0x1BA)
        grid_ptr = self.mem.read_int(automap + 0x1CC)
        if grid_ptr == 0 or w == 0 or h == 0:
            return
        grid = PINE + grid_ptr
        for i in range(w * h):
            self.mem.write_short(grid + i * 0x1C + 0x0C, 1)

    def _auto_key_tick(self):
        """Auto-use dungeon key on gate when player presses X."""
        if not self.auto_key:
            return
        PINE = 0x20000000
        menu_state = self.mem.read_int(PINE + 0x01ECD618)
        if menu_state != 9:
            return
        key_id = self.mem.read_short(PINE + 0x01ECD64C)
        if key_id < 0x151 or key_id > 0x15F:
            return
        if self._find_item(key_id) is not None:
            self._consume_item(key_id)
            p_use = self.mem.read_int(0x20377CE0)
            if p_use != 0:
                self.mem.write_int(0x20000000 + p_use + 4, key_id)
            self.mem.write_int(0x20377CE0, 0)
            self.mem.write_int(PINE + 0x01ECD630, key_id)
            self.mem.write_int(PINE + 0x01ECD618, 0)
            self.mem.write_int(PINE + 0x01ECE500, 0)
            log.info("Auto-used gate key 0x%X", key_id)
        else:
            self.mem.write_int(PINE + 0x01ECD630, 0)
            self.mem.write_int(PINE + 0x01ECD618, 0)
            self.mem.write_int(PINE + 0x01ECE500, 0)
            if hasattr(self, 'dialog') and self.dialog:
                self.dialog.show("You don't have the required key.", duration=3, mode=0)

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
            self.mem.write_short(slot + 0x10, 0)
        else:
            self.mem.write_short(slot + 0x10, count - 1)
        return True
