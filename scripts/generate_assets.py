from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import pygame

from settings import IMAGE_DIR


def save(surface: pygame.Surface, name: str) -> None:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    path = IMAGE_DIR / name
    if path.exists():
        return
    pygame.image.save(surface, path)


def rounded_surface(size: tuple[int, int]) -> pygame.Surface:
    return pygame.Surface(size, pygame.SRCALPHA)


def draw_skewer() -> pygame.Surface:
    s = rounded_surface((96, 96))
    pygame.draw.line(s, (210, 166, 99), (20, 76), (78, 18), 6)
    for x, y, color in [
        (34, 62, (194, 92, 67)),
        (46, 50, (228, 145, 86)),
        (58, 38, (176, 85, 61)),
    ]:
        pygame.draw.circle(s, color, (x, y), 16)
        pygame.draw.circle(s, (255, 210, 142), (x - 5, y - 5), 4)
        pygame.draw.circle(s, (92, 46, 39), (x, y), 16, 2)
    pygame.draw.polygon(s, (235, 220, 170), [(77, 18), (86, 6), (82, 24)])
    pygame.draw.circle(s, (255, 226, 128), (67, 64), 7)
    return s


def draw_wall() -> pygame.Surface:
    s = rounded_surface((96, 96))
    pygame.draw.rect(s, (181, 94, 77), (17, 18, 62, 58), border_radius=14)
    pygame.draw.rect(s, (114, 55, 49), (17, 18, 62, 58), 4, border_radius=14)
    for y in [30, 46, 62]:
        pygame.draw.arc(s, (244, 188, 152), (24, y - 18, 48, 28), 0.15, 2.95, 4)
    pygame.draw.rect(s, (240, 178, 127), (22, 14, 52, 14), border_radius=7)
    pygame.draw.circle(s, (255, 218, 160), (34, 42), 5)
    return s


def draw_meatball() -> pygame.Surface:
    s = rounded_surface((96, 96))
    pygame.draw.circle(s, (182, 81, 60), (48, 50), 34)
    pygame.draw.circle(s, (118, 51, 42), (48, 50), 34, 4)
    pygame.draw.circle(s, (255, 186, 116), (35, 36), 9)
    pygame.draw.circle(s, (255, 226, 126), (60, 64), 6)
    pygame.draw.circle(s, (125, 48, 44), (60, 37), 5)
    return s


def draw_charcoal() -> pygame.Surface:
    s = rounded_surface((96, 96))
    pygame.draw.rect(s, (74, 52, 39), (25, 24, 46, 48), border_radius=10)
    pygame.draw.rect(s, (37, 31, 28), (25, 24, 46, 48), 4, border_radius=10)
    pygame.draw.circle(s, (255, 105, 48), (39, 56), 11)
    pygame.draw.circle(s, (255, 190, 69), (43, 51), 7)
    pygame.draw.circle(s, (44, 38, 34), (55, 43), 12)
    pygame.draw.circle(s, (255, 151, 48), (58, 46), 5)
    pygame.draw.line(s, (195, 183, 157), (18, 76), (78, 76), 5)
    pygame.draw.line(s, (195, 183, 157), (28, 18), (72, 18), 4)
    return s


def draw_wing() -> pygame.Surface:
    s = rounded_surface((96, 96))
    pygame.draw.ellipse(s, (214, 127, 66), (20, 28, 58, 42))
    pygame.draw.ellipse(s, (126, 56, 38), (20, 28, 58, 42), 4)
    pygame.draw.circle(s, (252, 185, 87), (40, 38), 8)
    pygame.draw.circle(s, (255, 101, 48), (65, 63), 9)
    pygame.draw.circle(s, (255, 205, 75), (68, 60), 5)
    pygame.draw.line(s, (221, 169, 100), (15, 76), (82, 18), 5)
    pygame.draw.polygon(s, (255, 236, 171), [(82, 18), (89, 9), (87, 24)])
    return s


def draw_beef() -> pygame.Surface:
    s = rounded_surface((96, 96))
    pygame.draw.ellipse(s, (220, 97, 94), (18, 30, 62, 38))
    pygame.draw.ellipse(s, (255, 210, 218), (25, 38, 44, 13))
    pygame.draw.ellipse(s, (138, 53, 61), (18, 30, 62, 38), 3)
    for x, y in [(28, 25), (58, 23), (72, 39)]:
        pygame.draw.polygon(s, (171, 225, 255), [(x, y - 8), (x + 8, y), (x, y + 8), (x - 8, y)])
        pygame.draw.polygon(s, (93, 173, 224), [(x, y - 8), (x + 8, y), (x, y + 8), (x - 8, y)], 2)
    pygame.draw.circle(s, (229, 246, 255), (38, 64), 5)
    return s


def draw_zombie(kind: str) -> pygame.Surface:
    s = rounded_surface((96, 112))
    skin = (92, 157, 96)
    shirt = (90, 111, 153)
    pants = (56, 62, 78)
    if kind == "courier":
        skin = (100, 178, 111)
        shirt = (244, 156, 55)
    if kind == "pot":
        skin = (84, 145, 92)
        shirt = (93, 101, 121)
    pygame.draw.rect(s, pants, (32, 70, 13, 34), border_radius=5)
    pygame.draw.rect(s, pants, (52, 70, 13, 34), border_radius=5)
    pygame.draw.rect(s, shirt, (28, 43, 40, 38), border_radius=10)
    pygame.draw.circle(s, skin, (49, 28), 22)
    pygame.draw.circle(s, (39, 44, 38), (41, 25), 4)
    pygame.draw.circle(s, (39, 44, 38), (57, 25), 4)
    pygame.draw.arc(s, (55, 45, 44), (39, 31, 20, 12), 0.2, 2.9, 3)
    pygame.draw.line(s, skin, (27, 53), (14, 71), 8)
    pygame.draw.line(s, skin, (69, 53), (84, 67), 8)
    if kind == "pot":
        pygame.draw.ellipse(s, (167, 169, 164), (22, 4, 54, 20))
        pygame.draw.rect(s, (138, 141, 139), (27, 8, 44, 17), border_radius=7)
        pygame.draw.rect(s, (95, 97, 96), (38, 2, 21, 8), border_radius=4)
    if kind == "courier":
        pygame.draw.rect(s, (238, 190, 68), (63, 47, 22, 28), border_radius=4)
        pygame.draw.rect(s, (123, 75, 45), (63, 47, 22, 28), 2, border_radius=4)
        pygame.draw.line(s, (255, 229, 120), (36, 42), (61, 77), 4)
    return s


def draw_icons() -> None:
    save(draw_skewer(), "skewer.png")
    save(draw_wall(), "pork_wall.png")
    save(draw_meatball(), "meatball.png")
    save(draw_charcoal(), "charcoal.png")
    save(draw_wing(), "wing.png")
    save(draw_beef(), "beef.png")
    save(draw_zombie("normal"), "zombie_normal.png")
    save(draw_zombie("pot"), "zombie_pot.png")
    save(draw_zombie("courier"), "zombie_courier.png")


def main() -> None:
    pygame.init()
    draw_icons()
    pygame.quit()
    print(f"Generated assets in {IMAGE_DIR}")


if __name__ == "__main__":
    main()
