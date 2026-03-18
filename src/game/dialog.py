"""In-game dialog system for DC2 Reforged.

Usage:
    from game.dialog import Dialog

    dialog = Dialog(mem, root)

    # Simple timed message:
    dialog.show("Hello world!", duration=5)

    # Message with color:
    dialog.show("{red}Warning: {reset}something happened", duration=8)

    # Yes/No prompt with callback:
    dialog.ask("Enable feature?", callback=on_answer)

    def on_answer(choice):
        # choice is True (Yes/X) or False (No/O)
        if choice:
            dialog.show("Enabled!", duration=3)
"""
import logging
from game.addresses import (
    Pad, GAMEPAD_BUTTONS, LOCK_CHARA,
    SYSTEM_MESSAGE_0, MSG_0x81B1_TEXT, DIALOG_FLAG,
)

log = logging.getLogger(__name__)

# DC2 text encoding: ASCII - 0x20 for 0x01-0x3A, ASCII - 0x21 for 0x3B-0x5D
_DC2 = {' ': 0xFF02}
for _c in range(0x01, 0x3C):
    _DC2[chr(_c + 0x20)] = _c
for _c in range(0x3C, 0x5E):
    _DC2[chr(_c + 0x21)] = _c
_TAGS = {
    'red': [0xFC01], 'reset': [0xFC00], 'n': [0xFF00],
    'x': [0xFD06], 'o': [0xFD03], 'tri': [0xFD08], 'sq': [0xFD09],
    'l1': [0xFD07], 'r1': [0xFD0A], 'l2': [0xFD0B], 'r2': [0xFD0C],
}


def encode(text):
    """Encode a string to DC2 16-bit format. Supports {red}, {reset}, {n} tags."""
    result = []
    i = 0
    while i < len(text):
        if text[i] == '{':
            end = text.find('}', i)
            if end != -1:
                tag = text[i+1:end].lower()
                if tag in _TAGS:
                    result.extend(_TAGS[tag])
                    i = end + 1
                    continue
        result.append(_DC2.get(text[i], 0xFF02))
        i += 1
    result.append(0xFF01)
    result.append(0xFF00)
    return result


class Dialog:
    """In-game dialog system. Requires Memory and a tkinter root for timers."""

    def __init__(self, mem, root):
        self._mem = mem
        self._root = root
        self._timer = None
        self._poll_id = None
        self._callback = None

    @property
    def active(self):
        return self._mem.read_int(SYSTEM_MESSAGE_0 + 0x17E4) != -1

    def show(self, text, duration=5, mode=None, x=None, y=None):
        """Show a passive dialog for `duration` seconds.
        mode: MsgPreset mode (default 4=passive bottom-center, 0=NPC white text)
        """
        self._write_and_trigger(text, mode=mode)
        if x is not None or y is not None:
            import time; time.sleep(0.05)
            sm = SYSTEM_MESSAGE_0
            if x is not None:
                self._mem.write_int(sm + 0x198, x)
            if y is not None:
                self._mem.write_int(sm + 0x19C, y)
        self._set_timer(duration)

    def ask(self, text, callback=None):
        """Show a yes/no dialog. Calls callback(True) for Yes, callback(False) for No/cancel."""
        self._callback = callback
        self._write_and_trigger(text)

        import time; time.sleep(0.2)
        self._mem.write_int(SYSTEM_MESSAGE_0 + 0x130, 5)   # yes/no window
        self._mem.write_int(SYSTEM_MESSAGE_0 + 0x17F4, 1)  # enable button
        self._mem.write_int(SYSTEM_MESSAGE_0 + 0x1AF8, 2)  # selection mode
        self._mem.write_int(SYSTEM_MESSAGE_0 + 0x1AE4, 0)  # cursor on Yes
        self._mem.write_int(LOCK_CHARA, 1)
        self._poll()

    def dismiss(self):
        """Dismiss the current dialog."""
        self._cancel_timers()
        self._mem.write_int(SYSTEM_MESSAGE_0 + 0x17E4, -1)
        self._mem.write_int(LOCK_CHARA, 0)

    # --- internals ---

    def _write_and_trigger(self, text, mode=None):
        self._cancel_timers()
        encoded = encode(text)
        for i in range(max(len(encoded), 100)):
            self._mem.write_short(MSG_0x81B1_TEXT + i * 2, encoded[i] if i < len(encoded) else 0)
        self._mem.write_int(DIALOG_FLAG + 8, mode if mode is not None else 4)  # DIALOG_MODE
        self._mem.write_int(DIALOG_FLAG, 0x81B1)

    def _set_timer(self, seconds):
        self._timer = self._root.after(int(seconds * 1000), self.dismiss)

    def _cancel_timers(self):
        if self._timer:
            self._root.after_cancel(self._timer)
            self._timer = None
        if self._poll_id:
            self._root.after_cancel(self._poll_id)
            self._poll_id = None

    def _poll(self):
        try:
            btns = self._mem.read_int(GAMEPAD_BUTTONS)
            cur = self._mem.read_int(SYSTEM_MESSAGE_0 + 0x1AE4)

            if btns & Pad.LEFT:
                self._mem.write_int(SYSTEM_MESSAGE_0 + 0x1AE4, (cur - 1) % 2)
            elif btns & Pad.RIGHT:
                self._mem.write_int(SYSTEM_MESSAGE_0 + 0x1AE4, (cur + 1) % 2)
            elif btns & Pad.X:
                choice = cur == 0
                self.dismiss()
                log.info("Dialog: selected %s", "Yes" if choice else "No")
                if self._callback:
                    self._callback(choice)
                return
            elif btns & Pad.O:
                self.dismiss()
                log.info("Dialog: cancelled")
                if self._callback:
                    self._callback(False)
                return

            self._poll_id = self._root.after(20, self._poll)
        except Exception as e:
            log.error("Dialog poll failed: %s", e)
            self._mem.write_int(LOCK_CHARA, 0)
