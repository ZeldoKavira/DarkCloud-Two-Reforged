#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
bash scripts/build-pnach.sh
cp pcsx2-files/1DF41F33.pnach "$HOME/Library/Application Support/PCSX2/cheats/"
echo "Deployed to local PCSX2 cheats folder."
if [[ "$1" == "--run" ]]; then
    cd src && python3 main.py
fi
