"""Game state tracker. Polls memory and maintains a snapshot of current state."""

import logging
import time
from dataclasses import dataclass, field
from core.memory import Memory
from game import addresses as addr

log = logging.getLogger(__name__)


@dataclass
class PlayerInfo:
    character_id: int = 0
    character_name: str = "Max"
    gilda: int = 0
    pos_x: float = 0.0
    pos_y: float = 0.0
    pos_z: float = 0.0


@dataclass
class DungeonInfo:
    dungeon_id: int = 0
    dungeon_name: str = ""
    floor: int = 0
    status: int = 0


@dataclass
class TownInfo:
    area_id: int = 0
    area_name: str = ""


@dataclass
class ModFlags:
    pnach_active: bool = False
    mod_active: bool = False
    enhanced_save: bool = False


@dataclass
class BattleInfo:
    in_battle: bool = False
    battle_count: int = 0


@dataclass
class TitleInfo:
    title_info_ptr: int = 0
    title_info_0: int = 0       # *TitleInfo — screen (0=movie,1=menu,2=save select)
    title_info_1: int = 0       # TitleInfo[1] — next state
    title_info_8: int = 0       # TitleInfo[8] — cursor position (short at +8)
    title_phase: int = 0        # TitlePhase (separate global)
    instr_002a0134: int = 0     # Debug: instruction at patch target


@dataclass
class GameSnapshot:
    connected: bool = False
    emu_status: int = 2
    dc2_detected: bool = False
    loop_no: int = 0
    loop_name: str = "Unknown"
    now_mode: int = 0
    menu_mode: int = 0
    paused: bool = False
    play_time: int = 0
    player: PlayerInfo = field(default_factory=PlayerInfo)
    dungeon: DungeonInfo = field(default_factory=DungeonInfo)
    town: TownInfo = field(default_factory=TownInfo)
    title: TitleInfo = field(default_factory=TitleInfo)
    battle: BattleInfo = field(default_factory=BattleInfo)
    flags: ModFlags = field(default_factory=ModFlags)
    frame_counter: int = 0
    prev_frame_counter: int = 0
    error: str = ""


LOOP_NAMES = {
    0: "Exit",
    1: "Town",
    2: "Dungeon",
    3: "Title Screen",
}


class GameState:
    """Continuously polls PCSX2 memory and builds GameSnapshot."""

    def __init__(self, mem: Memory):
        self.mem = mem
        self.snapshot = GameSnapshot()
        self._callbacks = []
        self._prev_title = (None, None, None, None, None)  # loop, info0, info1, cursor, phase

    def on_update(self, cb):
        self._callbacks.append(cb)

    def _notify(self):
        for cb in self._callbacks:
            try:
                cb(self.snapshot)
            except Exception as e:
                log.error("Callback error: %s", e)

    def poll(self):
        snap = self.snapshot

        if not self.mem.connected:
            if not self.mem.connect():
                snap.connected = False
                snap.error = "PCSX2 not found — is PINE/IPC enabled?"
                self._notify()
                return
        snap.connected = True
        snap.error = ""

        try:
            self._poll_core(snap)
        except Exception as e:
            log.debug("Poll error: %s", e)
            self.mem.disconnect()
            snap.connected = False
            snap.dc2_detected = False
            snap.error = f"Connection lost: {e}"

        self._notify()

    def _poll_core(self, snap: GameSnapshot):
        mem = self.mem

        snap.emu_status = mem.status()
        if snap.emu_status == 2:
            snap.dc2_detected = False
            snap.error = "No game running"
            return

        # DC2 detection — cache after first successful check
        if not snap.dc2_detected:
            game_id = mem.game_id().strip().strip('\x00')
            snap.dc2_detected = game_id.startswith(addr.DC2_GAME_ID)
            if not snap.dc2_detected:
                snap.error = f"Dark Cloud 2 not detected (got: {game_id!r})"
                return

        # Frame counter for save state detection
        snap.prev_frame_counter = snap.frame_counter
        snap.frame_counter = mem.read_int(addr.PLAY_TIME_COUNT)

        # Core state
        snap.loop_no = mem.read_int(addr.LOOP_NO)
        snap.loop_name = LOOP_NAMES.get(snap.loop_no, f"Unknown ({snap.loop_no})")
        snap.now_mode = mem.read_int(addr.NOW_MODE)
        snap.menu_mode = mem.read_int(addr.MENU_MODE)
        snap.paused = mem.read_int(addr.PAUSE_FLAG) != 0
        snap.play_time = mem.read_int(addr.PLAY_TIME_COUNT)

        # Battle
        snap.battle.in_battle = mem.read_int(addr.BATTLE_FLAG) != 0
        snap.battle.battle_count = mem.read_int(addr.BATTLE_COUNT)

        # Player
        char_id = mem.read_int(addr.ACTIVE_CHARA_NO)
        snap.player.character_id = char_id
        snap.player.character_name = addr.CHARACTER_NAMES.get(char_id, "Unknown")
        snap.player.gilda = mem.read_int(addr.GILDA)

        # Mod flags
        snap.flags.pnach_active = mem.read_byte(addr.PNACH_FLAG) == 1
        snap.flags.mod_active = mem.read_byte(addr.MOD_FLAG) == 1
        snap.flags.enhanced_save = mem.read_byte(addr.ENHANCED_MOD_SAVE_FLAG) == 1

        # Dungeon info (when in dungeon loop)
        if snap.loop_no == addr.Mode.DUNGEON:
            snap.dungeon.status = mem.read_int(addr.DNG_STATUS)

        # Title screen info (when on title)
        if snap.loop_no == addr.Mode.TITLE:
            ptr = mem.read_int(addr.TITLE_INFO_PTR)
            snap.title.title_info_ptr = ptr
            if ptr != 0:
                snap.title.title_info_0 = mem.read_int(ptr)
                snap.title.title_info_1 = mem.read_int(ptr + 4)
                snap.title.title_info_8 = mem.read_short(ptr + 8)
            snap.title.title_phase = mem.read_short(addr.TITLE_PHASE)
            snap.title.instr_002a0134 = mem.read_int(0x202A0134)

        # Log title state changes
        cur = (snap.loop_no, snap.title.title_info_0, snap.title.title_info_1,
               snap.title.title_info_8, snap.title.title_phase)
        if cur != self._prev_title:
            log.info("Title: loop=%d info0=%d info1=%d cursor=%d phase=%d",
                     *cur)
            self._prev_title = cur
