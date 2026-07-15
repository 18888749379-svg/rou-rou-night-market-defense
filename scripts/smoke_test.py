from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import save_data
from settings import (
    ENEMIES,
    ENEMY_ORDER,
    IMAGE_DIR,
    LEVELS,
    LEVEL_COIN_REWARDS,
    UNITS,
    UNIT_ORDER,
)


def validate_configuration() -> None:
    assert len(LEVELS) == 15
    assert len(LEVEL_COIN_REWARDS) == len(LEVELS)
    assert set(UNIT_ORDER) == set(UNITS)
    assert set(ENEMY_ORDER) == set(ENEMIES)

    for config in (*UNITS.values(), *ENEMIES.values()):
        assert (IMAGE_DIR / config.image).is_file(), f"missing image: {config.image}"

    for level in LEVELS:
        times = [time for time, _ in level.waves]
        assert times == sorted(times), f"level {level.number}: waves are not sorted"
        assert len(times) == len(set(times)), f"level {level.number}: duplicate wave time"
        for _, wave in level.waves:
            assert wave, f"level {level.number}: empty wave"
            assert all(enemy in ENEMIES for enemy in wave), f"level {level.number}: unknown enemy"


def validate_game_flow() -> None:
    with tempfile.TemporaryDirectory(prefix="rou_rou_defense_") as temp_dir:
        save_data.SAVE_PATH = Path(temp_dir) / "save_data.json"
        from game import Game

        save_data.write_save(
            {
                "version": 4,
                "global_tuning": [],
                "level_tuning": {"1": {"resources": [], "units": "bad", "enemies": None}},
                "accounts": {
                    "invalid": "bad",
                    "recoverable": {
                        "coins": "not-a-number",
                        "completed_levels": 12,
                        "unlocked_level": None,
                        "selected_level": {},
                        "owned_units": None,
                        "unit_upgrades": [],
                        "oil_capacity_level": "bad",
                        "loadout": 3,
                    },
                },
                "active_account": "recoverable",
            }
        )
        game = Game()
        assert game.active_account == "recoverable"
        assert game.coins == 0 and game.unlocked_level == 1
        assert game._button_rect("close_info").bottom < 210
        for level in LEVELS:
            game.selected_level = level.number
            game._apply_level_tuning(level.number)
            game.reset_game()
            game.state = "playing"
            game.game_time = 1000.0
            game._spawn_waves()
            assert game.spawned_enemies == game.total_enemies, level.number
            for enemy in list(game.enemies):
                enemy.take_damage(enemy.hp, game)
            game.update(0.0)
            assert game.state == "win", level.number

        game.state = "menu"
        game.draw()
        saved = save_data.load_save()
        assert saved.get("version") == 4
        assert len(saved.get("level_tuning", {})) == len(LEVELS)
        pygame.quit()


def main() -> None:
    validate_configuration()
    validate_game_flow()
    print("Smoke test passed: assets, save data, UI, and all 15 levels")


if __name__ == "__main__":
    main()
