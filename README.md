# Dark Cloud 2 Reforged

A cross-platform mod for **Dark Cloud 2** (Dark Chronicle) using **PINE IPC** to communicate with PCSX2. Compatible with modern PCSX2 builds (v1.7+ and Nightly) on **Windows, Linux, and macOS** — including Steam Deck.

Built using the same framework as [Dark Cloud Reforged](https://github.com/ZeldoKavira/DarkCloud-Reforged).

## Requirements

- **PCSX2** (v1.7+ or Nightly) with PINE IPC enabled (Settings → Advanced → Enable PINE)
- **Dark Cloud 2 (NTSC-U)** — SCUS-97213
- **The Reforged PNACH file** — placed in PCSX2's cheats folder with cheats enabled
- **Python 3.10+** (if running from source) or a pre-built binary from Releases

This mod does not include the game. You must own a legal copy of Dark Cloud 2.

## Running

From source:

```bash
cd src
python main.py
```

Or download a pre-built binary from [Releases](../../releases) and run it alongside PCSX2.

## Project Status

This mod is in early development. The base framework (PINE IPC connection, memory read/write, game state polling, mod manager, UI dashboard) is in place. Game-specific memory addresses and mod features are being developed.

## Architecture

```
src/
├── main.py              # Entry point
├── core/                # Game-agnostic infrastructure
│   ├── pine_ipc.py      # PINE protocol client (TCP/Unix socket)
│   ├── memory.py        # Typed read/write with auto-reconnect
│   ├── version.py       # Version resolution (git tag / build stamp)
│   ├── settings.py      # JSON settings persistence
│   └── changelog.py     # Version changelog system
├── game/                # DC2-specific game layer
│   ├── addresses.py     # Memory addresses
│   ├── game_state.py    # Memory polling → GameSnapshot
│   └── helpers.py       # Reusable game helpers
├── mods/                # Mod subsystems
│   ├── base.py          # Threaded mod base class
│   └── manager.py       # Mod lifecycle orchestrator
├── ui/
│   └── app.py           # Tkinter status dashboard
└── data/                # Game data tables
```

## Building

```bash
pip install -r requirements-build.txt
bash scripts/stamp-version.sh
pyinstaller --onefile --name DC2-Reforged --windowed src/main.py
```

## Releasing

```bash
./scripts/release.sh          # auto-increments patch version
./scripts/release.sh v0.2.0   # explicit version
```

This generates a changelog from git commits, stamps the version, commits, tags, and pushes. The GitHub Actions workflow builds binaries for all platforms and creates a release.
