from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SOURCE_DIR = Path(__file__).resolve().parent
BASE_DIR = SOURCE_DIR if (SOURCE_DIR / "assets").is_dir() else SOURCE_DIR.parent
ASSET_DIR = BASE_DIR / "assets"
IMAGE_DIR = ASSET_DIR / "images"
AUDIO_DIR = ASSET_DIR / "audio"
FONT_DIR = ASSET_DIR / "fonts"

WIDTH = 1600
HEIGHT = 720
FPS = 60

TOP_BAR_HEIGHT = 132
GRID_ROWS = 5
GRID_COLS = 11
PLACEABLE_COLS = 10
CELL_SIZE = 82
GRID_X = (WIDTH - GRID_COLS * CELL_SIZE) // 2
GRID_Y = TOP_BAR_HEIGHT + (HEIGHT - TOP_BAR_HEIGHT - GRID_ROWS * CELL_SIZE) // 2
LANE_HEIGHT = CELL_SIZE
DEFENSE_LINE_X = GRID_X - 68
SPAWN_X = GRID_X + GRID_COLS * CELL_SIZE + 34

GAME_DURATION = 110.0
STARTING_CHARCOAL = 100
MAX_CHARCOAL = 999
AMBIENT_CHARCOAL_MIN_SECONDS = 5.0
AMBIENT_CHARCOAL_MAX_SECONDS = 8.5
CHARCOAL_PICKUP_TTL = 7.0
CHARCOAL_PICKUP_VALUE = 25
CHARCOAL_UNIT_COOLDOWN = 8.0
OIL_BOTTLE_PRICE = 100
OIL_CAPACITY_UPGRADE_COSTS = [150, 250, 400]
MAX_OIL_CAPACITY = 6
ENDING_ANIMATION_DURATION = 3.2
EGG_MINE_DEPLOY_HP = 1

REVERSE_STARTING_CHARCOAL = 300
REVERSE_CORE_HP = 3
REVERSE_ZOMBIE_ORDER = ["baby", "normal", "courier", "pot", "drunk", "butcher", "giant", "boss"]
REVERSE_ZOMBIE_COSTS = {
    "baby": 35,
    "normal": 60,
    "courier": 80,
    "pot": 110,
    "drunk": 125,
    "butcher": 180,
    "giant": 240,
    "boss": 300,
}
REVERSE_DEFENDER_POOL = ["charcoal", "skewer", "wall", "wing", "beef", "scallop", "sausage", "lotus"]
REVERSE_DEFENDERS_PER_LANE = 4
REVERSE_HARD_DEFENDERS_PER_LANE = 5

DIFFICULTY_NORMAL = "normal"
DIFFICULTY_HARD = "hard"
HARD_REWARD_MULTIPLIER = 1.8
TIER_TWO_HP_MULTIPLIER = 1.55
TIER_TWO_DAMAGE_MULTIPLIER = 1.35
TIER_TWO_SPEED_MULTIPLIER = 1.18
TIER_TWO_REWARD_MULTIPLIER = 1.5
LATE_GAME_TIER_START_LEVEL = 11


@dataclass
class UnitConfig:
    key: str
    name: str
    cost: int
    hp: int
    damage: int
    cooldown: float
    image: str
    description: str


@dataclass
class EnemyConfig:
    key: str
    name: str
    hp: int
    speed: float
    damage: int
    cooldown: float
    reward: int
    image: str
    description: str


@dataclass(frozen=True)
class LevelConfig:
    number: int
    name: str
    description: str
    waves: list[tuple[float, list[str]]]
    oil_drops: int = 1
    special: str = ""
    roulette_interval: float = 0.0
    conveyor_interval: float = 0.0
    order_interval: float = 0.0
    order_time_limit: float = 0.0
    order_reward: int = 0


UNITS: dict[str, UnitConfig] = {
    "skewer": UnitConfig("skewer", "羊肉串射手", 100, 100, 20, 1.2, "skewer.png", "同行远程输出，优先攻击最近僵尸。"),
    "wall": UnitConfig("wall", "五花肉墙", 75, 400, 0, 0.0, "pork_wall.png", "高生命阻挡单位，用来拖住僵尸。"),
    "meatball": UnitConfig("meatball", "爆汁丸子", 125, 80, 120, 1.0, "meatball.png", "放置 1 秒后爆炸，伤害同行左右 3 格。"),
    "charcoal": UnitConfig("charcoal", "木炭", 50, 120, 0, CHARCOAL_UNIT_COOLDOWN, "charcoal.png", "资源单位，定期生成可点击炭火。"),
    "wing": UnitConfig("wing", "烤鸡翅", 150, 120, 14, 0.55, "wing.png", "投出鸡翅骨头并回旋返程，可对同一目标造成二次伤害。"),
    "beef": UnitConfig("beef", "冰镇肥牛", 125, 100, 8, 1.1, "beef.png", "发射带冰霜轨迹的肥牛卷，命中后短暂减速僵尸。"),
    "egg_mine": UnitConfig("egg_mine", "鸡蛋地雷", 75, 80, 200, 5.0, "egg_mine.png", "部署前仅 1 点生命；5 秒后完成部署，僵尸踩中时造成 200 点范围伤害并自毁。"),
    "scallop": UnitConfig("scallop", "蒜香扇贝", 125, 105, 24, 1.4, "scallop.png", "发射蒜蓉弹，命中后会对目标附近的僵尸造成溅射伤害。"),
    "sausage": UnitConfig("sausage", "辣椒烤肠", 175, 110, 45, 2.6, "sausage.png", "喷出穿透整行的辣椒火焰，可同时灼伤多个僵尸。"),
    "lotus": UnitConfig("lotus", "糯米藕盒", 100, 260, 0, 6.0, "lotus.png", "周期治疗上下左右相邻肉肉，每次恢复 35 点生命。"),
}

# Placement cadence is independent from each unit's attack or production interval.
UNIT_PLACEMENT_COOLDOWNS: dict[str, float] = {
    "charcoal": 3.0,
    "skewer": 5.0,
    "beef": 6.0,
    "wing": 7.0,
    "scallop": 7.0,
    "lotus": 8.0,
    "meatball": 8.0,
    "egg_mine": 8.0,
    "sausage": 8.0,
    "wall": 15.0,
}

UNIT_ORDER = [
    "charcoal", "wall", "egg_mine", "skewer", "lotus",
    "meatball", "beef", "scallop", "wing", "sausage",
]

DEFAULT_OWNED_UNITS = ["charcoal", "wall", "skewer", "meatball", "beef", "wing"]
UNIT_COIN_PRICES = {
    "egg_mine": 40,
    "scallop": 60,
    "lotus": 70,
    "sausage": 80,
}
LEVEL_COIN_REWARDS = [20, 30, 45, 65, 90, 120, 150, 190, 240, 350, 450, 560, 700, 850, 1200]
UPGRADE_COSTS = [10, 20, 35, 60, 90, 130, 180]
MAX_LOADOUT_SIZE = 6

# Each path contains seven cumulative multipliers tailored to the unit's role.
UNIT_UPGRADE_PATHS: dict[str, list[tuple[str, float, str]]] = {
    "charcoal": [
        ("cost", 0.95, "费用 -5%"),
        ("cooldown", 0.90, "产炭间隔 -10%"),
        ("hp", 1.20, "生命 +20%"),
        ("cooldown", 0.88, "产炭间隔再 -12%"),
        ("cost", 0.92, "费用再 -8%"),
        ("hp", 1.25, "生命再 +25%"),
        ("cooldown", 0.85, "旺火间隔再 -15%"),
    ],
    "wall": [
        ("cost", 0.95, "费用 -5%"),
        ("hp", 1.18, "生命 +18%"),
        ("hp", 1.20, "生命再 +20%"),
        ("cost", 0.92, "费用再 -8%"),
        ("hp", 1.22, "生命再 +22%"),
        ("hp", 1.25, "生命再 +25%"),
        ("hp", 1.30, "终极厚切：生命 +30%"),
    ],
    "egg_mine": [
        ("cost", 0.95, "费用 -5%"),
        ("cooldown", 0.90, "部署时间 -10%"),
        ("damage", 1.15, "爆炸伤害 +15%"),
        ("cooldown", 0.85, "部署时间再 -15%"),
        ("damage", 1.20, "爆炸伤害再 +20%"),
        ("hp", 1.30, "部署后生命 +30%"),
        ("damage", 1.25, "终极爆破：伤害 +25%"),
    ],
    "skewer": [
        ("cost", 0.95, "费用 -5%"),
        ("cooldown", 0.90, "射击间隔 -10%"),
        ("damage", 1.15, "羊肉块伤害 +15%"),
        ("cooldown", 0.88, "射击间隔再 -12%"),
        ("damage", 1.18, "羊肉块伤害再 +18%"),
        ("hp", 1.20, "生命 +20%"),
        ("damage", 1.25, "终极火候：伤害 +25%"),
    ],
    "lotus": [
        ("cost", 0.95, "费用 -5%"),
        ("cooldown", 0.90, "治疗间隔 -10%"),
        ("hp", 1.20, "生命 +20%"),
        ("cooldown", 0.85, "治疗间隔再 -15%"),
        ("hp", 1.22, "生命再 +22%"),
        ("cost", 0.92, "费用再 -8%"),
        ("cooldown", 0.82, "终极治愈：间隔 -18%"),
    ],
    "meatball": [
        ("cost", 0.95, "费用 -5%"),
        ("cooldown", 0.90, "引爆时间 -10%"),
        ("damage", 1.18, "爆汁伤害 +18%"),
        ("damage", 1.20, "爆汁伤害再 +20%"),
        ("cost", 0.92, "费用再 -8%"),
        ("hp", 1.30, "引爆前生命 +30%"),
        ("damage", 1.30, "终极爆汁：伤害 +30%"),
    ],
    "beef": [
        ("cost", 0.95, "费用 -5%"),
        ("cooldown", 0.90, "投射间隔 -10%"),
        ("damage", 1.15, "肥牛伤害 +15%"),
        ("cooldown", 0.88, "投射间隔再 -12%"),
        ("hp", 1.20, "生命 +20%"),
        ("damage", 1.18, "肥牛伤害再 +18%"),
        ("cooldown", 0.82, "极寒连射：间隔 -18%"),
    ],
    "scallop": [
        ("cost", 0.95, "费用 -5%"),
        ("damage", 1.15, "蒜蓉伤害 +15%"),
        ("cooldown", 0.90, "投射间隔 -10%"),
        ("damage", 1.18, "溅射伤害再 +18%"),
        ("hp", 1.20, "生命 +20%"),
        ("cooldown", 0.85, "投射间隔再 -15%"),
        ("damage", 1.25, "满盘蒜香：伤害 +25%"),
    ],
    "wing": [
        ("cost", 0.95, "费用 -5%"),
        ("cooldown", 0.90, "回旋间隔 -10%"),
        ("damage", 1.15, "骨头伤害 +15%"),
        ("cooldown", 0.88, "回旋间隔再 -12%"),
        ("damage", 1.18, "往返伤害再 +18%"),
        ("hp", 1.20, "生命 +20%"),
        ("cooldown", 0.82, "终极回旋：间隔 -18%"),
    ],
    "sausage": [
        ("cost", 0.95, "费用 -5%"),
        ("damage", 1.18, "火焰伤害 +18%"),
        ("cooldown", 0.90, "喷火间隔 -10%"),
        ("damage", 1.20, "穿透伤害再 +20%"),
        ("hp", 1.20, "生命 +20%"),
        ("cooldown", 0.85, "喷火间隔再 -15%"),
        ("damage", 1.28, "烈焰整路：伤害 +28%"),
    ],
}

ENEMIES: dict[str, EnemyConfig] = {
    "normal": EnemyConfig("normal", "食客僵尸", 110, 34.0, 20, 1.0, 15, "zombie_normal.png", "基础敌人，生命与速度均衡。"),
    "baby": EnemyConfig("baby", "偷串宝宝", 55, 72.0, 10, 0.7, 10, "zombie_baby.png", "体型小、速度极快，但生命很低。"),
    "courier": EnemyConfig("courier", "外卖僵尸", 85, 58.0, 16, 0.75, 20, "zombie_courier.png", "背着餐箱快速冲线，反应时间很短。"),
    "pot": EnemyConfig("pot", "锅盖僵尸", 260, 24.0, 24, 1.0, 30, "zombie_pot.png", "锅盖护甲带来高生命，移动较慢。"),
    "drunk": EnemyConfig("drunk", "醉汉僵尸", 170, 38.0, 30, 1.1, 28, "zombie_drunk.png", "步伐不快，但近身破坏力更强。"),
    "butcher": EnemyConfig("butcher", "屠夫僵尸", 360, 29.0, 55, 1.25, 45, "zombie_butcher.png", "高生命高攻击，是中后期精英敌人。"),
    "giant": EnemyConfig("giant", "大巨人僵尸", 850, 19.0, 75, 1.5, 80, "zombie_giant.png", "极其耐打，重击能迅速破坏防线。"),
    "boss": EnemyConfig("boss", "夜市尸王", 2800, 14.0, 110, 1.4, 250, "zombie_boss.png", "最终首领，拥有巨量生命和强力重击。"),
}

ENEMY_ORDER = ["normal", "baby", "courier", "pot", "drunk", "butcher", "giant", "boss"]

LEVELS: list[LevelConfig] = [
    LevelConfig(1, "试营业", "食客与偷串宝宝出现，熟悉基础守摊。", [
        (8.0, ["normal"]),
        (16.0, ["baby"]),
        (25.0, ["normal", "baby"]),
        (36.0, ["normal", "normal"]),
        (49.0, ["baby", "normal", "baby"]),
        (64.0, ["normal", "normal", "baby", "normal"]),
    ], 1),
    LevelConfig(2, "外卖催单", "外卖僵尸加入，快攻频率提升。", [
        (8.0, ["normal"]), (15.0, ["baby", "normal"]),
        (23.0, ["courier", "normal"]), (32.0, ["normal", "baby", "courier"]),
        (43.0, ["courier", "courier", "normal"]),
        (57.0, ["normal", "baby", "courier", "normal", "courier"]),
    ], 1),
    LevelConfig(3, "锅盖来袭", "装甲敌人加入，考验持续输出。", [
        (8.0, ["normal", "baby"]), (16.0, ["courier", "normal"]),
        (25.0, ["pot", "normal"]), (35.0, ["courier", "pot", "normal"]),
        (47.0, ["pot", "normal", "courier", "baby"]),
        (62.0, ["pot", "pot", "courier", "normal", "baby"]),
    ], 1),
    LevelConfig(4, "醉客夜游", "醉汉混入队伍，单次攻击更危险。", [
        (8.0, ["normal", "courier"]), (15.0, ["drunk", "baby"]),
        (23.0, ["pot", "normal", "courier"]), (32.0, ["drunk", "normal", "baby"]),
        (43.0, ["pot", "drunk", "courier", "normal"]),
        (57.0, ["drunk", "pot", "courier", "normal", "baby", "normal"]),
    ], 1),
    LevelConfig(5, "屠夫巡街", "屠夫精英登场，防线承伤压力增加。", [
        (8.0, ["normal", "baby"]), (15.0, ["courier", "drunk"]),
        (23.0, ["pot", "normal", "courier"]), (32.0, ["butcher", "normal"]),
        (42.0, ["drunk", "pot", "courier", "normal"]),
        (54.0, ["butcher", "pot", "normal", "courier", "drunk"]),
        (68.0, ["butcher", "pot", "drunk", "courier", "normal", "baby"]),
    ], 2),
    LevelConfig(6, "巨人脚步", "巨人开始压阵，需要集中火力处理。", [
        (8.0, ["normal", "courier"]), (15.0, ["pot", "drunk"]),
        (23.0, ["butcher", "normal", "baby"]), (32.0, ["giant", "courier"]),
        (43.0, ["pot", "butcher", "drunk", "normal"]),
        (56.0, ["giant", "pot", "courier", "normal", "baby"]),
        (71.0, ["giant", "butcher", "pot", "drunk", "courier", "normal"]),
    ], 2),
    LevelConfig(7, "幸运转盘", "点击转盘取得随机肉肉，本关无需炭火。", [
        (8.0, ["normal"]), (16.0, ["baby", "courier"]),
        (25.0, ["pot", "normal"]), (35.0, ["drunk", "courier", "normal"]),
        (47.0, ["pot", "pot", "baby", "courier"]),
        (61.0, ["butcher", "drunk", "pot", "courier", "normal"]),
        (77.0, ["butcher", "pot", "drunk", "courier", "normal", "baby"]),
    ], 2, "roulette", 3.8),
    LevelConfig(8, "夜市封街", "多类敌人密集混编，巨人持续施压。", [
        (8.0, ["normal", "baby"]), (14.0, ["courier", "drunk", "normal"]),
        (21.0, ["pot", "butcher", "baby"]), (29.0, ["giant", "courier", "normal"]),
        (38.0, ["butcher", "pot", "drunk", "courier"]),
        (49.0, ["giant", "butcher", "normal", "courier", "baby"]),
        (62.0, ["giant", "pot", "butcher", "drunk", "courier", "normal"]),
        (76.0, ["giant", "giant", "butcher", "pot", "drunk", "courier", "baby"]),
    ], 2),
    LevelConfig(9, "黎明前夕", "短间隔精英波次，守住天亮前的围攻。", [
        (8.0, ["normal", "courier"]), (14.0, ["pot", "drunk", "baby"]),
        (20.0, ["butcher", "courier", "normal"]), (27.0, ["giant", "pot", "baby"]),
        (35.0, ["butcher", "butcher", "drunk", "courier"]),
        (44.0, ["giant", "pot", "butcher", "normal", "baby"]),
        (54.0, ["giant", "giant", "butcher", "drunk", "courier", "pot"]),
        (66.0, ["giant", "butcher", "butcher", "pot", "drunk", "courier", "normal"]),
        (79.0, ["giant", "giant", "butcher", "butcher", "pot", "drunk", "courier", "baby"]),
    ], 2),
    LevelConfig(10, "尸王终宴", "最终首领夜市尸王将在大波中登场。", [
        (8.0, ["normal", "baby"]), (14.0, ["courier", "normal", "drunk"]),
        (21.0, ["pot", "butcher", "courier"]), (29.0, ["giant", "normal", "baby"]),
        (38.0, ["butcher", "pot", "drunk", "courier"]),
        (48.0, ["giant", "butcher", "pot", "normal", "baby"]),
        (59.0, ["giant", "giant", "butcher", "drunk", "courier", "pot"]),
        (72.0, ["boss", "giant", "butcher", "pot", "drunk", "courier", "normal"]),
    ], 2),
    LevelConfig(11, "僵尸夜宵突袭", "固定随机肉肉防线；用有限军费买僵尸，吃肉返炭并三次突破烤炉。", [], 0, "reverse"),
    LevelConfig(12, "满巷催单", "完成限时肉肉订单赚取炭火，超时会提前引来下一波。", [
        (8.0, ["baby", "courier"]), (13.0, ["courier", "courier", "normal"]),
        (19.0, ["baby", "drunk", "courier", "normal"]),
        (26.0, ["pot", "butcher", "courier"]),
        (34.0, ["giant", "pot", "drunk", "baby"]),
        (43.0, ["butcher", "butcher", "courier", "normal", "baby"]),
        (54.0, ["giant", "giant", "pot", "drunk", "courier", "normal"]),
        (66.0, ["boss", "giant", "butcher", "butcher", "pot", "courier", "baby"]),
        (80.0, ["giant", "giant", "butcher", "pot", "drunk", "courier", "normal", "baby"]),
    ], oil_drops=2, special="orders", order_interval=14.0, order_time_limit=9.0, order_reward=50),
    LevelConfig(13, "回转烤盘", "环形烤盘每 12 秒右移，阵型会持续变化。", [
        (8.0, ["normal", "baby"]), (15.0, ["courier", "drunk", "normal"]),
        (23.0, ["pot", "butcher", "courier"]), (32.0, ["giant", "normal", "baby"]),
        (42.0, ["butcher", "pot", "drunk", "courier"]),
        (54.0, ["giant", "butcher", "pot", "normal", "baby"]),
        (67.0, ["giant", "giant", "butcher", "drunk", "courier", "pot"]),
        (82.0, ["boss", "giant", "butcher", "pot", "drunk", "courier", "normal"]),
    ], oil_drops=2, special="conveyor", conveyor_interval=12.0),
    LevelConfig(14, "尸潮封街", "精英与巨人连续压阵，几乎没有喘息。", [
        (8.0, ["normal", "courier"]), (13.0, ["baby", "drunk", "courier"]),
        (19.0, ["pot", "butcher", "normal"]), (26.0, ["giant", "courier", "baby"]),
        (34.0, ["butcher", "butcher", "pot", "drunk"]),
        (43.0, ["giant", "giant", "courier", "normal", "baby"]),
        (53.0, ["boss", "giant", "butcher", "pot", "drunk", "courier"]),
        (64.0, ["giant", "giant", "butcher", "butcher", "pot", "courier", "baby"]),
        (76.0, ["boss", "giant", "giant", "butcher", "pot", "drunk", "courier", "normal"]),
        (89.0, ["giant", "giant", "butcher", "butcher", "pot", "drunk", "courier", "normal", "baby"]),
    ], 2),
    LevelConfig(15, "黎明终宴", "最终尸王率领全种类僵尸发起最后围攻。", [
        (8.0, ["normal", "baby"]), (13.0, ["courier", "drunk", "normal"]),
        (19.0, ["pot", "butcher", "courier"]), (26.0, ["giant", "baby", "drunk"]),
        (34.0, ["butcher", "pot", "courier", "normal"]),
        (43.0, ["giant", "giant", "butcher", "baby", "courier"]),
        (53.0, ["boss", "giant", "pot", "drunk", "normal", "baby"]),
        (64.0, ["giant", "giant", "butcher", "butcher", "pot", "courier", "normal"]),
        (76.0, ["boss", "giant", "giant", "butcher", "pot", "drunk", "courier", "baby"]),
        (90.0, ["boss", "boss", "giant", "giant", "butcher", "butcher", "pot", "drunk", "courier", "normal", "baby"]),
    ], 2),
]

COLORS = {
    "night": (28, 29, 39),
    "night_2": (38, 43, 55),
    "lantern": (255, 173, 82),
    "paper": (255, 238, 202),
    "wood": (135, 81, 45),
    "wood_dark": (88, 51, 34),
    "grid_a": (76, 116, 77),
    "grid_b": (65, 101, 69),
    "grid_line": (32, 59, 43),
    "red": (225, 76, 69),
    "green": (85, 181, 100),
    "gold": (248, 190, 78),
    "white": (248, 246, 236),
    "black": (18, 18, 22),
    "muted": (168, 174, 168),
}
