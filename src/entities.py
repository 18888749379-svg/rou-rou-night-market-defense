from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from assets import load_image
from settings import (
    CELL_SIZE,
    EGG_MINE_DEPLOY_HP,
    ENEMIES,
    GRID_COLS,
    GRID_X,
    GRID_Y,
    SPAWN_X,
    TIER_TWO_DAMAGE_MULTIPLIER,
    TIER_TWO_HP_MULTIPLIER,
    TIER_TWO_REWARD_MULTIPLIER,
    TIER_TWO_SPEED_MULTIPLIER,
    UNITS,
)


def cell_center(row: int, col: int) -> tuple[int, int]:
    return GRID_X + col * CELL_SIZE + CELL_SIZE // 2, GRID_Y + row * CELL_SIZE + CELL_SIZE // 2


def row_center(row: int) -> int:
    return GRID_Y + row * CELL_SIZE + CELL_SIZE // 2


def x_to_col(x: float) -> int:
    return int((x - GRID_X) // CELL_SIZE)


@dataclass
class FloatingText:
    text: str
    x: float
    y: float
    color: tuple[int, int, int]
    ttl: float = 1.0

    def __post_init__(self) -> None:
        self.initial_ttl = self.ttl

    def update(self, dt: float) -> None:
        self.ttl -= dt
        self.y -= 34 * dt


class Unit:
    def __init__(self, unit_type: str, row: int, col: int) -> None:
        self.config = UNITS[unit_type]
        self.unit_type = unit_type
        self.row = row
        self.col = col
        self.max_hp = self.config.hp
        self.hp = self.config.hp
        self.deployed = unit_type != "egg_mine"
        self.deployment_timer = 0.0
        self.triggered = False
        if unit_type == "egg_mine":
            self.hp = EGG_MINE_DEPLOY_HP
        self.cooldown = 0.0
        self.timer = 0.0
        self.age = 0.0
        self.ultimate_timer = 0.0
        self.damage_multiplier = 1.0
        self.heal_range = 1
        self.alive = True
        unit_size = max(52, CELL_SIZE - 22)
        self.image = load_image(self.config.image, (unit_size, unit_size))
        x, y = cell_center(row, col)
        self.rect = self.image.get_rect(center=(x, y + 8))

    @property
    def block_rect(self) -> pygame.Rect:
        rect = self.rect.copy()
        rect.inflate_ip(-16, -12)
        return rect

    def update(self, dt: float, game: "Game") -> None:
        if not self.alive:
            return
        if self.ultimate_timer > 0:
            self.ultimate_timer = max(0.0, self.ultimate_timer - dt)
        if self.cooldown > 0:
            self.cooldown -= dt
        if self.unit_type in {"skewer", "wing", "beef", "scallop"}:
            self._update_skewer(game)
        elif self.unit_type == "meatball":
            self._update_meatball(dt, game)
        elif self.unit_type == "charcoal":
            self._update_charcoal(dt, game)
        elif self.unit_type == "egg_mine":
            self._update_egg_mine(dt, game)
        elif self.unit_type == "sausage":
            self._update_sausage(game)
        elif self.unit_type == "lotus":
            self._update_lotus(dt, game)

    def _update_skewer(self, game: "Game") -> None:
        if self.cooldown > 0:
            return
        targets = [
            enemy
            for enemy in game.enemies
            if enemy.alive and enemy.row == self.row and enemy.x > self.rect.centerx - 10
        ]
        if not targets:
            return
        targets.sort(key=lambda enemy: enemy.x)
        image_name = "lamb_chunk.png"
        boomerang = False
        slow_seconds = 0.0
        splash_radius = 0.0
        projectile_max_x = None
        if self.unit_type == "wing":
            image_name = "chicken_bone.png"
            boomerang = True
            if self.ultimate_timer > 0:
                projectile_max_x = GRID_X + (GRID_COLS - 0.5) * CELL_SIZE
        elif self.unit_type == "beef":
            image_name = "beef_projectile.png"
            slow_seconds = 2.4
        elif self.unit_type == "scallop":
            image_name = "garlic_clove"
            splash_radius = CELL_SIZE * 0.85
        game.projectiles.append(
            Projectile(
                self.row,
                self.rect.right - 4,
                self.rect.centery - 14,
                int(round(self.config.damage * self.damage_multiplier)),
                image_name,
                slow_seconds,
                boomerang,
                self.rect.centerx,
                splash_radius,
                projectile_max_x,
            )
        )
        cooldown = self.config.cooldown
        if self.ultimate_timer > 0 and self.unit_type == "skewer":
            cooldown = max(0.12, cooldown * 0.22)
        elif self.ultimate_timer > 0 and self.unit_type == "beef":
            cooldown = max(0.18, cooldown * 0.24)
        self.cooldown = cooldown
        sound_name = f"attack_{self.unit_type}"
        game.audio.play(sound_name if sound_name in game.audio.sounds else "attack_skewer")

    def _update_meatball(self, dt: float, game: "Game") -> None:
        self.timer += dt
        if self.timer < self.config.cooldown:
            return
        boom_x, boom_y = cell_center(self.row, self.col)
        hit_any = False
        for enemy in game.enemies:
            if not enemy.alive or enemy.row != self.row:
                continue
            if abs(enemy.x - boom_x) <= CELL_SIZE * 1.55:
                enemy.take_damage(int(round(self.config.damage * self.damage_multiplier)), game)
                hit_any = True
        game.effects.append(Explosion(boom_x, boom_y))
        game.trigger_shake(4, 0.20)
        game.floaters.append(FloatingText("爆炸!", boom_x, boom_y - 36, (255, 210, 88), 0.75))
        if not hit_any:
            game.floaters.append(FloatingText("空爆", boom_x, boom_y + 8, (255, 180, 120), 0.6))
        self.alive = False
        game.audio.play("attack_meatball")

    def _update_charcoal(self, dt: float, game: "Game") -> None:
        if game.is_reverse_mode:
            return
        self.age += dt
        self.timer += dt
        if self.timer < self.config.cooldown:
            return
        self.timer = 0.0
        x, y = cell_center(self.row, self.col)
        if self.age >= 60.0:
            game.spawn_pickup_at(x - 18, y - 20, game.charcoal_unit_value)
            game.spawn_pickup_at(x + 18, y - 8, game.charcoal_unit_value)
        else:
            game.spawn_pickup_at(x + 18, y - 18, game.charcoal_unit_value)

    def _update_egg_mine(self, dt: float, game: "Game") -> None:
        if self.triggered:
            return
        if not self.deployed:
            self.deployment_timer += dt
            if self.deployment_timer < self.config.cooldown:
                return
            self.deployed = True
            self.max_hp = self.config.hp
            self.hp = self.config.hp
            game.effects.append(ImpactBurst(self.rect.centerx, self.rect.centery, "spark"))
            game.floaters.append(
                FloatingText("部署完成", self.rect.centerx, self.rect.top - 6, (132, 236, 145), 0.8)
            )
            return
        targets = [
            enemy for enemy in game.enemies
            if enemy.alive and enemy.row == self.row and abs(enemy.x - self.rect.centerx) <= CELL_SIZE * 0.55
        ]
        if not targets:
            return
        self.triggered = True
        for enemy in game.enemies:
            if enemy.alive and enemy.row == self.row and abs(enemy.x - self.rect.centerx) <= CELL_SIZE * 1.45:
                enemy.take_damage(int(round(self.config.damage * self.damage_multiplier)), game)
        game.effects.append(Explosion(self.rect.centerx, self.rect.centery))
        game.trigger_shake(4, 0.18)
        game.floaters.append(FloatingText("鸡蛋爆破!", self.rect.centerx, self.rect.top - 8, (255, 219, 105), 0.8))
        self.alive = False
        game.audio.play("attack_meatball")

    def _update_sausage(self, game: "Game") -> None:
        if self.cooldown > 0:
            return
        targets = [
            enemy for enemy in game.enemies
            if enemy.alive and enemy.row == self.row and enemy.x > self.rect.centerx
        ]
        if not targets:
            return
        end_x = min(SPAWN_X + 30, self.rect.centerx + CELL_SIZE * 5.3)
        for enemy in targets:
            if enemy.x <= end_x:
                enemy.take_damage(int(round(self.config.damage * self.damage_multiplier)), game)
        game.effects.append(FlameWave(self.rect.right, self.rect.centery, end_x))
        self.cooldown = self.config.cooldown
        game.audio.play("attack_meatball")

    def _update_lotus(self, dt: float, game: "Game") -> None:
        self.timer += dt
        if self.timer < self.config.cooldown:
            return
        healed = False
        for unit in game.units:
            distance = abs(unit.row - self.row) + abs(unit.col - self.col)
            if unit.alive and unit is not self and 0 < distance <= self.heal_range and unit.hp < unit.max_hp:
                amount = min(35, unit.max_hp - unit.hp)
                unit.hp += amount
                game.floaters.append(FloatingText(f"+{amount}", unit.rect.centerx, unit.rect.top, (116, 235, 146), 0.8))
                healed = True
        self.timer = 0.0
        if healed:
            game.effects.append(HealingPulse(self.rect.centerx, self.rect.centery, self.heal_range))
            game.audio.play("place")

    def take_damage(self, amount: int) -> None:
        self.hp -= amount
        if self.hp <= 0:
            self.alive = False

    def double_defense(self) -> None:
        self.max_hp *= 2
        self.hp = self.max_hp
        center = self.rect.center
        size = min(CELL_SIZE - 4, int(self.image.get_width() * 1.28))
        self.image = load_image(self.config.image, (size, size))
        self.rect = self.image.get_rect(center=center)

    def move_to(self, row: int, col: int) -> None:
        self.row = row
        self.col = col
        x, y = cell_center(row, col)
        self.rect.center = (x, y + 8)

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.image, self.rect)
        if self.ultimate_timer > 0:
            pulse = pygame.Surface((self.rect.width + 18, self.rect.height + 18), pygame.SRCALPHA)
            pygame.draw.ellipse(pulse, (255, 190, 72, 125), pulse.get_rect(), 3)
            surface.blit(pulse, pulse.get_rect(center=self.rect.center))
            timer_bar = pygame.Rect(self.rect.left + 5, self.rect.top - 13, self.rect.width - 10, 5)
            pygame.draw.rect(surface, (59, 42, 31), timer_bar, border_radius=3)
            fill = timer_bar.copy()
            duration = 7.0 if self.unit_type == "wing" else 5.0
            fill.width = int(timer_bar.width * min(1.0, self.ultimate_timer / duration))
            pygame.draw.rect(surface, (255, 185, 67), fill, border_radius=3)
        if self.unit_type == "meatball":
            ratio = max(0.0, min(1.0, self.timer / self.config.cooldown))
            color = (255, int(210 - 120 * ratio), int(90 - 30 * ratio))
            pygame.draw.circle(surface, color, self.rect.center, int(12 + 20 * ratio), 3)
        elif self.unit_type == "charcoal":
            ratio = max(0.0, min(1.0, self.timer / self.config.cooldown))
            meter = pygame.Rect(self.rect.left + 10, self.rect.top - 8, self.rect.width - 20, 5)
            pygame.draw.rect(surface, (64, 48, 38), meter, border_radius=3)
            fill = meter.copy()
            fill.width = int(meter.width * ratio)
            pygame.draw.rect(surface, (255, 181, 69), fill, border_radius=3)
        elif self.unit_type == "egg_mine":
            ratio = 1.0 if self.deployed else max(
                0.0,
                min(1.0, self.deployment_timer / self.config.cooldown),
            )
            color = (99, 225, 113) if self.deployed else (255, 184, 70)
            meter = pygame.Rect(self.rect.left + 8, self.rect.top - 8, self.rect.width - 16, 5)
            pygame.draw.rect(surface, (55, 43, 35), meter, border_radius=3)
            fill = meter.copy()
            fill.width = int(meter.width * ratio)
            pygame.draw.rect(surface, color, fill, border_radius=3)
            if self.deployed:
                pygame.draw.circle(surface, color, self.rect.center, self.rect.width // 2, 2)
        elif self.unit_type == "lotus":
            ratio = max(0.0, min(1.0, self.timer / self.config.cooldown))
            pygame.draw.arc(surface, (105, 231, 135), self.rect.inflate(8, 8), 0, 6.283 * ratio, 3)
        self._draw_hp(surface)

    def _draw_hp(self, surface: pygame.Surface) -> None:
        if self.hp >= self.max_hp:
            return
        bar = pygame.Rect(self.rect.left + 6, self.rect.bottom - 9, self.rect.width - 12, 8)
        pygame.draw.rect(surface, (48, 43, 40), bar.inflate(4, 4), border_radius=4)
        pygame.draw.rect(surface, (143, 112, 72), bar.inflate(4, 4), 1, border_radius=4)
        pygame.draw.rect(surface, (42, 18, 16), bar, border_radius=3)
        fill = bar.copy()
        fill.width = int(bar.width * max(0, self.hp) / self.max_hp)
        pygame.draw.rect(surface, (179, 55, 39), fill, border_radius=3)
        if fill.width > 3:
            pygame.draw.line(surface, (255, 145, 95), (fill.x + 2, fill.y + 2), (fill.right - 2, fill.y + 2), 1)


class Enemy:
    def __init__(self, enemy_type: str, row: int, offset: float = 0.0, tier: int = 1) -> None:
        self.config = ENEMIES[enemy_type]
        self.enemy_type = enemy_type
        self.tier = 2 if tier >= 2 else 1
        self.row = row
        self.x = SPAWN_X + offset
        self.y = row_center(row) + 10
        hp_multiplier = TIER_TWO_HP_MULTIPLIER if self.tier == 2 else 1.0
        damage_multiplier = TIER_TWO_DAMAGE_MULTIPLIER if self.tier == 2 else 1.0
        speed_multiplier = TIER_TWO_SPEED_MULTIPLIER if self.tier == 2 else 1.0
        reward_multiplier = TIER_TWO_REWARD_MULTIPLIER if self.tier == 2 else 1.0
        self.max_hp = max(1, int(round(self.config.hp * hp_multiplier)))
        self.hp = self.max_hp
        self.attack_damage = max(0, int(round(self.config.damage * damage_multiplier)))
        self.move_speed = self.config.speed * speed_multiplier
        self.reward = max(0, int(round(self.config.reward * reward_multiplier)))
        self.attack_timer = 0.0
        self.slow_timer = 0.0
        self.animation_time = 0.0
        self.hurt_timer = 0.0
        self.alive = True
        sizes = {
            "baby": (46, 58),
            "normal": (58, 78),
            "courier": (60, 78),
            "drunk": (60, 80),
            "pot": (70, 88),
            "butcher": (72, 92),
            "giant": (92, 116),
            "boss": (126, 154),
        }
        self.image = load_image(self.config.image, sizes.get(enemy_type, (58, 78)))
        self.rect = self.image.get_rect(center=(self.x, self.y))
        self.target: Unit | None = None

    def col(self) -> int:
        return x_to_col(self.x)

    def update(self, dt: float, game: "Game") -> None:
        if not self.alive:
            return
        self.animation_time += dt
        self.hurt_timer = max(0.0, self.hurt_timer - dt)
        self.rect.center = (int(self.x), int(self.y))
        if self.slow_timer > 0:
            self.slow_timer -= dt
        self.target = self._find_blocking_unit(game)
        blocked_by_enemy = self._blocked_by_front_enemy(game)
        if self.target:
            self.attack_timer -= dt
            if self.attack_timer <= 0:
                target = self.target
                was_alive = target.alive
                target.take_damage(self.attack_damage)
                game.effects.append(ImpactBurst(target.rect.centerx, target.rect.centery, "grease"))
                if self.attack_damage >= 50:
                    game.trigger_shake(2, 0.10)
                if was_alive and not target.alive:
                    game.on_unit_eaten(target, self)
                self.attack_timer = self.config.cooldown
                game.audio.play("hit")
        elif not blocked_by_enemy:
            speed = self.move_speed * (0.48 if self.slow_timer > 0 else 1.0)
            self.x -= speed * dt
        self.rect.center = (int(self.x), int(self.y))

    def _find_blocking_unit(self, game: "Game") -> Unit | None:
        for unit in game.units:
            if unit.alive and unit.row == self.row and self.rect.colliderect(unit.block_rect):
                return unit
        return None

    def _blocked_by_front_enemy(self, game: "Game") -> bool:
        front = [
            enemy
            for enemy in game.enemies
            if enemy is not self and enemy.alive and enemy.row == self.row and enemy.x < self.x
        ]
        if not front:
            return False
        nearest = max(front, key=lambda enemy: enemy.x)
        return self.x - nearest.x < 70 and nearest.target is not None

    def take_damage(self, amount: int, game: "Game") -> None:
        self.hp -= amount
        self.hurt_timer = 0.13
        game.floaters.append(FloatingText(f"-{amount}", self.x, self.rect.top, (255, 236, 124)))
        game.effects.append(ImpactBurst(int(self.x), int(self.y), "spark"))
        if self.hp <= 0:
            self.alive = False
            if game.is_reverse_mode:
                game.on_reverse_enemy_lost(self)
            else:
                game.floaters.append(FloatingText(f"+{self.reward}", self.x, self.y, (255, 189, 71), 0.7))
                game.add_charcoal_auto(self.reward, self.x, self.y - 18)

    def apply_slow(self, seconds: float) -> None:
        self.slow_timer = max(self.slow_timer, seconds)

    def draw(self, surface: pygame.Surface) -> None:
        moving = self.target is None
        bob = int(math.sin(self.animation_time * 8.0) * 2) if moving else 0
        lunge = -3 if self.target is not None and self.attack_timer < self.config.cooldown * 0.35 else 0
        draw_rect = self.rect.move(lunge, bob)
        image = self.image.copy() if self.hurt_timer > 0 else self.image
        if self.hurt_timer > 0:
            image.fill((74, 15, 10, 0), special_flags=pygame.BLEND_RGBA_ADD)
        surface.blit(image, draw_rect)
        if self.slow_timer > 0:
            frost = pygame.Surface((self.rect.width + 18, self.rect.height + 12), pygame.SRCALPHA)
            pygame.draw.ellipse(frost, (118, 226, 255, 150), frost.get_rect(), 3)
            surface.blit(frost, frost.get_rect(center=self.rect.center))
        if self.tier == 2:
            badge = pygame.Rect(self.rect.right - 20, self.rect.top - 25, 22, 20)
            pygame.draw.rect(surface, (128, 35, 28), badge, border_radius=5)
            pygame.draw.rect(surface, (255, 186, 72), badge, 1, border_radius=5)
            for x in (badge.centerx - 3, badge.centerx + 3):
                pygame.draw.line(surface, (255, 237, 188), (x, badge.y + 5), (x, badge.bottom - 5), 2)
        self._draw_hp(surface)

    def _draw_hp(self, surface: pygame.Surface) -> None:
        bar = pygame.Rect(self.rect.left + 6, self.rect.top - 12, self.rect.width - 12, 8)
        pygame.draw.rect(surface, (40, 43, 35), bar.inflate(4, 4), border_radius=4)
        pygame.draw.rect(surface, (132, 113, 77), bar.inflate(4, 4), 1, border_radius=4)
        pygame.draw.rect(surface, (20, 35, 18), bar, border_radius=3)
        fill = bar.copy()
        fill.width = int(bar.width * max(0, self.hp) / self.max_hp)
        pygame.draw.rect(surface, (91, 173, 67), fill, border_radius=3)
        if fill.width > 3:
            pygame.draw.line(surface, (180, 234, 114), (fill.x + 2, fill.y + 2), (fill.right - 2, fill.y + 2), 1)


class Projectile:
    def __init__(
        self,
        row: int,
        x: float,
        y: float,
        damage: int,
        image_name: str = "lamb_chunk.png",
        slow_seconds: float = 0.0,
        boomerang: bool = False,
        origin_x: float = 0.0,
        splash_radius: float = 0.0,
        max_x: float | None = None,
    ) -> None:
        self.row = row
        self.x = x
        self.y = y
        self.damage = damage
        self.image_name = image_name
        self.slow_seconds = slow_seconds
        self.boomerang = boomerang
        self.origin_x = origin_x
        self.splash_radius = splash_radius
        self.direction = 1
        self.max_x = max_x if max_x is not None else x + CELL_SIZE * 3.2
        self.hit_ids: set[int] = set()
        self.angle = 0.0
        self.speed = 520.0 if not boomerang else 440.0
        self.alive = True
        if image_name == "chicken_bone.png":
            size = (50, 26)
        elif image_name == "beef_projectile.png":
            size = (44, 34)
        elif image_name == "garlic_clove":
            size = (32, 24)
        else:
            size = (34, 28)
        if image_name == "garlic_clove":
            self.image = pygame.Surface(size, pygame.SRCALPHA)
            pygame.draw.ellipse(self.image, (255, 239, 183), (2, 5, 16, 14))
            pygame.draw.ellipse(self.image, (238, 212, 148), (13, 2, 16, 15))
            pygame.draw.line(self.image, (102, 151, 72), (25, 4), (29, 0), 3)
        else:
            self.image = load_image(image_name, size)
        self.rect = self.image.get_rect(center=(int(x), int(y)))

    def update(self, dt: float, game: "Game") -> None:
        self.x += self.speed * self.direction * dt
        if self.boomerang and self.direction > 0 and self.x >= self.max_x:
            self.direction = -1
            # The return trip is a second attack pass.
            self.hit_ids.clear()
        self.rect.centerx = int(self.x)
        targets = [enemy for enemy in game.enemies if enemy.alive and enemy.row == self.row]
        targets.sort(key=lambda enemy: enemy.x)
        for enemy in targets:
            enemy_id = id(enemy)
            if enemy_id not in self.hit_ids and self.rect.colliderect(enemy.rect):
                enemy.take_damage(self.damage, game)
                if self.splash_radius > 0:
                    for nearby in game.enemies:
                        if nearby is not enemy and nearby.alive and nearby.row == self.row and abs(nearby.x - enemy.x) <= self.splash_radius:
                            nearby.take_damage(max(1, self.damage // 2), game)
                    game.effects.append(GarlicBurst(int(enemy.x), int(enemy.y)))
                if self.slow_seconds > 0:
                    enemy.apply_slow(self.slow_seconds)
                    game.effects.append(ImpactBurst(int(enemy.x), int(enemy.y), "frost"))
                self.hit_ids.add(enemy_id)
                if not self.boomerang:
                    self.alive = False
                game.audio.play("hit")
                break
        if self.boomerang:
            self.angle += 720 * dt * self.direction
        if self.x > SPAWN_X + 160 or (self.boomerang and self.direction < 0 and self.x <= self.origin_x):
            self.alive = False

    def draw(self, surface: pygame.Surface) -> None:
        if self.boomerang:
            trail = pygame.Surface((68, 42), pygame.SRCALPHA)
            pygame.draw.ellipse(trail, (255, 177, 72, 58), trail.get_rect(), 4)
            pygame.draw.line(trail, (255, 226, 145, 120), (4, 28), (24, 18), 3)
            surface.blit(trail, trail.get_rect(center=self.rect.center))
        if self.slow_seconds > 0:
            glow = pygame.Surface((62, 48), pygame.SRCALPHA)
            pygame.draw.ellipse(glow, (103, 224, 255, 70), glow.get_rect())
            pygame.draw.circle(glow, (220, 250, 255, 180), (12, 25), 3)
            pygame.draw.circle(glow, (150, 232, 255, 150), (22, 10), 2)
            surface.blit(glow, glow.get_rect(center=self.rect.center))
        image = self.image
        if self.boomerang:
            image = pygame.transform.rotate(self.image, self.angle)
        rect = image.get_rect(center=self.rect.center)
        surface.blit(image, rect)


class ImpactBurst:
    COLORS = {
        "spark": ((255, 211, 86), (255, 116, 47)),
        "grease": ((255, 178, 72), (135, 54, 32)),
        "frost": ((213, 251, 255), (92, 205, 244)),
        "garlic": ((255, 239, 174), (158, 196, 83)),
    }

    def __init__(self, x: int, y: int, kind: str = "spark") -> None:
        self.x = x
        self.y = y
        self.kind = kind
        self.ttl = 0.32
        self.max_ttl = self.ttl
        self.colors = self.COLORS.get(kind, self.COLORS["spark"])
        self.particles = []
        phase = (x * 0.037 + y * 0.021) % (math.pi * 2)
        for index in range(8):
            angle = phase + index * math.pi / 4
            speed = 32 + (index % 3) * 13
            self.particles.append((angle, speed, 2 + index % 2))

    @property
    def alive(self) -> bool:
        return self.ttl > 0

    def update(self, dt: float) -> None:
        self.ttl -= dt

    def draw(self, surface: pygame.Surface) -> None:
        progress = 1.0 - max(0.0, self.ttl) / self.max_ttl
        alpha = max(0, int(230 * (1.0 - progress)))
        layer = pygame.Surface((96, 96), pygame.SRCALPHA)
        for index, (angle, speed, size) in enumerate(self.particles):
            distance = speed * progress
            px = 48 + int(math.cos(angle) * distance)
            py = 48 + int(math.sin(angle) * distance + 22 * progress * progress)
            color = self.colors[index % len(self.colors)]
            pygame.draw.circle(layer, (*color, alpha), (px, py), size)
        surface.blit(layer, (self.x - 48, self.y - 48))


class Explosion:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y
        self.ttl = 0.35
        self.max_ttl = 0.35

    def update(self, dt: float) -> None:
        self.ttl -= dt

    @property
    def alive(self) -> bool:
        return self.ttl > 0

    def draw(self, surface: pygame.Surface) -> None:
        progress = 1.0 - self.ttl / self.max_ttl
        radius = int(CELL_SIZE * 0.38 + progress * CELL_SIZE * 1.12)
        alpha = max(0, int(210 * (1.0 - progress)))
        layer = pygame.Surface((radius * 2 + 8, radius * 2 + 8), pygame.SRCALPHA)
        pygame.draw.circle(layer, (255, 95, 52, alpha), (radius + 4, radius + 4), radius)
        pygame.draw.circle(layer, (255, 218, 92, alpha), (radius + 4, radius + 4), max(8, radius // 2))
        for dx, dy in [(-0.72, -0.32), (-0.55, 0.58), (0.22, -0.78), (0.74, 0.18), (0.42, 0.68)]:
            px = radius + 4 + int(dx * radius)
            py = radius + 4 + int(dy * radius)
            pygame.draw.circle(layer, (255, 132, 47, alpha), (px, py), max(3, radius // 9))
        surface.blit(layer, (self.x - radius - 4, self.y - radius - 4))


class FlameWave:
    def __init__(self, start_x: int, y: int, end_x: float) -> None:
        self.start_x = start_x
        self.y = y
        self.end_x = int(end_x)
        self.ttl = 0.42
        self.max_ttl = self.ttl

    @property
    def alive(self) -> bool:
        return self.ttl > 0

    def update(self, dt: float) -> None:
        self.ttl -= dt

    def draw(self, surface: pygame.Surface) -> None:
        progress = 1.0 - self.ttl / self.max_ttl
        visible_end = int(self.start_x + (self.end_x - self.start_x) * min(1.0, progress * 2.4))
        width = max(4, visible_end - self.start_x)
        layer = pygame.Surface((width, 54), pygame.SRCALPHA)
        alpha = max(0, int(210 * (1.0 - progress)))
        pygame.draw.line(layer, (255, 83, 35, alpha), (0, 29), (width, 29), 25)
        pygame.draw.line(layer, (255, 216, 75, alpha), (0, 29), (width, 29), 9)
        for x in range(10, width, 32):
            pygame.draw.circle(layer, (255, 126, 40, alpha), (x, 16 + (x // 32 % 2) * 12), 10)
        surface.blit(layer, (self.start_x, self.y - 27))


class ScallopRain:
    def __init__(self, x: int, y: int, targets: list[Enemy], damage: int) -> None:
        self.x = x
        self.y = y
        self.damage = damage
        self.elapsed = 0.0
        self.duration = 1.8
        self.entries = [
            {"enemy": enemy, "delay": index * 0.12, "hit": False, "impact": (enemy.x, enemy.y)}
            for index, enemy in enumerate(targets)
        ]
        self.image = load_image("scallop.png", (38, 38))

    @property
    def alive(self) -> bool:
        return self.elapsed < self.duration

    def update(self, dt: float, game: "Game") -> None:
        self.elapsed += dt
        for entry in self.entries:
            impact_time = 0.78 + float(entry["delay"])
            if entry["hit"] or self.elapsed < impact_time:
                continue
            enemy = entry["enemy"]
            if enemy.alive:
                entry["impact"] = (enemy.x, enemy.y)
                enemy.take_damage(self.damage, game)
                game.effects.append(GarlicBurst(int(enemy.x), int(enemy.y)))
            entry["hit"] = True

    def draw(self, surface: pygame.Surface) -> None:
        for entry in self.entries:
            if entry["hit"]:
                continue
            delay = float(entry["delay"])
            progress = max(0.0, min(1.0, (self.elapsed - delay) / 0.78))
            enemy = entry["enemy"]
            target_x = enemy.x if enemy.alive else float(entry["impact"][0])
            target_y = enemy.y if enemy.alive else float(entry["impact"][1])
            x = self.x + (target_x - self.x) * progress
            y = self.y + (target_y - self.y) * progress - 190 * 4 * progress * (1.0 - progress)
            image = pygame.transform.rotate(self.image, progress * 540)
            surface.blit(image, image.get_rect(center=(int(x), int(y))))


class LaneBurn:
    def __init__(self, row: int, damage: int, duration: float = 4.0) -> None:
        self.row = row
        self.damage = max(1, damage // 2)
        self.duration = duration
        self.elapsed = 0.0
        self.tick_timer = 0.0

    @property
    def alive(self) -> bool:
        return self.elapsed < self.duration

    def update(self, dt: float, game: "Game") -> None:
        self.elapsed += dt
        self.tick_timer -= dt
        if self.tick_timer > 0:
            return
        self.tick_timer += 0.5
        for enemy in list(game.enemies):
            if enemy.alive and enemy.row == self.row:
                enemy.take_damage(self.damage, game)

    def draw(self, surface: pygame.Surface) -> None:
        y = row_center(self.row)
        width = GRID_COLS * CELL_SIZE
        layer = pygame.Surface((width, 66), pygame.SRCALPHA)
        fade = min(1.0, max(0.0, (self.duration - self.elapsed) * 2.0))
        alpha = int(145 * fade)
        pygame.draw.rect(layer, (238, 62, 28, alpha // 2), (0, 19, width, 34), border_radius=12)
        offset = int(self.elapsed * 110) % 38
        for x in range(-offset, width + 30, 38):
            height = 17 + ((x // 38) % 3) * 8
            pygame.draw.circle(layer, (255, 91, 31, alpha), (x, 41), 15)
            pygame.draw.polygon(layer, (255, 191, 48, alpha), [(x - 10, 41), (x, 41 - height), (x + 10, 41)])
        surface.blit(layer, (GRID_X, y - 33))


class HealingPulse:
    def __init__(self, x: int, y: int, range_cells: int = 1) -> None:
        self.x = x
        self.y = y
        self.range_cells = max(1, range_cells)
        self.ttl = 0.7
        self.max_ttl = self.ttl

    @property
    def alive(self) -> bool:
        return self.ttl > 0

    def update(self, dt: float) -> None:
        self.ttl -= dt

    def draw(self, surface: pygame.Surface) -> None:
        progress = 1.0 - self.ttl / self.max_ttl
        radius = int(18 + progress * CELL_SIZE * 1.25 * self.range_cells)
        alpha = max(0, int(180 * (1.0 - progress)))
        pygame.draw.circle(surface, (104, 233, 134, alpha), (self.x, self.y), radius, 4)


class GarlicBurst:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y
        self.ttl = 0.3
        self.max_ttl = self.ttl

    @property
    def alive(self) -> bool:
        return self.ttl > 0

    def update(self, dt: float) -> None:
        self.ttl -= dt

    def draw(self, surface: pygame.Surface) -> None:
        progress = 1.0 - self.ttl / self.max_ttl
        radius = int(8 + progress * CELL_SIZE * 0.8)
        alpha = max(0, int(190 * (1.0 - progress)))
        pygame.draw.circle(surface, (255, 226, 130, alpha), (self.x, self.y), radius, 3)
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            pygame.draw.circle(surface, (246, 238, 184, alpha), (self.x + dx * radius // 2, self.y + dy * radius // 2), 4)


# Avoid importing Game at runtime just for type checking.
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game import Game
