"""人机：每一步都把能做的动作在副本上试一遍，挑局面评分最高的那个（贪心一层搜索）。

评分只看场面：血量、护盾、纹兽、纹域、纹力、手牌等，所以不会针对某一套牌，
三个职业都能打出正常水平，方便用来比较数值。
"""

from __future__ import annotations

import copy
import random

from .cards import GREEN, RED
from .engine import Beast, Controller, Field, Game, GameOver, Pending, Player, RuleError

DAMAGE = {"damage", "burn", "storm", "field_damage"}


def card_value(c) -> float:
    return c.cost + c.sigil * 0.3


def _noop(*a, **kw):
    pass


# ---------------------------------------------------------------- 评分
def threat(p: Player) -> int:
    """p 下回合大概能打出多少伤害。"""
    t = p.hero_atk()
    for _, b in p.live_beasts():
        t += p.beast_atk(b)
    return t


def side_score(game: Game, p: Player) -> float:
    foe = game.opp(p)
    s = p.hp * 1.0 + min(p.hp, 6) * 0.6  # 血少时每点血更值钱
    s += min(p.shield_total(), threat(foe) + 1) * 0.8
    for _, b in p.live_beasts():
        s += p.beast_atk(b) * 1.0 + b.hp * 0.6 + b.shield_total() * 0.4 + (b.level - 1) * 0.5
        if b.level == 3:
            s += b.l3_rounds * 0.5
    for x in p.beasts:
        if isinstance(x, Pending):
            s += 1.0
    for f in p.fields:
        if isinstance(f, Field):
            s += min(f.durability, 4) * f.bonus() * 0.9 + (0.5 if f.ward else 0)
        elif isinstance(f, Pending):
            s += 1.0
    # 攻击加成：本回合还能攻击才算本回合那一份
    now = 1 if (p is game.players[game.current] and p.hero_attacks > 0) else 0
    s += sum(b.atk * max(0, b.rounds - 1 + now) for b in p.buffs) * 0.6
    if p.defense is not None:
        s += 1.0 + p.defense.cost * 0.3
    s += p.power * 0.3
    s += min(len(p.hand), 6) * 0.55
    s -= p.burn * 0.9
    if p.deck_empty:
        s -= 3
    return s


def score(game: Game, me: Player) -> float:
    if game.winner is not None:
        return 1000 if game.winner.name == me.name else -1000
    if me.hp <= 0:
        return -1000
    foe = game.opp(me)
    if foe.hp <= 0:
        return 1000
    return side_score(game, me) - side_score(game, foe)


# ---------------------------------------------------------------- 动作
def candidate_actions(game: Game, me: Player) -> list[tuple]:
    hand = me.hand
    foe = game.opp(me)
    acts = []
    for i, c in enumerate(hand):
        if game.card_cost(me, c) <= me.power:
            acts.append(("play", i))
            for j, a in enumerate(hand):
                if j != i:
                    acts.append(("combo", i, j))
        if c.color != "blue":
            for s, b in enumerate(me.beasts):
                if b is None or (isinstance(b, Pending) and b.card.color != c.color):
                    acts.append(("beast", i, s))
        for s in range(2):
            acts.append(("field", i, s))
            if c.color == "blue" and isinstance(me.fields[s], Field) and not me.extended:
                acts.append(("extend", i, s))
        if c.color != RED and me.defense is None:
            acts.append(("set_def", i))
    live = me.live_beasts()
    if len(live) == 2:
        for t, m in ((0, 1), (1, 0)):
            for i in range(len(hand)):
                acts.append(("evolve", t, m, i))
    if me.defense is not None:
        acts.append(("flip_def",))
    if me.turns > 1:
        targets = [("hero",)] + [("beast", i) for i, _ in foe.live_beasts()]
        targets += [("field", i) for i, f in enumerate(foe.fields) if isinstance(f, Field)]
        attackers = [None] if me.hero_attacks > 0 else []
        attackers += [i for i, b in live if not b.sick and not b.attacked and not b.sealed]
        for a in attackers:
            for t in targets:
                acts.append(("attack", a, t))
    return acts


def apply(game: Game, me: Player, act: tuple) -> None:
    k = act[0]
    h = me.hand
    if k == "play":
        game.act_play(me, h[act[1]])
    elif k == "combo":
        game.act_combo(me, h[act[1]], h[act[2]])
    elif k == "beast":
        game.act_beast_card(me, h[act[1]], act[2])
    elif k == "field":
        game.act_field_card(me, h[act[1]], act[2])
    elif k == "extend":
        game.act_extend(me, h[act[1]], act[2])
    elif k == "set_def":
        game.act_set_defense(me, h[act[1]])
    elif k == "evolve":
        game.act_evolve(me, act[1], act[2], h[act[3]])
    elif k == "flip_def":
        game.act_flip_defense(me)
    elif k == "sacrifice":
        game.act_sacrifice(me, h[act[1]])
    elif k == "attack":
        game.act_attack(me, act[1], act[2])


# ---------------------------------------------------------------- 控制器
class AIController(Controller):
    def __init__(self, think: bool = True):
        self.think = think
        self._rng = random.Random()

    # ---------- 各种选择（防守、目标等）----------
    def choose(self, game: Game, me: Player, kind: str, prompt: str, options: list[str]) -> int:
        foe = game.opp(me)
        if kind == "class":
            return game.rng.randrange(len(options))
        if kind == "bid":
            return game.rng.randrange(2)
        if kind == "ban":
            return game.rng.randrange(len(options))
        if kind == "discard":
            return min(range(len(me.hand)), key=lambda i: card_value(me.hand[i]))
        if kind == "defense":
            return self._defense(game, me, prompt, options)
        if kind == "target_damage":
            for k, (i, b) in enumerate(foe.live_beasts(), start=1):
                if b.hp + b.shield_total() <= 2 and b.atk >= 2:
                    return k
            return 0
        if kind == "target_own_beast":
            mine = me.live_beasts()
            return max(range(len(mine)), key=lambda k: mine[k][1].atk + mine[k][1].level)
        if kind == "target_enemy_beast":
            theirs = foe.live_beasts()
            return max(range(len(theirs)), key=lambda k: foe.beast_atk(theirs[k][1]))
        return 0

    def _defense(self, game, me, prompt, options) -> int:
        digits = "".join(ch for ch in prompt.split("造成")[-1] if ch.isdigit())
        dmg = int(digits or 0)
        incoming = dmg - me.shield_total()
        if incoming <= 0:
            return 0
        best, best_cost = 0, incoming * (1.6 if me.hp - incoming <= 5 else 1.0)
        for k, opt in enumerate(options):
            if opt.startswith("让"):
                for _, b in me.live_beasts():
                    if b.describe() in opt:
                        loss = min(dmg, b.hp + b.shield_total())
                        dies = dmg >= b.hp + b.shield_total()
                        cost = (b.atk + b.hp * 0.6 if dies else loss * 0.4)
                        if cost < best_cost:
                            best, best_cost = k, cost
            elif opt.startswith("紧急举盾") and me.defense is not None:
                pay = 2 * me.defense_cost() * 0.3 + 1.0
                gain = me.defense.params.get("amount", 0) if me.defense.effect == "shield" else 0
                if me.defense.color == GREEN and gain:
                    cost = max(0, incoming - gain) + pay
                    if cost < best_cost:
                        best, best_cost = k, cost
        return best

    # ---------- 回合 ----------
    def take_turn(self, game: Game, me: Player) -> None:
        for _ in range(30):
            if game.winner is not None:
                return
            act = self._best(game, me)
            if act is None:
                if not self._fuel(game, me):
                    return
                continue
            try:
                apply(game, me, act)
            except RuleError:
                return

    def _best(self, game: Game, me: Player):
        idx = game.players.index(me)
        base = score(game, me)
        best, best_gain = None, 0.15
        sim = AIController(think=False)
        for act in candidate_actions(game, me):
            memo = {id(c): sim for c in game.ctrl}
            memo[id(game.log)] = _noop
            g2 = copy.deepcopy(game, memo)
            g2.log = _noop
            g2.rng = random.Random(self._rng.random())
            me2 = g2.players[idx]
            try:
                apply(g2, me2, act)
            except RuleError:
                continue
            except GameOver:
                pass
            gain = score(g2, me2) - base
            if gain > best_gain:
                best, best_gain = act, gain
        return best

    def _fuel(self, game: Game, me: Player) -> bool:
        """没有好动作时，纹力紧张就献祭最没用的牌换纹力。"""
        if me.power < 3 and len(me.hand) >= 4:
            worst = min(me.hand, key=card_value)
            game.act_sacrifice(me, worst)
            return True
        return False
