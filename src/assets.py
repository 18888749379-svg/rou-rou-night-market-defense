from __future__ import annotations

import math
from array import array
from pathlib import Path

import pygame

from settings import AUDIO_DIR, IMAGE_DIR


_FONT_CACHE: dict[tuple[int, bool], pygame.font.Font] = {}
_IMAGE_CACHE: dict[tuple[str, tuple[int, int] | None], pygame.Surface] = {}


def get_font(size: int, bold: bool = False) -> pygame.font.Font:
    cache_key = (size, bold)
    cached = _FONT_CACHE.get(cache_key)
    if cached is not None:
        return cached
    font_paths = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for path in font_paths:
        if path.exists():
            font = pygame.font.Font(str(path), size)
            _FONT_CACHE[cache_key] = font
            return font
    font = pygame.font.Font(None, size)
    _FONT_CACHE[cache_key] = font
    return font


def load_image(name: str, size: tuple[int, int] | None = None) -> pygame.Surface:
    cache_key = (name, size)
    cached = _IMAGE_CACHE.get(cache_key)
    if cached is not None:
        return cached
    path = IMAGE_DIR / name
    if path.exists():
        image = pygame.image.load(path).convert_alpha()
    else:
        image = pygame.Surface(size or (80, 80), pygame.SRCALPHA)
        image.fill((210, 110, 90, 255))
        pygame.draw.rect(image, (50, 40, 40), image.get_rect(), 3, border_radius=8)
    if size:
        image = pygame.transform.smoothscale(image, size)
    _IMAGE_CACHE[cache_key] = image
    return image


class Audio:
    def __init__(self) -> None:
        self.available = False
        self.music_enabled = True
        self.sfx_enabled = True
        self.music_volume = 0.35
        self.sfx_volume = 0.7
        self.effect_volumes = {
            "attack_skewer": 0.8,
            "attack_wing": 0.75,
            "attack_beef": 0.7,
            "attack_meatball": 0.8,
            "zombie_spawn": 0.65,
            "final_wave": 0.85,
        }
        self.music_tracks = {
            "menu": AUDIO_DIR / "menu_music.ogg",
            "game": AUDIO_DIR / "game_music.mp3",
        }
        self.current_music: str | None = None
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            self.available = True
            self.sounds = {
                "click": self._tone(760, 0.05, 0.18),
                "place": self._tone(520, 0.08, 0.22),
                "hit": self._tone(210, 0.04, 0.18),
                "remove": self._tone(340, 0.09, 0.22),
                "bad": self._tone(130, 0.11, 0.22),
                "win": self._tone(660, 0.25, 0.25),
                "lose": self._tone(120, 0.35, 0.28),
            }
            files = {
                "attack_skewer": "attack_skewer.ogg",
                "attack_wing": "attack_wing.ogg",
                "attack_beef": "attack_beef.wav",
                "attack_meatball": "attack_meatball.ogg",
                "zombie_spawn": "zombie_spawn.mp3",
                "final_wave": "final_wave.mp3",
            }
            for name, filename in files.items():
                path = AUDIO_DIR / filename
                if path.exists():
                    self.sounds[name] = pygame.mixer.Sound(path)
        except pygame.error:
            self.available = False

    def _tone(self, frequency: int, seconds: float, volume: float) -> pygame.mixer.Sound:
        sample_rate = 22050
        samples = int(sample_rate * seconds)
        data = array("h")
        amplitude = int(32767 * volume)
        for i in range(samples):
            fade = 1.0 - i / max(samples, 1)
            value = int(amplitude * fade * math.sin(2 * math.pi * frequency * i / sample_rate))
            data.append(value)
            data.append(value)
        return pygame.mixer.Sound(buffer=data.tobytes())

    def play(self, name: str) -> None:
        if not self.available or not self.sfx_enabled or name not in self.sounds:
            return
        sound = self.sounds[name]
        sound.set_volume(self.sfx_volume * self.effect_volumes.get(name, 1.0))
        sound.play()

    def play_music(self, track: str) -> None:
        if not self.available:
            return
        if not self.music_enabled:
            self.current_music = track
            pygame.mixer.music.stop()
            return
        path = self.music_tracks.get(track)
        if path is None or not path.exists():
            return
        if self.current_music == track and pygame.mixer.music.get_busy():
            return
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(self.music_volume)
            pygame.mixer.music.play(-1, fade_ms=350)
            self.current_music = track
        except pygame.error:
            pass

    def set_music_enabled(self, enabled: bool) -> None:
        self.music_enabled = enabled
        if not self.available:
            return
        if enabled and self.current_music:
            track = self.current_music
            self.current_music = None
            self.play_music(track)
        else:
            pygame.mixer.music.stop()

    def set_music_volume(self, volume: float) -> None:
        self.music_volume = max(0.0, min(1.0, volume))
        if self.available:
            pygame.mixer.music.set_volume(self.music_volume)

    def set_sfx_volume(self, volume: float) -> None:
        self.sfx_volume = max(0.0, min(1.0, volume))

    def set_effect_volume(self, name: str, volume: float) -> None:
        self.effect_volumes[name] = max(0.0, min(1.0, volume))
