"""《双生纹》图形界面：鼠标拖动出牌，参考炉石传说的操作方式。

操作：
- 把手牌拖到场地中间：打出这张牌
- 把手牌拖到另一张手牌上：合纹（被拖的那张当附加卡）
- 把红牌 / 绿牌拖到纹兽位：放牌召唤（一红一绿凑齐就召唤）
- 把牌拖到已有纹兽上：用这张牌进化它（另一只 1 级纹兽当素材）
- 把牌拖到纹域位：放牌成型纹域；把蓝牌拖到生效的纹域上可以续命
- 把牌拖到防御纹：盖牌；点击自己的防御纹：翻开
- 把牌拖到「献祭」台：献祭换 1 纹力
- 从自己的角色或纹兽拖出箭头到敌方目标：攻击
"""

from __future__ import annotations

import math
import sys
import time

import pygame

from ..ai import AIController
from ..cards import BLUE, Card
from ..engine import CLASSES, Beast, Controller, Field, Game, Pending, Player, RuleError
from . import art
from .art import BOARD, BOARD_EDGE, CARD_H, CARD_W, DANGER, DIM, GOLD, INK, OK, PANEL

W, H = 1280, 800
LOG_X = 1010
TURN_SECONDS = 30
DEFENSE_SECONDS = 8
HAND_SCALE = 0.86


class Quit(Exception):
    pass


class GUI:
    def __init__(self, seed=None, timer=True, screenshot_dir=None):
        pygame.init()
        pygame.display.set_caption("双生纹")
        self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        self.seed = seed
        self.timer = timer
        self.logs: list[str] = []
        self.toast = ("", 0.0)
        self.drag = None          # ("card", card) 或 ("attack", attacker)
        self.mouse = (0, 0)
        self.turn_deadline = None
        self.popups = []          # [x, y, text, color, born]
        self._last_hp = {}
        self.game: Game | None = None
        self.me: Player | None = None
        self.layout()

    # ================================================================ 布局
    def layout(self):
        self.enemy_hero = (500, 92)
        self.my_hero = (500, 548)
        self.hero_r = 46
        self.rows = {"foe": 182, "me": 360}
        self.slot_rects = {}
        for side, y in self.rows.items():
            self.slot_rects[(side, "field", 0)] = pygame.Rect(40, y, 170, 120)
            self.slot_rects[(side, "beast", 0)] = pygame.Rect(300, y + 4, 150, 116)
            self.slot_rects[(side, "beast", 1)] = pygame.Rect(550, y + 4, 150, 116)
            self.slot_rects[(side, "field", 1)] = pygame.Rect(790, y, 170, 120)
        self.foe_def = pygame.Rect(340, 44, 66, 92)
        self.my_def = pygame.Rect(340, 500, 66, 92)
        self.altar = pygame.Rect(700, 500, 84, 92)
        self.end_btn = pygame.Rect(830, 548, 140, 52)
        self.play_zone = pygame.Rect(0, 160, LOG_X, 450)

    def hand_rects(self, n: int) -> list[pygame.Rect]:
        w, h = int(CARD_W * HAND_SCALE), int(CARD_H * HAND_SCALE)
        gap = min(w + 8, (LOG_X - 120) // max(1, n))
        total = gap * (n - 1) + w
        x0 = (LOG_X - total) // 2
        return [pygame.Rect(x0 + i * gap, H - h - 12, w, h) for i in range(n)]

    # ================================================================ 事件工具
    def pump(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                raise Quit
        self.mouse = pygame.mouse.get_pos()

    def wait(self, seconds: float):
        end = time.time() + seconds
        while time.time() < end:
            self.pump()
            self.render()
            self.clock.tick(60)

    def say(self, msg: str, color=DANGER):
        self.toast = (msg, time.time(), color)

    def on_log(self, line: str):
        self.logs.append(line)
        self.logs = self.logs[-200:]
        if self.game and self.me and self.game.players[self.game.current] is not self.me and line.startswith("▶"):
            self.wait(0.55)

    # ================================================================ 绘制
    def render(self, overlay=None):
        s = self.screen
        s.fill(art.BG)
        pygame.draw.rect(s, BOARD, (0, 0, LOG_X, H))
        pygame.draw.line(s, BOARD_EDGE, (0, 350), (LOG_X, 350), 1)
        g, me = self.game, self.me
        if g and me:
            foe = g.opp(me)
            self.draw_side(foe, "foe")
            self.draw_side(me, "me")
            self.draw_heroes(me, foe)
            self.draw_hand(me)
            self.draw_hud(me, foe)
        self.draw_log()
        self.draw_popups()
        if self.drag:
            self.draw_drag()
        msg, born, *col = self.toast if len(self.toast) == 3 else (*self.toast, DANGER)
        if msg and time.time() - born < 2.2:
            r = art.text(s, msg, (LOG_X // 2, 330), 20, col[0] if col else DANGER, center=True, bold=True)
            pygame.draw.rect(s, (0, 0, 0), r.inflate(24, 12), border_radius=8)
            art.text(s, msg, (LOG_X // 2, 330), 20, col[0] if col else DANGER, center=True, bold=True)
        if overlay:
            overlay()
        pygame.display.flip()

    def draw_side(self, p: Player, side: str):
        s = self.screen
        g = self.game
        mine = side == "me"
        t = time.time()
        for (sd, kind, i), r in self.slot_rects.items():
            if sd != side:
                continue
            if kind == "field":
                f = p.fields[i]
                pygame.draw.rect(s, (20, 22, 34), r, border_radius=12)
                if isinstance(f, Field):
                    art.draw_field_floor(s, r.inflate(-8, -8), f.first.color, f.second.color, t)
                    pygame.draw.rect(s, art.COLOR[f.first.color], r, 2, border_radius=12)
                    lines = art.wrap(f.describe().split("（", 1)[1].rstrip("）"), 12, r.w - 20)[:4]
                    box = pygame.Surface((r.w - 12, 30 + 16 * len(lines)), pygame.SRCALPHA)
                    box.fill((0, 0, 0, 150))
                    s.blit(box, (r.left + 6, r.top + 4))
                    art.text(s, f.name, (r.centerx, r.top + 16), 14, INK, center=True, bold=True)
                    for k, line in enumerate(lines):
                        art.text(s, line, (r.left + 10, r.top + 30 + k * 16), 12, INK)
                elif isinstance(f, Pending):
                    art.draw_card_back(s, pygame.Rect(r.centerx - 30, r.top + 14, 60, 84), "1/2")
                    art.text(s, "纹域（盖着 1 张）", (r.centerx, r.bottom - 10), 12, DIM, center=True)
                    if mine:
                        art.text(s, f.card.name, (r.centerx, r.top + 6), 11, DIM, center=True)
                else:
                    pygame.draw.rect(s, BOARD_EDGE, r, 1, border_radius=12)
                    art.text(s, "纹域位", r.center, 14, DIM, center=True)
            else:
                b = p.beasts[i]
                if isinstance(b, Beast):
                    can = mine and g.players[g.current] is self.me and not b.sick and not b.attacked \
                        and not b.sealed and p.turns > 1
                    sel = self.drag and self.drag[0] == "attack" and self.drag[1] == i and mine
                    art.draw_beast(s, r, b, p.beast_atk(b), selected=sel, can_attack=can)
                elif isinstance(b, Pending):
                    pygame.draw.ellipse(s, (30, 32, 46), r)
                    art.draw_card_back(s, pygame.Rect(r.centerx - 30, r.top + 14, 60, 84), "1/2")
                    art.text(s, "等另一色", (r.centerx, r.bottom - 8), 12, DIM, center=True)
                    if mine:
                        art.text(s, f"{b.card.name}", (r.centerx, r.top + 4), 11, DIM, center=True)
                else:
                    pygame.draw.ellipse(s, BOARD_EDGE, r, 1)
                    art.text(s, "纹兽位", r.center, 14, DIM, center=True)
        # 防御纹
        r = self.my_def if mine else self.foe_def
        if p.defense is not None:
            art.draw_card_back(s, r, f"{p.defense_cost()}费" if mine else "?")
            if mine:
                art.text(s, p.defense.name, (r.centerx, r.bottom + 10), 12, INK, center=True)
        else:
            pygame.draw.rect(s, BOARD_EDGE, r, 1, border_radius=8)
            art.text(s, "防御纹", r.center, 12, DIM, center=True)

    def draw_heroes(self, me: Player, foe: Player):
        g = self.game
        my_turn = g.players[g.current] is me
        can = my_turn and me.hero_attacks > 0 and me.turns > 1
        sel = bool(self.drag and self.drag[0] == "attack" and self.drag[1] is None)
        art.draw_hero(self.screen, self.enemy_hero, self.hero_r, foe)
        art.draw_hero(self.screen, self.my_hero, self.hero_r, me, selected=sel, glow=can)
        for p, c in ((foe, self.enemy_hero), (me, self.my_hero)):
            art.text(self.screen, f"{p.name} · {CLASSES[p.cls].split('（')[0]}", (c[0] + 70, c[1] - 30), 15, INK, bold=True)
            if p.burn:
                art.text(self.screen, f"燃烧 {p.burn}", (c[0] + 70, c[1] - 10), 13, DANGER)
            if p.deck_empty:
                art.text(self.screen, "牌库空：受伤翻倍", (c[0] + 70, c[1] + 8), 13, DANGER)
        self.track_hp(foe, self.enemy_hero)
        self.track_hp(me, self.my_hero)

    def track_hp(self, p: Player, pos):
        key = id(p)
        last = self._last_hp.get(key)
        if last is not None and p.hp != last:
            d = p.hp - last
            self.popups.append([pos[0] - 70, pos[1], f"{d:+d}", OK if d > 0 else DANGER, time.time()])
        self._last_hp[key] = p.hp

    def draw_popups(self):
        now = time.time()
        self.popups = [p for p in self.popups if now - p[4] < 1.2]
        for x, y, t, c, born in self.popups:
            k = now - born
            art.text(self.screen, t, (x, y - k * 40), 30, c, center=True, bold=True)

    def draw_hand(self, me: Player):
        g = self.game
        rects = self.hand_rects(len(me.hand))
        hover = None
        for i, (c, r) in enumerate(zip(me.hand, rects)):
            if self.drag and self.drag[0] == "card" and self.drag[1] is c:
                continue
            cost = g.card_cost(me, c)
            ok = cost <= me.power
            hl = OK if ok and g.players[g.current] is me else None
            target = self.drag and self.drag[0] == "card" and r.collidepoint(self.mouse)
            art.draw_card(self.screen, c, r.topleft, HAND_SCALE, cost=cost,
                          highlight=GOLD if target else hl, dim=not ok)
            if r.collidepoint(self.mouse) and not self.drag:
                hover = (c, r, cost)
        if hover:
            c, r, cost = hover
            big = 1.35
            x = min(max(0, r.centerx - int(CARD_W * big) // 2), LOG_X - int(CARD_W * big))
            art.draw_card(self.screen, c, (x, r.top - int(CARD_H * big) + 40), big, cost=cost)
        # 敌方手牌背面
        foe = g.opp(me)
        for i in range(len(foe.hand)):
            art.draw_card_back(self.screen, pygame.Rect(20 + i * 26, 10, 44, 62))

    def draw_hud(self, me: Player, foe: Player):
        s = self.screen
        g = self.game
        art.gem(s, (230, 560), 26, (60, 110, 220), me.power, 24)
        art.text(s, "纹力", (230, 596), 13, DIM, center=True)
        art.gem(s, (230, 92), 22, (60, 110, 220), foe.power, 20)
        art.text(s, "纹力", (230, 124), 12, DIM, center=True)
        art.text(s, f"牌库 {len(me.deck)}", (120, 548), 14, DIM)
        art.text(s, f"牌库 {len(foe.deck)}", (120, 84), 14, DIM)
        # 献祭台
        r = self.altar
        hot = self.drag and self.drag[0] == "card" and r.collidepoint(self.mouse)
        pygame.draw.rect(s, (60, 30, 40) if hot else (40, 26, 34), r, border_radius=10)
        pygame.draw.rect(s, DANGER, r, 2, border_radius=10)
        art.sigil_pattern(s, r.inflate(-16, -30), (255, 120, 110), 99, density=3, width=1, alpha=150)
        art.text(s, "献祭", (r.centerx, r.bottom - 14), 14, INK, center=True, bold=True)
        art.text(s, "+1 纹力", (r.centerx, r.top + 12), 11, DIM, center=True)
        # 结束回合
        my_turn = g.players[g.current] is me
        b = self.end_btn
        hover = b.collidepoint(self.mouse)
        pygame.draw.rect(s, (200, 150, 40) if my_turn else (70, 70, 80), b, border_radius=12)
        if hover and my_turn:
            pygame.draw.rect(s, (255, 230, 150), b, 3, border_radius=12)
        art.text(s, "结束回合" if my_turn else "对手回合", b.center, 20, (20, 16, 10), center=True, bold=True)
        if my_turn and self.turn_deadline:
            left = max(0, self.turn_deadline - time.time())
            col = DANGER if left < 8 else INK
            art.text(s, f"{left:0.0f} 秒", (b.centerx, b.top - 16), 16, col, center=True, bold=True)
            frac = left / TURN_SECONDS
            pygame.draw.rect(s, (40, 40, 50), (b.left, b.bottom + 6, b.w, 6), border_radius=3)
            pygame.draw.rect(s, col, (b.left, b.bottom + 6, int(b.w * frac), 6), border_radius=3)
        art.text(s, f"第 {me.turns} 回合", (b.centerx, b.top - 40), 13, DIM, center=True)

    def draw_log(self):
        s = self.screen
        pygame.draw.rect(s, PANEL, (LOG_X, 0, W - LOG_X, H))
        art.text(s, "战斗记录", (LOG_X + 14, 12), 16, GOLD, bold=True)
        y = H - 24
        for line in reversed(self.logs):
            for sub in reversed(art.wrap(line.strip(), 13, W - LOG_X - 24) or [""]):
                col = INK if line.startswith("▶") else (GOLD if line.startswith("=") or line.startswith("\n=") else DIM)
                art.text(s, sub, (LOG_X + 12, y), 13, col)
                y -= 18
                if y < 40:
                    return

    def draw_drag(self):
        s = self.screen
        kind, obj = self.drag
        if kind == "card":
            w, h = int(CARD_W * HAND_SCALE), int(CARD_H * HAND_SCALE)
            hint = self.drop_hint(obj, self.mouse)
            art.draw_card(s, obj, (self.mouse[0] - w // 2, self.mouse[1] - h // 2), HAND_SCALE,
                          cost=self.game.card_cost(self.me, obj))
            if hint:
                r = art.text(s, hint, (self.mouse[0], self.mouse[1] - h // 2 - 16), 15, GOLD, center=True, bold=True)
        else:
            start = self.my_hero if obj is None else self.slot_rects[("me", "beast", obj)].center
            end = self.mouse
            pygame.draw.line(s, DANGER, start, end, 6)
            ang = math.atan2(end[1] - start[1], end[0] - start[0])
            tip = [end, (end[0] - 22 * math.cos(ang - 0.4), end[1] - 22 * math.sin(ang - 0.4)),
                   (end[0] - 22 * math.cos(ang + 0.4), end[1] - 22 * math.sin(ang + 0.4))]
            pygame.draw.polygon(s, DANGER, tip)
            pygame.draw.circle(s, DANGER, end, 18, 3)

    # ================================================================ 拖放规则
    def hit_hand(self, pos):
        hit = None
        for c, r in zip(self.me.hand, self.hand_rects(len(self.me.hand))):
            if r.collidepoint(pos):
                hit = c  # 牌有重叠时取最上面（最右边）那张
        return hit

    def hit_slot(self, side: str, pos):
        for (sd, kind, i), r in self.slot_rects.items():
            if sd == side and r.collidepoint(pos):
                return kind, i
        return None

    def drop_hint(self, card: Card, pos) -> str | None:
        me = self.me
        other = self.hit_hand(pos)
        if other is not None and other is not card:
            return f"合纹：附加到【{other.name}】"
        slot = self.hit_slot("me", pos)
        if slot:
            kind, i = slot
            if kind == "beast":
                return "进化这只纹兽" if isinstance(me.beasts[i], Beast) else "放入纹兽位（召唤）"
            if isinstance(me.fields[i], Field) and card.color == BLUE:
                return "续命 / 覆盖纹域"
            return "放入纹域位"
        if self.my_def.collidepoint(pos):
            return "盖到防御纹"
        if self.altar.collidepoint(pos):
            return "献祭（+1 纹力）"
        if self.play_zone.collidepoint(pos) and pos[1] < H - 170:
            return "打出"
        return None

    def drop_card(self, card: Card, pos) -> None:
        """把 card 放到 pos。所有规则检查都在引擎里，违规会抛 RuleError。"""
        g, me = self.game, self.me
        other = self.hit_hand(pos)
        if other is not None and other is not card:
            g.act_combo(me, other, card)
            return
        slot = self.hit_slot("me", pos)
        if slot:
            kind, i = slot
            if kind == "beast":
                if isinstance(me.beasts[i], Beast):
                    g.act_evolve(me, i, 1 - i, card)
                else:
                    g.act_beast_card(me, card, i)
            else:
                if isinstance(me.fields[i], Field) and card.color == BLUE:
                    k = self.modal("这张蓝牌要怎么用？", ["献祭给纹域续命（+1 耐久）", "覆盖这个纹域", "取消"])
                    if k == 0:
                        g.act_extend(me, card, i)
                    elif k == 1:
                        g.act_field_card(me, card, i)
                    return
                g.act_field_card(me, card, i)
            return
        if self.my_def.collidepoint(pos):
            g.act_set_defense(me, card)
        elif self.altar.collidepoint(pos):
            g.act_sacrifice(me, card)
        elif self.play_zone.collidepoint(pos) and pos[1] < H - 170:
            g.act_play(me, card)

    def drop_attack(self, attacker, pos) -> None:
        foe = self.game.opp(self.me)
        if math.dist(pos, self.enemy_hero) <= self.hero_r + 10:
            self.game.act_attack(self.me, attacker, ("hero",))
            return
        slot = self.hit_slot("foe", pos)
        if slot:
            kind, i = slot
            if kind == "beast" and isinstance(foe.beasts[i], Beast):
                self.game.act_attack(self.me, attacker, ("beast", i))
            elif kind == "field" and isinstance(foe.fields[i], Field):
                self.game.act_attack(self.me, attacker, ("field", i))

    # ================================================================ 自己的回合
    def run_turn(self, me: Player):
        self.turn_deadline = time.time() + TURN_SECONDS if self.timer else None
        self.drag = None
        while True:
            if self.game.winner is not None:
                return
            if self.turn_deadline and time.time() >= self.turn_deadline:
                self.say("时间到，自动结束回合", GOLD)
                self.drag = None
                return
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    raise Quit
                if e.type == pygame.KEYDOWN and e.key in (pygame.K_SPACE, pygame.K_RETURN):
                    return
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    if self.end_btn.collidepoint(e.pos):
                        return
                    self.press(e.pos)
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 3:
                    self.drag = None
                if e.type == pygame.MOUSEBUTTONUP and e.button == 1 and self.drag:
                    self.release(e.pos)
            self.mouse = pygame.mouse.get_pos()
            self.render()
            self.clock.tick(60)

    def press(self, pos):
        me = self.me
        c = self.hit_hand(pos)
        if c is not None:
            self.drag = ("card", c)
            return
        if math.dist(pos, self.my_hero) <= self.hero_r:
            self.drag = ("attack", None)
            return
        slot = self.hit_slot("me", pos)
        if slot and slot[0] == "beast" and isinstance(me.beasts[slot[1]], Beast):
            self.drag = ("attack", slot[1])
            return
        if self.my_def.collidepoint(pos) and me.defense is not None:
            k = self.modal(f"翻开防御纹【{me.defense.name}】，花费 {me.defense_cost()} 纹力？", ["翻开", "取消"])
            if k == 0:
                self.act(self.game.act_flip_defense, me)

    def release(self, pos):
        kind, obj = self.drag
        self.drag = None
        if kind == "card":
            self.act(self.drop_card, obj, pos)
        else:
            self.act(self.drop_attack, obj, pos)

    def act(self, fn, *args):
        paused = self.turn_deadline - time.time() if self.turn_deadline else None
        try:
            fn(*args)
        except RuleError as e:
            self.say(str(e))
        finally:
            if paused is not None:
                self.turn_deadline = time.time() + max(paused, 1)

    # ================================================================ 弹窗选择
    def modal(self, prompt: str, options: list[str], timeout: float | None = None, cards=None) -> int:
        """弹出选项，返回下标。timeout 秒内不选就默认第一个（8 秒判定用）。cards 不为空时用卡面显示。"""
        deadline = time.time() + timeout if timeout else None
        saved = self.turn_deadline
        buttons = []

        def overlay():
            nonlocal buttons
            s = self.screen
            shade = pygame.Surface((W, H), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 160))
            s.blit(shade, (0, 0))
            art.text(s, prompt, (W // 2, 150), 22, GOLD, center=True, bold=True)
            if deadline:
                left = max(0, deadline - time.time())
                art.text(s, f"{left:0.1f} 秒后默认选第一项", (W // 2, 182), 15, DANGER, center=True)
            buttons = []
            if cards:
                n = len(cards)
                gap = min(CARD_W + 16, (W - 80) // n)
                x0 = (W - (gap * (n - 1) + CARD_W)) // 2
                for i, c in enumerate(cards):
                    r = pygame.Rect(x0 + i * gap, 240, CARD_W, CARD_H)
                    hot = r.collidepoint(self.mouse)
                    art.draw_card(s, c, r.topleft, highlight=GOLD if hot else None)
                    buttons.append(r)
            else:
                y = 220
                for i, o in enumerate(options):
                    lines = art.wrap(o, 17, 640)
                    r = pygame.Rect(W // 2 - 340, y, 680, 22 * len(lines) + 20)
                    hot = r.collidepoint(self.mouse)
                    pygame.draw.rect(s, (70, 64, 96) if hot else (44, 46, 66), r, border_radius=10)
                    pygame.draw.rect(s, GOLD if hot else BOARD_EDGE, r, 2, border_radius=10)
                    for k, line in enumerate(lines):
                        art.text(s, line, (r.left + 20, r.top + 10 + k * 22), 17, INK)
                    buttons.append(r)
                    y = r.bottom + 12

        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    raise Quit
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    for i, r in enumerate(buttons):
                        if r.collidepoint(e.pos):
                            if saved:
                                self.turn_deadline = saved + (time.time() - (deadline or time.time()))
                            return i
            if deadline and time.time() >= deadline:
                return 0
            self.mouse = pygame.mouse.get_pos()
            self.render(overlay)
            self.clock.tick(60)

    # ================================================================ 开始和结束
    def title(self) -> bool:
        btn = pygame.Rect(W // 2 - 120, 470, 240, 64)
        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    raise Quit
                if e.type == pygame.MOUSEBUTTONDOWN and btn.collidepoint(e.pos):
                    return True
                if e.type == pygame.KEYDOWN and e.key in (pygame.K_SPACE, pygame.K_RETURN):
                    return True
            s = self.screen
            s.fill(art.BG)
            t = time.time()
            r = pygame.Rect(W // 2 - 300, 60, 600, 360)
            art.draw_field_floor(s, r, "red", "blue", t)
            art.text(s, "双生纹", (W // 2, 210), 96, GOLD, center=True, bold=True)
            art.text(s, "测试版", (W // 2, 300), 22, DIM, center=True)
            hot = btn.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(s, (220, 170, 60) if hot else (200, 150, 40), btn, border_radius=14)
            art.text(s, "开始对战", btn.center, 26, (20, 16, 10), center=True, bold=True)
            art.text(s, "拖动手牌出牌 · 从角色或纹兽拖出箭头攻击 · 空格结束回合", (W // 2, 580), 16, DIM, center=True)
            pygame.display.flip()
            self.clock.tick(60)

    def game_over(self, winner) -> bool:
        again = pygame.Rect(W // 2 - 250, 470, 220, 60)
        quit_ = pygame.Rect(W // 2 + 30, 470, 220, 60)
        msg = "你赢了！" if winner is self.me else ("你输了" if winner else "平局")

        def overlay():
            s = self.screen
            shade = pygame.Surface((W, H), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 170))
            s.blit(shade, (0, 0))
            art.text(s, msg, (W // 2, 330), 72, GOLD if winner is self.me else DANGER, center=True, bold=True)
            for r, label in ((again, "再来一局"), (quit_, "退出")):
                pygame.draw.rect(s, (200, 150, 40), r, border_radius=12)
                art.text(s, label, r.center, 22, (20, 16, 10), center=True, bold=True)

        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    raise Quit
                if e.type == pygame.MOUSEBUTTONDOWN:
                    if again.collidepoint(e.pos):
                        return True
                    if quit_.collidepoint(e.pos):
                        return False
            self.mouse = pygame.mouse.get_pos()
            self.render(overlay)
            self.clock.tick(60)

    def new_game(self):
        self.logs = []
        self._last_hp = {}
        self.popups = []
        human = GUIController(self)
        g = Game(("你", "人机"), (human, AIController()), seed=self.seed, log=self.on_log)
        self.game, self.me = g, g.players[0]
        return g

    def run(self):
        try:
            self.title()
            while True:
                g = self.new_game()
                w = g.play()
                if not self.game_over(w):
                    break
        except Quit:
            pass
        pygame.quit()


class GUIController(Controller):
    def __init__(self, gui: GUI):
        self.gui = gui

    def take_turn(self, game: Game, me: Player) -> None:
        self.gui.run_turn(me)

    def choose(self, game, me, kind, prompt, options):
        gui = self.gui
        if kind == "class":
            return gui.modal("选择你的职业（职业对双方公开）", options)
        if kind == "bid":
            return gui.modal("要抢先手吗？抢到先手要多亮 1 张牌给对手禁", options)
        if kind == "defense":
            return gui.modal(f"8 秒判定：{prompt}", options, timeout=DEFENSE_SECONDS)
        if kind == "discard":
            return gui.modal(prompt, options, cards=list(me.hand))
        return gui.modal(prompt, options)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="《双生纹》图形界面")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--no-timer", action="store_true", help="关闭每回合 30 秒计时")
    a = ap.parse_args(argv)
    GUI(seed=a.seed, timer=not a.no_timer).run()
