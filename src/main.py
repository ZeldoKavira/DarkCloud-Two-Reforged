"""Dark Cloud 2 Reforged
Entry point. Launches the mod window and connects to PCSX2 via PINE IPC.
"""

import sys
import signal
from core.pine_ipc import PineIPC
from core.memory import Memory
from game.game_state import GameState
from ui.app import App


def main():
    ipc = PineIPC()
    mem = Memory(ipc)
    state = GameState(mem)
    app = App(state)

    def _quit(*args):
        app._on_close()
        sys.exit(0)

    signal.signal(signal.SIGINT, _quit)
    app.run()


if __name__ == "__main__":
    main()
