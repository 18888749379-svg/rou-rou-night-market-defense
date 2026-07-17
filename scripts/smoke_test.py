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
    CELL_SIZE,
    EGG_MINE_DEPLOY_HP,
    ENDING_ANIMATION_DURATION,
    GRID_X,
    GRID_Y,
    IMAGE_DIR,
    LEVELS,
    LEVEL_COIN_REWARDS,
    REVERSE_AI_SCHEDULE,
    REVERSE_ZOMBIE_COSTS,
    UNITS,
    UNIT_ORDER,
    UNIT_PLACEMENT_COOLDOWNS,
)


def validate_configuration() -> None:
    assert len(LEVELS) == 15
    assert len(LEVEL_COIN_REWARDS) == len(LEVELS)
    assert set(UNIT_ORDER) == set(UNITS)
    assert set(ENEMY_ORDER) == set(ENEMIES)
    assert set(UNIT_PLACEMENT_COOLDOWNS) == set(UNITS)
    assert UNIT_PLACEMENT_COOLDOWNS["charcoal"] == 3.0
    assert UNIT_PLACEMENT_COOLDOWNS["wall"] == 15.0
    assert (IMAGE_DIR / "ending_victory.png").is_file()
    assert (IMAGE_DIR / "ending_defeat.png").is_file()

    for config in (*UNITS.values(), *ENEMIES.values()):
        assert (IMAGE_DIR / config.image).is_file(), f"missing image: {config.image}"

    for level in LEVELS:
        times = [time for time, _ in level.waves]
        assert times == sorted(times), f"level {level.number}: waves are not sorted"
        assert len(times) == len(set(times)), f"level {level.number}: duplicate wave time"
        if level.special == "reverse":
            assert not level.waves
            continue
        for _, wave in level.waves:
            assert wave, f"level {level.number}: empty wave"
            assert all(enemy in ENEMIES for enemy in wave), f"level {level.number}: unknown enemy"


def validate_game_flow() -> None:
    with tempfile.TemporaryDirectory(prefix="rou_rou_defense_") as temp_dir:
        save_data.SAVE_PATH = Path(temp_dir) / "save_data.json"
        from entities import Enemy, Unit
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
        assert game.state == "login" and game.login_required
        game.login_text = "中文名"
        game._login_or_create()
        assert game.state == "login" and "英文字母" in game.login_message
        game.login_text = "recoverable"
        game._login_or_create()
        assert game.state == "home" and game.active_account == "recoverable"

        game.accounts["Second2"] = game._new_account()
        game.accounts["Second2"]["coins"] = 77
        game._open_login("home", None)
        game._switch_account("Second2")
        assert game.state == "home" and game.active_account == "Second2" and game.coins == 77
        game._open_login("home", None)
        game.login_text = "NewPlayer3"
        game._login_or_create()
        assert game.active_account == "NewPlayer3"
        assert game.coins == 0 and game.unlocked_level == 1 and not game.completed_levels
        assert game._button_rect("close_info").bottom < 210
        assert game._button_rect("home_start").centerx == game.screen.get_rect().centerx
        assert game._level_rect(0).y == 160
        for level in LEVELS:
            game.selected_level = level.number
            game._apply_level_tuning(level.number)
            game.reset_game()
            game.state = "playing"
            if level.special == "reverse":
                assert len(game.reverse_cards) == len(REVERSE_ZOMBIE_COSTS)
                game.game_time = REVERSE_AI_SCHEDULE[0][0] - 2.0
                game._update_reverse_director()
                assert game.reverse_previews
                game.game_time = REVERSE_AI_SCHEDULE[0][0] + 0.1
                game._update_reverse_director()
                assert game.units
                before = game.charcoal
                baby_card = next(card for card in game.reverse_cards if card.enemy_type == "baby")
                assert game._begin_reverse_drag(baby_card.rect.center)
                game._finish_reverse_drag((GRID_X + CELL_SIZE, GRID_Y + CELL_SIZE // 2))
                assert game.enemies and game.enemies[0].enemy_type == "baby"
                assert game.charcoal == before - REVERSE_ZOMBIE_COSTS["baby"]
                eaten = game.units[0]
                reward_before = game.charcoal
                eaten.alive = False
                game.on_unit_eaten(eaten, game.enemies[0])
                assert game.charcoal > reward_before
                game.reverse_core_hp = 1
                game.enemies[0].x = -100
                game.update(0.0)
                assert game.state == "ending"
                game.update(ENDING_ANIMATION_DURATION + 0.1)
                assert game.state == "win"
                continue
            game.game_time = 1000.0
            game._spawn_waves()
            assert game.spawned_enemies == game.total_enemies, level.number
            for enemy in list(game.enemies):
                enemy.take_damage(enemy.hp, game)
            game.update(0.0)
            assert game.state == "ending", level.number
            game.update(ENDING_ANIMATION_DURATION + 0.1)
            assert game.state == "win", level.number

        game.selected_level = 1
        game._apply_level_tuning(1)
        game.reset_game()
        game.state = "playing"
        game.charcoal = 999
        game._select_unit("charcoal")
        game.try_place(0, 0)
        assert game.card_cooldowns["charcoal"] == UNIT_PLACEMENT_COOLDOWNS["charcoal"]
        game._select_unit("charcoal")
        assert game.selected_unit is None
        game.update(UNIT_PLACEMENT_COOLDOWNS["charcoal"] + 0.1)
        assert game.card_cooldowns["charcoal"] == 0.0

        mine = Unit("egg_mine", 1, 3)
        assert not mine.deployed and mine.hp == EGG_MINE_DEPLOY_HP
        assert mine.config.damage == 200 and mine.config.cooldown == 5.0
        mine.update(mine.config.cooldown - 0.1, game)
        assert not mine.deployed and mine.alive
        mine.update(0.2, game)
        assert mine.deployed and mine.hp == mine.config.hp
        target = Enemy("normal", 1)
        target.x = mine.rect.centerx
        target.rect.centerx = int(target.x)
        game.enemies = [target]
        mine.update(0.01, game)
        assert mine.triggered and not mine.alive
        assert not target.alive

        game.reset_game()
        game.state = "playing"
        game._open_exit_confirm()
        assert game.exit_confirm and game.paused
        game.draw()
        game._close_exit_confirm()
        assert not game.exit_confirm and not game.paused
        game._begin_ending("lose")
        game.ending_timer = ENDING_ANIMATION_DURATION * 0.55
        game.draw()
        game.update(ENDING_ANIMATION_DURATION)
        assert game.state == "lose"
        game.draw()
        game.state = "playing"
        game._open_exit_confirm()
        game._exit_to_menu()
        assert game.state == "home"

        game.state = "home"
        game.draw()
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
