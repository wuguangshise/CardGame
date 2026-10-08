"""Time-based launch, travel and impact effects; no changes to game state."""
from dataclasses import dataclass
import math
import pygame

from . import art


@dataclass
class Flight:
    start: tuple
    end: tuple
    color: str = 'red'
    style: str = 'spell'
    duration: float = .46
    body: pygame.Surface | None = None

    def position(self, progress):
        u = max(0., min(1., progress))
        # Slow launch, accelerated travel, slight arc. Always reaches the real target.
        t = u * u * (3 - 2 * u)
        x = self.start[0] + (self.end[0] - self.start[0]) * t
        y = self.start[1] + (self.end[1] - self.start[1]) * t
        return x + math.sin(math.pi * t) * 30, y

    def draw(self, surface, progress):
        col = art.COLOR_GLOW[self.color]
        layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        x, y = self.position(progress)
        center = (round(x), round(y))
        trail = [self.position(max(0, progress - k * .023)) for k in range(12)]
        for k in range(len(trail)-1, 0, -1):
            alpha = int(170 * (1 - k / len(trail)))
            pygame.draw.line(layer, (*col, alpha), trail[k], trail[k-1], max(2, 13-k))
        # Traveling particles, deterministic so the effect doesn't flicker randomly.
        for k in range(8):
            tx, ty = self.position(max(0, progress - .025 * k))
            dy = math.sin(k * 2.2 + progress * 12) * (4+k)
            pygame.draw.circle(layer, (*col, max(20, 180-k*20)), (round(tx), round(ty+dy)), 3)
        for radius, alpha in ((28, 25), (20, 65), (13, 145)):
            pygame.draw.circle(layer, (*col, alpha), center, radius)
        angle = math.atan2(self.end[1]-self.start[1], self.end[0]-self.start[0])
        if self.style == 'beast' and self.body is not None:
            ghost = self.body.copy()
            ghost.set_alpha(230)
            layer.blit(ghost, ghost.get_rect(center=center))
            for k in range(3):
                offset = (k-1)*10
                pygame.draw.line(layer, (255, 245, 220, 230),
                                 (x-12+offset, y-18), (x+12+offset, y+18), 3)
        elif self.color == 'red':
            dx, dy = math.cos(angle), math.sin(angle)
            pygame.draw.line(layer, (*col, 255), (x-dx*28, y-dy*28), (x+dx*20, y+dy*20), 9)
            pygame.draw.line(layer, (255, 250, 230, 255), (x-dx*20, y-dy*20), (x+dx*15, y+dy*15), 3)
        else:
            pygame.draw.circle(layer, (250, 255, 245, 255), center, 7)
            pygame.draw.circle(layer, (*col, 230), center, 19, 2)
            for k in range(3):
                a = angle + progress * 7 + k * math.tau / 3
                pygame.draw.circle(layer, (*col, 240), (round(x+22*math.cos(a)), round(y+22*math.sin(a))), 4)
        # Source rune and target marker make direction obvious before contact.
        if progress < .35:
            pygame.draw.circle(layer, (*col, int(150*(1-progress/.35))), self.start, round(18+progress*65), 2)
        pygame.draw.circle(layer, (*col, 90), self.end, 24, 2)
        surface.blit(layer, (0, 0))


def draw_burst(surface, center, color, age, blocked=False, awakening=False):
    duration = .65 if awakening else .4
    if not 0 <= age < duration:
        return
    t = age / duration
    col = art.COLOR_GLOW[color]
    layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    radius = round(12 + t * (85 if awakening else 48))
    alpha = round(230 * (1-t))
    pygame.draw.circle(layer, (*col, alpha), center, radius, max(1, round(6*(1-t))))
    if t < .22:
        pygame.draw.circle(layer, (255, 255, 235, round(160*(1-t/.22))), center, 34)
    for k in range(12):
        angle = k * math.tau / 12 + .3
        reach = radius * (1.4 if k % 2 else 1.8)
        a = (center[0]+math.cos(angle)*radius*.6, center[1]+math.sin(angle)*radius*.6)
        b = (center[0]+math.cos(angle)*reach, center[1]+math.sin(angle)*reach)
        pygame.draw.line(layer, (*col, alpha), a, b, 3)
    if blocked:
        pygame.draw.arc(layer, (170, 220, 255, alpha), pygame.Rect(center[0]-42, center[1]-45, 84, 90), .2, math.pi-.2, 6)
    surface.blit(layer, (0, 0))
