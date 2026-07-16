from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "docs" / "screenshots"
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import save_data
from entities import Enemy, Unit
from game import CharcoalPickup, Game, OilPickup


def save_frame(game: Game, name: str) -> None:
    game.draw()
    pygame.image.save(game.screen, OUTPUT_DIR / name)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rou_rou_screenshots_") as temp_dir:
        save_data.SAVE_PATH = Path(temp_dir) / "save_data.json"
        game = Game()
        game.accounts = {"夜市摊主": game._new_account()}
        game.active_account = "夜市摊主"
        game._load_active_account()
        game.unlocked_level = 15
        game.completed_levels = set(range(1, 12))
        game.selected_level = 12
        game.coins = 188
        game.state = "menu"
        save_frame(game, "level-select.png")

        game.active_loadout = ["charcoal", "wall", "skewer", "beef", "wing", "meatball"]
        game._apply_level_tuning(12)
        game.reset_game()
        game.state = "playing"
        game.game_time = 20.0
        game.charcoal = 375
        game.oil_inventory = 2
        game.order_unit = "wing"
        game.order_deadline = 26.0
        game.order_next_time = 34.0
        game.units = [
            Unit("charcoal", 0, 0),
            Unit("skewer", 0, 2),
            Unit("beef", 1, 1),
            Unit("wall", 1, 5),
            Unit("wing", 2, 2),
            Unit("skewer", 3, 1),
            Unit("meatball", 3, 5),
            Unit("charcoal", 4, 0),
            Unit("beef", 4, 2),
        ]
        game.enemies = [
            Enemy("baby", 0),
            Enemy("courier", 1),
            Enemy("pot", 2),
            Enemy("drunk", 3),
            Enemy("butcher", 4),
        ]
        for index, enemy in enumerate(game.enemies):
            enemy.x -= 80 + index * 28
            enemy.rect.centerx = int(enemy.x)
        game.pickups = [CharcoalPickup(150, 325, 25, 7.0)]
        game.oil_pickups = [OilPickup(1170, 305)]
        save_frame(game, "order-battle.png")

        game.selected_level = 11
        game._apply_level_tuning(11)
        game.reset_game()
        game.state = "playing"
        game.game_time = 40.0
        game.charcoal = 620
        game._update_reverse_director()
        game.reverse_hot_lane = 2
        game.reverse_hot_until = 49.0
        for enemy_type, row in [("pot", 0), ("baby", 1), ("butcher", 2), ("courier", 3), ("normal", 4)]:
            game.spawn_reverse_enemy(enemy_type, row)
        for index, enemy in enumerate(game.enemies):
            enemy.x -= 85 + index * 42
            enemy.rect.centerx = int(enemy.x)
        game.floaters = []
        game.charcoal = 360
        game.selected_enemy = "drunk"
        game.message = "第 3 路今日热卖：吃掉肉肉返还 ×1.5"
        game.message_timer = 3.0
        save_frame(game, "reverse-raid.png")

        game.state = "shop"
        game.coins = 188
        game.owned_units = ["charcoal", "wall", "skewer", "meatball", "beef", "wing"]
        game.login_message = ""
        save_frame(game, "shop.png")

        pygame.quit()

    print(f"Screenshots written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
