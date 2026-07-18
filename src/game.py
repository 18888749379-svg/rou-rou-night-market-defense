from __future__ import annotations

import asyncio
import math
import random
from dataclasses import dataclass
from typing import Callable

import pygame

from assets import Audio, get_font, load_image
from entities import (
    Enemy,
    Explosion,
    FloatingText,
    ImpactBurst,
    LaneBurn,
    Projectile,
    ScallopRain,
    Unit,
    cell_center,
    x_to_col,
)
from save_data import clear_save, load_save, write_save
from settings import (
    AMBIENT_CHARCOAL_MAX_SECONDS,
    AMBIENT_CHARCOAL_MIN_SECONDS,
    CELL_SIZE,
    CHARCOAL_PICKUP_TTL,
    CHARCOAL_PICKUP_VALUE,
    COLORS,
    DEFAULT_OWNED_UNITS,
    DEFENSE_LINE_X,
    DIFFICULTY_HARD,
    DIFFICULTY_NORMAL,
    ENDING_ANIMATION_DURATION,
    ENEMIES,
    ENEMY_ORDER,
    FPS,
    GRID_COLS,
    GRID_ROWS,
    GRID_X,
    GRID_Y,
    HARD_REWARD_MULTIPLIER,
    HEIGHT,
    LATE_GAME_TIER_START_LEVEL,
    LEVELS,
    LEVEL_COIN_REWARDS,
    MAX_CHARCOAL,
    MAX_LOADOUT_SIZE,
    MAX_OIL_CAPACITY,
    OIL_BOTTLE_PRICE,
    OIL_CAPACITY_UPGRADE_COSTS,
    PLACEABLE_COLS,
    REVERSE_CORE_HP,
    REVERSE_DEFENDER_POOL,
    REVERSE_DEFENDERS_PER_LANE,
    REVERSE_HARD_DEFENDERS_PER_LANE,
    REVERSE_STARTING_CHARCOAL,
    REVERSE_ZOMBIE_COSTS,
    REVERSE_ZOMBIE_ORDER,
    STARTING_CHARCOAL,
    TOP_BAR_HEIGHT,
    UNITS,
    UNIT_ORDER,
    UNIT_COIN_PRICES,
    UNIT_PLACEMENT_COOLDOWNS,
    UNIT_UPGRADE_PATHS,
    UPGRADE_COSTS,
    WIDTH,
)


def _as_dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _is_finite_number(value: object) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except OverflowError:
        return False


@dataclass
class Card:
    unit_type: str
    rect: pygame.Rect


@dataclass
class EnemyCard:
    enemy_type: str
    rect: pygame.Rect


@dataclass
class TuningControl:
    label: str
    value: str
    minus_rect: pygame.Rect
    plus_rect: pygame.Rect
    change: Callable[[int], None]


@dataclass
class CharcoalPickup:
    x: float
    y: float
    value: int
    ttl: float = CHARCOAL_PICKUP_TTL

    def __post_init__(self) -> None:
        self.initial_ttl = max(0.01, self.ttl)

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x) - 22, int(self.y) - 22, 44, 44)

    def update(self, dt: float) -> None:
        self.ttl -= dt
        self.y += 6 * dt

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        ratio = max(0.0, min(1.0, self.ttl / self.initial_ttl))
        alpha = int(110 + 145 * ratio)
        layer = pygame.Surface((56, 56), pygame.SRCALPHA)
        pygame.draw.circle(layer, (255, 187, 70, alpha), (28, 28), 21)
        pygame.draw.circle(layer, (84, 50, 34, alpha), (28, 28), 12)
        pygame.draw.circle(layer, (255, 228, 122, alpha), (20, 19), 5)
        pygame.draw.circle(layer, (38, 31, 27, alpha), (31, 31), 10, 2)
        text = font.render(str(self.value), True, (255, 246, 190))
        layer.blit(text, text.get_rect(center=(28, 49)))
        surface.blit(layer, (self.x - 28, self.y - 28))


@dataclass
class CoinPickup:
    x: float
    y: float
    value: int = 1
    ttl: float = 10.0

    def __post_init__(self) -> None:
        self.image = load_image("coin.png", (48, 48))

    @property
    def rect(self) -> pygame.Rect:
        return self.image.get_rect(center=(int(self.x), int(self.y)))

    def update(self, dt: float) -> None:
        self.ttl -= dt
        self.y += 4 * dt

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        alpha = max(70, min(255, int(self.ttl * 70)))
        image = self.image.copy()
        image.set_alpha(alpha)
        surface.blit(image, image.get_rect(center=(int(self.x), int(self.y))))
        label = font.render(f"+{self.value}", True, (255, 235, 132))
        surface.blit(label, label.get_rect(center=(int(self.x), int(self.y + 31))))


@dataclass
class OilPickup:
    x: float
    y: float
    ttl: float = 12.0

    def __post_init__(self) -> None:
        self.image = load_image("oil_bottle.png", (54, 54))

    @property
    def rect(self) -> pygame.Rect:
        return self.image.get_rect(center=(int(self.x), int(self.y)))

    def update(self, dt: float) -> None:
        self.ttl -= dt
        self.y += 4 * dt

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        pulse = 1.0 + 0.06 * ((pygame.time.get_ticks() // 180) % 2)
        size = max(48, int(54 * pulse))
        image = pygame.transform.smoothscale(self.image, (size, size))
        surface.blit(image, image.get_rect(center=(int(self.x), int(self.y))))
        label = font.render("点击收取", True, (255, 224, 128))
        surface.blit(label, label.get_rect(center=(int(self.x), int(self.y + 38))))


class Game:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("肉肉守摊大战僵尸")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.audio = Audio()
        self.factory_audio_settings = {
            "music_enabled": self.audio.music_enabled,
            "sfx_enabled": self.audio.sfx_enabled,
            "music_volume": self.audio.music_volume,
            "sfx_volume": self.audio.sfx_volume,
            "effect_volumes": dict(self.audio.effect_volumes),
        }
        self.font_sm = get_font(20)
        self.font_xs = get_font(16)
        self.font_md = get_font(28, True)
        self.font_lg = get_font(48, True)
        self.font_title = get_font(68, True)
        self.running = True
        self.state = "home"
        self.selected_unit: str | None = None
        self.remove_mode = False
        self.message = ""
        self.message_timer = 0.0
        self.flash_cell: tuple[int, int] | None = None
        self.flash_timer = 0.0
        self.random = random.Random()
        self.factory_unit_stats = {
            key: {attr: getattr(config, attr) for attr in ("cost", "hp", "damage", "cooldown")}
            for key, config in UNITS.items()
        }
        self.factory_enemy_stats = {
            key: {attr: getattr(config, attr) for attr in ("hp", "speed", "damage", "cooldown", "reward")}
            for key, config in ENEMIES.items()
        }
        self.initial_charcoal = STARTING_CHARCOAL
        self.grill_interval = (AMBIENT_CHARCOAL_MIN_SECONDS + AMBIENT_CHARCOAL_MAX_SECONDS) / 2
        self.grill_pickup_value = CHARCOAL_PICKUP_VALUE
        self.charcoal_unit_value = CHARCOAL_PICKUP_VALUE
        self.pickup_ttl = CHARCOAL_PICKUP_TTL
        self.reverse_starting_charcoal = REVERSE_STARTING_CHARCOAL
        self.reverse_core_max_hp = REVERSE_CORE_HP
        self.reverse_reward_percent = 50
        self.factory_resource_settings = {
            "initial_charcoal": self.initial_charcoal,
            "grill_interval": self.grill_interval,
            "grill_pickup_value": self.grill_pickup_value,
            "charcoal_unit_value": self.charcoal_unit_value,
            "pickup_ttl": self.pickup_ttl,
            "reverse_starting_charcoal": self.reverse_starting_charcoal,
            "reverse_reward_percent": self.reverse_reward_percent,
        }
        self.level_tuning: dict[str, dict] = {}
        self.unlocked_level = 1
        self.completed_levels: set[int] = set()
        self.hard_completed_levels: set[int] = set()
        self.selected_level = 1
        self.selected_difficulty = DIFFICULTY_NORMAL
        self.accounts: dict[str, dict] = {}
        self.active_account: str | None = None
        self.coins = 0
        self.owned_units = list(DEFAULT_OWNED_UNITS)
        self.unit_upgrades = {key: 0 for key in UNIT_ORDER}
        self.oil_capacity_level = 0
        self.saved_loadout = list(DEFAULT_OWNED_UNITS)
        self.active_loadout = list(DEFAULT_OWNED_UNITS)
        self.login_text = ""
        self.login_composition = ""
        self.login_replace_existing = False
        self.login_message = ""
        self.login_required = False
        self.post_login_state = "home"
        self.login_source_account: str | None = None
        self.login_account_page = 0
        self.info_return_state = "home"
        self.reset_return_state = "home"
        self.loadout_selection: list[str] = []
        self.reset_confirm_stage = 0
        self.level_reward = 0
        self.show_tuning = False
        self.tuning_tab = "resources"
        self.tuning_controls: list[TuningControl] = []
        self._apply_saved_data(load_save())
        self.background = load_image("alley_background.png", (WIDTH, HEIGHT))
        self.grill_image = load_image("grill_resource.png", (190, 430))
        self.tray_image = load_image("tray_tile.png", (CELL_SIZE - 8, CELL_SIZE - 8))
        self.tongs_image = load_image("tongs.png", (66, 58))
        self.oil_image = load_image("oil_bottle.png", (64, 64))
        self.roulette_image = load_image("roulette_wheel.png", (200, 200))
        self.ending_images = {
            "win": self._load_cover_image("ending_victory.png"),
            "lose": self._load_cover_image("ending_defeat.png"),
        }
        self.coin_image = load_image("coin.png", (48, 48))
        self.card_images = {key: load_image(config.image, (56, 56)) for key, config in UNITS.items()}
        self.enemy_card_images = {key: load_image(config.image, (58, 68)) for key, config in ENEMIES.items()}
        self.cards = self._make_cards()
        self.reverse_cards = self._make_reverse_cards()
        self.reset_game()
        self._save_all()
        self.audio.play_music("menu")
        self._open_login(
            "home",
            None,
            "用户名仅支持英文字母和数字；同名读取存档，新名字从零开始",
            required=True,
        )

    @staticmethod
    def _load_cover_image(name: str) -> pygame.Surface:
        image = load_image(name)
        scale = max(WIDTH / image.get_width(), HEIGHT / image.get_height())
        size = (math.ceil(image.get_width() * scale), math.ceil(image.get_height() * scale))
        scaled = pygame.transform.smoothscale(image, size)
        crop = pygame.Rect((size[0] - WIDTH) // 2, (size[1] - HEIGHT) // 2, WIDTH, HEIGHT)
        return scaled.subsurface(crop).copy()

    def _make_cards(self) -> list[Card]:
        if hasattr(self, "level_config") and self.level_config.special in {"roulette", "reverse"}:
            return []
        cards: list[Card] = []
        x = 330
        available = [key for key in self.active_loadout if key in UNITS]
        other_units = [key for key in available if key != "charcoal"]
        shop_order = ["charcoal"] + sorted(other_units, key=lambda key: (UNITS[key].cost, UNIT_ORDER.index(key)))
        shop_order = [key for key in shop_order if key in available]
        for key in shop_order:
            cards.append(Card(key, pygame.Rect(x, 14, 122, 76)))
            x += 130
        return cards

    def _make_reverse_cards(self) -> list[EnemyCard]:
        cards: list[EnemyCard] = []
        x = 222
        for key in REVERSE_ZOMBIE_ORDER:
            cards.append(EnemyCard(key, pygame.Rect(x, 14, 102, 76)))
            x += 108
        return cards

    def _wave_size(self, enemy_types: list[str]) -> int:
        if self.selected_difficulty != DIFFICULTY_HARD or not enemy_types:
            return len(enemy_types)
        return len(enemy_types) + max(1, len(enemy_types) // 4)

    def _enemy_tier_for_spawn(self, spawn_index: int) -> int:
        late_game = self.selected_level >= LATE_GAME_TIER_START_LEVEL
        if self.selected_difficulty == DIFFICULTY_HARD:
            return 2 if late_game or spawn_index % 2 else 1
        if late_game:
            return 2 if spawn_index % 3 == 2 else 1
        return 1

    def _setup_reverse_defense(self) -> None:
        count = (
            REVERSE_HARD_DEFENDERS_PER_LANE
            if self.selected_difficulty == DIFFICULTY_HARD
            else REVERSE_DEFENDERS_PER_LANE
        )
        for row in range(GRID_ROWS):
            columns = sorted(self.random.sample(range(1, PLACEABLE_COLS - 1), count))
            for index, col in enumerate(columns):
                if index == len(columns) - 1:
                    unit_type = "wall"
                elif index == 0 and self.random.random() < 0.45:
                    unit_type = "charcoal"
                else:
                    choices = [key for key in REVERSE_DEFENDER_POOL if key != "wall"]
                    unit_type = self.random.choice(choices)
                unit = Unit(unit_type, row, col)
                if self.selected_difficulty == DIFFICULTY_HARD:
                    unit.max_hp = int(round(unit.max_hp * 1.35))
                    unit.hp = unit.max_hp
                    unit.damage_multiplier *= 1.25
                self.units.append(unit)

    def reset_game(self) -> None:
        self.units: list[Unit] = []
        self.enemies: list[Enemy] = []
        self.projectiles: list[Projectile] = []
        self.effects: list[Explosion] = []
        self.special_effects: list[ScallopRain | LaneBurn] = []
        self.floaters: list[FloatingText] = []
        self.pickups: list[CharcoalPickup] = []
        self.coin_pickups: list[CoinPickup] = []
        self.oil_pickups: list[OilPickup] = []
        self.charcoal = self.initial_charcoal
        self.game_time = 0.0
        self.next_ambient_pickup = self._next_ambient_delay()
        self.wave_index = 0
        self.spawned_enemies = 0
        self.defeated_enemies = 0
        self.level_config = LEVELS[self.selected_level - 1]
        self.total_enemies = sum(self._wave_size(enemy_types) for _, enemy_types in self.level_config.waves)
        if self.level_config.special == "reverse":
            self.charcoal = self.reverse_starting_charcoal
            self.total_enemies = 0
        oil_count = min(self.level_config.oil_drops, self.total_enemies)
        self.oil_drop_kills = set(self.random.sample(range(1, self.total_enemies + 1), oil_count))
        self.oil_inventory = 0
        self.ultimate_mode = False
        self.roulette_unit: str | None = None
        self.roulette_timer = 0.8
        self.conveyor_next_shift = self.level_config.conveyor_interval or 12.0
        self.conveyor_flash_timer = 0.0
        self.order_unit: str | None = None
        self.last_order_unit: str | None = None
        self.order_next_time = 12.0
        self.order_deadline = 0.0
        self.orders_completed = 0
        self.orders_failed = 0
        self.selected_enemy: str | None = None
        self.dragging_enemy: str | None = None
        self.drag_position = (0, 0)
        self.reverse_core_hp = self.reverse_core_max_hp
        self.reverse_eaten_units = 0
        self.reverse_zombies_lost = 0
        self.reverse_spawned_count = 0
        self.shake_timer = 0.0
        self.shake_intensity = 0
        self.card_cooldowns = {key: 0.0 for key in UNITS}
        self.exit_confirm = False
        self.exit_was_paused = False
        self.ending_result: str | None = None
        self.ending_timer = 0.0
        self.level_reward = 0
        self.final_wave_started = False
        self.final_wave_timer = 0.0
        self.paused = False
        self.show_info = False
        self.show_tuning = False
        self.selected_unit = None
        self.remove_mode = False
        if self.is_reverse_mode:
            self._setup_reverse_defense()
        if self.level_config.special == "conveyor":
            self.message = "回转烤盘每 12 秒右移一格，最右侧会回到最左侧"
            self.message_timer = 3.2
        elif self.level_config.special == "orders":
            self.message = "限时订单：按要求放置肉肉赚炭火，超时会提前出怪"
            self.message_timer = 3.2
        elif self.level_config.special == "reverse":
            self.message = "固定防线已就位：吃掉肉肉赚炭火，三次突破即可获胜"
            self.message_timer = 4.0
        else:
            self.message = "点击油瓶收取；使用油瓶后点击肉肉释放大招"
            self.message_timer = 2.2
        self.flash_cell = None
        self.flash_timer = 0.0
        self.cards = self._make_cards()
        self.reverse_cards = self._make_reverse_cards()

    def _apply_saved_data(self, data: dict) -> None:
        tuning = _as_dict(data.get("global_tuning", data.get("tuning", {})))
        saved_levels = _as_dict(data.get("level_tuning", {}))
        if saved_levels:
            self.level_tuning = {
                str(level.number): self._build_level_profile(saved_levels.get(str(level.number), {}))
                for level in LEVELS
            }
        else:
            migrated = self._build_level_profile(tuning)
            self.level_tuning = {
                str(level.number): self._copy_level_profile(migrated) for level in LEVELS
            }
        self._apply_level_tuning(1)
        audio = _as_dict(tuning.get("audio", {}))
        if isinstance(audio.get("music_enabled"), bool):
            self.audio.music_enabled = audio["music_enabled"]
        if isinstance(audio.get("sfx_enabled"), bool):
            self.audio.sfx_enabled = audio["sfx_enabled"]
        if _is_finite_number(audio.get("music_volume")):
            self.audio.set_music_volume(audio["music_volume"])
        if _is_finite_number(audio.get("sfx_volume")):
            self.audio.set_sfx_volume(audio["sfx_volume"])
        for key, value in _as_dict(audio.get("effect_volumes", {})).items():
            if key in self.audio.effect_volumes and _is_finite_number(value):
                self.audio.set_effect_volume(key, value)

        if data.get("version") == 1 or ("progress" in data and "accounts" not in data):
            progress = data.get("progress", {})
            self.accounts = {"本地玩家": self._new_account(progress)}
            self.active_account = "本地玩家"
        else:
            accounts = _as_dict(data.get("accounts", {}))
            self.accounts = {
                name: account
                for name, account in accounts.items()
                if isinstance(name, str) and isinstance(account, dict)
            }
            active = data.get("active_account")
            self.active_account = active if isinstance(active, str) and active in self.accounts else None
        self._load_active_account()

    def _build_level_profile(self, values: dict) -> dict:
        values = _as_dict(values)
        resources = dict(self.factory_resource_settings)
        for attr, value in _as_dict(values.get("resources", {})).items():
            if attr in resources and _is_finite_number(value):
                resources[attr] = value
        units = {key: dict(stats) for key, stats in self.factory_unit_stats.items()}
        for key, saved in _as_dict(values.get("units", {})).items():
            if key not in units or not isinstance(saved, dict):
                continue
            for attr, value in saved.items():
                if attr in units[key] and _is_finite_number(value):
                    units[key][attr] = value
        enemies = {key: dict(stats) for key, stats in self.factory_enemy_stats.items()}
        for key, saved in _as_dict(values.get("enemies", {})).items():
            if key not in enemies or not isinstance(saved, dict):
                continue
            for attr, value in saved.items():
                if attr in enemies[key] and _is_finite_number(value):
                    enemies[key][attr] = value
        return {"resources": resources, "units": units, "enemies": enemies}

    @staticmethod
    def _copy_level_profile(profile: dict) -> dict:
        return {
            "resources": dict(profile["resources"]),
            "units": {key: dict(stats) for key, stats in profile["units"].items()},
            "enemies": {key: dict(stats) for key, stats in profile["enemies"].items()},
        }

    def _capture_level_tuning(self, level_number: int | None = None) -> None:
        level_number = level_number or self.selected_level
        self.level_tuning[str(level_number)] = {
            "resources": {
                attr: getattr(self, attr) for attr in self.factory_resource_settings
            },
            "units": {key: dict(stats) for key, stats in self.base_unit_stats.items()},
            "enemies": {
                key: {attr: getattr(config, attr) for attr in self.factory_enemy_stats[key]}
                for key, config in ENEMIES.items()
            },
        }

    def _apply_level_tuning(self, level_number: int) -> None:
        profile = self.level_tuning.get(str(level_number))
        if not profile:
            profile = self._build_level_profile({})
            self.level_tuning[str(level_number)] = profile
        for attr, value in profile["resources"].items():
            setattr(self, attr, value)
        self.base_unit_stats = {key: dict(stats) for key, stats in profile["units"].items()}
        for key, stats in profile["enemies"].items():
            for attr, value in stats.items():
                setattr(ENEMIES[key], attr, value)
        self._apply_account_upgrades()

    def _new_account(self, progress: dict | None = None) -> dict:
        progress = _as_dict(progress)
        completed_values = progress.get("completed_levels", [])
        if not isinstance(completed_values, list):
            completed_values = []
        completed = [
            value for value in completed_values
            if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= len(LEVELS)
        ]
        hard_values = progress.get("hard_completed_levels", [])
        if not isinstance(hard_values, list):
            hard_values = []
        hard_completed = [
            value for value in hard_values
            if isinstance(value, int) and not isinstance(value, bool) and value in completed
        ]
        unlocked = _safe_int(progress.get("unlocked_level", 1), 1)
        selected = _safe_int(progress.get("selected_level", unlocked), unlocked)
        difficulty = progress.get("selected_difficulty", DIFFICULTY_NORMAL)
        if difficulty not in {DIFFICULTY_NORMAL, DIFFICULTY_HARD}:
            difficulty = DIFFICULTY_NORMAL
        return {
            "coins": 0,
            "unlocked_level": max(1, min(len(LEVELS), unlocked)),
            "completed_levels": sorted(set(completed)),
            "hard_completed_levels": sorted(set(hard_completed)),
            "selected_level": max(1, min(len(LEVELS), selected)),
            "selected_difficulty": difficulty,
            "owned_units": list(DEFAULT_OWNED_UNITS),
            "unit_upgrades": {key: 0 for key in UNIT_ORDER},
            "oil_capacity_level": 0,
            "loadout": list(DEFAULT_OWNED_UNITS),
        }

    def _load_active_account(self) -> None:
        if not self.active_account or self.active_account not in self.accounts:
            self.coins = 0
            self.unlocked_level = 1
            self.completed_levels = set()
            self.hard_completed_levels = set()
            self.selected_level = 1
            self.selected_difficulty = DIFFICULTY_NORMAL
            self.owned_units = list(DEFAULT_OWNED_UNITS)
            self.unit_upgrades = {key: 0 for key in UNIT_ORDER}
            self.oil_capacity_level = 0
            self.saved_loadout = list(DEFAULT_OWNED_UNITS)
            self.active_loadout = list(DEFAULT_OWNED_UNITS)
            self._apply_level_tuning(self.selected_level)
            return
        account = self.accounts[self.active_account]
        self.coins = max(0, _safe_int(account.get("coins", 0)))
        completed = account.get("completed_levels", [])
        if not isinstance(completed, list):
            completed = []
        self.completed_levels = {
            int(level)
            for level in completed
            if isinstance(level, int) and not isinstance(level, bool) and 1 <= level <= len(LEVELS)
        }
        hard_completed = account.get("hard_completed_levels", [])
        if not isinstance(hard_completed, list):
            hard_completed = []
        self.hard_completed_levels = {
            int(level)
            for level in hard_completed
            if isinstance(level, int)
            and not isinstance(level, bool)
            and int(level) in self.completed_levels
        }
        derived_unlock = min(len(LEVELS), max(self.completed_levels, default=0) + 1)
        self.unlocked_level = max(1, min(len(LEVELS), _safe_int(account.get("unlocked_level", 1), 1)))
        self.unlocked_level = max(self.unlocked_level, derived_unlock)
        self.selected_level = max(
            1,
            min(self.unlocked_level, _safe_int(account.get("selected_level", self.unlocked_level), self.unlocked_level)),
        )
        saved_difficulty = account.get("selected_difficulty", DIFFICULTY_NORMAL)
        self.selected_difficulty = (
            DIFFICULTY_HARD
            if saved_difficulty == DIFFICULTY_HARD and self.selected_level in self.completed_levels
            else DIFFICULTY_NORMAL
        )
        owned = account.get("owned_units", DEFAULT_OWNED_UNITS)
        if not isinstance(owned, list):
            owned = DEFAULT_OWNED_UNITS
        self.owned_units = [key for key in UNIT_ORDER if key in owned]
        for key in DEFAULT_OWNED_UNITS:
            if key not in self.owned_units:
                self.owned_units.append(key)
        saved_upgrades = _as_dict(account.get("unit_upgrades", {}))
        self.unit_upgrades = {
            key: max(0, min(len(UPGRADE_COSTS), _safe_int(saved_upgrades.get(key, 0)))) for key in UNIT_ORDER
        }
        self.oil_capacity_level = max(
            0,
            min(len(OIL_CAPACITY_UPGRADE_COSTS), _safe_int(account.get("oil_capacity_level", 0))),
        )
        saved_loadout = account.get("loadout", DEFAULT_OWNED_UNITS)
        if not isinstance(saved_loadout, list):
            saved_loadout = DEFAULT_OWNED_UNITS
        self.saved_loadout = [key for key in saved_loadout if key in self.owned_units][:MAX_LOADOUT_SIZE]
        if not self.saved_loadout:
            self.saved_loadout = ["charcoal"]
        self.active_loadout = list(self.saved_loadout)
        self._apply_level_tuning(self.selected_level)

    def _apply_account_upgrades(self) -> None:
        for key, stats in self.base_unit_stats.items():
            config = UNITS[key]
            for attr, value in stats.items():
                setattr(config, attr, value)
            level = self.unit_upgrades.get(key, 0)
            for attr, multiplier, _ in UNIT_UPGRADE_PATHS[key][:level]:
                value = getattr(config, attr)
                if attr == "cooldown":
                    setattr(config, attr, round(max(0.1, value * multiplier), 2))
                elif attr == "cost":
                    setattr(config, attr, max(0, int(value * multiplier + 0.5)))
                else:
                    setattr(config, attr, max(1, int(round(value * multiplier))))

    def _sync_account(self) -> None:
        if not self.active_account:
            return
        self.accounts[self.active_account] = {
            "coins": self.coins,
            "unlocked_level": self.unlocked_level,
            "completed_levels": sorted(self.completed_levels),
            "hard_completed_levels": sorted(self.hard_completed_levels),
            "selected_level": self.selected_level,
            "selected_difficulty": self.selected_difficulty,
            "owned_units": list(self.owned_units),
            "unit_upgrades": dict(self.unit_upgrades),
            "oil_capacity_level": self.oil_capacity_level,
            "loadout": list(self.saved_loadout),
        }

    @property
    def oil_capacity(self) -> int:
        return min(MAX_OIL_CAPACITY, 3 + self.oil_capacity_level)

    @property
    def is_reverse_mode(self) -> bool:
        return hasattr(self, "level_config") and self.level_config.special == "reverse"

    def _save_all(self) -> None:
        self._capture_level_tuning()
        self._sync_account()
        write_save(
            {
                "version": 5,
                "active_account": self.active_account,
                "accounts": self.accounts,
                "level_tuning": self.level_tuning,
                "global_tuning": {
                    "audio": {
                        "music_enabled": self.audio.music_enabled,
                        "sfx_enabled": self.audio.sfx_enabled,
                        "music_volume": self.audio.music_volume,
                        "sfx_volume": self.audio.sfx_volume,
                        "effect_volumes": dict(self.audio.effect_volumes),
                    },
                },
            }
        )

    def _complete_current_level(self) -> None:
        completed_level = self.selected_level
        if self.selected_difficulty == DIFFICULTY_HARD:
            self.hard_completed_levels.add(self.selected_level)
            self.level_reward = int(round(LEVEL_COIN_REWARDS[self.selected_level - 1] * HARD_REWARD_MULTIPLIER))
        else:
            self.completed_levels.add(self.selected_level)
            self.unlocked_level = min(len(LEVELS), max(self.unlocked_level, self.selected_level + 1))
            self.level_reward = LEVEL_COIN_REWARDS[self.selected_level - 1]
        self.coins += self.level_reward
        self.selected_level = completed_level
        self._save_all()

    def run(self) -> None:
        while self.running:
            self._run_frame()
        pygame.quit()

    async def run_async(self) -> None:
        while self.running:
            self._run_frame()
            await asyncio.sleep(0)
        pygame.quit()

    def _run_frame(self) -> None:
        dt = self.clock.tick(FPS) / 1000.0
        self.handle_events()
        self.update(dt)
        self.draw()

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.TEXTINPUT and self.state == "login":
                if self.login_replace_existing:
                    self.login_text = ""
                    self.login_replace_existing = False
                room = 12 - len(self.login_text)
                if room > 0:
                    accepted = "".join(char for char in event.text if char.isascii() and char.isalnum())
                    self.login_text += accepted[:room]
                    if accepted != event.text:
                        self.login_message = "用户名只能使用英文字母或数字"
                    elif accepted:
                        self.login_message = ""
                self.login_composition = ""
            elif event.type == pygame.TEXTEDITING and self.state == "login":
                self.login_composition = ""
                if event.text:
                    self.login_message = "请切换到英文输入法，只能输入字母或数字"
            elif event.type == pygame.KEYDOWN:
                self._handle_key(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.state == "playing" and self.is_reverse_mode and self._begin_reverse_drag(event.pos):
                    continue
                self._handle_click(event.pos)
            elif event.type == pygame.MOUSEMOTION and self.dragging_enemy is not None:
                self.drag_position = event.pos
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.dragging_enemy is not None:
                self._finish_reverse_drag(event.pos)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3 and self.state == "playing":
                if self._cancel_action_modes():
                    self.message = "已取消当前操作"
                    self.message_timer = 1.0
                    self.audio.play("click")

    def _handle_key(self, key: int) -> None:
        if self.state == "ending":
            if key in {pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE}:
                self._finish_ending()
            return
        if self.state == "login":
            if key == pygame.K_ESCAPE:
                self._close_login()
            elif key == pygame.K_RETURN:
                self._login_or_create()
            elif key == pygame.K_a and pygame.key.get_mods() & pygame.KMOD_CTRL:
                self.login_text = ""
                self.login_composition = ""
                self.login_replace_existing = False
            elif key == pygame.K_BACKSPACE:
                if self.login_replace_existing:
                    self.login_text = ""
                    self.login_replace_existing = False
                else:
                    self.login_text = self.login_text[:-1]
            return
        if self.state in {"loadout", "shop", "skills"}:
            if key == pygame.K_ESCAPE:
                self.state = "menu"
            return
        if self.state == "reset_confirm":
            if key == pygame.K_ESCAPE:
                self.state = self.reset_return_state
                self.reset_confirm_stage = 0
            return
        if self.state == "tuning":
            if key in {pygame.K_ESCAPE, pygame.K_t}:
                self.state = "menu"
                self.show_tuning = False
            return
        if self.state == "menu_info":
            if key in {pygame.K_ESCAPE, pygame.K_i}:
                self.state = self.info_return_state
                self.show_info = False
            return
        if self.state == "playing" and self.exit_confirm:
            if key == pygame.K_ESCAPE:
                self._close_exit_confirm()
            return
        if self.state == "playing" and self.show_info:
            if key in {pygame.K_ESCAPE, pygame.K_i}:
                self.show_info = False
            return
        if self.state == "playing" and self.show_tuning:
            if key in {pygame.K_ESCAPE, pygame.K_t}:
                self.show_tuning = False
            return
        if key == pygame.K_ESCAPE:
            if self.state == "playing":
                if self._cancel_action_modes():
                    self.message = "已取消当前操作"
                    self.message_timer = 1.0
                else:
                    self._open_exit_confirm()
                return
            if self.state in {"win", "lose"}:
                self.state = "menu"
                self.audio.play_music("menu")
                return
            if self.state == "menu":
                self.state = "home"
                return
            if self.state == "home":
                self.running = False
                return
            else:
                self.state = "menu"
                return
        if self.state == "playing":
            number_keys = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6]
            if key in number_keys:
                index = number_keys.index(key)
                if self.is_reverse_mode and index < len(self.reverse_cards) and not self.paused:
                    self._select_enemy(self.reverse_cards[index].enemy_type)
                elif index < len(self.cards) and not self.paused:
                    self._select_unit(self.cards[index].unit_type)
            elif key == pygame.K_p:
                self.paused = not self.paused
                if self.paused:
                    self._cancel_action_modes()
            elif key == pygame.K_r:
                self.start_game()
            elif key == pygame.K_i:
                self.show_info = not self.show_info
                if self.show_info:
                    self._cancel_action_modes()
            elif key == pygame.K_t:
                self.show_tuning = not self.show_tuning
                if self.show_tuning:
                    self._cancel_action_modes()
        elif self.state == "home" and key in {pygame.K_RETURN, pygame.K_SPACE}:
            self.state = "menu"
        elif self.state == "menu" and key in {pygame.K_RETURN, pygame.K_SPACE}:
            self._open_loadout()
        elif self.state == "menu" and key == pygame.K_t:
            self.show_tuning = True
            self.state = "tuning"

    def _handle_tuning_click(self, pos: tuple[int, int], return_to_menu: bool) -> None:
        if self._button_rect("close_tuning").collidepoint(pos):
            self.show_tuning = False
            if return_to_menu:
                self.state = "menu"
            self.audio.play("click")
            return
        tabs = {
            "resources": self._tuning_tab_rect(0),
            "units": self._tuning_tab_rect(1),
            "enemies": self._tuning_tab_rect(2),
            "audio": self._tuning_tab_rect(3),
        }
        for tab, rect in tabs.items():
            if rect.collidepoint(pos):
                self.tuning_tab = tab
                self.audio.play("click")
                return
        for control in self.tuning_controls:
            if control.minus_rect.collidepoint(pos):
                control.change(-1)
                self.audio.play("click")
                return
            if control.plus_rect.collidepoint(pos):
                control.change(1)
                self.audio.play("click")
                return

    def _cancel_action_modes(self) -> bool:
        had_active = (
            self.selected_unit is not None
            or self.selected_enemy is not None
            or self.dragging_enemy is not None
            or self.remove_mode
            or self.ultimate_mode
        )
        self.selected_unit = None
        self.selected_enemy = None
        self.dragging_enemy = None
        self.remove_mode = False
        self.ultimate_mode = False
        return had_active

    def _select_unit(self, unit_type: str) -> None:
        remaining = self.card_cooldowns.get(unit_type, 0.0)
        if self.level_config.special != "roulette" and remaining > 0:
            self.selected_unit = None
            self.message = f"{UNITS[unit_type].name}还需冷却 {remaining:.1f} 秒"
            self.message_timer = 1.4
            self.audio.play("bad")
            return
        if self.selected_unit == unit_type and not self.remove_mode and not self.ultimate_mode:
            self.selected_unit = None
            return
        self.selected_unit = unit_type
        self.remove_mode = False
        self.ultimate_mode = False

    def _select_enemy(self, enemy_type: str) -> None:
        self.selected_enemy = None if self.selected_enemy == enemy_type else enemy_type
        self.selected_unit = None
        self.remove_mode = False
        self.ultimate_mode = False

    def _handle_click(self, pos: tuple[int, int]) -> None:
        if self.state == "ending":
            if self.ending_timer >= 0.65:
                self._finish_ending()
            return
        if self.state == "home":
            if self._button_rect("home_start").collidepoint(pos):
                self.state = "menu"
                self.audio.play("click")
                return
            if self._button_rect("home_info").collidepoint(pos):
                self.info_return_state = "home"
                self.show_info = True
                self.state = "menu_info"
                self.audio.play("click")
                return
            if self._button_rect("home_reset").collidepoint(pos):
                self.reset_confirm_stage = 1
                self.reset_return_state = "home"
                self.state = "reset_confirm"
                return
            if self._button_rect("account").collidepoint(pos):
                self._open_login("home", None, "选择本地账户，或输入新用户名创建账户")
                return
        if self.state == "menu":
            for index, level in enumerate(LEVELS):
                if self._level_rect(index).collidepoint(pos):
                    if level.number <= self.unlocked_level:
                        self._select_level(level.number)
                        self._save_all()
                        self.audio.play("click")
                    else:
                        self.audio.play("bad")
                    return
            if self._button_rect("difficulty_normal").collidepoint(pos):
                self._set_difficulty(DIFFICULTY_NORMAL)
                return
            if self._button_rect("difficulty_hard").collidepoint(pos):
                self._set_difficulty(DIFFICULTY_HARD)
                return
            if self._button_rect("start").collidepoint(pos):
                self._open_loadout()
                return
            if self._button_rect("account").collidepoint(pos):
                self._open_login("menu", None, "选择本地账户，或输入新用户名创建账户")
                return
            if self._button_rect("shop").collidepoint(pos):
                self._require_account("shop")
                return
            if self._button_rect("skills").collidepoint(pos):
                self._require_account("skills")
                return
            if self._button_rect("menu_tuning").collidepoint(pos):
                self.show_tuning = True
                self.state = "tuning"
                self.audio.play("click")
                return
            if self._button_rect("screen_back").collidepoint(pos):
                self.state = "home"
                self.audio.play("click")
                return
        if self.state == "login":
            account_names = self._visible_login_accounts()
            for index, name in enumerate(account_names):
                if self._login_account_rect(index).collidepoint(pos):
                    self._switch_account(name)
                    return
            if len(self.accounts) > 6:
                if self._button_rect("login_prev").collidepoint(pos):
                    self.login_account_page = max(0, self.login_account_page - 1)
                    return
                if self._button_rect("login_next").collidepoint(pos):
                    last_page = (len(self.accounts) - 1) // 6
                    self.login_account_page = min(last_page, self.login_account_page + 1)
                    return
            if self.active_account and self._button_rect("login_rename").collidepoint(pos):
                self.login_source_account = self.active_account
                self.login_text = self.active_account
                self.login_replace_existing = True
                self.login_message = "输入新的英文或数字用户名，确认后保留全部进度"
                return
            if self._button_rect("login_confirm").collidepoint(pos):
                self._login_or_create()
            elif self._button_rect("login_back").collidepoint(pos):
                self._close_login()
            return
        if self.state == "loadout":
            for index, key in enumerate(self.owned_units):
                if self._unit_library_rect(index).collidepoint(pos):
                    if key in self.loadout_selection:
                        self.loadout_selection.remove(key)
                    elif len(self.loadout_selection) < MAX_LOADOUT_SIZE:
                        self.loadout_selection.append(key)
                    else:
                        self.login_message = "最多选择 6 个肉肉"
                        self.audio.play("bad")
                    return
            if self._button_rect("loadout_start").collidepoint(pos):
                if not self.loadout_selection:
                    self.login_message = "请至少选择一个肉肉"
                    self.audio.play("bad")
                else:
                    self.saved_loadout = list(self.loadout_selection)
                    self.active_loadout = list(self.loadout_selection)
                    self.start_game()
                return
            if self._button_rect("screen_back").collidepoint(pos):
                self.state = "menu"
            return
        if self.state == "shop":
            for index, key in enumerate(UNIT_ORDER):
                if self._shop_buy_rect(index).collidepoint(pos) and key not in self.owned_units:
                    self._buy_unit(key)
                    return
            if self._button_rect("screen_back").collidepoint(pos):
                self.state = "menu"
            return
        if self.state == "skills":
            if self._oil_capacity_upgrade_rect().collidepoint(pos):
                self._upgrade_oil_capacity()
                return
            for index, key in enumerate(UNIT_ORDER):
                if self._skill_upgrade_rect(index).collidepoint(pos):
                    self._upgrade_unit(key)
                    return
            if self._button_rect("screen_back").collidepoint(pos):
                self.state = "menu"
            return
        if self.state == "reset_confirm":
            if self._button_rect("reset_confirm").collidepoint(pos):
                if self.reset_confirm_stage == 1:
                    self.reset_confirm_stage = 2
                else:
                    self._reset_all_data()
                return
            if self._button_rect("reset_cancel").collidepoint(pos):
                self.reset_confirm_stage = 0
                self.state = self.reset_return_state
            return
        if self.state == "tuning":
            self._handle_tuning_click(pos, return_to_menu=True)
            return
        if self.state == "menu_info":
            if self._button_rect("close_info").collidepoint(pos):
                self.state = self.info_return_state
                self.show_info = False
                self.audio.play("click")
                return
        if self.state in {"win", "lose"}:
            next_target = self._next_result_target() if self.state == "win" else None
            if next_target and self._button_rect("next_level").collidepoint(pos):
                next_level, next_difficulty = next_target
                self._select_level(next_level)
                self._set_difficulty(next_difficulty)
                self._open_loadout()
                return
            if self._button_rect("restart").collidepoint(pos):
                self.start_game()
                return
            if self._button_rect("menu").collidepoint(pos):
                self.state = "menu"
                self._save_all()
                self.audio.play_music("menu")
                return
        if self.state != "playing":
            return
        if self.exit_confirm:
            if self._button_rect("exit_confirm_yes").collidepoint(pos):
                self._exit_to_menu()
            elif self._button_rect("exit_confirm_no").collidepoint(pos):
                self._close_exit_confirm()
            return
        if self.show_info:
            if self._button_rect("close_info").collidepoint(pos):
                self.show_info = False
                self.audio.play("click")
            return
        if self.show_tuning:
            self._handle_tuning_click(pos, return_to_menu=False)
            return
        if self._button_rect("pause").collidepoint(pos):
            self.paused = not self.paused
            if self.paused:
                self._cancel_action_modes()
            self.audio.play("click")
            return
        if self._button_rect("restart_play").collidepoint(pos):
            self.start_game()
            return
        if self._button_rect("exit_play").collidepoint(pos):
            self._open_exit_confirm()
            return
        if self._button_rect("info").collidepoint(pos):
            self.show_info = True
            self._cancel_action_modes()
            self.audio.play("click")
            return
        if self._button_rect("tuning").collidepoint(pos):
            self.show_tuning = True
            self._cancel_action_modes()
            self.audio.play("click")
            return
        if self.paused:
            return
        if self.is_reverse_mode:
            self._handle_reverse_click(pos)
            return
        for pickup in list(self.pickups):
            if pickup.rect.collidepoint(pos):
                self.collect_pickup(pickup)
                return
        for pickup in list(self.coin_pickups):
            if pickup.rect.collidepoint(pos):
                self.collect_coin(pickup)
                return
        for pickup in list(self.oil_pickups):
            if pickup.rect.collidepoint(pos):
                self.collect_oil(pickup)
                return
        if self._oil_inventory_rect().collidepoint(pos):
            if self.oil_inventory > 0:
                enable = not self.ultimate_mode
                self._cancel_action_modes()
                self.ultimate_mode = enable
                self.audio.play("click")
            else:
                self.message = "当前没有油瓶"
                self.message_timer = 1.5
                self.audio.play("bad")
            return
        if self._oil_buy_rect().collidepoint(pos):
            self.buy_oil_bottle()
            return
        if self.level_config.special == "roulette" and self._roulette_rect().collidepoint(pos):
            if self.roulette_unit:
                self._select_unit(self.roulette_unit)
                self.roulette_unit = None
                self.roulette_timer = self.level_config.roulette_interval
                self.audio.play("click")
            return
        if self._tongs_rect().collidepoint(pos):
            enable = not self.remove_mode
            self._cancel_action_modes()
            self.remove_mode = enable
            self.audio.play("click")
            return
        for card in self.cards:
            if card.rect.collidepoint(pos):
                self._select_unit(card.unit_type)
                self.audio.play("click")
                return
        cell = self.pos_to_cell(pos)
        if cell:
            if self.ultimate_mode:
                unit = self.unit_at(*cell)
                if unit:
                    self.activate_ultimate(unit)
                else:
                    self.reject(*cell, "请点击一个已放置的肉肉释放大招")
            elif self.remove_mode:
                self.try_remove(*cell)
            else:
                self.try_place(*cell)

    def start_game(self, level_number: int | None = None) -> None:
        if level_number is not None:
            if not 1 <= level_number <= self.unlocked_level:
                return
            self._select_level(level_number)
        if self.selected_difficulty == DIFFICULTY_HARD and self.selected_level not in self.completed_levels:
            self.selected_difficulty = DIFFICULTY_NORMAL
        self._save_all()
        self.reset_game()
        self.state = "playing"
        self.audio.play_music("game")
        self.audio.play("click")

    def _open_exit_confirm(self) -> None:
        if self.state != "playing" or self.exit_confirm:
            return
        self.exit_was_paused = self.paused
        self.exit_confirm = True
        self.paused = True
        self._cancel_action_modes()
        self.audio.play("click")

    def _close_exit_confirm(self) -> None:
        self.exit_confirm = False
        self.paused = self.exit_was_paused
        self.audio.play("click")

    def _exit_to_menu(self) -> None:
        self.exit_confirm = False
        self.paused = False
        self._save_all()
        self.state = "menu"
        self.audio.play_music("menu")
        self.audio.play("click")

    def _begin_ending(self, result: str) -> None:
        if self.state != "playing" or result not in {"win", "lose"}:
            return
        self.ending_result = result
        self.ending_timer = 0.0
        self.exit_confirm = False
        self.paused = False
        self._cancel_action_modes()
        if result == "win":
            self._complete_current_level()
        else:
            self.level_reward = 0
        self.state = "ending"
        self.audio.play(result)

    def _finish_ending(self) -> None:
        if self.state == "ending" and self.ending_result in {"win", "lose"}:
            self.state = self.ending_result

    def _select_level(self, level_number: int) -> None:
        level_number = max(1, min(len(LEVELS), level_number))
        if level_number == self.selected_level:
            return
        self._capture_level_tuning(self.selected_level)
        self.selected_level = level_number
        if self.selected_difficulty == DIFFICULTY_HARD and level_number not in self.completed_levels:
            self.selected_difficulty = DIFFICULTY_NORMAL
        self._apply_level_tuning(level_number)
        self.cards = self._make_cards()

    def _set_difficulty(self, difficulty: str) -> None:
        if difficulty == DIFFICULTY_HARD and self.selected_level not in self.completed_levels:
            self.login_message = "请先通关本关普通模式"
            self.audio.play("bad")
            return
        self.selected_difficulty = DIFFICULTY_HARD if difficulty == DIFFICULTY_HARD else DIFFICULTY_NORMAL
        self.login_message = ""
        self._save_all()
        self.audio.play("click")

    def _next_result_target(self) -> tuple[int, str] | None:
        if self.selected_level >= len(LEVELS):
            return None
        next_level = self.selected_level + 1
        if self.selected_difficulty == DIFFICULTY_HARD:
            if next_level in self.completed_levels:
                return next_level, DIFFICULTY_HARD
            return None
        if next_level <= self.unlocked_level:
            return next_level, DIFFICULTY_NORMAL
        return None

    def _require_account(self, target_state: str) -> None:
        if self.active_account:
            self.state = target_state
            return
        self._open_login(target_state, None, "请先输入本地玩家名")

    def _open_login(
        self,
        target_state: str,
        source_account: str | None,
        message: str = "",
        required: bool = False,
    ) -> None:
        self.login_text = source_account or ""
        self.login_composition = ""
        self.login_replace_existing = source_account is not None
        self.login_message = message
        self.post_login_state = target_state
        self.login_source_account = source_account
        self.login_required = required
        account_names = sorted(self.accounts, key=str.casefold)
        self.login_account_page = account_names.index(self.active_account) // 6 if self.active_account in account_names else 0
        self.state = "login"
        pygame.key.start_text_input()

    def _close_login(self) -> None:
        if self.login_required:
            self.login_message = "请先输入本地玩家名"
            self.audio.play("bad")
            return
        pygame.key.stop_text_input()
        self.login_composition = ""
        self.login_source_account = None
        self.login_replace_existing = False
        self.login_required = False
        self.post_login_state = "home"
        self.state = "home"

    def _login_or_create(self) -> None:
        name = self.login_text.strip()
        if not name:
            self.login_message = "玩家名不能为空"
            self.audio.play("bad")
            return
        if not all(char.isascii() and char.isalnum() for char in name):
            self.login_message = "用户名只能使用英文字母或数字"
            self.audio.play("bad")
            return
        source = self.login_source_account
        if source and name != source and name in self.accounts:
            self.login_message = "该玩家名已被其他本地账户使用"
            self.audio.play("bad")
            return
        if source and source in self.accounts and name != source and name not in self.accounts:
            self.accounts[name] = self.accounts.pop(source)
        elif name not in self.accounts:
            self.accounts[name] = self._new_account()
        self.active_account = name
        self._load_active_account()
        self.cards = self._make_cards()
        self._save_all()
        self._finish_login()

    def _switch_account(self, name: str) -> None:
        if name not in self.accounts:
            return
        self.active_account = name
        self._load_active_account()
        self.cards = self._make_cards()
        self._save_all()
        self._finish_login()

    def _finish_login(self) -> None:
        target = self.post_login_state
        pygame.key.stop_text_input()
        self.login_source_account = None
        self.login_replace_existing = False
        self.login_required = False
        self.post_login_state = "home"
        self.login_message = ""
        self.state = target if target in {"home", "menu", "shop", "skills"} else "home"
        if target == "loadout":
            self._open_loadout()
        self.audio.play("click")

    def _visible_login_accounts(self) -> list[str]:
        names = sorted(self.accounts, key=str.casefold)
        start = self.login_account_page * 6
        return names[start:start + 6]

    def _open_loadout(self) -> None:
        if not self.active_account:
            self._require_account("loadout")
            return
        level = LEVELS[self.selected_level - 1]
        if level.special == "reverse":
            self.start_game()
            return
        if level.special == "roulette":
            self.active_loadout = [key for key in self.owned_units if key != "charcoal"]
            if not self.active_loadout:
                self.login_message = "转盘关需要至少拥有一个非木炭肉肉"
                self.audio.play("bad")
                return
            self.start_game()
            return
        self.loadout_selection = [key for key in self.saved_loadout if key in self.owned_units]
        self.login_message = ""
        self.state = "loadout"

    def _buy_unit(self, key: str) -> None:
        price = UNIT_COIN_PRICES.get(key, 0)
        if price <= 0 or key in self.owned_units:
            return
        if self.coins < price:
            self.login_message = "金币不足"
            self.audio.play("bad")
            return
        self.coins -= price
        self.owned_units.append(key)
        self.owned_units.sort(key=UNIT_ORDER.index)
        self.login_message = f"已购买 {UNITS[key].name}"
        self._save_all()
        self.audio.play("place")

    def _upgrade_unit(self, key: str) -> None:
        if key not in self.owned_units:
            self.login_message = "请先在商店购买这个肉肉"
            self.audio.play("bad")
            return
        level = self.unit_upgrades.get(key, 0)
        if level >= len(UPGRADE_COSTS):
            self.login_message = f"{UNITS[key].name} 已经满级"
            self.audio.play("bad")
            return
        price = UPGRADE_COSTS[level]
        if self.coins < price:
            self.login_message = "金币不足"
            self.audio.play("bad")
            return
        self.coins -= price
        self.unit_upgrades[key] = level + 1
        self._apply_account_upgrades()
        self.cards = self._make_cards()
        self.login_message = f"{UNITS[key].name} 升级成功"
        self._save_all()
        self.audio.play("place")

    def _upgrade_oil_capacity(self) -> None:
        level = self.oil_capacity_level
        if level >= len(OIL_CAPACITY_UPGRADE_COSTS):
            self.login_message = "油瓶容量已经满级"
            self.audio.play("bad")
            return
        price = OIL_CAPACITY_UPGRADE_COSTS[level]
        if self.coins < price:
            self.login_message = "金币不足"
            self.audio.play("bad")
            return
        self.coins -= price
        self.oil_capacity_level += 1
        self.login_message = f"油瓶容量提升至 {self.oil_capacity}"
        self._save_all()
        self.audio.play("place")

    def _reset_all_data(self) -> None:
        clear_save()
        self.accounts = {}
        self.active_account = None
        default_profile = self._build_level_profile({})
        self.level_tuning = {
            str(level.number): self._copy_level_profile(default_profile) for level in LEVELS
        }
        self.base_unit_stats = {key: dict(stats) for key, stats in self.factory_unit_stats.items()}
        for key, stats in self.factory_enemy_stats.items():
            for attr, value in stats.items():
                setattr(ENEMIES[key], attr, value)
        self.initial_charcoal = STARTING_CHARCOAL
        self.grill_interval = (AMBIENT_CHARCOAL_MIN_SECONDS + AMBIENT_CHARCOAL_MAX_SECONDS) / 2
        self.grill_pickup_value = CHARCOAL_PICKUP_VALUE
        self.charcoal_unit_value = CHARCOAL_PICKUP_VALUE
        self.pickup_ttl = CHARCOAL_PICKUP_TTL
        self.audio.set_music_enabled(self.factory_audio_settings["music_enabled"])
        self.audio.sfx_enabled = self.factory_audio_settings["sfx_enabled"]
        self.audio.set_music_volume(self.factory_audio_settings["music_volume"])
        self.audio.set_sfx_volume(self.factory_audio_settings["sfx_volume"])
        for key, value in self.factory_audio_settings["effect_volumes"].items():
            self.audio.set_effect_volume(key, value)
        self._load_active_account()
        self.cards = self._make_cards()
        self.reset_confirm_stage = 0
        self._save_all()
        self._open_login(
            "home",
            None,
            "数据已清空，请输入英文或数字用户名创建新账户",
            required=True,
        )

    def pos_to_cell(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        x, y = pos
        if not (GRID_X <= x < GRID_X + GRID_COLS * CELL_SIZE):
            return None
        if not (GRID_Y <= y < GRID_Y + GRID_ROWS * CELL_SIZE):
            return None
        col = (x - GRID_X) // CELL_SIZE
        row = (y - GRID_Y) // CELL_SIZE
        return int(row), int(col)

    def try_place(self, row: int, col: int) -> None:
        if self.selected_unit is None:
            return
        if col >= PLACEABLE_COLS:
            self.reject(row, col, "这里是僵尸入口，不能放置")
            return
        config = UNITS[self.selected_unit]
        free_roulette = self.level_config.special == "roulette"
        remaining = self.card_cooldowns.get(self.selected_unit, 0.0)
        if not free_roulette and remaining > 0:
            self.reject(row, col, f"卡片还需冷却 {remaining:.1f} 秒")
            self.selected_unit = None
            return
        if not free_roulette and self.charcoal < config.cost:
            self.reject(row, col, "炭火值不足")
            return
        if self.unit_at(row, col):
            self.reject(row, col, "这个格子已经有肉肉守卫")
            return
        placed_type = self.selected_unit
        unit = Unit(placed_type, row, col)
        self.units.append(unit)
        if not free_roulette:
            self.charcoal -= config.cost
            self.card_cooldowns[placed_type] = UNIT_PLACEMENT_COOLDOWNS[placed_type]
        self._complete_order_if_matched(placed_type, unit.rect.centerx, unit.rect.top)
        self.selected_unit = None
        self.audio.play("place")

    def _begin_reverse_drag(self, pos: tuple[int, int]) -> bool:
        if self.paused or self.show_info or self.show_tuning:
            return False
        for card in self.reverse_cards:
            if card.rect.collidepoint(pos):
                self._select_enemy(card.enemy_type)
                self.selected_enemy = card.enemy_type
                self.dragging_enemy = card.enemy_type
                self.drag_position = pos
                self.audio.play("click")
                return True
        return False

    def _finish_reverse_drag(self, pos: tuple[int, int]) -> None:
        enemy_type = self.dragging_enemy
        self.dragging_enemy = None
        if enemy_type is None:
            return
        if any(card.enemy_type == enemy_type and card.rect.collidepoint(pos) for card in self.reverse_cards):
            return
        cell = self.pos_to_cell(pos)
        if cell is None:
            self.message = "把僵尸拖到五条烤盘路线中的任意一条"
            self.message_timer = 1.8
            self.audio.play("bad")
            return
        self.spawn_reverse_enemy(enemy_type, cell[0])

    def _handle_reverse_click(self, pos: tuple[int, int]) -> None:
        for card in self.reverse_cards:
            if card.rect.collidepoint(pos):
                self._select_enemy(card.enemy_type)
                self.audio.play("click")
                return
        cell = self.pos_to_cell(pos)
        if cell and self.selected_enemy is not None:
            self.spawn_reverse_enemy(self.selected_enemy, cell[0])

    def spawn_reverse_enemy(self, enemy_type: str, row: int) -> bool:
        if enemy_type not in REVERSE_ZOMBIE_COSTS or not 0 <= row < GRID_ROWS:
            return False
        cost = REVERSE_ZOMBIE_COSTS[enemy_type]
        if self.charcoal < cost:
            missing = cost - self.charcoal
            self.message = f"炭火军费不足，还差 {missing}"
            self.message_timer = 1.8
            self.audio.play("bad")
            return False
        tier = self._enemy_tier_for_spawn(self.reverse_spawned_count)
        enemy = Enemy(enemy_type, row, tier=tier)
        self.reverse_spawned_count += 1
        enemy.x = GRID_X + (GRID_COLS - 0.52) * CELL_SIZE
        enemy.rect.centerx = int(enemy.x)
        self.enemies.append(enemy)
        self.charcoal -= cost
        self.selected_enemy = None
        self.effects.append(ImpactBurst(enemy.rect.centerx, enemy.rect.centery, "spark"))
        self.floaters.append(FloatingText(f"-{cost}", enemy.x, enemy.rect.top, (255, 205, 91), 0.8))
        self.message = f"{tier}阶{ENEMIES[enemy_type].name} 已投入第 {row + 1} 路"
        self.message_timer = 1.2
        self.audio.play("zombie_spawn")
        return True

    def on_unit_eaten(self, unit: Unit, enemy: Enemy) -> None:
        if not self.is_reverse_mode:
            return
        reward = max(20, min(80, int(round(unit.config.cost * self.reverse_reward_percent / 100))))
        if unit.unit_type == "charcoal":
            reward += 25
        self.charcoal = min(MAX_CHARCOAL, self.charcoal + reward)
        self.reverse_eaten_units += 1
        self.floaters.append(FloatingText(f"吃掉 +{reward}", unit.rect.centerx, unit.rect.top, (255, 202, 84), 1.0))
        self.effects.append(ImpactBurst(unit.rect.centerx, unit.rect.centery, "grease"))
        self.trigger_shake(3, 0.14)

    def on_reverse_enemy_lost(self, enemy: Enemy) -> None:
        self.reverse_zombies_lost += 1
        self.floaters.append(FloatingText("进攻失败", enemy.x, enemy.y - 16, (173, 207, 126), 0.8))

    def trigger_shake(self, intensity: int = 2, duration: float = 0.10) -> None:
        self.shake_intensity = max(self.shake_intensity, max(0, intensity))
        self.shake_timer = max(self.shake_timer, max(0.0, duration))

    def try_remove(self, row: int, col: int) -> None:
        unit = self.unit_at(row, col)
        if unit is None:
            self.reject(row, col, "这个烤盘上没有可以夹走的肉肉")
            return
        unit.alive = False
        self.remove_mode = False
        self.message = "肉肉已经夹出烤盘并丢弃"
        self.message_timer = 1.5
        self.audio.play("remove")

    def _next_ambient_delay(self) -> float:
        jitter = max(0.1, self.grill_interval * 0.25)
        return self.random.uniform(max(0.5, self.grill_interval - jitter), self.grill_interval + jitter)

    def spawn_pickup_at(self, x: float, y: float, value: int = CHARCOAL_PICKUP_VALUE) -> None:
        self.pickups.append(CharcoalPickup(x, y, value, self.pickup_ttl))

    def spawn_grill_pickup(self) -> None:
        x = self.random.uniform(72, 204)
        y = self.random.uniform(255, 560)
        self.spawn_pickup_at(x, y, self.grill_pickup_value)

    def add_charcoal_auto(self, value: int, x: float, y: float) -> None:
        self.charcoal = min(MAX_CHARCOAL, self.charcoal + value)
        self.defeated_enemies += 1
        self.floaters.append(FloatingText(f"自动+{value}", x, y, (255, 211, 93), 0.85))
        if self.random.random() < 0.10:
            self.coin_pickups.append(CoinPickup(x, y + 18))
        if self.defeated_enemies in self.oil_drop_kills:
            self.oil_pickups.append(OilPickup(x, y + 24))
            self.floaters.append(FloatingText("油瓶掉落!", x, y - 22, (255, 191, 73), 1.2))
        self.audio.play("place")

    def collect_pickup(self, pickup: CharcoalPickup) -> None:
        if pickup not in self.pickups:
            return
        if self.charcoal >= MAX_CHARCOAL:
            self.message = "炭火值已满"
            self.message_timer = 1.2
            self.audio.play("bad")
            return
        self.charcoal = min(MAX_CHARCOAL, self.charcoal + pickup.value)
        self.floaters.append(FloatingText(f"+{pickup.value}", pickup.x, pickup.y - 10, (255, 211, 93), 0.8))
        self.pickups.remove(pickup)
        self.audio.play("place")

    def collect_coin(self, pickup: CoinPickup) -> None:
        if pickup not in self.coin_pickups:
            return
        self.coins += pickup.value
        self.floaters.append(FloatingText(f"金币+{pickup.value}", pickup.x, pickup.y - 12, (255, 232, 118), 0.9))
        self.coin_pickups.remove(pickup)
        self._save_all()
        self.audio.play("place")

    def collect_oil(self, pickup: OilPickup) -> None:
        if pickup not in self.oil_pickups:
            return
        if self.oil_inventory >= self.oil_capacity:
            self.message = f"油瓶已满（{self.oil_capacity}/{self.oil_capacity}）"
            self.message_timer = 1.8
            self.audio.play("bad")
            return
        self.oil_inventory += 1
        self.oil_pickups.remove(pickup)
        self.floaters.append(FloatingText("油瓶+1", pickup.x, pickup.y - 12, (255, 220, 105), 0.9))
        self.audio.play("place")

    def buy_oil_bottle(self) -> None:
        if self.oil_inventory >= self.oil_capacity:
            self.message = "油瓶容量已满"
            self.message_timer = 1.5
            self.audio.play("bad")
            return
        if self.coins < OIL_BOTTLE_PRICE:
            self.message = "金币不足，油瓶需要 100 金币"
            self.message_timer = 1.8
            self.audio.play("bad")
            return
        self.coins -= OIL_BOTTLE_PRICE
        self.oil_inventory += 1
        self.message = "购买油瓶成功"
        self.message_timer = 1.5
        self._save_all()
        self.audio.play("place")

    def activate_ultimate(self, unit: Unit) -> None:
        if self.oil_inventory <= 0 or unit not in self.units or not unit.alive:
            self.ultimate_mode = False
            return
        empty_cells: list[tuple[int, int]] = []
        scallop_targets: list[Enemy] = []
        if unit.unit_type == "lotus" and unit.heal_range >= 2:
            self.reject(unit.row, unit.col, "这个糯米藕盒的治疗范围已经强化")
            return
        if unit.unit_type == "egg_mine":
            empty_cells = [
                (row, col)
                for row in range(GRID_ROWS)
                for col in range(PLACEABLE_COLS)
                if self.unit_at(row, col) is None and not self.enemy_occupies_cell(row, col)
            ]
            if not empty_cells:
                self.reject(unit.row, unit.col, "没有空烤盘可以部署鸡蛋地雷")
                return
        elif unit.unit_type == "scallop":
            alive_enemies = [enemy for enemy in self.enemies if enemy.alive]
            if not alive_enemies:
                self.reject(unit.row, unit.col, "场上没有可供扇贝雨攻击的僵尸")
                return
            scallop_targets = self.random.sample(alive_enemies, min(6, len(alive_enemies)))

        self.oil_inventory -= 1
        self.ultimate_mode = False
        if unit.unit_type == "charcoal":
            for index, dx in enumerate((-26, 0, 26)):
                self.spawn_pickup_at(unit.rect.centerx + dx, unit.rect.centery - 22 + index % 2 * 16, self.charcoal_unit_value)
        elif unit.unit_type == "wall":
            unit.double_defense()
        elif unit.unit_type == "lotus":
            unit.heal_range = 2
            unit.timer = unit.config.cooldown
        elif unit.unit_type == "meatball":
            unit.damage_multiplier *= 2.0
        elif unit.unit_type == "egg_mine":
            row, col = self.random.choice(empty_cells)
            new_mine = Unit("egg_mine", row, col)
            self.units.append(new_mine)
            self.effects.append(Explosion(new_mine.rect.centerx, new_mine.rect.centery))
            self.floaters.append(FloatingText("追加地雷!", new_mine.rect.centerx, new_mine.rect.top, (255, 220, 108), 1.2))
        elif unit.unit_type == "beef":
            for enemy in self.enemies:
                if enemy.alive and enemy.row == unit.row:
                    enemy.apply_slow(5.0)
            unit.ultimate_timer = 5.0
            unit.cooldown = 0.0
        elif unit.unit_type == "wing":
            unit.ultimate_timer = 7.0
            unit.cooldown = 0.0
        elif unit.unit_type == "skewer":
            unit.ultimate_timer = 5.0
            unit.cooldown = 0.0
        elif unit.unit_type == "scallop":
            self.special_effects.append(
                ScallopRain(unit.rect.centerx, unit.rect.centery, scallop_targets, max(1, unit.config.damage * 2))
            )
        elif unit.unit_type == "sausage":
            self.special_effects.append(LaneBurn(unit.row, unit.config.damage, 4.0))
        self.effects.append(Explosion(unit.rect.centerx, unit.rect.centery))
        self.floaters.append(FloatingText("油火大招!", unit.rect.centerx, unit.rect.top - 18, (255, 213, 87), 1.2))
        self.message = f"{unit.config.name} 释放大招"
        self.message_timer = 1.8
        self.audio.play("final_wave")

    def reject(self, row: int, col: int, message: str) -> None:
        self.flash_cell = (row, col)
        self.flash_timer = 0.24
        self.message = message
        self.message_timer = 1.4
        self.audio.play("bad")

    def unit_at(self, row: int, col: int) -> Unit | None:
        for unit in self.units:
            if unit.alive and unit.row == row and unit.col == col:
                return unit
        return None

    def enemy_occupies_cell(self, row: int, col: int) -> bool:
        for enemy in self.enemies:
            if enemy.alive and enemy.row == row and x_to_col(enemy.x) == col:
                return True
        return False

    def update(self, dt: float) -> None:
        if self.state == "ending":
            self.ending_timer += dt
            if self.shake_timer > 0:
                self.shake_timer = max(0.0, self.shake_timer - dt)
            if self.ending_timer >= ENDING_ANIMATION_DURATION:
                self._finish_ending()
            return
        if self.state != "playing" or self.paused or self.show_info or self.show_tuning:
            return
        self.game_time += dt
        for key, remaining in self.card_cooldowns.items():
            self.card_cooldowns[key] = max(0.0, remaining - dt)
        if self.level_config.special == "roulette":
            self._update_roulette(dt)
        elif not self.is_reverse_mode:
            self.next_ambient_pickup -= dt
            if self.next_ambient_pickup <= 0:
                self.spawn_grill_pickup()
                self.next_ambient_pickup = self._next_ambient_delay()
        if self.level_config.special == "conveyor":
            self._update_conveyor()
        elif self.level_config.special == "orders":
            self._update_orders()
        if not self.is_reverse_mode:
            self._spawn_waves()
        for unit in list(self.units):
            unit.update(dt, self)
        for enemy in list(self.enemies):
            enemy.update(dt, self)
        for projectile in list(self.projectiles):
            projectile.update(dt, self)
        for effect in list(self.effects):
            effect.update(dt)
        for effect in list(self.special_effects):
            effect.update(dt, self)
        for floater in list(self.floaters):
            floater.update(dt)
        for pickup in list(self.pickups):
            pickup.update(dt)
        for pickup in list(self.coin_pickups):
            pickup.update(dt)
        for pickup in list(self.oil_pickups):
            pickup.update(dt)
        self.units = [unit for unit in self.units if unit.alive]
        self.enemies = [enemy for enemy in self.enemies if enemy.alive]
        self.projectiles = [projectile for projectile in self.projectiles if projectile.alive]
        self.effects = [effect for effect in self.effects if effect.alive]
        self.special_effects = [effect for effect in self.special_effects if effect.alive]
        self.floaters = [floater for floater in self.floaters if floater.ttl > 0]
        self.pickups = [pickup for pickup in self.pickups if pickup.ttl > 0]
        self.coin_pickups = [pickup for pickup in self.coin_pickups if pickup.ttl > 0]
        self.oil_pickups = [pickup for pickup in self.oil_pickups if pickup.ttl > 0]
        if self.message_timer > 0:
            self.message_timer -= dt
        if self.flash_timer > 0:
            self.flash_timer -= dt
        if self.final_wave_timer > 0:
            self.final_wave_timer -= dt
        if self.conveyor_flash_timer > 0:
            self.conveyor_flash_timer -= dt
        if self.shake_timer > 0:
            self.shake_timer = max(0.0, self.shake_timer - dt)
        if self.is_reverse_mode:
            self._update_reverse_outcome()
            return
        for enemy in self.enemies:
            if enemy.x <= DEFENSE_LINE_X:
                self._begin_ending("lose")
                return
        if self.wave_index >= len(self.level_config.waves) and not self.enemies:
            self._begin_ending("win")

    def _update_roulette(self, dt: float) -> None:
        if self.roulette_unit is not None or self.selected_unit is not None:
            return
        self.roulette_timer -= dt
        if self.roulette_timer > 0:
            return
        choices = [key for key in self.active_loadout if key != "charcoal" and key in UNITS]
        if choices:
            self.roulette_unit = self.random.choice(choices)

    def _update_conveyor(self) -> None:
        if self.game_time < self.conveyor_next_shift:
            return
        for unit in self.units:
            if unit.alive:
                unit.move_to(unit.row, (unit.col + 1) % PLACEABLE_COLS)
        self.conveyor_next_shift += self.level_config.conveyor_interval
        self.conveyor_flash_timer = 0.8
        self.message = "回转烤盘启动：所有肉肉右移一格！"
        self.message_timer = 1.8
        self.audio.play("place")

    def _update_reverse_outcome(self) -> None:
        reached = [enemy for enemy in self.enemies if enemy.alive and enemy.x <= DEFENSE_LINE_X]
        for enemy in reached:
            enemy.alive = False
            self.reverse_core_hp = max(0, self.reverse_core_hp - 1)
            self.effects.append(Explosion(DEFENSE_LINE_X, enemy.rect.centery))
            self.trigger_shake(6, 0.28)
            self.message = f"突破成功！烤炉耐久剩余 {self.reverse_core_hp}"
            self.message_timer = 2.0
        if reached:
            self.enemies = [enemy for enemy in self.enemies if enemy.alive]
        if self.reverse_core_hp <= 0:
            self._begin_ending("win")
            return
        minimum_cost = min(REVERSE_ZOMBIE_COSTS.values())
        if not self.enemies and self.charcoal < minimum_cost:
            self.message = "军费不足且场上没有僵尸，突袭失败"
            self._begin_ending("lose")

    def _update_orders(self) -> None:
        if self.order_unit is not None:
            if self.game_time >= self.order_deadline:
                self._fail_order()
            return
        if self.final_wave_started or self.wave_index >= len(self.level_config.waves) - 1:
            return
        if self.game_time < self.order_next_time:
            return
        choices = [key for key in self.active_loadout if key in UNITS and key != "charcoal"]
        if not choices:
            self.order_next_time = self.game_time + self.level_config.order_interval
            return
        fresh_choices = [key for key in choices if key != self.last_order_unit]
        self.order_unit = self.random.choice(fresh_choices or choices)
        self.last_order_unit = self.order_unit
        self.order_deadline = self.game_time + self.level_config.order_time_limit
        self.message = f"新订单：{UNITS[self.order_unit].name}，限时 {self.level_config.order_time_limit:g} 秒"
        self.message_timer = 2.2
        self.audio.play("zombie_spawn")

    def _complete_order_if_matched(self, unit_type: str, x: float, y: float) -> None:
        if self.level_config.special != "orders" or unit_type != self.order_unit:
            return
        reward = self.level_config.order_reward
        gained = min(reward, max(0, MAX_CHARCOAL - self.charcoal))
        self.charcoal += gained
        self.orders_completed += 1
        self.order_unit = None
        self.order_deadline = 0.0
        self.order_next_time = self.game_time + self.level_config.order_interval
        self.floaters.append(FloatingText(f"订单完成 +{gained}", x, y - 8, (255, 220, 105), 1.2))
        self.message = f"订单完成，获得 {gained} 炭火"
        self.message_timer = 1.8

    def _fail_order(self) -> None:
        failed_name = UNITS[self.order_unit].name if self.order_unit else "肉肉"
        self.order_unit = None
        self.order_deadline = 0.0
        self.order_next_time = self.game_time + self.level_config.order_interval
        self.orders_failed += 1
        waves = self.level_config.waves
        advanced = self.wave_index < len(waves) and waves[self.wave_index][0] > self.game_time + 1.0
        if advanced:
            self._spawn_current_wave()
        if self.final_wave_timer <= 0:
            suffix = "，下一波提前到场！" if advanced else ""
            self.message = f"{failed_name}订单超时{suffix}"
            self.message_timer = 2.2
            self.audio.play("bad")

    def _spawn_waves(self) -> None:
        waves = self.level_config.waves
        while self.wave_index < len(waves) and self.game_time >= waves[self.wave_index][0]:
            self._spawn_current_wave()

    def _spawn_current_wave(self) -> None:
        waves = self.level_config.waves
        if self.wave_index >= len(waves):
            return
        _, configured_types = waves[self.wave_index]
        enemy_types = list(configured_types)
        if self.selected_difficulty == DIFFICULTY_HARD and configured_types:
            reinforcement = max(configured_types, key=lambda key: ENEMIES[key].hp)
            enemy_types.extend([reinforcement] * max(1, len(configured_types) // 4))
        if self.wave_index == len(waves) - 1:
            self.final_wave_started = True
            self.order_unit = None
            self.order_deadline = 0.0
            self.final_wave_timer = 2.8
            self.message = "最后一波来了！守住烧烤摊！"
            self.message_timer = 3.0
            self.audio.play("final_wave")
        else:
            self.audio.play("zombie_spawn")
        rows: list[int] = []
        while len(rows) < len(enemy_types):
            cycle = list(range(GRID_ROWS))
            self.random.shuffle(cycle)
            rows.extend(cycle)
        row_counts = {row: 0 for row in range(GRID_ROWS)}
        for enemy_type, row in zip(enemy_types, rows):
            offset = row_counts[row] * 52
            row_counts[row] += 1
            tier = self._enemy_tier_for_spawn(self.spawned_enemies)
            self.enemies.append(Enemy(enemy_type, row, offset, tier))
            self.spawned_enemies += 1
        self.wave_index += 1

    def draw(self) -> None:
        self._draw_background()
        if self.state == "home":
            self._draw_home()
        elif self.state == "menu":
            self._draw_menu()
        elif self.state == "menu_info":
            if self.info_return_state == "home":
                self._draw_home()
            else:
                self._draw_menu()
            self._draw_info_overlay()
        elif self.state == "tuning":
            self._draw_menu()
            self._draw_tuning_overlay(return_to_menu=True)
        elif self.state == "login":
            if self.post_login_state == "home":
                self._draw_home()
            else:
                self._draw_menu()
            self._draw_login_overlay()
        elif self.state == "loadout":
            self._draw_collection_screen("出战肉肉库", "选择最多 6 个肉肉，本关只能使用所选阵容。", "loadout")
        elif self.state == "shop":
            self._draw_collection_screen("夜市肉肉商店", "使用金币购买新肉肉，已拥有的商品不可重复购买。", "shop")
        elif self.state == "skills":
            self._draw_collection_screen("肉肉技能升级", "每个肉肉拥有专属 7 级成长路线，升级永久保存在当前账户。", "skills")
        elif self.state == "reset_confirm":
            if self.reset_return_state == "home":
                self._draw_home()
            else:
                self._draw_menu()
            self._draw_reset_overlay()
        elif self.state == "ending":
            self._draw_ending_animation()
        elif self.state in {"win", "lose"}:
            self._draw_ending_background(self.state, 1.0)
            self._draw_end_overlay()
        else:
            self._draw_game()
            if self.show_info:
                self._draw_info_overlay()
            if self.show_tuning:
                self._draw_tuning_overlay(return_to_menu=False)
        if self.shake_timer > 0 and self.shake_intensity > 0:
            frame = self.screen.copy()
            dx = self.random.randint(-self.shake_intensity, self.shake_intensity)
            dy = self.random.randint(-self.shake_intensity, self.shake_intensity)
            self.screen.blit(frame, (dx, dy))
        pygame.display.flip()

    def _draw_background(self) -> None:
        self.screen.blit(self.background, (0, 0))
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((8, 9, 12, 44))
        self.screen.blit(shade, (0, 0))

    def _draw_themed_panel(
        self,
        rect: pygame.Rect,
        base: tuple[int, int, int],
        border: tuple[int, int, int],
        selected: bool = False,
        metal: bool = False,
    ) -> None:
        shadow = pygame.Surface((rect.width + 10, rect.height + 12), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 115), (5, 7, rect.width, rect.height), border_radius=8)
        self.screen.blit(shadow, (rect.x - 5, rect.y - 5))
        pygame.draw.rect(self.screen, base, rect, border_radius=8)
        texture = pygame.Surface(rect.size, pygame.SRCALPHA)
        grain = (184, 177, 160, 28) if metal else (157, 101, 64, 30)
        for offset in range(9, rect.height, 18):
            pygame.draw.line(
                texture,
                grain,
                (10, offset),
                (rect.width - 10, offset + (offset % 3 - 1)),
                1,
            )
        self.screen.blit(texture, rect.topleft)
        pygame.draw.rect(self.screen, border, rect, 4 if selected else 2, border_radius=8)
        if selected:
            glow = pygame.Surface((rect.width + 16, rect.height + 16), pygame.SRCALPHA)
            pygame.draw.rect(glow, (255, 177, 49, 76), glow.get_rect(), 5, border_radius=10)
            self.screen.blit(glow, (rect.x - 8, rect.y - 8))
        for corner in (rect.topleft, rect.topright, rect.bottomleft, rect.bottomright):
            inset_x = 7 if corner[0] == rect.left else -7
            inset_y = 7 if corner[1] == rect.top else -7
            point = (corner[0] + inset_x, corner[1] + inset_y)
            pygame.draw.circle(self.screen, (207, 151, 62), point, 3)
            pygame.draw.circle(self.screen, (92, 61, 34), point, 3, 1)

    def _draw_account_summary(self) -> None:
        self._draw_button(self._button_rect("account"), f"账户：{self.active_account}" if self.active_account else "登录 / 新建账户", False)
        if not self.active_account:
            return
        coin = pygame.transform.smoothscale(load_image("coin.png", (36, 36)), (36, 36))
        coin_label = self.font_sm.render(str(self.coins), True, (255, 226, 111))
        group_width = coin.get_width() + 8 + coin_label.get_width()
        x = WIDTH - 25 - group_width
        self.screen.blit(coin, (x, 84))
        self.screen.blit(coin_label, (x + 44, 91))

    def _draw_home(self) -> None:
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((8, 7, 6, 66))
        self.screen.blit(shade, (0, 0))
        title = self.font_title.render("肉肉守摊大战僵尸", True, COLORS["paper"])
        self.screen.blit(title, title.get_rect(center=(WIDTH // 2, 145)))
        subtitle = self.font_md.render("夜市烧烤塔防 · 守住今晚最后一炉", True, (255, 196, 114))
        self.screen.blit(subtitle, subtitle.get_rect(center=(WIDTH // 2, 205)))
        self._draw_account_summary()
        self._draw_button(self._button_rect("home_start"), "开始游戏", True)
        self._draw_button(self._button_rect("home_info"), "游戏简介", False)
        self._draw_button(self._button_rect("home_reset"), "重置数据", False)
        account_tip = self.font_xs.render("点击右上角账户可切换或新建本地账号", True, (224, 205, 170))
        self.screen.blit(account_tip, account_tip.get_rect(center=(WIDTH // 2, 505)))

    def _draw_menu(self) -> None:
        title = self.font_title.render("肉肉守摊大战僵尸", True, COLORS["paper"])
        self.screen.blit(title, title.get_rect(center=(WIDTH // 2, 55)))
        subtitle = self.font_md.render("选择关卡 · 通关后解锁下一关", True, (255, 196, 114))
        self.screen.blit(subtitle, subtitle.get_rect(center=(WIDTH // 2, 104)))
        self._draw_account_summary()
        for index, level in enumerate(LEVELS):
            rect = self._level_rect(index)
            unlocked = level.number <= self.unlocked_level
            completed = level.number in self.completed_levels
            hard_completed = level.number in self.hard_completed_levels
            selected = level.number == self.selected_level
            base = (72, 57, 45) if unlocked else (39, 36, 35)
            pygame.draw.rect(self.screen, base, rect, border_radius=8)
            border = COLORS["gold"] if selected else ((124, 94, 65) if unlocked else (68, 63, 60))
            pygame.draw.rect(self.screen, border, rect, 4 if selected else 2, border_radius=8)
            number = self.font_md.render(str(level.number), True, COLORS["paper"] if unlocked else (105, 101, 98))
            self.screen.blit(number, (rect.x + 14, rect.y + 10))
            name = self.font_sm.render(level.name, True, COLORS["gold"] if unlocked else (120, 115, 110))
            self.screen.blit(name, (rect.x + 50, rect.y + 10))
            if hard_completed:
                status = "普通过关 · 困难过关"
            elif completed:
                status = "普通过关 · 困难可玩"
            else:
                status = "普通可挑战" if unlocked else "未解锁"
            status_color = (112, 218, 132) if completed else ((255, 206, 105) if unlocked else (130, 124, 118))
            status_s = self.font_xs.render(status, True, status_color)
            self.screen.blit(status_s, (rect.x + 51, rect.y + 38))
            description = self._fit_text(
                level.description if unlocked else "请先通关上一关",
                self.font_xs,
                rect.width - 28,
            )
            description_s = self.font_xs.render(
                description,
                True,
                (226, 211, 182) if unlocked else (115, 110, 106),
            )
            self.screen.blit(description_s, (rect.x + 14, rect.y + 64))
        self._draw_difficulty_selector()
        difficulty_name = "困难" if self.selected_difficulty == DIFFICULTY_HARD else "普通"
        self._draw_button(self._button_rect("start"), f"开始第 {self.selected_level} 关 · {difficulty_name}", True)
        self._draw_button(self._button_rect("menu_tuning"), f"第 {self.selected_level} 关调参", False)
        self._draw_button(self._button_rect("shop"), "肉肉商店", False)
        self._draw_button(self._button_rect("skills"), "技能升级", False)
        self._draw_button(self._button_rect("screen_back"), "返回主界面", False)
        if self.login_message:
            message = self.font_xs.render(self.login_message, True, (255, 174, 112))
            self.screen.blit(message, message.get_rect(center=(WIDTH // 2, 628)))

    def _draw_difficulty_selector(self) -> None:
        normal_rect = self._button_rect("difficulty_normal")
        hard_rect = self._button_rect("difficulty_hard")
        hard_unlocked = self.selected_level in self.completed_levels
        for difficulty, rect, label, enabled in (
            (DIFFICULTY_NORMAL, normal_rect, "普通", True),
            (DIFFICULTY_HARD, hard_rect, "困难 · 奖励更高", hard_unlocked),
        ):
            selected = self.selected_difficulty == difficulty
            base = (113, 76, 42) if selected else ((61, 53, 47) if enabled else (37, 36, 35))
            border = COLORS["gold"] if selected else ((133, 104, 70) if enabled else (70, 66, 62))
            self._draw_themed_panel(rect, base, border, selected, metal=True)
            text = label if enabled else "困难 · 普通通关后解锁"
            font = self.font_xs if difficulty == DIFFICULTY_HARD else self.font_sm
            color = COLORS["paper"] if enabled else (126, 121, 115)
            surface = font.render(text, True, color)
            self.screen.blit(surface, surface.get_rect(center=rect.center))

    def _draw_login_overlay(self) -> None:
        self._draw_modal_backdrop()
        panel = pygame.Rect(WIDTH // 2 - 380, HEIGHT // 2 - 280, 760, 560)
        pygame.draw.rect(self.screen, (42, 34, 30), panel, border_radius=8)
        pygame.draw.rect(self.screen, COLORS["gold"], panel, 3, border_radius=8)
        title = self.font_lg.render("本地账户", True, COLORS["paper"])
        self.screen.blit(title, title.get_rect(center=(panel.centerx, panel.y + 45)))
        note_text = "输入新名称会保留原账户数据。" if self.login_source_account else "选择已有账户，或创建一个新的本地账户。"
        note = self.font_xs.render(note_text, True, (222, 204, 171))
        self.screen.blit(note, note.get_rect(center=(panel.centerx, panel.y + 84)))

        section = self.font_xs.render("本地账户", True, (255, 205, 105))
        self.screen.blit(section, (panel.x + 50, panel.y + 112))
        account_names = self._visible_login_accounts()
        if account_names:
            for index, name in enumerate(account_names):
                rect = self._login_account_rect(index)
                selected = name == self.active_account
                self._draw_themed_panel(rect, (76, 59, 45) if selected else (55, 49, 44), COLORS["gold"] if selected else (126, 103, 76), selected, metal=True)
                suffix = "  当前" if selected else ""
                label_text = self._fit_text(name + suffix, self.font_sm, rect.width - 24)
                label = self.font_sm.render(label_text, True, COLORS["paper"])
                self.screen.blit(label, label.get_rect(center=rect.center))
        else:
            empty = self.font_xs.render("暂无本地账户，请在下方创建", True, COLORS["muted"])
            self.screen.blit(empty, empty.get_rect(center=(panel.centerx, panel.y + 205)))
        if len(self.accounts) > 6:
            self._draw_button(self._button_rect("login_prev"), "上一页", False)
            self._draw_button(self._button_rect("login_next"), "下一页", False)
        if self.active_account:
            self._draw_button(self._button_rect("login_rename"), "重命名当前", False)

        field_title = self.font_xs.render("仅限英文字母或数字，最多 12 位", True, (255, 205, 105))
        self.screen.blit(field_title, (panel.x + 70, panel.y + 360))
        field = pygame.Rect(panel.x + 70, panel.y + 388, panel.width - 140, 54)
        pygame.key.set_text_input_rect(field)
        pygame.draw.rect(self.screen, (27, 24, 22), field, border_radius=6)
        pygame.draw.rect(self.screen, (255, 213, 112), field, 2, border_radius=6)
        shown = self.login_text + self.login_composition + ("|" if pygame.time.get_ticks() // 500 % 2 == 0 else "")
        if not self.login_text and not self.login_composition:
            shown = "EnglishOrNumber" + ("|" if pygame.time.get_ticks() // 500 % 2 == 0 else "")
        label = self.font_md.render(shown, True, COLORS["paper"])
        if not self.login_text and not self.login_composition:
            label.set_alpha(115)
        self.screen.blit(label, (field.x + 18, field.y + 10))
        if self.login_message:
            message = self.font_xs.render(self.login_message, True, (255, 154, 111))
            self.screen.blit(message, message.get_rect(center=(panel.centerx, panel.y + 466)))
        action_text = "确认修改" if self.login_source_account else "创建 / 登录"
        self._draw_button(self._button_rect("login_confirm"), action_text, True)
        if not self.login_required:
            self._draw_button(self._button_rect("login_back"), "返回", False)

    def _draw_collection_screen(self, title_text: str, subtitle_text: str, mode: str) -> None:
        self._draw_background()
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((12, 10, 9, 125))
        self.screen.blit(shade, (0, 0))
        title = self.font_lg.render(title_text, True, COLORS["paper"])
        self.screen.blit(title, (70, 30))
        subtitle = self.font_sm.render(subtitle_text, True, (255, 199, 118))
        self.screen.blit(subtitle, (72, 88))
        self._draw_coin_balance()
        if mode == "skills":
            self._draw_oil_capacity_upgrade()
        if mode == "loadout":
            keys = self.owned_units
        else:
            keys = UNIT_ORDER
        for index, key in enumerate(keys):
            rect = self._unit_library_rect(index)
            config = UNITS[key]
            owned = key in self.owned_units
            selected = mode == "loadout" and key in self.loadout_selection
            base = (65, 59, 52) if owned else (39, 38, 37)
            border = COLORS["gold"] if selected else ((154, 119, 73) if owned else (75, 70, 65))
            self._draw_themed_panel(rect, base, border, selected, metal=True)
            image = pygame.transform.smoothscale(self.card_images[key], (70, 70)).copy()
            if not owned:
                image = pygame.transform.grayscale(image)
                image.set_alpha(145)
            self.screen.blit(image, (rect.x + 14, rect.y + 18))
            name = self.font_sm.render(config.name, True, COLORS["paper"] if owned else COLORS["muted"])
            self.screen.blit(name, (rect.x + 98, rect.y + 14))
            stats = self.font_xs.render(f"炭火 {config.cost}  生命 {config.hp}  攻击 {config.damage}  间隔 {config.cooldown:g}s", True, (231, 213, 180))
            self.screen.blit(stats, (rect.x + 98, rect.y + 44))
            if mode != "skills":
                self._draw_wrapped_text(config.description, rect.x + 98, rect.y + 68, rect.width - 116, self.font_xs, (190, 181, 166), 18)
            if mode == "loadout":
                status = "已选择" if selected else "点击选择"
                color = (105, 226, 133) if selected else (255, 205, 107)
                tag = self.font_xs.render(status, True, color)
                self.screen.blit(tag, (rect.right - tag.get_width() - 14, rect.y + 14))
            elif mode == "shop":
                self._draw_shop_action(index, key, owned)
            else:
                self._draw_skill_action(index, key, owned)
        if self.login_message:
            message = self.font_sm.render(self.login_message, True, (255, 177, 112))
            self.screen.blit(message, message.get_rect(center=(WIDTH // 2, HEIGHT - 72)))
        if mode == "loadout":
            count = self.font_sm.render(f"已选 {len(self.loadout_selection)} / {MAX_LOADOUT_SIZE}", True, COLORS["paper"])
            self.screen.blit(count, count.get_rect(center=(WIDTH // 2, HEIGHT - 100)))
            self._draw_button(self._button_rect("loadout_start"), "确认阵容并开始", True)
        self._draw_button(self._button_rect("screen_back"), "返回", False)

    def _draw_shop_action(self, index: int, key: str, owned: bool) -> None:
        rect = self._shop_buy_rect(index)
        price = UNIT_COIN_PRICES.get(key, 0)
        if owned:
            pygame.draw.rect(self.screen, (66, 64, 61), rect, border_radius=6)
            label = self.font_xs.render("已拥有", True, (160, 157, 151))
        elif self.coins < price:
            pygame.draw.rect(self.screen, (61, 55, 52), rect, border_radius=6)
            pygame.draw.rect(self.screen, (116, 73, 63), rect, 1, border_radius=6)
            label = self.font_xs.render(f"还差 {price - self.coins}", True, (219, 149, 128))
        else:
            pygame.draw.rect(self.screen, (226, 166, 65), rect, border_radius=6)
            pygame.draw.rect(self.screen, (255, 225, 151), rect, 1, border_radius=6)
            label = self.font_xs.render(f"{price} 金币", True, COLORS["black"])
        self.screen.blit(label, label.get_rect(center=rect.center))

    def _draw_skill_action(self, index: int, key: str, owned: bool) -> None:
        rect = self._skill_upgrade_rect(index)
        level = self.unit_upgrades.get(key, 0)
        if not owned:
            text, color = "未拥有", (67, 65, 63)
        elif level >= len(UPGRADE_COSTS):
            text, color = "已满级", (67, 95, 71)
        elif self.coins < UPGRADE_COSTS[level]:
            text, color = f"还差 {UPGRADE_COSTS[level] - self.coins}", (79, 58, 53)
        else:
            text, color = f"升级 {UPGRADE_COSTS[level]} 金币", (226, 166, 65)
        pygame.draw.rect(self.screen, color, rect, border_radius=6)
        label = self.font_xs.render(text, True, COLORS["paper"] if color[0] < 100 else COLORS["black"])
        self.screen.blit(label, label.get_rect(center=rect.center))
        path = UNIT_UPGRADE_PATHS[key]
        next_effect = path[level][2] if level < len(path) else "全部完成"
        level_text = self.font_xs.render(
            f"等级 {level}/{len(path)} · 下一效果：{next_effect}",
            True,
            (255, 213, 119),
        )
        base = self._unit_library_rect(index)
        self.screen.blit(level_text, (base.x + 98, base.bottom - 23))

    def _draw_coin_balance(self) -> None:
        image = pygame.transform.smoothscale(load_image("coin.png", (42, 42)), (42, 42))
        self.screen.blit(image, (WIDTH - 230, 32))
        text = self.font_md.render(f"{self.coins} 金币", True, (255, 226, 112))
        self.screen.blit(text, (WIDTH - 180, 38))

    def _oil_capacity_upgrade_rect(self) -> pygame.Rect:
        return pygame.Rect(980, 78, 360, 38)

    def _draw_oil_capacity_upgrade(self) -> None:
        rect = self._oil_capacity_upgrade_rect()
        level = self.oil_capacity_level
        full = level >= len(OIL_CAPACITY_UPGRADE_COSTS)
        price = 0 if full else OIL_CAPACITY_UPGRADE_COSTS[level]
        pygame.draw.rect(self.screen, (80, 58, 40), rect, border_radius=7)
        pygame.draw.rect(self.screen, COLORS["gold"], rect, 2, border_radius=7)
        icon = pygame.transform.smoothscale(self.oil_image, (34, 34))
        self.screen.blit(icon, (rect.x + 5, rect.y + 2))
        text = f"油瓶容量 {self.oil_capacity}/{MAX_OIL_CAPACITY} · " + ("已满级" if full else f"升级 {price} 金币")
        label = self.font_xs.render(text, True, COLORS["paper"])
        self.screen.blit(label, label.get_rect(center=(rect.centerx + 18, rect.centery)))

    def _draw_reset_overlay(self) -> None:
        self._draw_modal_backdrop()
        panel = pygame.Rect(WIDTH // 2 - 330, HEIGHT // 2 - 150, 660, 300)
        pygame.draw.rect(self.screen, (46, 32, 30), panel, border_radius=8)
        pygame.draw.rect(self.screen, COLORS["red"], panel, 3, border_radius=8)
        title = "再次确认删除" if self.reset_confirm_stage == 2 else "重置所有本地数据？"
        detail = "这是第二次确认。删除后无法恢复。" if self.reset_confirm_stage == 2 else "将删除所有账户、金币、通关进度、购买、升级和调参。"
        self.screen.blit(self.font_lg.render(title, True, COLORS["paper"]), self.font_lg.render(title, True, COLORS["paper"]).get_rect(center=(panel.centerx, panel.y + 72)))
        detail_s = self.font_sm.render(detail, True, (255, 183, 148))
        self.screen.blit(detail_s, detail_s.get_rect(center=(panel.centerx, panel.y + 132)))
        self._draw_button(self._button_rect("reset_confirm"), "确认删除" if self.reset_confirm_stage == 2 else "继续", True)
        self._draw_button(self._button_rect("reset_cancel"), "取消", False)

    def _draw_modal_backdrop(self) -> None:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

    def _draw_game(self) -> None:
        self._draw_top_bar()
        self._draw_grid()
        self._draw_defense_line()
        if self.level_config.special == "conveyor":
            self._draw_conveyor_status()
        elif self.level_config.special == "orders":
            self._draw_order_status()
        if not self.is_reverse_mode:
            for pickup in self.pickups:
                pickup.draw(self.screen, self.font_sm)
            for pickup in self.coin_pickups:
                pickup.draw(self.screen, self.font_xs)
        for unit in self.units:
            unit.draw(self.screen)
        for enemy in sorted(self.enemies, key=lambda e: e.y):
            enemy.draw(self.screen)
        for projectile in self.projectiles:
            projectile.draw(self.screen)
        for effect in self.effects:
            effect.draw(self.screen)
        for effect in self.special_effects:
            effect.draw(self.screen)
        if not self.is_reverse_mode:
            for pickup in self.oil_pickups:
                pickup.draw(self.screen, self.font_xs)
            self._draw_oil_hud()
        else:
            self._draw_reverse_hud()
            self._draw_dragged_enemy()
        self._draw_floaters()
        if self.message_timer > 0 and self.message and self.final_wave_timer <= 0:
            self._draw_message_toast()
        if self.paused:
            self._draw_center_banner("已暂停", "按 P 或点击继续")
        if self.final_wave_timer > 0:
            self._draw_wave_warning()
        if self.exit_confirm:
            self._draw_exit_overlay()

    def _draw_top_bar(self) -> None:
        bar = pygame.Surface((WIDTH, TOP_BAR_HEIGHT), pygame.SRCALPHA)
        bar.fill((31, 25, 21, 236))
        for y in range(10, TOP_BAR_HEIGHT - 8, 17):
            pygame.draw.line(bar, (77, 50, 34, 110), (0, y), (WIDTH, y + y % 3 - 1), 1)
        for x in range(14, WIDTH, 86):
            pygame.draw.circle(bar, (191, 135, 57, 190), (x, 9), 3)
            pygame.draw.circle(bar, (77, 48, 29, 220), (x, 9), 3, 1)
        self.screen.blit(bar, (0, 0))
        pygame.draw.rect(self.screen, (65, 42, 29), (0, TOP_BAR_HEIGHT - 9, WIDTH, 9))
        pygame.draw.line(self.screen, (224, 153, 61), (0, TOP_BAR_HEIGHT - 9), (WIDTH, TOP_BAR_HEIGHT - 9), 2)
        self._draw_charcoal_status()
        difficulty_name = "困难" if self.selected_difficulty == DIFFICULTY_HARD else "普通"
        status = "突袭无时限" if self.is_reverse_mode else f"时间 {int(self.game_time)}s"
        timer = self.font_sm.render(
            f"第 {self.selected_level} 关 · {difficulty_name} · {status}",
            True,
            COLORS["paper"],
        )
        self.screen.blit(timer, (24, 99))
        self._draw_progress_bar()
        if self.is_reverse_mode:
            for card in self.reverse_cards:
                self._draw_reverse_card(card)
        else:
            self._draw_tongs_tool()
            for card in self.cards:
                self._draw_card(card)
        self._draw_button(self._button_rect("pause"), "继续" if self.paused else "暂停", False)
        self._draw_button(self._button_rect("restart_play"), "重开", False)
        self._draw_button(self._button_rect("exit_play"), "退出", False)
        self._draw_button(self._button_rect("info"), "简介", False)
        self._draw_button(self._button_rect("tuning"), "设置", False)

    def _tongs_rect(self) -> pygame.Rect:
        return pygame.Rect(226, 14, 88, 76)

    def _draw_tongs_tool(self) -> None:
        rect = self._tongs_rect()
        mouse = pygame.mouse.get_pos()
        active = self.remove_mode
        base = (104, 70, 48) if active else (55, 48, 43)
        if rect.collidepoint(mouse):
            base = tuple(min(255, value + 18) for value in base)
        pygame.draw.rect(self.screen, base, rect, border_radius=8)
        pygame.draw.rect(self.screen, COLORS["red"] if active else (128, 103, 73), rect, 3 if active else 2, border_radius=8)
        image = pygame.transform.smoothscale(self.tongs_image, (58, 48))
        self.screen.blit(image, image.get_rect(center=(rect.centerx, rect.centery - 5)))
        label = self.font_xs.render("夹除", True, COLORS["paper"])
        self.screen.blit(label, label.get_rect(center=(rect.centerx, rect.bottom - 11)))

    def _draw_message_toast(self) -> None:
        text = self.font_sm.render(self.message, True, COLORS["paper"])
        width = min(WIDTH - 80, max(320, text.get_width() + 48))
        panel = pygame.Surface((width, 38), pygame.SRCALPHA)
        pygame.draw.rect(panel, (41, 31, 26, 220), panel.get_rect(), border_radius=8)
        pygame.draw.rect(panel, (255, 191, 86, 220), panel.get_rect(), 2, border_radius=8)
        panel.blit(text, text.get_rect(center=panel.get_rect().center))
        self.screen.blit(panel, (WIDTH // 2 - width // 2, HEIGHT - 54))

    def _draw_charcoal_status(self) -> None:
        panel = pygame.Rect(18, 14, 190, 76)
        glow = pygame.Surface((panel.width + 24, panel.height + 24), pygame.SRCALPHA)
        pygame.draw.rect(glow, (255, 171, 58, 90), glow.get_rect(), border_radius=18)
        self.screen.blit(glow, (panel.x - 12, panel.y - 12))
        pygame.draw.rect(self.screen, (34, 24, 18), panel, border_radius=10)
        pygame.draw.rect(self.screen, (255, 198, 84), panel, 3, border_radius=10)
        pygame.draw.circle(self.screen, (255, 101, 45), (panel.x + 28, panel.y + 38), 16)
        pygame.draw.circle(self.screen, (255, 219, 92), (panel.x + 34, panel.y + 31), 7)
        tick = pygame.time.get_ticks() // 120
        for index in range(5):
            sx = panel.x + 18 + (index * 29 + tick * 3) % 160
            sy = panel.bottom - 5 - (index * 11 + tick * 5) % 36
            radius = 1 + index % 2
            pygame.draw.circle(self.screen, (255, 143 + index * 16, 51), (sx, sy), radius)
        roulette = self.level_config.special == "roulette"
        label_text = "转盘关" if roulette else ("炭火军费" if self.is_reverse_mode else "炭火值")
        label = self.font_sm.render(label_text, True, COLORS["paper"])
        value_font = get_font(22 if roulette else (26 if self.charcoal < 1000 else 22), True)
        value = value_font.render("无需炭火" if roulette else str(self.charcoal), True, (255, 221, 104))
        self.screen.blit(label, (panel.x + 62, panel.y + 10))
        self.screen.blit(value, (panel.x + 62, panel.y + 38))

    def _draw_card(self, card: Card) -> None:
        config = UNITS[card.unit_type]
        remaining = self.card_cooldowns.get(card.unit_type, 0.0)
        ready = remaining <= 0
        selected = card.unit_type == self.selected_unit and ready
        affordable = self.charcoal >= config.cost
        base = (66, 59, 50) if affordable and ready else (38, 36, 34)
        border = COLORS["gold"] if selected else ((128, 103, 73) if affordable and ready else (66, 58, 52))
        self._draw_themed_panel(card.rect, base, border, selected, metal=True)
        image = pygame.transform.smoothscale(self.card_images[card.unit_type], (38, 38)).copy()
        if not affordable or not ready:
            dark_mask = pygame.Surface(image.get_size(), pygame.SRCALPHA)
            dark_mask.fill((0, 0, 0, 150))
            image.blit(dark_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        self.screen.blit(image, (card.rect.x + 6, card.rect.y + 12))
        text_ready = affordable and ready
        name_font = self.font_xs if self.font_xs.size(config.name)[0] <= card.rect.width - 52 else get_font(14)
        name = name_font.render(config.name, True, COLORS["paper"] if text_ready else COLORS["muted"])
        cost = self.font_sm.render(str(config.cost), True, COLORS["gold"] if affordable else (226, 83, 72))
        self.screen.blit(name, (card.rect.x + 48, card.rect.y + 15))
        self.screen.blit(cost, (card.rect.x + 48, card.rect.y + 41))
        if not ready:
            total = max(0.1, UNIT_PLACEMENT_COOLDOWNS[card.unit_type])
            ratio = min(1.0, remaining / total)
            cover = pygame.Surface((card.rect.width, max(1, int(card.rect.height * ratio))), pygame.SRCALPHA)
            cover.fill((12, 15, 17, 172))
            self.screen.blit(cover, (card.rect.x, card.rect.bottom - cover.get_height()))
            cooldown_text = self.font_xs.render(f"冷却 {remaining:.1f}s", True, (232, 236, 238))
            self.screen.blit(cooldown_text, cooldown_text.get_rect(center=card.rect.center))

    def _draw_reverse_card(self, card: EnemyCard) -> None:
        config = ENEMIES[card.enemy_type]
        cost_value = REVERSE_ZOMBIE_COSTS[card.enemy_type]
        selected = card.enemy_type == self.selected_enemy
        affordable = self.charcoal >= cost_value
        base = (70, 55, 48) if affordable else (38, 36, 35)
        border = (245, 173, 62) if selected else ((142, 91, 66) if affordable else (73, 65, 61))
        self._draw_themed_panel(card.rect, base, border, selected, metal=True)
        pygame.draw.line(self.screen, (126, 48, 37), (card.rect.x + 8, card.rect.bottom - 11), (card.rect.right - 8, card.rect.bottom - 11), 3)
        image = pygame.transform.smoothscale(self.enemy_card_images[card.enemy_type], (36, 50)).copy()
        if not affordable:
            image.set_alpha(86)
        self.screen.blit(image, image.get_rect(center=(card.rect.x + 22, card.rect.centery - 2)))
        name_font = self.font_xs if self.font_xs.size(config.name)[0] <= 54 else get_font(13)
        name = name_font.render(config.name, True, COLORS["paper"] if affordable else COLORS["muted"])
        price_text = str(cost_value) if affordable else f"差{cost_value - self.charcoal}"
        price_font = self.font_sm if affordable else self.font_xs
        price = price_font.render(price_text, True, COLORS["gold"] if affordable else (216, 102, 83))
        self.screen.blit(name, (card.rect.x + 42, card.rect.y + 14))
        self.screen.blit(price, (card.rect.x + 42, card.rect.y + 41))

    def _draw_grid(self) -> None:
        mouse_cell = self.pos_to_cell(pygame.mouse.get_pos())
        for row in range(GRID_ROWS):
            for col in range(GRID_COLS):
                rect = pygame.Rect(GRID_X + col * CELL_SIZE, GRID_Y + row * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                tile = self.tray_image.copy()
                if col >= PLACEABLE_COLS:
                    dark = pygame.Surface(tile.get_size(), pygame.SRCALPHA)
                    dark.fill((20, 18, 16, 54 if self.is_reverse_mode else 86))
                    tile.blit(dark, (0, 0))
                self.screen.blit(tile, (rect.x + 4, rect.y + 4))
                pygame.draw.ellipse(
                    self.screen,
                    (226, 211, 173),
                    (rect.x + 15, rect.y + 12, CELL_SIZE - 34, 5),
                    1,
                )
                mark_seed = row * 17 + col * 11
                if mark_seed % 3 == 0:
                    pygame.draw.arc(
                        self.screen,
                        (72, 48, 34),
                        (rect.x + 25, rect.y + 34, 31, 22),
                        0.3,
                        2.5,
                        2,
                    )
                border_color = (137, 91, 51) if col < PLACEABLE_COLS else (125, 69, 55)
                pygame.draw.rect(self.screen, border_color, rect.inflate(-8, -8), 2, border_radius=8)
                occupying_unit = self.unit_at(row, col)
                if occupying_unit and occupying_unit.hp < occupying_unit.max_hp * 0.5:
                    damage_color = (203, 75, 47)
                    pygame.draw.line(self.screen, damage_color, (rect.x + 17, rect.y + 22), (rect.x + 30, rect.y + 34), 2)
                    pygame.draw.line(self.screen, damage_color, (rect.x + 30, rect.y + 34), (rect.x + 24, rect.y + 47), 2)
                if (pygame.time.get_ticks() // 500 + mark_seed) % 13 == 0 and col < PLACEABLE_COLS:
                    steam = pygame.Surface((CELL_SIZE, 30), pygame.SRCALPHA)
                    pygame.draw.arc(steam, (245, 237, 218, 72), (19, 7, 17, 22), 2.5, 5.1, 2)
                    pygame.draw.arc(steam, (245, 237, 218, 52), (36, 1, 15, 23), 2.3, 5.0, 2)
                    self.screen.blit(steam, (rect.x, rect.y - 12))
                if self.is_reverse_mode and col == GRID_COLS - 1:
                    active_lane = mouse_cell is not None and mouse_cell[0] == row and self.selected_enemy is not None
                    can_afford = self.selected_enemy is not None and self.charcoal >= REVERSE_ZOMBIE_COSTS[self.selected_enemy]
                    gate_color = ((247, 177, 65) if can_afford else (221, 73, 55)) if active_lane else (164, 68, 50)
                    pygame.draw.rect(self.screen, gate_color, rect.inflate(-14, -14), 3, border_radius=8)
                    pygame.draw.polygon(
                        self.screen,
                        gate_color,
                        [(rect.centerx - 12, rect.centery), (rect.centerx + 8, rect.centery - 11), (rect.centerx + 8, rect.centery + 11)],
                    )
                if self.level_config.special == "conveyor" and col < PLACEABLE_COLS:
                    arrow_color = (255, 196, 82) if self.conveyor_flash_timer > 0 else (136, 101, 67)
                    cy = rect.y + 16
                    pygame.draw.line(self.screen, arrow_color, (rect.right - 29, cy), (rect.right - 13, cy), 2)
                    pygame.draw.polygon(
                        self.screen,
                        arrow_color,
                        [(rect.right - 13, cy), (rect.right - 20, cy - 5), (rect.right - 20, cy + 5)],
                    )
                if mouse_cell == (row, col) and self.state == "playing":
                    if self.is_reverse_mode:
                        pygame.draw.rect(self.screen, (235, 154, 64), rect.inflate(-12, -12), 2, border_radius=8)
                    elif self.remove_mode:
                        removable = self.unit_at(row, col) is not None
                        preview = pygame.transform.smoothscale(self.tongs_image, (56, 48)).copy()
                        preview.set_alpha(190 if removable else 90)
                        self.screen.blit(preview, preview.get_rect(center=rect.center))
                        outline = (255, 184, 82) if removable else COLORS["red"]
                        pygame.draw.rect(self.screen, outline, rect.inflate(-14, -14), 3, border_radius=8)
                    elif self.selected_unit is not None:
                        config = UNITS[self.selected_unit]
                        occupied = self.unit_at(row, col) is not None
                        valid = col < PLACEABLE_COLS and (self.level_config.special == "roulette" or self.charcoal >= config.cost) and not occupied
                        preview = pygame.transform.smoothscale(
                            self.card_images[self.selected_unit],
                            (max(52, CELL_SIZE - 22), max(52, CELL_SIZE - 22)),
                        ).copy()
                        preview.set_alpha(170 if valid else 88)
                        self.screen.blit(preview, preview.get_rect(center=(rect.centerx, rect.centery + 8)))
                        outline = (255, 235, 144) if valid else COLORS["red"]
                        pygame.draw.rect(self.screen, outline, rect.inflate(-14, -14), 3, border_radius=8)
                        if not valid:
                            warning = pygame.Surface((CELL_SIZE - 18, CELL_SIZE - 18), pygame.SRCALPHA)
                            warning.fill((190, 35, 35, 68))
                            self.screen.blit(warning, (rect.x + 9, rect.y + 9))
                    else:
                        pygame.draw.rect(self.screen, (190, 153, 102), rect.inflate(-14, -14), 2, border_radius=8)
        if self.is_reverse_mode and mouse_cell is not None and self.selected_enemy is not None:
            row = mouse_cell[0]
            can_afford = self.charcoal >= REVERSE_ZOMBIE_COSTS[self.selected_enemy]
            lane_overlay = pygame.Surface((GRID_COLS * CELL_SIZE, CELL_SIZE - 10), pygame.SRCALPHA)
            lane_overlay.fill((255, 170, 57, 34) if can_afford else (220, 56, 48, 38))
            self.screen.blit(lane_overlay, (GRID_X, GRID_Y + row * CELL_SIZE + 5))
            pygame.draw.rect(
                self.screen,
                (255, 188, 76) if can_afford else (230, 75, 61),
                (GRID_X, GRID_Y + row * CELL_SIZE + 5, GRID_COLS * CELL_SIZE, CELL_SIZE - 10),
                2,
                border_radius=8,
            )
        if self.flash_cell and self.flash_timer > 0:
            row, col = self.flash_cell
            rect = pygame.Rect(GRID_X + col * CELL_SIZE, GRID_Y + row * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            pygame.draw.rect(self.screen, COLORS["red"], rect.inflate(-16, -16), 5, border_radius=8)

    def _draw_defense_line(self) -> None:
        if self.level_config.special == "roulette":
            rect = self._roulette_rect()
            self.screen.blit(self.roulette_image, self.roulette_image.get_rect(center=rect.center))
            if self.roulette_unit:
                icon = pygame.transform.smoothscale(self.card_images[self.roulette_unit], (74, 74))
                glow = pygame.Surface((94, 94), pygame.SRCALPHA)
                pygame.draw.circle(glow, (255, 207, 86, 110), (47, 47), 45)
                self.screen.blit(glow, glow.get_rect(center=rect.center))
                self.screen.blit(icon, icon.get_rect(center=rect.center))
                label = self.font_xs.render("点击领取", True, COLORS["paper"])
                self.screen.blit(label, label.get_rect(center=(rect.centerx, rect.bottom + 14)))
        else:
            self.screen.blit(self.grill_image, (42, GRID_Y - 8))
        pygame.draw.line(self.screen, (255, 152, 67), (DEFENSE_LINE_X, GRID_Y - 8), (DEFENSE_LINE_X, GRID_Y + GRID_ROWS * CELL_SIZE + 8), 3)
        if self.is_reverse_mode:
            panel = pygame.Rect(76, GRID_Y + 306, 154, 72)
            self._draw_themed_panel(panel, (47, 33, 27), (202, 124, 53))
            title = self.font_xs.render("烤炉耐久", True, COLORS["paper"])
            self.screen.blit(title, title.get_rect(center=(panel.centerx, panel.y + 18)))
            for index in range(self.reverse_core_max_hp):
                center = (panel.x + 49 + index * 29, panel.y + 47)
                alive = index < self.reverse_core_hp
                pygame.draw.circle(self.screen, (255, 102, 42) if alive else (65, 58, 54), center, 10)
                pygame.draw.circle(self.screen, (255, 221, 92) if alive else (100, 92, 86), (center[0] + 3, center[1] - 3), 4)

    def _draw_conveyor_status(self) -> None:
        remaining = max(0, math.ceil(self.conveyor_next_shift - self.game_time))
        rect = pygame.Rect(GRID_X, GRID_Y - 34, 286, 28)
        urgent = remaining <= 3
        pygame.draw.rect(self.screen, (72, 35, 28) if urgent else (54, 45, 38), rect, border_radius=7)
        pygame.draw.rect(self.screen, (255, 112, 72) if urgent else COLORS["gold"], rect, 2, border_radius=7)
        text = self.font_xs.render(f"回转烤盘 · {remaining} 秒后全体右移", True, COLORS["paper"])
        self.screen.blit(text, text.get_rect(center=rect.center))

    def _draw_order_status(self) -> None:
        rect = pygame.Rect(GRID_X, GRID_Y - 38, 430, 32)
        active = self.order_unit is not None
        urgent = active and self.order_deadline - self.game_time <= 3.0
        base = (91, 39, 31) if urgent else ((73, 54, 37) if active else (48, 43, 39))
        border = (255, 108, 76) if urgent else COLORS["gold"]
        pygame.draw.rect(self.screen, base, rect, border_radius=7)
        pygame.draw.rect(self.screen, border, rect, 2, border_radius=7)
        if self.final_wave_started:
            label = f"催单结束 · 已完成 {self.orders_completed} · 专心守住最后一波"
        elif active:
            remaining = max(0, math.ceil(self.order_deadline - self.game_time))
            icon = pygame.transform.smoothscale(self.card_images[self.order_unit], (26, 26))
            self.screen.blit(icon, (rect.x + 5, rect.y + 3))
            label = f"限时订单：放置 {UNITS[self.order_unit].name} · {remaining}s · 奖励 {self.level_config.order_reward} 炭火"
        else:
            remaining = max(0, math.ceil(self.order_next_time - self.game_time))
            label = f"催单板 · 下一份订单 {remaining}s · 已完成 {self.orders_completed}"
        text = self.font_xs.render(label, True, COLORS["paper"])
        center_x = rect.centerx + (14 if active else 0)
        self.screen.blit(text, text.get_rect(center=(center_x, rect.centery)))

    def _draw_reverse_hud(self) -> None:
        rect = pygame.Rect(18, HEIGHT - 74, 330, 60)
        self._draw_themed_panel(rect, (47, 36, 31), (151, 91, 58), metal=True)
        title = self.font_xs.render("僵尸夜宵突袭", True, (255, 197, 102))
        stats = self.font_xs.render(
            f"吃掉 {self.reverse_eaten_units}  ·  损失 {self.reverse_zombies_lost}  ·  固定防线不会补充",
            True,
            COLORS["paper"],
        )
        self.screen.blit(title, (rect.x + 14, rect.y + 9))
        self.screen.blit(stats, (rect.x + 14, rect.y + 32))

    def _draw_dragged_enemy(self) -> None:
        if self.dragging_enemy is None:
            return
        image = pygame.transform.smoothscale(self.enemy_card_images[self.dragging_enemy], (66, 78)).copy()
        image.set_alpha(178)
        self.screen.blit(image, image.get_rect(center=self.drag_position))
        affordable = self.charcoal >= REVERSE_ZOMBIE_COSTS[self.dragging_enemy]
        pygame.draw.circle(
            self.screen,
            (255, 186, 68) if affordable else (229, 68, 55),
            self.drag_position,
            41,
            3,
        )

    def _roulette_rect(self) -> pygame.Rect:
        return pygame.Rect(48, GRID_Y + 72, 190, 190)

    def _oil_inventory_rect(self) -> pygame.Rect:
        return pygame.Rect(18, HEIGHT - 74, 122, 60)

    def _oil_buy_rect(self) -> pygame.Rect:
        return pygame.Rect(146, HEIGHT - 66, 132, 44)

    def _draw_oil_hud(self) -> None:
        inventory = self._oil_inventory_rect()
        active = self.ultimate_mode
        pygame.draw.rect(self.screen, (67, 46, 31), inventory, border_radius=8)
        pygame.draw.rect(self.screen, COLORS["gold"] if active else (145, 102, 64), inventory, 3 if active else 2, border_radius=8)
        icon = pygame.transform.smoothscale(self.oil_image, (48, 48))
        self.screen.blit(icon, (inventory.x + 5, inventory.y + 5))
        count = self.font_sm.render(f"{self.oil_inventory}/{self.oil_capacity}", True, COLORS["paper"])
        self.screen.blit(count, count.get_rect(center=(inventory.x + 87, inventory.centery - 7)))
        action = self.font_xs.render("选大招" if not active else "点肉肉", True, (255, 211, 105))
        self.screen.blit(action, action.get_rect(center=(inventory.x + 87, inventory.centery + 15)))
        buy = self._oil_buy_rect()
        enabled = self.oil_inventory < self.oil_capacity and self.coins >= OIL_BOTTLE_PRICE
        pygame.draw.rect(self.screen, (202, 145, 55) if enabled else (67, 61, 57), buy, border_radius=8)
        pygame.draw.rect(self.screen, (255, 230, 168), buy, 1, border_radius=8)
        label = self.font_xs.render(f"购买 {OIL_BOTTLE_PRICE} 金币", True, COLORS["black"] if enabled else COLORS["muted"])
        self.screen.blit(label, label.get_rect(center=buy.center))

    def _draw_progress_bar(self) -> None:
        rect = pygame.Rect(WIDTH - 330, 68, 300, 16)
        if self.is_reverse_mode:
            hits = self.reverse_core_max_hp - self.reverse_core_hp
            progress = hits / max(1, self.reverse_core_max_hp)
            pygame.draw.rect(self.screen, (47, 38, 34), rect, border_radius=8)
            fill = rect.copy()
            fill.width = int(rect.width * progress)
            pygame.draw.rect(self.screen, (173, 65, 46), fill, border_radius=8)
            if fill.width > 4:
                pygame.draw.line(self.screen, (255, 151, 77), (fill.x + 3, fill.y + 3), (fill.right - 3, fill.y + 3), 2)
            pygame.draw.rect(self.screen, (229, 194, 132), rect, 1, border_radius=8)
            label = self.font_xs.render(
                f"已突破 {hits}/{self.reverse_core_max_hp} · 无时间限制",
                True,
                COLORS["paper"],
            )
            self.screen.blit(label, (rect.x, rect.y + 18))
            return
        progress = 0 if self.total_enemies <= 0 else self.defeated_enemies / self.total_enemies
        pygame.draw.rect(self.screen, (54, 44, 38), rect, border_radius=8)
        fill = rect.copy()
        fill.width = int(rect.width * max(0.0, min(1.0, progress)))
        pygame.draw.rect(self.screen, (255, 183, 72), fill, border_radius=8)
        pygame.draw.rect(self.screen, (255, 239, 191), rect, 1, border_radius=8)
        final_wave_before = sum(self._wave_size(enemy_types) for _, enemy_types in self.level_config.waves[:-1])
        marker_x = rect.x + int(rect.width * final_wave_before / max(1, self.total_enemies))
        pygame.draw.line(self.screen, (255, 91, 69), (marker_x, rect.y - 7), (marker_x, rect.bottom + 7), 3)
        pygame.draw.polygon(self.screen, (255, 91, 69), [(marker_x, rect.y - 9), (marker_x - 6, rect.y - 18), (marker_x + 6, rect.y - 18)])
        label = self.font_xs.render("关卡进度", True, COLORS["paper"])
        self.screen.blit(label, (rect.x, rect.y + 18))

    def _draw_wave_warning(self) -> None:
        alpha = int(150 + 70 * max(0.0, min(1.0, self.final_wave_timer / 2.8)))
        panel = pygame.Surface((420, 76), pygame.SRCALPHA)
        pygame.draw.rect(panel, (120, 42, 35, alpha), panel.get_rect(), border_radius=8)
        pygame.draw.rect(panel, (255, 198, 84, 230), panel.get_rect(), 3, border_radius=8)
        text = self.font_lg.render("最后一波！", True, COLORS["paper"])
        panel.blit(text, text.get_rect(center=(210, 38)))
        self.screen.blit(panel, (WIDTH // 2 - 210, 128))

    def _draw_info_overlay(self) -> None:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))
        panel = pygame.Rect(170, 82, 1260, 560)
        pygame.draw.rect(self.screen, (35, 29, 27), panel, border_radius=8)
        pygame.draw.rect(self.screen, COLORS["gold"], panel, 3, border_radius=8)
        title = self.font_lg.render("游戏简介", True, COLORS["paper"])
        self.screen.blit(title, (panel.x + 34, panel.y + 24))
        intro = (
            "第11关防线会在开局随机摆好并保持不变。用有限军费购买僵尸，吃掉肉肉返还炭火，三次突破即可获胜。"
            if self.is_reverse_mode
            else "点击烧烤架或木炭生成的炭火获得资源；击败僵尸的炭火自动收集。油瓶可释放肉肉大招，每关会清零。"
        )
        intro += " 二阶僵尸的生命、攻击和移速均高于一阶；困难模式会更早、更密集地出现二阶僵尸。"
        self._draw_wrapped_text(
            intro,
            panel.x + 34,
            panel.y + 82,
            1180,
            self.font_sm,
            (255, 204, 132),
            24,
        )
        self._draw_info_units(panel.x + 34, panel.y + 128)
        self._draw_info_enemies(panel.x + 690, panel.y + 128)
        self._draw_button(self._button_rect("close_info"), "关闭", True)

    def _draw_info_units(self, x: int, y: int) -> None:
        heading = self.font_md.render("肉肉守卫", True, COLORS["gold"])
        self.screen.blit(heading, (x, y))
        for index, key in enumerate(UNIT_ORDER):
            config = UNITS[key]
            top = y + 36 + index * 37
            rect = pygame.Rect(x, top, 600, 34)
            pygame.draw.rect(self.screen, (55, 45, 39), rect, border_radius=8)
            pygame.draw.rect(self.screen, (103, 78, 55), rect, 1, border_radius=8)
            image = pygame.transform.smoothscale(self.card_images[key], (28, 28))
            self.screen.blit(image, (rect.x + 5, rect.y + 3))
            cd = "无" if config.cooldown <= 0 else f"{config.cooldown:g}s"
            place_cd = UNIT_PLACEMENT_COOLDOWNS[key]
            line = f"{config.name}  费用:{config.cost}  生命:{config.hp}  攻击:{config.damage}  攻/产:{cd}  放置:{place_cd:g}s"
            line = self._fit_text(line, self.font_xs, rect.width - 48)
            line_s = self.font_xs.render(line, True, COLORS["paper"])
            self.screen.blit(line_s, (rect.x + 40, rect.y + 8))

    def _draw_info_enemies(self, x: int, y: int) -> None:
        heading = self.font_md.render("僵尸分类", True, COLORS["gold"])
        self.screen.blit(heading, (x, y))
        for index, key in enumerate(ENEMY_ORDER):
            config = ENEMIES[key]
            col = index % 2
            row = index // 2
            rect = pygame.Rect(x + col * 264, y + 40 + row * 91, 254, 82)
            pygame.draw.rect(self.screen, (55, 45, 39), rect, border_radius=8)
            pygame.draw.rect(self.screen, (103, 78, 55), rect, 1, border_radius=8)
            image = load_image(config.image, (46, 62))
            self.screen.blit(image, (rect.x + 8, rect.y + 10))
            name = self.font_xs.render(config.name, True, COLORS["paper"])
            stats1 = self.font_xs.render(f"生命 {config.hp}  攻击 {config.damage}", True, (232, 211, 177))
            stats2 = self.font_xs.render(f"移速 {config.speed:g}  奖励 {config.reward}", True, (255, 201, 105))
            self.screen.blit(name, (rect.x + 60, rect.y + 8))
            self.screen.blit(stats1, (rect.x + 60, rect.y + 31))
            self.screen.blit(stats2, (rect.x + 60, rect.y + 54))

    def _draw_tuning_overlay(self, return_to_menu: bool) -> None:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 176))
        self.screen.blit(overlay, (0, 0))
        panel = pygame.Rect(120, 62, 1360, 594)
        pygame.draw.rect(self.screen, (31, 27, 25), panel, border_radius=8)
        pygame.draw.rect(self.screen, COLORS["gold"], panel, 3, border_radius=8)
        title = self.font_lg.render(f"第 {self.selected_level} 关设置与调参", True, COLORS["paper"])
        self.screen.blit(title, (panel.x + 32, panel.y + 24))
        note = "资源、肉肉和僵尸参数仅影响本关；声音设置全局生效。初始炭火值在重开后生效。"
        self._draw_wrapped_text(note, panel.x + 32, panel.y + 82, 780, self.font_sm, (255, 204, 132), 24)
        for i, (tab, label) in enumerate([("resources", "资源"), ("units", "肉肉"), ("enemies", "僵尸"), ("audio", "声音")]):
            rect = self._tuning_tab_rect(i)
            active = self.tuning_tab == tab
            pygame.draw.rect(self.screen, COLORS["gold"] if active else (76, 61, 49), rect, border_radius=8)
            pygame.draw.rect(self.screen, (255, 239, 191), rect, 2, border_radius=8)
            text = self.font_md.render(label, True, COLORS["black"] if active else COLORS["paper"])
            self.screen.blit(text, text.get_rect(center=rect.center))
        self.tuning_controls = []
        if self.tuning_tab == "resources":
            items = self._resource_tuning_items()
        elif self.tuning_tab == "units":
            items = self._unit_tuning_items()
        elif self.tuning_tab == "enemies":
            items = self._enemy_tuning_items()
        else:
            items = self._audio_tuning_items()
        start_x = panel.x + 44
        dense = len(items) > 20
        start_y = panel.y + (114 if dense else 126)
        row_h = 20 if dense else 24
        rows_per_col = 20 if len(items) > 20 else 18
        col_width = 630 if len(items) > 20 else 1010
        for index, item in enumerate(items):
            label, value, change = item
            col = index // rows_per_col
            row = index % rows_per_col
            x = start_x + col * col_width
            y = start_y + row * row_h
            if row % 2 == 0:
                pygame.draw.rect(self.screen, (45, 38, 34), (x - 10, y - 2, col_width - 24, row_h - 2), border_radius=5)
            label_s = self.font_xs.render(label, True, COLORS["paper"])
            value_s = self.font_xs.render(value, True, COLORS["gold"])
            self.screen.blit(label_s, (x, y))
            self.screen.blit(value_s, (x + 310, y))
            button_y = y - 1 if dense else y - 3
            button_h = 18 if dense else 22
            minus = pygame.Rect(x + 390, button_y, 38, button_h)
            plus = pygame.Rect(x + 438, button_y, 38, button_h)
            self._draw_small_step_button(minus, "-")
            self._draw_small_step_button(plus, "+")
            self.tuning_controls.append(TuningControl(label, value, minus, plus, change))
        self._draw_button(self._button_rect("close_tuning"), "关闭", True)

    def _draw_small_step_button(self, rect: pygame.Rect, text: str) -> None:
        pygame.draw.rect(self.screen, (88, 71, 56), rect, border_radius=6)
        pygame.draw.rect(self.screen, (255, 239, 191), rect, 1, border_radius=6)
        label = self.font_sm.render(text, True, COLORS["paper"])
        self.screen.blit(label, label.get_rect(center=rect.center))

    def _resource_tuning_items(self) -> list[tuple[str, str, Callable[[int], None]]]:
        if self.is_reverse_mode:
            return [
                ("初始炭火军费", str(self.reverse_starting_charcoal), lambda direction: self._change_attr("reverse_starting_charcoal", direction, 10, 35, 999, True)),
                ("吃肉返还比例", f"{self.reverse_reward_percent}%", lambda direction: self._change_attr("reverse_reward_percent", direction, 5, 20, 100, True)),
            ]
        return [
            ("初始炭火值", str(self.initial_charcoal), lambda direction: self._change_attr("initial_charcoal", direction, 25, 0, 999, True)),
            ("烧烤架生成间隔(秒，越小越快)", f"{self.grill_interval:.1f}", lambda direction: self._change_attr("grill_interval", direction, 0.5, 1.0, 30.0, False)),
            ("烧烤架每次生成量", str(self.grill_pickup_value), lambda direction: self._change_attr("grill_pickup_value", direction, 5, 5, 200, True)),
            ("木炭每次生成量", str(self.charcoal_unit_value), lambda direction: self._change_attr("charcoal_unit_value", direction, 5, 5, 200, True)),
            ("炭火消失时间(秒)", f"{self.pickup_ttl:.1f}", lambda direction: self._change_attr("pickup_ttl", direction, 0.5, 2.0, 20.0, False)),
        ]

    def _unit_tuning_items(self) -> list[tuple[str, str, Callable[[int], None]]]:
        items: list[tuple[str, str, Callable[[int], None]]] = []
        for key in UNIT_ORDER:
            config = UNITS[key]
            base = self.base_unit_stats[key]
            items.extend(
                [
                    (f"{config.name} - 基准所需炭火", str(base["cost"]), lambda direction, k=key: self._change_config(UNITS[k], "cost", direction, 5, 0, 999, True)),
                    (f"{config.name} - 基准生命值", str(base["hp"]), lambda direction, k=key: self._change_config(UNITS[k], "hp", direction, 10, 1, 2000, True)),
                    (f"{config.name} - 基准攻击力", str(base["damage"]), lambda direction, k=key: self._change_config(UNITS[k], "damage", direction, 5, 0, 999, True)),
                    (f"{config.name} - 基准间隔(秒)", f"{base['cooldown']:.1f}", lambda direction, k=key: self._change_config(UNITS[k], "cooldown", direction, 0.1, 0.1, 30.0, False)),
                ]
            )
        return items

    def _enemy_tuning_items(self) -> list[tuple[str, str, Callable[[int], None]]]:
        items: list[tuple[str, str, Callable[[int], None]]] = []
        for key in ENEMY_ORDER:
            config = ENEMIES[key]
            items.extend(
                [
                    (f"{config.name} - 生命值", str(config.hp), lambda direction, k=key: self._change_config(ENEMIES[k], "hp", direction, 10, 1, 5000, True)),
                    (f"{config.name} - 移速", f"{config.speed:.1f}", lambda direction, k=key: self._change_config(ENEMIES[k], "speed", direction, 2.0, 5.0, 200.0, False)),
                    (f"{config.name} - 攻击力", str(config.damage), lambda direction, k=key: self._change_config(ENEMIES[k], "damage", direction, 5, 0, 999, True)),
                    (f"{config.name} - 攻击间隔(秒)", f"{config.cooldown:.1f}", lambda direction, k=key: self._change_config(ENEMIES[k], "cooldown", direction, 0.1, 0.1, 10.0, False)),
                    (f"{config.name} - 击败奖励炭火", str(config.reward), lambda direction, k=key: self._change_config(ENEMIES[k], "reward", direction, 5, 0, 500, True)),
                ]
            )
        return items

    def _audio_tuning_items(self) -> list[tuple[str, str, Callable[[int], None]]]:
        labels = {
            "attack_skewer": "羊肉串发射音量",
            "attack_wing": "鸡翅骨头音量",
            "attack_beef": "冰冻肥牛音量",
            "attack_meatball": "爆汁丸子音量",
            "zombie_spawn": "僵尸出现音量",
            "final_wave": "最后一波警报音量",
        }
        items: list[tuple[str, str, Callable[[int], None]]] = [
            ("背景音乐", "开启" if self.audio.music_enabled else "关闭", self._toggle_music),
            ("背景音乐音量", f"{round(self.audio.music_volume * 100)}%", self._change_music_volume),
            ("游戏音效", "开启" if self.audio.sfx_enabled else "关闭", self._toggle_sfx),
            ("游戏音效总音量", f"{round(self.audio.sfx_volume * 100)}%", self._change_sfx_volume),
        ]
        for name, label in labels.items():
            items.append(
                (
                    label,
                    f"{round(self.audio.effect_volumes[name] * 100)}%",
                    lambda direction, key=name: self._change_effect_volume(key, direction),
                )
            )
        return items

    def _change_attr(self, attr: str, direction: int, step: float, minimum: float, maximum: float, as_int: bool) -> None:
        value = getattr(self, attr) + direction * step
        value = max(minimum, min(maximum, value))
        setattr(self, attr, int(round(value)) if as_int else round(value, 2))
        if attr == "grill_interval":
            self.next_ambient_pickup = min(self.next_ambient_pickup, self.grill_interval)
        self._save_all()

    def _change_config(self, config: object, attr: str, direction: int, step: float, minimum: float, maximum: float, as_int: bool) -> None:
        unit_key = next((key for key, unit_config in UNITS.items() if config is unit_config), None)
        current = self.base_unit_stats[unit_key][attr] if unit_key else getattr(config, attr)
        value = current + direction * step
        value = max(minimum, min(maximum, value))
        value = int(round(value)) if as_int else round(value, 2)
        if unit_key:
            self.base_unit_stats[unit_key][attr] = value
            self._apply_account_upgrades()
            self.cards = self._make_cards()
        else:
            setattr(config, attr, value)
        self._save_all()

    def _toggle_music(self, direction: int) -> None:
        self.audio.set_music_enabled(not self.audio.music_enabled)
        self._save_all()

    def _change_music_volume(self, direction: int) -> None:
        self.audio.set_music_volume(self.audio.music_volume + direction * 0.05)
        self._save_all()

    def _toggle_sfx(self, direction: int) -> None:
        self.audio.sfx_enabled = not self.audio.sfx_enabled
        self._save_all()

    def _change_sfx_volume(self, direction: int) -> None:
        self.audio.set_sfx_volume(self.audio.sfx_volume + direction * 0.05)
        self._save_all()

    def _change_effect_volume(self, key: str, direction: int) -> None:
        self.audio.set_effect_volume(key, self.audio.effect_volumes[key] + direction * 0.05)
        self._save_all()

    def _tuning_tab_rect(self, index: int) -> pygame.Rect:
            return pygame.Rect(900 + index * 124, 92, 104, 42)

    def _draw_wrapped_text(
        self,
        text: str,
        x: int,
        y: int,
        max_width: int,
        font: pygame.font.Font,
        color: tuple[int, int, int],
        line_height: int,
    ) -> int:
        line = ""
        current_y = y
        for char in text:
            candidate = line + char
            if font.size(candidate)[0] <= max_width:
                line = candidate
                continue
            if line:
                self.screen.blit(font.render(line, True, color), (x, current_y))
                current_y += line_height
            line = char
        if line:
            self.screen.blit(font.render(line, True, color), (x, current_y))
            current_y += line_height
        return current_y

    @staticmethod
    def _fit_text(text: str, font: pygame.font.Font, max_width: int) -> str:
        if font.size(text)[0] <= max_width:
            return text
        trimmed = text
        while trimmed and font.size(trimmed + "…")[0] > max_width:
            trimmed = trimmed[:-1]
        return trimmed + "…"

    def _draw_floaters(self) -> None:
        for floater in self.floaters:
            text = self.font_sm.render(floater.text, True, floater.color)
            ratio = max(0.0, min(1.0, floater.ttl / max(0.01, floater.initial_ttl)))
            text.set_alpha(int(255 * ratio))
            self.screen.blit(text, text.get_rect(center=(int(floater.x), int(floater.y))))

    def _ending_scene_key(self, result: str) -> str:
        if self.is_reverse_mode:
            return "lose" if result == "win" else "win"
        return result

    def _draw_ending_background(self, result: str, progress: float) -> None:
        scene_key = self._ending_scene_key(result)
        image = self.ending_images[scene_key]
        eased = 1.0 - (1.0 - max(0.0, min(1.0, progress))) ** 2
        zoom = 1.0 + eased * 0.045
        size = (int(WIDTH * zoom), int(HEIGHT * zoom))
        frame = pygame.transform.smoothscale(image, size)
        x = (WIDTH - size[0]) // 2 + int((eased - 0.5) * 14)
        y = (HEIGHT - size[1]) // 2
        if scene_key == "lose" and progress < 0.72:
            strength = max(0, int(6 * (1.0 - progress / 0.72)))
            x += self.random.randint(-strength, strength)
            y += self.random.randint(-strength, strength)
        self.screen.blit(frame, (x, y))

        particles = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        tick = pygame.time.get_ticks()
        if scene_key == "win":
            for index in range(34):
                px = (index * 149 + tick // 7) % WIDTH
                py = HEIGHT - ((index * 83 + tick // 4) % (HEIGHT + 90))
                radius = 1 + index % 3
                pygame.draw.circle(particles, (255, 161 + index % 70, 58, 155), (px, py), radius)
            for index in range(8):
                px = 160 + (index * 211) % 1260
                py = 560 - ((tick // 22 + index * 47) % 180)
                pygame.draw.circle(particles, (235, 238, 224, 20), (px, py), 35 + index * 4)
        else:
            for index in range(12):
                px = (index * 173 + tick // 35) % WIDTH
                py = 560 - ((index * 51 + tick // 28) % 260)
                pygame.draw.circle(particles, (48, 54, 60, 58), (px, py), 28 + index * 5)
            pulse = int(18 + 18 * abs(math.sin(tick / 180.0)))
            particles.fill((105, 12, 8, pulse), special_flags=pygame.BLEND_RGBA_ADD)
        self.screen.blit(particles, (0, 0))

    def _draw_ending_animation(self) -> None:
        result = self.ending_result or "lose"
        progress = min(1.0, self.ending_timer / ENDING_ANIMATION_DURATION)
        self._draw_ending_background(result, progress)
        bars = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(bars, (0, 0, 0, 220), (0, 0, WIDTH, 46))
        pygame.draw.rect(bars, (0, 0, 0, 220), (0, HEIGHT - 46, WIDTH, 46))
        self.screen.blit(bars, (0, 0))
        fade_alpha = int(255 * max(0.0, 1.0 - progress / 0.18))
        if fade_alpha:
            fade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            fade.fill((0, 0, 0, fade_alpha))
            self.screen.blit(fade, (0, 0))
        if progress >= 0.28:
            if self.is_reverse_mode:
                title = "突袭成功" if result == "win" else "突袭失败"
                subtitle = "烤炉防线已经攻破" if result == "win" else "系统摊主守住了最后一炉"
            else:
                title = "守卫成功" if result == "win" else "守卫失败"
                subtitle = "烧烤摊重新燃起炉火" if result == "win" else "僵尸摧毁了夜市烧烤摊"
            alpha = min(255, int((progress - 0.28) / 0.18 * 255))
            title_surface = self.font_title.render(title, True, COLORS["paper"])
            subtitle_surface = self.font_md.render(subtitle, True, (255, 190, 116))
            title_surface.set_alpha(alpha)
            subtitle_surface.set_alpha(alpha)
            self.screen.blit(title_surface, title_surface.get_rect(center=(WIDTH // 2, 176)))
            self.screen.blit(subtitle_surface, subtitle_surface.get_rect(center=(WIDTH // 2, 244)))

    def _draw_end_overlay(self) -> None:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 126))
        self.screen.blit(overlay, (0, 0))
        panel = pygame.Rect(WIDTH // 2 - 390, 116, 780, 444)
        self._draw_themed_panel(panel, (43, 35, 31), (229, 166, 69), metal=False)
        if self.is_reverse_mode:
            title = "夜宵突袭成功" if self.state == "win" else "夜宵突袭失败"
            result_line = "烤炉防线已经攻破" if self.state == "win" else "系统摊主守住了烤炉"
        else:
            title = "守卫成功" if self.state == "win" else "守卫失败"
            result_line = f"第 {self.selected_level} 关已通过" if self.state == "win" else "僵尸冲进烧烤摊了"
        title_surface = self.font_lg.render(title, True, COLORS["paper"])
        result_surface = self.font_md.render(result_line, True, (255, 190, 116))
        self.screen.blit(title_surface, title_surface.get_rect(center=(panel.centerx, panel.y + 70)))
        self.screen.blit(result_surface, result_surface.get_rect(center=(panel.centerx, panel.y + 126)))

        reward_panel = pygame.Rect(panel.centerx - 150, panel.y + 166, 300, 78)
        pygame.draw.rect(self.screen, (28, 24, 21), reward_panel, border_radius=6)
        pygame.draw.rect(self.screen, (187, 132, 51), reward_panel, 2, border_radius=6)
        self.screen.blit(self.coin_image, self.coin_image.get_rect(center=(reward_panel.x + 55, reward_panel.centery)))
        reward_label = self.font_xs.render("本关获得奖励", True, COLORS["muted"])
        reward_value = self.font_md.render(f"{self.level_reward} 金币", True, (255, 220, 104))
        self.screen.blit(reward_label, (reward_panel.x + 92, reward_panel.y + 12))
        self.screen.blit(reward_value, (reward_panel.x + 92, reward_panel.y + 36))

        if self.state == "win":
            if self.selected_difficulty == DIFFICULTY_HARD:
                unlock_text = "困难模式已通关，奖励已提高"
            elif self.selected_level == len(LEVELS):
                unlock_text = "普通模式已通关，困难模式已解锁"
            else:
                unlock_text = f"本关困难模式与第 {self.selected_level + 1} 关普通模式已解锁"
        else:
            unlock_text = "返回关卡选择，可调整难度或重玩前面关卡"
        unlock_surface = self.font_sm.render(unlock_text, True, COLORS["paper"])
        self.screen.blit(unlock_surface, unlock_surface.get_rect(center=(panel.centerx, panel.y + 282)))
        if self.state == "win" and self._next_result_target() is not None:
            self._draw_button(self._button_rect("next_level"), "下一关", True)
        self._draw_button(self._button_rect("restart"), "重玩本关", self.state != "win" or self._next_result_target() is None)
        self._draw_button(self._button_rect("menu"), "返回关卡选择", False)

    def _draw_exit_overlay(self) -> None:
        self._draw_modal_backdrop()
        panel = pygame.Rect(WIDTH // 2 - 320, HEIGHT // 2 - 150, 640, 300)
        self._draw_themed_panel(panel, (44, 35, 31), (222, 159, 66), metal=False)
        title = self.font_lg.render("退出本关？", True, COLORS["paper"])
        detail = self.font_sm.render("当前关卡进度不会保留，也不会获得通关奖励。", True, (255, 190, 116))
        self.screen.blit(title, title.get_rect(center=(panel.centerx, panel.y + 78)))
        self.screen.blit(detail, detail.get_rect(center=(panel.centerx, panel.y + 140)))
        self._draw_button(self._button_rect("exit_confirm_yes"), "退出关卡", True)
        self._draw_button(self._button_rect("exit_confirm_no"), "继续守摊", False)

    def _draw_center_banner(self, title: str, subtitle: str) -> None:
        panel = pygame.Rect(0, 210, 620, 172)
        panel.centerx = WIDTH // 2
        pygame.draw.rect(self.screen, (44, 36, 34), panel, border_radius=8)
        pygame.draw.rect(self.screen, COLORS["gold"], panel, 3, border_radius=8)
        title_s = self.font_lg.render(title, True, COLORS["paper"])
        sub_s = self.font_md.render(subtitle, True, (255, 190, 116))
        self.screen.blit(title_s, title_s.get_rect(center=(WIDTH // 2, panel.y + 62)))
        self.screen.blit(sub_s, sub_s.get_rect(center=(WIDTH // 2, panel.y + 118)))

    def _button_rect(self, name: str) -> pygame.Rect:
        if name == "home_start":
            return pygame.Rect(WIDTH // 2 - 180, 292, 360, 66)
        if name == "home_info":
            return pygame.Rect(WIDTH // 2 - 190, 388, 180, 54)
        if name == "home_reset":
            return pygame.Rect(WIDTH // 2 + 10, 388, 180, 54)
        if name == "start":
            return pygame.Rect(WIDTH // 2 - 170, 496, 340, 54)
        if name == "difficulty_normal":
            return pygame.Rect(WIDTH // 2 - 220, 448, 210, 38)
        if name == "difficulty_hard":
            return pygame.Rect(WIDTH // 2 + 10, 448, 210, 38)
        if name == "menu_tuning":
            return pygame.Rect(WIDTH // 2 - 290, 562, 180, 48)
        if name == "shop":
            return pygame.Rect(WIDTH // 2 - 90, 562, 180, 48)
        if name == "skills":
            return pygame.Rect(WIDTH // 2 + 110, 562, 180, 48)
        if name == "account":
            return pygame.Rect(WIDTH - 305, 20, 280, 48)
        if name == "pause":
            return pygame.Rect(WIDTH - 410, 18, 70, 36)
        if name == "restart_play":
            return pygame.Rect(WIDTH - 330, 18, 70, 36)
        if name == "exit_play":
            return pygame.Rect(WIDTH - 250, 18, 70, 36)
        if name == "info":
            return pygame.Rect(WIDTH - 170, 18, 70, 36)
        if name == "tuning":
            return pygame.Rect(WIDTH - 90, 18, 70, 36)
        if name == "close_info":
            return pygame.Rect(1270, 98, 120, 42)
        if name == "close_tuning":
            return pygame.Rect(WIDTH // 2 - 70, 594, 140, 46)
        if name == "restart":
            if self.state == "win" and self._next_result_target() is not None:
                return pygame.Rect(WIDTH // 2 - 110, 470, 220, 58)
            return pygame.Rect(WIDTH // 2 - 230, 470, 220, 58)
        if name == "next_level":
            return pygame.Rect(WIDTH // 2 - 350, 470, 220, 58)
        if name == "menu":
            return pygame.Rect(WIDTH // 2 + (130 if self.state == "win" and self._next_result_target() is not None else 10), 470, 220, 58)
        if name == "exit_confirm_yes":
            return pygame.Rect(WIDTH // 2 - 230, HEIGHT // 2 + 70, 220, 54)
        if name == "exit_confirm_no":
            return pygame.Rect(WIDTH // 2 + 10, HEIGHT // 2 + 70, 220, 54)
        if name == "login_confirm":
            return pygame.Rect(WIDTH // 2 - 110, HEIGHT // 2 + 198, 220, 52)
        if name == "login_back":
            return pygame.Rect(WIDTH // 2 - 340, HEIGHT // 2 + 198, 150, 52)
        if name == "login_rename":
            return pygame.Rect(WIDTH // 2 + 190, HEIGHT // 2 - 258, 160, 38)
        if name == "login_prev":
            return pygame.Rect(WIDTH // 2 - 170, HEIGHT // 2 + 20, 130, 38)
        if name == "login_next":
            return pygame.Rect(WIDTH // 2 + 40, HEIGHT // 2 + 20, 130, 38)
        if name == "screen_back":
            return pygame.Rect(70, HEIGHT - 62, 150, 44)
        if name == "loadout_start":
            return pygame.Rect(WIDTH // 2 - 150, HEIGHT - 62, 300, 44)
        if name == "reset_confirm":
            return pygame.Rect(WIDTH // 2 - 240, HEIGHT // 2 + 72, 210, 52)
        if name == "reset_cancel":
            return pygame.Rect(WIDTH // 2 + 30, HEIGHT // 2 + 72, 210, 52)
        return pygame.Rect(WIDTH // 2 + 65, HEIGHT // 2 + 82, 140, 52)

    def _level_rect(self, index: int) -> pygame.Rect:
        width = 244
        gap = 16
        columns = 5
        total_width = width * columns + gap * (columns - 1)
        col = index % columns
        row = index // columns
        return pygame.Rect((WIDTH - total_width) // 2 + col * (width + gap), 160 + row * 96, width, 88)

    def _login_account_rect(self, index: int) -> pygame.Rect:
        panel_x = WIDTH // 2 - 380
        panel_y = HEIGHT // 2 - 280
        col = index % 2
        row = index // 2
        return pygame.Rect(panel_x + 50 + col * 335, panel_y + 136 + row * 54, 315, 44)

    def _unit_library_rect(self, index: int) -> pygame.Rect:
        col = index % 2
        row = index // 2
        return pygame.Rect(70 + col * 760, 122 + row * 103, 700, 90)

    def _shop_buy_rect(self, index: int) -> pygame.Rect:
        card = self._unit_library_rect(index)
        return pygame.Rect(card.right - 132, card.y + 8, 118, 34)

    def _skill_upgrade_rect(self, index: int) -> pygame.Rect:
        return self._shop_buy_rect(index)

    def _draw_button(self, rect: pygame.Rect, text: str, primary: bool) -> None:
        mouse = pygame.mouse.get_pos()
        hover = rect.collidepoint(mouse)
        pressed = hover and pygame.mouse.get_pressed()[0]
        color = COLORS["gold"] if primary else (97, 92, 86)
        offset = 0
        if hover:
            color = tuple(min(255, c + 22) for c in color)
            offset = 2 if pressed else -2
        shadow = rect.move(0, 4)
        pygame.draw.rect(self.screen, (20, 18, 16), shadow, border_radius=8)
        main_rect = rect.move(0, offset)
        pygame.draw.rect(self.screen, color, main_rect, border_radius=8)
        pygame.draw.rect(self.screen, (255, 239, 191), main_rect, 2, border_radius=8)
        font = self.font_sm if rect.width <= 90 else self.font_md
        label = font.render(text, True, COLORS["black"] if primary else COLORS["paper"])
        self.screen.blit(label, label.get_rect(center=main_rect.center))
