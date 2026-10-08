"""程序绘制的美术：卡牌、纹兽、纹域、角色头像。

所有图都用代码画，不依赖图片文件。以后有了正式插画，放进 assets/ 目录就会自动替换：
    assets/cards/<卡名>.png      卡面插画（任意尺寸，会缩放到插画区）
    assets/beasts/<种类>.png     纹兽本体，例如 assets/beasts/苍狼.png
    assets/heroes/<职业>.png     角色头像，例如 assets/heroes/warrior.png
"""

from __future__ import annotations

import hashlib
import math
import os
import random

import pygame

from ..cards import BLUE, GREEN, RED, Card

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS = os.path.join(ROOT, "assets")

# ---------------------------------------------------------------- 配色
BG = (22, 29, 27)
BOARD = (35, 43, 37)
BOARD_EDGE = (94, 98, 73)
INK = (232, 230, 220)
DIM = (140, 144, 160)
GOLD = (232, 190, 92)
DANGER = (230, 80, 70)
OK = (110, 210, 140)
PANEL = (37, 45, 39)

COLOR = {RED: (214, 72, 60), GREEN: (64, 182, 112), BLUE: (66, 140, 232)}
COLOR_DARK = {RED: (70, 22, 20), GREEN: (18, 58, 36), BLUE: (18, 38, 74)}
COLOR_GLOW = {RED: (255, 140, 110), GREEN: (140, 255, 180), BLUE: (140, 200, 255)}

CARD_W, CARD_H = 124, 176

# ---------------------------------------------------------------- 字体
_FONT_NAMES = ["microsoftyahei", "pingfangsc", "pingfang", "notosanscjksc", "notosanscjk",
               "sourcehansanssc", "wenquanyizenhei", "wqyzenhei", "simhei", "heiti", "arialunicode"]
_fonts: dict = {}


def font(size: int, bold: bool = False) -> pygame.font.Font:
    key = (size, bold)
    if key not in _fonts:
        f = None
        for name in _FONT_NAMES:
            path = pygame.font.match_font(name, bold=bold)
            if path:
                f = pygame.font.Font(path, size)
                break
        _fonts[key] = f or pygame.font.Font(None, size)
    return _fonts[key]


def text(surf, s, pos, size=16, color=INK, center=False, bold=False, right=False):
    img = font(size, bold).render(str(s), True, color)
    r = img.get_rect()
    if center:
        r.center = pos
    elif right:
        r.topright = pos
    else:
        r.topleft = pos
    surf.blit(img, r)
    return r


def wrap(s: str, size: int, width: int) -> list[str]:
    f = font(size)
    lines, cur = [], ""
    for ch in s:
        if f.size(cur + ch)[0] > width:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------- 外部插画
_images: dict = {}


def asset(kind: str, name: str, size: tuple[int, int]):
    key = (kind, name, size)
    if key not in _images:
        img = None
        path = os.path.join(ASSETS, kind, f"{name}.png")
        if os.path.exists(path):
            try:
                original = pygame.image.load(path).convert_alpha()
                # Preserve the hand-drawn subject's proportions in every display slot.
                if kind == "beasts":
                    factor = min(size[0] / original.get_width(), size[1] / original.get_height())
                    fitted = pygame.transform.smoothscale(original, (
                        max(1, round(original.get_width() * factor)),
                        max(1, round(original.get_height() * factor)),
                    ))
                    img = pygame.Surface(size, pygame.SRCALPHA)
                    img.blit(fitted, fitted.get_rect(center=(size[0] // 2, size[1] // 2)))
                else:
                    factor = max(size[0] / original.get_width(), size[1] / original.get_height())
                    fitted = pygame.transform.smoothscale(original, (
                        max(size[0], round(original.get_width() * factor)),
                        max(size[1], round(original.get_height() * factor)),
                    ))
                    img = pygame.Surface(size, pygame.SRCALPHA)
                    img.blit(fitted, fitted.get_rect(center=(size[0] // 2, size[1] // 2)))
            except pygame.error:
                img = None
        _images[key] = img
    return _images[key]


def draw_background(surf, rect: pygame.Rect, name: str, t: float):
    """Static hand-drawn art with inexpensive drifting leaves and fireflies."""
    background = asset("backgrounds", name, rect.size)
    if background:
        surf.blit(background, rect.topleft)
        veil = pygame.Surface(rect.size, pygame.SRCALPHA)
        veil.fill((10, 22, 16, 55))
        surf.blit(veil, rect.topleft)
    else:
        pygame.draw.rect(surf, BOARD, rect)
    layer = pygame.Surface(rect.size, pygame.SRCALPHA)
    rng = random.Random(2718)
    for k in range(14):
        x = (rng.uniform(0, rect.w) + t * (3 + k % 4)) % rect.w
        y = (rng.uniform(0, rect.h) + t * (2 + k % 3)) % rect.h
        if k % 3:
            pygame.draw.ellipse(layer, (161, 177, 112, 70), (x, y, 7, 3))
        else:
            alpha = 45 + int(35 * (1 + math.sin(t + k)))
            pygame.draw.circle(layer, (230, 214, 140, alpha), (x, y), 2)
    surf.blit(layer, rect.topleft)


def draw_impact(surf, center, color, age: float, healing=False):
    """Short cel-style impact slash or healing ripple, without frame images."""
    duration = 0.45
    if not 0 <= age < duration:
        return
    progress = age / duration
    alpha = round(200 * (1 - progress))
    layer = pygame.Surface((160, 160), pygame.SRCALPHA)
    rgba = (*color, alpha)
    radius = round(12 + progress * 48)
    pygame.draw.circle(layer, rgba, (80, 80), radius, 2)
    if healing:
        for k in range(4):
            angle = k * math.pi / 2 + progress
            point = (round(80 + math.cos(angle) * radius), round(80 + math.sin(angle) * radius))
            pygame.draw.circle(layer, rgba, point, 3)
    else:
        width = max(1, round(6 * (1 - progress)))
        pygame.draw.line(layer, rgba, (35, 112), (122, 35), width)
        for k in range(6):
            angle = k * math.tau / 6
            start = (round(80 + math.cos(angle) * radius), round(80 + math.sin(angle) * radius))
            end = (round(80 + math.cos(angle) * (radius + 12)), round(80 + math.sin(angle) * (radius + 12)))
            pygame.draw.line(layer, rgba, start, end, 2)
    surf.blit(layer, (center[0] - 80, center[1] - 80))


# ---------------------------------------------------------------- 纹路
def seed_of(s: str) -> int:
    return int(hashlib.md5(s.encode("utf-8")).hexdigest()[:8], 16)


def sigil_pattern(surf, rect: pygame.Rect, color, seed: int, density: int = 7, width: int = 2, alpha=255):
    """每张卡独一无二的纹：一组对称的折线和弧线，像刻在石头上的符文。"""
    rng = random.Random(seed)
    layer = pygame.Surface(rect.size, pygame.SRCALPHA)
    cx, cy = rect.w / 2, rect.h / 2
    glow = (*color, max(30, alpha // 4))
    main = (*color, alpha)
    strokes = []
    for _ in range(density):
        n = rng.randint(2, 4)
        pts = [(rng.uniform(0.08, 0.5) * rect.w, rng.uniform(0.1, 0.9) * rect.h) for _ in range(n)]
        strokes.append(pts)
    for pts in strokes:
        for mirror in (False, True):
            p = [((2 * cx - x) if mirror else x, y) for x, y in pts]
            pygame.draw.lines(layer, glow, False, p, width + 4)
    for pts in strokes:
        for mirror in (False, True):
            p = [((2 * cx - x) if mirror else x, y) for x, y in pts]
            pygame.draw.lines(layer, main, False, p, width)
    r = rng.uniform(0.18, 0.32) * min(rect.w, rect.h)
    pygame.draw.circle(layer, glow, (cx, cy), r, width + 4)
    pygame.draw.circle(layer, main, (cx, cy), r, width)
    for k in range(rng.choice([3, 4, 6])):
        a = k * math.tau / 6 + rng.random() * 0.2
        pygame.draw.circle(layer, main, (cx + math.cos(a) * r, cy + math.sin(a) * r), 3)
    surf.blit(layer, rect.topleft)


def gem(surf, center, r, fill, label, size=18, outline=(20, 20, 20)):
    pygame.draw.circle(surf, outline, center, r + 2)
    pygame.draw.circle(surf, fill, center, r)
    pygame.draw.circle(surf, tuple(min(255, c + 60) for c in fill), (center[0] - r // 3, center[1] - r // 3), r // 3)
    text(surf, label, center, size, (255, 255, 255), center=True, bold=True)


def shield_icon(surf, center, n, size=14):
    x, y = center
    pts = [(x - 11, y - 12), (x + 11, y - 12), (x + 11, y), (x, y + 13), (x - 11, y)]
    pygame.draw.polygon(surf, (40, 40, 40), [(px, py + 1) for px, py in pts])
    pygame.draw.polygon(surf, (190, 200, 215), pts)
    text(surf, n, (x, y - 1), size, (30, 30, 40), center=True, bold=True)


# ---------------------------------------------------------------- 卡牌
def draw_card(surf, card: Card, topleft, scale=1.0, cost=None, highlight=None, dim=False):
    w, h = int(CARD_W * scale), int(CARD_H * scale)
    s = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
    c, dark = COLOR[card.color], COLOR_DARK[card.color]
    pygame.draw.rect(s, (12, 12, 16), (0, 0, CARD_W, CARD_H), border_radius=12)
    pygame.draw.rect(s, c, (2, 2, CARD_W - 4, CARD_H - 4), border_radius=11)
    pygame.draw.rect(s, dark, (7, 7, CARD_W - 14, CARD_H - 14), border_radius=8)
    frame = asset("ui", f"card_frame_{card.color}", (CARD_W, CARD_H))
    if frame:
        s.blit(frame, (0, 0))
    art = pygame.Rect(12, 30, CARD_W - 24, 66)
    pygame.draw.rect(s, (8, 10, 16), art, border_radius=6)
    img = asset("cards", card.name, art.size)
    if img:
        s.blit(img, art.topleft)
    else:
        sigil_pattern(s, art, COLOR_GLOW[card.color], seed_of(card.name), density=5, width=2)
    pygame.draw.rect(s, c, art, 1, border_radius=6)
    text(s, card.name, (CARD_W // 2, 18), 15, INK, center=True, bold=True)
    y = 100
    if card.keyword:
        text(s, f"【{card.keyword}】", (CARD_W // 2, y + 6), 12, GOLD, center=True)
        y += 14
    for line in wrap(card.text, 12, CARD_W - 22)[:4]:
        text(s, line, (11, y), 12, INK)
        y += 15
    shown = card.cost if cost is None else cost
    gem(s, (16, 16), 13, (60, 110, 220) if shown == card.cost else (60, 190, 120), shown, 17)
    # 纹值：右上角一个小纹章
    pygame.draw.polygon(s, (12, 12, 16), [(CARD_W - 17, 2), (CARD_W - 3, 16), (CARD_W - 17, 30), (CARD_W - 31, 16)])
    pygame.draw.polygon(s, COLOR_GLOW[card.color], [(CARD_W - 17, 5), (CARD_W - 6, 16), (CARD_W - 17, 27), (CARD_W - 28, 16)])
    text(s, card.sigil, (CARD_W - 17, 16), 14, (15, 15, 20), center=True, bold=True)
    if dim:
        shade = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 110))
        s.blit(shade, (0, 0))
    if highlight:
        pygame.draw.rect(s, highlight, (0, 0, CARD_W, CARD_H), 3, border_radius=12)
    if scale != 1.0:
        s = pygame.transform.smoothscale(s, (w, h))
    surf.blit(s, topleft)
    return pygame.Rect(topleft, (w, h))


def draw_card_back(surf, rect: pygame.Rect, label: str | None = None):
    pygame.draw.rect(surf, (12, 12, 16), rect, border_radius=10)
    inner = rect.inflate(-6, -6)
    pygame.draw.rect(surf, (48, 40, 72), inner, border_radius=8)
    sigil_pattern(surf, inner.inflate(-8, -8), (190, 160, 255), 7, density=4, width=1, alpha=180)
    pygame.draw.rect(surf, GOLD, inner, 1, border_radius=8)
    backing = asset("ui", "card_back", rect.size)
    if backing:
        surf.blit(backing, rect.topleft)
    if label:
        text(surf, label, rect.center, 14, INK, center=True, bold=True)


# ---------------------------------------------------------------- 纹兽
def beast_body(surf, rect: pygame.Rect, base_atk: int, base_hp: int, species: str):
    """几何风格的纹兽本体。攻击高的更尖锐，血量高的更宽厚，数值越高越大。"""
    img = asset("beasts", species, rect.size)
    if img:
        surf.blit(img, rect.topleft)
        return
    rng = random.Random(seed_of(species))
    power = (base_atk + base_hp) / 6
    cx, cy = rect.centerx, rect.centery + 6
    R = rect.w * (0.22 + 0.16 * power)
    spikes = 3 + base_atk * 2
    bulk = 0.55 + base_hp * 0.12
    pts = []
    for k in range(spikes * 2):
        a = -math.pi / 2 + k * math.pi / spikes
        rr = R if k % 2 == 0 else R * bulk
        rr *= 1 + rng.uniform(-0.08, 0.08)
        pts.append((cx + math.cos(a) * rr * 1.1, cy + math.sin(a) * rr * 0.85))
    hue = (60 + base_atk * 40, 70 + base_hp * 30, 110)
    pygame.draw.polygon(surf, (10, 10, 14), [(x + 3, y + 4) for x, y in pts])
    pygame.draw.polygon(surf, hue, pts)
    pygame.draw.polygon(surf, tuple(min(255, v + 70) for v in hue), pts, 2)
    eye_y = cy - R * 0.15
    for dx in (-1, 1):
        ex = cx + dx * R * 0.32
        pygame.draw.ellipse(surf, (250, 240, 200), (ex - 6, eye_y - 4, 12, 8 + base_atk))
        pygame.draw.circle(surf, (20, 10, 10), (ex, eye_y), 3)


def draw_beast(surf, rect: pygame.Rect, b, atk_shown: int, selected=False, can_attack=False):
    pygame.draw.ellipse(surf, (10, 10, 14), rect.inflate(6, 6))
    ring = OK if can_attack else BOARD_EDGE
    pygame.draw.ellipse(surf, (34, 38, 56), rect)
    pygame.draw.ellipse(surf, ring, rect, 3)
    if b.level >= 2:
        pulse = (math.sin(pygame.time.get_ticks() / 280) + 1) / 2
        glow = COLOR_GLOW[b.sigils[-1]] if b.sigils else GOLD
        layer = pygame.Surface(rect.inflate(28, 28).size, pygame.SRCALPHA)
        pygame.draw.ellipse(layer, (*glow, int(70+90*pulse)), layer.get_rect().inflate(-6, -6), 3 if b.level == 2 else 5)
        if b.level == 3:
            sigil_pattern(layer, layer.get_rect(), glow, seed_of(b.species), density=5, width=2, alpha=150)
        surf.blit(layer, rect.inflate(28, 28).topleft)
    beast_body(surf, rect.inflate(-28, -36), b.base_atk, b.base_hp, b.species)
    # 进化叠加的纹路：每级一道对应颜色的光纹
    for k, col in enumerate(b.sigils):
        layer = pygame.Surface(rect.size, pygame.SRCALPHA)
        sigil_pattern(layer, layer.get_rect(), COLOR_GLOW[col], seed_of(b.species + str(k)), 3, 2, 200)
        surf.blit(layer, rect.topleft)
    text(surf, b.name, (rect.centerx, rect.top - 12), 14, INK, center=True, bold=True)
    text(surf, "觉醒·3级" if b.level == 3 else f"{b.level}级", (rect.centerx, rect.bottom - 14), 12, GOLD, center=True)
    gem(surf, (rect.left + 12, rect.bottom - 12), 15, (200, 150, 40), atk_shown, 18)
    gem(surf, (rect.right - 12, rect.bottom - 12), 15, (190, 50, 50), b.hp, 18)
    if b.shield_total():
        shield_icon(surf, (rect.right - 10, rect.top + 14), b.shield_total())
    tags = []
    if b.pierce:
        tags.append("穿透")
    if b.level == 3:
        tags.append(f"剩{b.l3_rounds}回合")
    if b.sick:
        tags.append("休整")
    if b.sealed:
        tags.append("封印")
    if tags:
        text(surf, " ".join(tags), (rect.centerx, rect.bottom + 12), 12, DIM, center=True)
    if selected:
        pygame.draw.ellipse(surf, GOLD, rect.inflate(8, 8), 3)


# ---------------------------------------------------------------- 纹域
def draw_field_floor(surf, rect: pygame.Rect, first: str, second: str, t: float):
    """纹域生效后地板上的光线；两种颜色交叉成渐变纹。"""
    layer = pygame.Surface(rect.size, pygame.SRCALPHA)
    floor = asset("fields", first, rect.size)
    if floor:
        layer.blit(floor, (0, 0))
    c1, c2 = COLOR_GLOW[first], COLOR_GLOW[second]
    n = 9
    for k in range(n):
        f = k / (n - 1)
        col = tuple(int(c1[i] * (1 - f) + c2[i] * f) for i in range(3))
        pulse = 120 + int(80 * math.sin(t * 2 + k * 0.7))
        x = int(f * rect.w)
        pygame.draw.line(layer, (*col, pulse), (x, 0), (rect.w - x, rect.h), 2)
        y = int(f * rect.h)
        pygame.draw.line(layer, (*col, pulse // 2), (0, y), (rect.w, rect.h - y), 1)
    surf.blit(layer, rect.topleft)


# ---------------------------------------------------------------- 角色
HERO_COLOR = {"warrior": RED, "archmage": BLUE, "guardian": GREEN}


def draw_hero(surf, center, radius, p, selected=False, glow=False):
    col = COLOR[HERO_COLOR[p.cls]]
    pygame.draw.circle(surf, (10, 10, 14), center, radius + 6)
    pygame.draw.circle(surf, OK if glow else col, center, radius + 4, 4)
    pygame.draw.circle(surf, COLOR_DARK[HERO_COLOR[p.cls]], center, radius)
    img = asset("heroes", p.cls, (radius * 2, radius * 2))
    if img:
        mask = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(mask, (255, 255, 255, 255), (radius, radius), radius)
        img = img.copy()
        img.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        surf.blit(img, (center[0] - radius, center[1] - radius))
    else:
        r = pygame.Rect(0, 0, radius * 2, radius * 2)
        r.center = center
        sigil_pattern(surf, r.inflate(-radius // 2, -radius // 2), COLOR_GLOW[HERO_COLOR[p.cls]],
                      seed_of(p.cls), density=4, width=2)
    gem(surf, (center[0] + radius - 6, center[1] + radius - 8), 17, (190, 50, 50), p.hp, 20)
    gem(surf, (center[0] - radius + 6, center[1] + radius - 8), 17, (200, 150, 40), p.hero_atk(), 20)
    if p.shield_total():
        shield_icon(surf, (center[0], center[1] + radius + 4), p.shield_total(), 15)
    if selected:
        pygame.draw.circle(surf, GOLD, center, radius + 9, 3)

