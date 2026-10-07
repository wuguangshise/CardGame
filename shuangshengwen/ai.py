"""简单的人机：按固定优先级出牌，够测试规则和数值用。"""

from __future__ import annotations

from .cards import BLUE, GREEN, RED
from .engine import Beast, Controller, Field, Game, Pending, Player, RuleError

DAMAGE = {"damage", "burn", "storm", "field_damage"}


def card_value(c) -> float:
    return c.cost + c.sigil * 0.3


class AIController(Controller):
    def __init__(self, reserve: int = 2):
        self.reserve = reserve

    # ---------- 选择 ----------
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
            # 能打死纹兽就打纹兽，否则打脸
            for k, (i, b) in enumerate(foe.live_beasts(), start=1):
                if b.hp + b.shield_total() <= 2 and b.atk >= 2:
                    return k
            return 0
        if kind in ("target_enemy_beast", "target_own_beast", "target_own_field", "target_enemy_field"):
            return 0
        return 0

    def _defense(self, game, me, prompt, options) -> int:
        dmg = int("".join(ch for ch in prompt.split("造成")[-1] if ch.isdigit()) or 0)
        incoming = dmg - me.shield_total()
        for k, opt in enumerate(options):
            if opt.startswith("让") and incoming >= 3:
                # 纹兽血量够厚才挡
                for _, b in me.live_beasts():
                    if b.describe() in opt and b.hp + b.shield_total() > dmg:
                        return k
        for k, opt in enumerate(options):
            if opt.startswith("紧急举盾") and incoming >= 3 and me.defense and me.defense.color == GREEN:
                return k
        return 0

    # ---------- 回合 ----------
    def take_turn(self, game: Game, me: Player) -> None:
        foe = game.opp(me)
        for _ in range(40):
            if not self._step(game, me, foe):
                break
        self._attacks(game, me, foe)

    def _try(self, fn, *args) -> bool:
        try:
            fn(*args)
            return True
        except RuleError:
            return False

    def _step(self, game: Game, me: Player, foe: Player) -> bool:
        hand = sorted(me.hand, key=card_value, reverse=True)
        spare = me.power - self.reserve

        # 1. 完成盖着的召唤
        for slot, b in enumerate(me.beasts):
            if isinstance(b, Pending):
                need = GREEN if b.card.color == RED else RED
                for c in hand:
                    if c.color == need and c.cost <= spare:
                        return self._try(game.act_beast_card, me, c, slot)
        # 2. 空纹兽位：开始召唤
        if None in me.beasts:
            slot = me.beasts.index(None)
            reds = [c for c in hand if c.color == RED and c.sigil >= 2]
            greens = [c for c in hand if c.color == GREEN and c.sigil >= 2]
            if reds and greens and reds[0].cost + greens[0].cost <= spare:
                return self._try(game.act_beast_card, me, reds[0], slot)
        # 3. 进化
        live = me.live_beasts()
        if len(live) == 2:
            (i, a), (j, b) = live
            tgt, mat = (i, j) if (a.level, a.atk + a.hp) >= (b.level, b.atk + b.hp) else (j, i)
            if me.beasts[mat].level == 1 and me.beasts[tgt].level < 3:
                for c in hand:
                    cost = c.cost if me.beasts[tgt].level == 2 else 0
                    if c.color == RED and cost <= spare:
                        return self._try(game.act_evolve, me, tgt, mat, c)
        # 4. 防御纹
        if me.defense is None and len(me.hand) >= 3:
            greens = [c for c in hand if c.color == GREEN and c.cost >= 2]
            if greens:
                return self._try(game.act_set_defense, me, greens[0])
        # 5. 纹域：纹力富余时铺
        for slot, f in enumerate(me.fields):
            if isinstance(f, Pending):
                for c in hand:
                    if c.cost <= spare - 1:
                        return self._try(game.act_field_card, me, c, slot)
        if me.power >= 9 and None in me.fields and len(me.hand) >= 4:
            reds = [c for c in hand if c.color == RED]
            if reds:
                return self._try(game.act_field_card, me, reds[0], me.fields.index(None))
        # 6. 出单牌
        for c in hand:
            cost = game.card_cost(me, c)
            if cost > spare:
                continue
            if c.color == RED and c.effect == "buff" and me.turns > 1 and me.hero_attacks > 0:
                if c.params.get("vs_beast") and not foe.live_beasts():
                    continue
                if self._combo_or_play(game, me, c, hand):
                    return True
            if c.color == GREEN and c.effect in ("shield", "heal") and (me.hp <= 10 or me.turns == 1):
                if c.effect == "heal" and me.hp > 12:
                    continue
                return self._try(game.act_play, me, c)
            if c.color == BLUE:
                if c.effect in DAMAGE and me.turns <= 1:
                    continue
                if c.effect == "draw" and len(me.hand) > 4:
                    continue
                if c.effect == "summon_random" and None not in me.beasts:
                    continue
                if c.effect in ("field_ward", "field_fortify") and not me.active_fields():
                    continue
                if c.effect == "seal" and not foe.live_beasts():
                    continue
                if c.effect == "dispel" and not foe.shields:
                    continue
                if c.effect == "break_defense" and foe.defense is None:
                    continue
                if c.effect == "field_damage" and not foe.active_fields():
                    continue
                if c.effect == "beast_shield":
                    continue
                return self._try(game.act_play, me, c)
        # 7. 纹力紧张时献祭
        if me.power < 3 and len(me.hand) >= 4:
            worst = min(me.hand, key=card_value)
            return self._try(game.act_sacrifice, me, worst)
        return False

    def _combo_or_play(self, game, me, c, hand) -> bool:
        # 有多余的低价值牌就当附加卡
        extras = [x for x in hand if x is not c and x.cost == 0 and x.color != RED]
        if extras and len(me.hand) >= 4:
            return self._try(game.act_combo, me, c, extras[0])
        return self._try(game.act_play, me, c)

    def _attacks(self, game: Game, me: Player, foe: Player) -> None:
        if me.turns <= 1:
            return
        for slot, b in me.live_beasts():
            if b.sick or b.attacked or b.sealed:
                continue
            target = ("hero",)
            for i, eb in foe.live_beasts():
                if eb.atk >= 3 and eb.hp + eb.shield_total() <= me.beast_atk(b):
                    target = ("beast", i)
                    break
            self._try(game.act_attack, me, slot, target)
            if game.winner:
                return
        while me.hero_attacks > 0:
            target = ("hero",)
            for i, eb in foe.live_beasts():
                if eb.hp + eb.shield_total() <= me.hero_atk(vs_beast=True) and (eb.atk >= 3 or me.vs_beast):
                    target = ("beast", i)
                    break
            if not self._try(game.act_attack, me, None, target):
                break
