"""
Locate Horsey Game directories relative to HorseSDK layout.

Layout:
  HorseSDK/
    Game/Horsey.exe
    Game/data/
    Game/save/
    RE_Tools/
"""
from __future__ import annotations

import os
from pathlib import Path


def _horse_sdk_root() -> Path:
    # RE_Tools/tools/core/paths.py -> up 3 = HorseSDK
    return Path(__file__).resolve().parents[3]


def get_game_dir() -> Path:
    root = _horse_sdk_root()
    game = root / "Game"
    if game.is_dir():
        return game
    raise FileNotFoundError(f"Game directory not found: {game}")


def get_exe_path() -> Path:
    exe = get_game_dir() / "Horsey.exe"
    if exe.is_file():
        return exe
    raise FileNotFoundError(f"Horsey.exe not found: {exe}")


def get_data_dir() -> Path:
    data = get_game_dir() / "data"
    if data.is_dir():
        return data
    raise FileNotFoundError(f"data/ not found: {data}")


def get_save_dir() -> Path:
    save = get_game_dir() / "save"
    if save.is_dir():
        return save
    raise FileNotFoundError(f"save/ not found: {save}")
