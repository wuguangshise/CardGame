"""《双生纹》规则引擎。

不含任何输入输出：所有选择都交给 Controller（人类界面或 AI），
所以以后换成图形界面、或者搬到 Godot，只需要照着这一层改。
"""

from __future__ import annotations

import math
import random as _random
from dataclasses import dataclass, field

from .cards import BLUE, FIELD_TYPES, FIRST, GREEN, RED, SECOND, SPECIES, Card, starter_deck

HERO_HP = 15
BASE_ATK = 1
START_POWER = 12
OPEN_HAND = 4
DRAW_PER_TURN = 2
HAND_LIMIT_END = 5
HAND_LIMIT_TURN = 8
SHIELD_ROUNDS = 1  # 护盾挡对方接下来 1 个回合，守护者挡 2 个回合
L3_ROUNDS = 2
EVOLVE_BONUS = 1  # 红纹进化 +1 攻，绿纹进化 +1 血（加纹值会让 2 级纹兽一出来就 6 攻，超过场攻上限）

CLASSES = {
    "warrior": "红 · 战士（每回合第一张红牌 -1 费）",
    "archmage": "蓝 · 大魔导师（每回合第一张蓝牌 -1 费）",
    "guardian": "绿 · 守护者（护盾多挡对方 1 个回合）",
}


MARK = {RED: "赤", GREEN: "翠", BLUE: "苍"}
DAMAGE_EFFECTS = {"field_damage", "damage", "burn", "storm"}


CLASS_DISCOUNT = {"warrior": RED, "archmage": BLUE}


class RuleError(Exception):
    """违反规则的操作。界面层把 message 展示给玩家即可。"""


# ---------------------------------------------------------------- 状态
@dataclass
class Shield:
    amount: int
    rounds: int
    thorns: bool = False


@dataclass
class Buff:
    atk: int
    rounds: int  # 自己回合结束时 -1


@dataclass
class Beast:
    base_atk: int
    base_hp: int
    atk: int
    hp: int
    max_hp: int
    level: int = 1
    sigils: list = field(default_factory=list)
    pierce: bool = False
    shields: list = field(default_factory=list)
    sick: bool = True
    attacked: bool = False
    sealed: int = 0
    l3_rounds: int = 0
    l2_snapshot: tuple | None = None

    @property
    def species(self) -> str:
        return SPECIES.get((self.base_atk, self.base_hp), f"{self.base_atk}/{self.base_hp}纹兽")

    @property
    def name(self) -> str:
        mark = "".join(MARK[c] for c in self.sigils)
        return f"{self.species}·{mark}" if mark else self.species

    def shield_total(self) -> int:
        return sum(s.amount for s in self.shields)

    def describe(self) -> str:
        s = f"{self.name}（{self.level}级 {self.atk}攻 {self.hp}/{self.max_hp}血"
        if self.shield_total():
            s += f" 盾{self.shield_total()}"
        if self.pierce:
            s += " 穿透"
        if self.level == 3:
            s += f" 剩{self.l3_rounds}回合"
        if self.sick:
            s += " 刚召唤"
        if self.sealed:
            s += " 被封印"
        return s + "）"


@dataclass
class Pending:
    """分两回合放的第一张牌，盖着放。"""
    card: Card


@dataclass
class Field:
    first: Card
    second: Card
    durability: int
    ward: bool = False

    @property
    def strong(self) -> bool:
        return self.first.cost + self.second.cost >= 6

    @property
    def name(self) -> str:
        return f"{FIELD_TYPES[self.first.color]}·{MARK[self.second.color]}"

    def bonus(self) -> int:
        return 1 + (1 if self.strong else 0)

    def describe(self) -> str:
        n = self.bonus()
        t, v = self.first.color, self.second.color
        if t == RED:
            what = {RED: f"角色 +{n + 1} 攻", GREEN: f"纹兽 +{n + 1} 攻", BLUE: f"角色和纹兽各 +{n} 攻"}[v]
        elif t == GREEN:
            what = {RED: f"每回合开始角色 +{n + 1} 盾", GREEN: f"每回合开始每只纹兽 +{n + 1} 盾",
                    BLUE: f"每回合开始角色和纹兽各 +{n} 盾"}[v]
        else:
            what = {RED: f"每回合开始对方角色受 {n} 伤害", GREEN: f"每回合开始回 {n} 血",
                    BLUE: f"每回合多抽 {n} 张"}[v]
        ward = " 免伤一次" if self.ward else ""
        return f"{self.name}（{what}，耐久 {self.durability}{ward}）"


@dataclass
class Player:
    name: str
    cls: str = "warrior"
    hp: int = HERO_HP
    power: int = START_POWER
    deck: list = field(default_factory=list)
    hand: list = field(default_factory=list)
    grave: list = field(default_factory=list)
    beasts: list = field(default_factory=lambda: [None, None])   # None / Pending / Beast
    fields: list = field(default_factory=lambda: [None, None])   # None / Pending / Field
    defense: Card | None = None
    defense_turns: int = 0
    shields: list = field(default_factory=list)
    buffs: list = field(default_factory=list)
    is_first: bool = False
    turns: int = 0
    # 每回合重置
    hero_attacks: int = 1
    pierce: bool = False
    vs_beast: int = 0
    draw_on_attack: bool = False
    extended: bool = False
    discount_used: bool = False
    burn: int = 0
    deck_empty: bool = False
    known_defense: Card | None = None  # 洞察看到的对方盖牌

    @property
    def base_atk(self) -> int:
        return BASE_ATK

    def shield_total(self) -> int:
        return sum(s.amount for s in self.shields)

    def active_fields(self) -> list[Field]:
        return [f for f in self.fields if isinstance(f, Field)]

    def live_beasts(self) -> list[tuple[int, Beast]]:
        return [(i, b) for i, b in enumerate(self.beasts) if isinstance(b, Beast)]

    def hero_atk(self, vs_beast=False) -> int:
        a = self.base_atk + sum(b.atk for b in self.buffs)
        for f in self.active_fields():
            if f.first.color == RED:
                a += {RED: f.bonus() + 1, GREEN: 0, BLUE: f.bonus()}[f.second.color]
        if vs_beast:
            a += self.vs_beast
        return a

    def beast_atk(self, b: Beast) -> int:
        a = b.atk
        for f in self.active_fields():
            if f.first.color == RED:
                a += {RED: 0, GREEN: f.bonus() + 1, BLUE: f.bonus()}[f.second.color]
        return a

    def defense_cost(self) -> int:
        if self.defense is None:
            return 0
        return max(0, self.defense.cost - min(self.defense_turns, 2))


# ---------------------------------------------------------------- 控制器接口
class Controller:
    """人类界面和 AI 都实现这两个方法。"""

    def take_turn(self, game: "Game", me: Player) -> None:
        """在自己回合里调用 game 的动作方法，返回即结束回合。"""
        raise NotImplementedError

    def choose(self, game: "Game", me: Player, kind: str, prompt: str, options: list[str]) -> int:
        """从 options 里选一个，返回下标。kind 告诉 AI 这是什么选择。"""
        raise NotImplementedError


class GameOver(Exception):
    pass


# ---------------------------------------------------------------- 对局
class Game:
    def __init__(self, names, controllers, seed=None, log=print, classes=None):
        self.rng = _random.Random(seed)
        self.log = log
        self.players = [Player(n) for n in names]
        self.ctrl = list(controllers)
        self.current = 0
        self.winner: Player | None = None
        self.preset_classes = classes

    # ---------- 工具 ----------
    def opp(self, p: Player) -> Player:
        return self.players[1] if p is self.players[0] else self.players[0]

    def ctl(self, p: Player) -> Controller:
        return self.ctrl[self.players.index(p)]

    def ask(self, p: Player, kind: str, prompt: str, options: list[str]) -> int:
        if len(options) == 1:
            return 0
        i = self.ctl(p).choose(self, p, kind, prompt, options)
        if not 0 <= i < len(options):
            i = 0
        return i

    def draw(self, p: Player, n: int) -> None:
        for _ in range(n):
            if not p.deck:
                if not p.deck_empty:
                    p.deck_empty = True
                    self.log(f"  {p.name}的牌库抽空了！之后受到的伤害翻倍")
                return
            c = p.deck.pop()
            if len(p.hand) >= HAND_LIMIT_TURN:
                p.grave.append(c)
                self.log(f"  {p.name}手牌已满 8 张，抽到的【{c.name}】直接销毁")
            else:
                p.hand.append(c)

    def check_end(self) -> None:
        dead = [p for p in self.players if p.hp <= 0]
        if dead:
            alive = [p for p in self.players if p.hp > 0]
            self.winner = alive[0] if alive else None
            raise GameOver

    def first_turn_guard(self, p: Player) -> None:
        if p.turns <= 1:
            raise RuleError("自己的第一回合不能造成伤害")

    def pay(self, p: Player, n: int) -> None:
        if n > p.power:
            raise RuleError(f"纹力不够（需要 {n}，现有 {p.power}）")
        p.power -= n

    def card_cost(self, p: Player, card: Card) -> int:
        """职业被动：战士每回合第一张红牌 -1 费，大魔导师每回合第一张蓝牌 -1 费。"""
        if CLASS_DISCOUNT.get(p.cls) == card.color and not p.discount_used:
            return max(0, card.cost - 1)
        return card.cost

    def _use_class_discount(self, p: Player, card: Card) -> None:
        if CLASS_DISCOUNT.get(p.cls) == card.color:
            p.discount_used = True

    def precheck(self, p: Player, card: Card) -> None:
        if card.effect in DAMAGE_EFFECTS and p.turns <= 1:
            raise RuleError("自己的第一回合不能造成伤害")

    def take_from_hand(self, p: Player, card: Card) -> None:
        if card not in p.hand:
            raise RuleError("这张牌不在手牌里")
        p.hand.remove(card)

    # ---------- 伤害 ----------
    def hit_hero(self, target: Player, dmg: int, pierce=False, source=None) -> int:
        if dmg <= 0:
            return 0
        if target.deck_empty:
            dmg *= 2
        thorns = any(s.thorns for s in target.shields)
        if not pierce:
            for s in target.shields:
                blocked = min(s.amount, dmg)
                s.amount -= blocked
                dmg -= blocked
            target.shields = [s for s in target.shields if s.amount > 0]
        target.hp -= dmg
        if thorns and source is not None:
            self.log("  荆棘反伤 1")
            self.hit_attacker(source, 1)
        return dmg

    def hit_beast(self, owner: Player, slot: int, dmg: int, pierce=False) -> int:
        b = owner.beasts[slot]
        if dmg <= 0 or not isinstance(b, Beast):
            return 0
        if not pierce:
            for s in b.shields:
                blocked = min(s.amount, dmg)
                s.amount -= blocked
                dmg -= blocked
            b.shields = [s for s in b.shields if s.amount > 0]
        b.hp -= dmg
        if b.hp <= 0:
            owner.beasts[slot] = None
            self.log(f"  {owner.name}的{b.name}倒下了")
        return dmg

    def hit_field(self, owner: Player, slot: int, dmg: int) -> int:
        f = owner.fields[slot]
        if not isinstance(f, Field) or dmg <= 0:
            return 0
        if f.ward:
            f.ward = False
            self.log(f"  {f.name}的免伤挡下了这次伤害")
            return 0
        f.durability -= dmg
        if f.durability <= 0:
            owner.fields[slot] = None
            owner.grave += [f.first, f.second]
            self.log(f"  {owner.name}的{f.name}被打爆了")
        return dmg

    def hit_attacker(self, source, dmg: int) -> None:
        owner, slot = source
        if slot is None:
            self.hit_hero(owner, dmg)
        else:
            self.hit_beast(owner, slot, dmg)

    # ---------- 开局 ----------
    def setup(self) -> int:
        """选职业、抢先手、亮牌禁牌、起手。返回先手玩家下标。"""
        names = list(CLASSES)
        for i, p in enumerate(self.players):
            if self.preset_classes:
                p.cls = self.preset_classes[i]
            else:
                p.cls = names[self.ask(p, "class", "选择职业", [CLASSES[k] for k in names])]
            p.deck = starter_deck(p.cls)
            self.rng.shuffle(p.deck)
            self.log(f"{p.name}选择了 {CLASSES[p.cls]}")

        bids = [self.ask(p, "bid", "是否抢先手？抢到要多亮 1 张牌", ["抢先手", "不抢"]) == 0
                for p in self.players]
        if bids[0] != bids[1]:
            first = 0 if bids[0] else 1
            reveal = [5 if i == first else 4 for i in range(2)]
            self.log(f"{self.players[first].name}抢到先手")
        else:
            first = self.rng.randrange(2)
            reveal = [5 if (bids[0] and i == first) else 4 for i in range(2)]
            self.log(f"{'双方都抢' if bids[0] else '双方都不抢'}，抛硬币：{self.players[first].name}先手")

        shown = [self.rng.sample(p.deck, reveal[i]) for i, p in enumerate(self.players)]
        for i, p in enumerate(self.players):
            self.log(f"{p.name}亮出：" + "、".join(c.name for c in shown[i]))
        for i, p in enumerate(self.players):
            other = self.players[1 - i]
            pool = list(shown[1 - i])
            for k in range(2):
                j = self.ask(p, "ban", f"禁掉{other.name}的第 {k + 1} 张牌", [c.label() for c in pool])
                banned = pool.pop(j)
                other.deck.remove(banned)
                self.log(f"{p.name}禁掉了{other.name}的【{banned.name}】")

        for i, p in enumerate(self.players):
            p.is_first = i == first
            self.draw(p, OPEN_HAND)
        self.draw(self.players[1 - first], 1)
        return first

    # ---------- 回合 ----------
    def play(self, max_turns=60) -> Player | None:
        try:
            self.current = self.setup()
            for _ in range(max_turns):
                p = self.players[self.current]
                self.start_turn(p)
                self.ctl(p).take_turn(self, p)
                self.end_turn(p)
                self.current = 1 - self.current
        except GameOver:
            pass
        return self.winner

    def start_turn(self, p: Player) -> None:
        p.turns += 1
        p.hero_attacks = 1
        p.pierce = False
        p.vs_beast = 0
        p.draw_on_attack = False
        p.extended = False
        p.discount_used = False
        self.log(f"\n===== {p.name}的第 {p.turns} 回合 =====")
        for s in p.shields:
            s.rounds -= 1
        p.shields = [s for s in p.shields if s.rounds > 0]
        for _, b in p.live_beasts():
            for s in b.shields:
                s.rounds -= 1
            b.shields = [s for s in b.shields if s.rounds > 0]
            b.sick = False
            b.attacked = False
            if b.sealed:
                b.sealed -= 1
        if p.defense is not None:
            p.defense_turns += 1
        if p.burn:
            dealt = self.hit_hero(p, p.burn, pierce=True)
            self.log(f"  燃烧：{p.name}受到 {dealt} 伤害")
            p.burn = 0
            self.check_end()
        extra = 0
        for f in p.active_fields():
            n = f.bonus()
            if f.first.color == GREEN:
                if f.second.color in (RED, BLUE):
                    p.shields.append(self.new_shield(p, n + 1 if f.second.color == RED else n))
                if f.second.color in (GREEN, BLUE):
                    for _, b in p.live_beasts():
                        b.shields.append(Shield(n + 1 if f.second.color == GREEN else n, SHIELD_ROUNDS))
            elif f.first.color == BLUE:
                if f.second.color == RED and p.turns > 1:
                    dealt = self.hit_hero(self.opp(p), n, pierce=True)
                    self.log(f"  {f.name}：对方受到 {dealt} 伤害")
                    self.check_end()
                elif f.second.color == GREEN:
                    self.heal(p, n)
                elif f.second.color == BLUE:
                    extra += n
        self.draw(p, DRAW_PER_TURN + extra)

    def end_turn(self, p: Player) -> None:
        for b in p.buffs:
            b.rounds -= 1
        p.buffs = [b for b in p.buffs if b.rounds > 0]
        for i, f in enumerate(p.fields):
            if isinstance(f, Field):
                f.durability -= 1
                if f.durability <= 0:
                    p.fields[i] = None
                    p.grave += [f.first, f.second]
                    self.log(f"  {p.name}的{f.name}耐久耗尽，消失了")
        for _, b in p.live_beasts():
            if b.level == 3:
                b.l3_rounds -= 1
                if b.l3_rounds <= 0:
                    b.atk, b.hp, b.max_hp, b.sigils, b.pierce = b.l2_snapshot
                    b.hp = max(1, b.hp)
                    b.level = 2
                    self.log(f"  {p.name}的纹兽退化回 2 级：{b.describe()}")
        while len(p.hand) > HAND_LIMIT_END:
            i = self.ask(p, "discard", f"手牌超过 {HAND_LIMIT_END} 张，选一张献祭（+1 纹力）",
                         [c.label() for c in p.hand])
            c = p.hand.pop(i)
            p.grave.append(c)
            p.power += 1
            self.log(f"  {p.name}回合结束献祭了一张牌，纹力 +1")

    def new_shield(self, p: Player, amount: int, thorns=False) -> Shield:
        rounds = SHIELD_ROUNDS + 1 if p.cls == "guardian" else SHIELD_ROUNDS
        return Shield(amount, rounds, thorns)

    def heal(self, p: Player, n: int) -> None:
        before = p.hp
        p.hp = min(HERO_HP, p.hp + n)
        if p.hp > before:
            self.log(f"  {p.name}回复 {p.hp - before} 血")

    # ================================================================ 动作
    def act_play(self, p: Player, card: Card) -> None:
        """打出一张牌，发挥牌面效果。"""
        self.precheck(p, card)
        self.take_from_hand(p, card)
        try:
            self.pay(p, self.card_cost(p, card))
        except RuleError:
            p.hand.append(card)
            raise
        self._use_class_discount(p, card)
        self.log(f"▶ {p.name}打出【{card.name}】：{card.text}")
        try:
            self.resolve(p, card)
        finally:
            p.grave.append(card)
        self.check_end()

    def act_combo(self, p: Player, main: Card, addon: Card) -> None:
        """合纹：主卡照常付费生效，附加卡免费，只加颜色特性。"""
        if main is addon:
            raise RuleError("主卡和附加卡不能是同一张")
        if addon not in p.hand or main not in p.hand:
            raise RuleError("这张牌不在手牌里")
        cost = self.card_cost(p, main)
        if cost > p.power:
            raise RuleError(f"纹力不够（需要 {cost}，现有 {p.power}）")
        self.precheck(p, main)
        p.hand.remove(main)
        p.hand.remove(addon)
        p.power -= cost
        self._use_class_discount(p, main)
        self.log(f"▶ {p.name}合纹【{main.name}】+【{addon.name}】")
        try:
            self.resolve(p, main)
            self.addon_trait(p, addon)
        finally:
            p.grave += [main, addon]
        self.check_end()

    def addon_trait(self, p: Player, addon: Card) -> None:
        if addon.color == RED:
            p.pierce = True
            self.log("  红纹附加：本回合角色攻击无视护盾")
        elif addon.color == GREEN:
            n = math.ceil(addon.sigil / 2)
            p.shields.append(self.new_shield(p, n))
            self.log(f"  绿纹附加：角色获得 {n} 护盾")
        else:
            n = math.ceil(addon.sigil / 2)
            if n == 0:
                self.log("  蓝纹附加：纹值 0，什么也没发生")
                return
            pick = self.rng.choice(["draw", "lifesteal", "burn"])
            if pick == "draw":
                self.draw(p, n)
                self.log(f"  蓝纹附加：抽 {n} 张")
            elif pick == "lifesteal":
                self.log(f"  蓝纹附加：吸血 {n}")
                self.heal(p, n)
            else:
                if p.turns <= 1:
                    self.log("  蓝纹附加：燃烧，但第一回合不能造成伤害，无效")
                else:
                    self.opp(p).burn += n
                    self.log(f"  蓝纹附加：燃烧，对方下回合开始受 {n} 伤害")

    def act_beast_card(self, p: Player, card: Card, slot: int) -> None:
        """往纹兽位放红牌或绿牌。两张凑齐（一红一绿）就召唤。"""
        if card.color == BLUE:
            raise RuleError("召唤要用红牌加绿牌，蓝牌不行")
        cur = p.beasts[slot]
        if isinstance(cur, Beast):
            raise RuleError("这个纹兽位已经有纹兽了")
        if isinstance(cur, Pending) and cur.card.color == card.color:
            raise RuleError("需要一红一绿，这个位置已经有同色的牌了")
        self.take_from_hand(p, card)
        try:
            self.pay(p, self.card_cost(p, card))
        except RuleError:
            p.hand.append(card)
            raise
        self._use_class_discount(p, card)
        if cur is None:
            p.beasts[slot] = Pending(card)
            self.log(f"▶ {p.name}在纹兽位 {slot + 1} 盖了一张牌")
            return
        red, green = (card, cur.card) if card.color == RED else (cur.card, card)
        b = Beast(red.sigil, green.sigil, red.sigil, green.sigil, green.sigil)
        p.beasts[slot] = b
        p.grave += [red, green]
        self.log(f"▶ {p.name}召唤了纹兽：{b.describe()}")

    def act_evolve(self, p: Player, target: int, material: int, card: Card) -> None:
        """献祭一只 1 级纹兽，加一张纹牌，让另一只进化。升 2 级免费，升 3 级要付费。"""
        t, m = p.beasts[target], p.beasts[material]
        if target == material or not isinstance(t, Beast) or not isinstance(m, Beast):
            raise RuleError("进化需要场上两只纹兽：一只进化，一只当素材")
        if m.level != 1:
            raise RuleError("当素材的纹兽必须是 1 级")
        if t.level >= 3:
            raise RuleError("已经是 3 级了")
        cost = card.cost if t.level == 2 else 0
        self.take_from_hand(p, card)
        try:
            self.pay(p, cost)
        except RuleError:
            p.hand.append(card)
            raise
        p.grave.append(card)
        p.beasts[material] = None
        if t.level == 2:
            t.l2_snapshot = (t.atk, t.hp, t.max_hp, list(t.sigils), t.pierce)
            t.l3_rounds = L3_ROUNDS
        t.atk += m.atk // 2
        t.hp += m.hp // 2
        t.max_hp += m.hp // 2
        if card.color == RED:
            t.atk += EVOLVE_BONUS
        elif card.color == GREEN:
            t.hp += EVOLVE_BONUS
            t.max_hp += EVOLVE_BONUS
        else:
            t.pierce = True
        t.sigils.append(card.color)
        t.level += 1
        self.log(f"▶ {p.name}献祭{m.name}，用【{card.name}】进化：{t.describe()}")

    def act_field_card(self, p: Player, card: Card, slot: int) -> None:
        """往纹域位放牌。第一张定类型（盖着），第二张配合；位子上已有纹域就覆盖。"""
        cur = p.fields[slot]
        self.take_from_hand(p, card)
        cost = self.card_cost(p, card)
        try:
            self.pay(p, cost)
        except RuleError:
            p.hand.append(card)
            raise
        self._use_class_discount(p, card)
        if isinstance(cur, Field):
            p.grave += [cur.first, cur.second]
            self.log(f"  {p.name}覆盖了旧的{cur.name}")
            cur = None
        if cur is None:
            p.fields[slot] = Pending(card)
            self.log(f"▶ {p.name}在纹域位 {slot + 1} 盖了一张牌")
            return
        dur = max(1, cur.card.sigil + card.sigil)
        f = Field(cur.card, card, dur)
        p.fields[slot] = f
        self.log(f"▶ {p.name}的纹域成型：{f.describe()}")

    def act_extend(self, p: Player, card: Card, slot: int) -> None:
        """献祭一张蓝牌（不换纹力）给纹域 +1 耐久，每回合 1 次。"""
        if card.color != BLUE:
            raise RuleError("只有蓝牌可以献祭续命")
        if p.extended:
            raise RuleError("每回合只能献祭续命 1 次")
        f = p.fields[slot]
        if not isinstance(f, Field):
            raise RuleError("这个位置没有生效的纹域")
        self.take_from_hand(p, card)
        p.grave.append(card)
        f.durability += 1
        p.extended = True
        self.log(f"▶ {p.name}献祭【{card.name}】给{f.name}续命，耐久 {f.durability}")

    def act_set_defense(self, p: Player, card: Card) -> None:
        if card.color == RED:
            raise RuleError("防御纹不能放红牌")
        if p.defense is not None:
            raise RuleError("防御纹已经有一张盖牌了")
        self.take_from_hand(p, card)
        p.defense = card
        p.defense_turns = 0
        self.log(f"▶ {p.name}在防御纹盖了一张牌")

    def act_flip_defense(self, p: Player) -> None:
        if p.defense is None:
            raise RuleError("防御纹里没有牌")
        self.pay(p, p.defense_cost())
        self._flip(p)
        self.check_end()

    def _flip(self, p: Player) -> None:
        card = p.defense
        p.defense = None
        self.log(f"  {p.name}翻开防御纹【{card.name}】：{card.text}")
        try:
            self.resolve(p, card)
        except RuleError as e:
            self.log(f"  （{e}，效果无效）")
        p.grave.append(card)

    def act_sacrifice(self, p: Player, card: Card) -> None:
        self.take_from_hand(p, card)
        p.grave.append(card)
        p.power += 1
        self.log(f"▶ {p.name}献祭了一张牌，纹力 +1（现在 {p.power}）")

    def act_attack(self, p: Player, attacker: int | None, target: tuple) -> None:
        """attacker: None = 角色，数字 = 纹兽位。target: ("hero",) / ("beast", i) / ("field", i)。"""
        self.first_turn_guard(p)
        foe = self.opp(p)
        if attacker is None:
            if p.hero_attacks <= 0:
                raise RuleError("角色这回合已经攻击过了")
        else:
            b = p.beasts[attacker]
            if not isinstance(b, Beast):
                raise RuleError("这个位置没有纹兽")
            if b.sick:
                raise RuleError("刚召唤的纹兽要下回合才能攻击")
            if b.attacked:
                raise RuleError("这只纹兽这回合已经攻击过了")
            if b.sealed:
                raise RuleError("这只纹兽被封印了")
        kind = target[0]
        if kind == "beast" and not isinstance(foe.beasts[target[1]], Beast):
            raise RuleError("那里没有纹兽")
        if kind == "field" and not isinstance(foe.fields[target[1]], Field):
            raise RuleError("那里没有生效的纹域")

        if attacker is None:
            p.hero_attacks -= 1
            dmg = p.hero_atk(vs_beast=kind == "beast")
            pierce = p.pierce
            who = p.name
        else:
            b = p.beasts[attacker]
            b.attacked = True
            dmg = p.beast_atk(b)
            pierce = b.pierce
            who = f"{p.name}的{b.name}"
        source = (p, attacker)
        tname = {"hero": foe.name, "beast": "纹兽", "field": "纹域"}[kind]
        self.log(f"▶ {who}宣告攻击{tname}（{dmg} 点）")

        if kind in ("hero", "beast"):
            target = self.defense_window(foe, target, dmg)

        if target[0] == "hero":
            dealt = self.hit_hero(foe, dmg, pierce, source)
            self.log(f"  {foe.name}受到 {dealt} 伤害，剩 {foe.hp} 血")
        elif target[0] == "beast":
            dealt = self.hit_beast(foe, target[1], dmg, pierce)
            self.log(f"  纹兽受到 {dealt} 伤害")
        else:
            self.hit_field(foe, target[1], dmg)
        if attacker is None and p.draw_on_attack:
            self.draw(p, 1)
            self.log(f"  {p.name}攻击后抽 1 张")
        self.check_end()

    def defense_window(self, foe: Player, target: tuple, dmg: int) -> tuple:
        """8 秒判定：防守方选择纹兽挡刀、紧急举盾（两倍费用）或都不用。"""
        options, actions = ["都不用"], [None]
        if target[0] == "hero":
            for i, b in foe.live_beasts():
                options.append(f"让{b.describe()}挡刀")
                actions.append(("block", i))
        if foe.defense is not None and foe.power >= 2 * foe.defense_cost():
            options.append(f"紧急举盾：翻开防御纹（{2 * foe.defense_cost()} 纹力）")
            actions.append(("flip",))
        if len(options) == 1:
            return target
        self.log(f"  —— {foe.name}的 8 秒判定 ——")
        what = "角色" if target[0] == "hero" else "纹兽"
        a = actions[self.ask(foe, "defense", f"对方要攻击你的{what}，造成 {dmg} 点。你要：", options)]
        if a is None:
            return target
        if a[0] == "block":
            self.log(f"  {foe.name}让纹兽挡刀")
            return ("beast", a[1])
        foe.power -= 2 * foe.defense_cost()
        self._flip(foe)
        self.check_end()
        return target

    # ================================================================ 牌面效果
    def resolve(self, p: Player, card: Card) -> None:
        foe = self.opp(p)
        e, prm = card.effect, card.params
        kw = (card.keyword == FIRST and p.is_first) or (card.keyword == SECOND and not p.is_first)
        if kw and card.keyword:
            self.log(f"  {card.keyword}生效")

        if e == "buff":
            atk = prm.get("kw_atk", prm["atk"]) if kw else prm["atk"]
            if atk:
                p.buffs.append(Buff(atk, prm["rounds"]))
            if prm.get("pierce"):
                p.pierce = True
            if prm.get("vs_beast"):
                p.vs_beast += prm["vs_beast"]
            if prm.get("draw_on_attack"):
                p.draw_on_attack = True
        elif e == "extra_attack":
            p.hero_attacks += 1
        elif e == "field_damage":
            self.first_turn_guard(p)
            slots = [i for i, f in enumerate(foe.fields) if isinstance(f, Field)]
            if not slots:
                self.log("  对方没有纹域，效果落空")
                return
            i = slots[self.ask(p, "target_enemy_field", "选择敌方纹域",
                               [foe.fields[i].describe() for i in slots])]
            self.hit_field(foe, i, prm["amount"])
        elif e == "shield":
            amount = prm.get("kw_amount", prm["amount"]) if kw else prm["amount"]
            p.shields.append(self.new_shield(p, amount, prm.get("thorns", False)))
            self.log(f"  {p.name}获得 {amount} 护盾")
            if prm.get("beasts"):
                for _, b in p.live_beasts():
                    b.shields.append(self.new_shield(p, prm["beasts"]))
            if prm.get("draw"):
                self.draw(p, prm["draw"])
        elif e == "heal":
            self.heal(p, prm["amount"])
            if prm.get("shield"):
                p.shields.append(self.new_shield(p, prm["shield"]))
        elif e == "beast_shield":
            mine = p.live_beasts()
            if not mine:
                self.log("  没有己方纹兽，效果落空")
                return
            i = mine[self.ask(p, "target_own_beast", "选择己方纹兽", [b.describe() for _, b in mine])][0]
            p.beasts[i].shields.append(self.new_shield(p, prm["amount"]))
        elif e == "draw":
            self.draw(p, prm["n"])
        elif e == "summon_random":
            slots = [i for i, b in enumerate(p.beasts) if b is None]
            if not slots:
                self.log("  纹兽位满了，召唤失败")
                return
            a, h = self.rng.randint(1, 3), self.rng.randint(1, 3)
            b = Beast(a, h, a, h, h)
            p.beasts[slots[0]] = b
            self.log(f"  随机召唤：{b.describe()}")
        elif e == "damage":
            self.first_turn_guard(p)
            opts, targets = [f"{foe.name}本人"], [None]
            for i, b in foe.live_beasts():
                opts.append(b.describe())
                targets.append(i)
            t = targets[self.ask(p, "target_damage", "选择目标", opts)]
            if t is None:
                d = self.hit_hero(foe, prm["amount"])
                self.log(f"  {foe.name}受到 {d} 伤害")
            else:
                self.hit_beast(foe, t, prm["amount"])
        elif e == "burn":
            self.first_turn_guard(p)
            foe.burn += prm["amount"]
        elif e == "gain_power":
            p.power += prm["n"]
            self.log(f"  纹力 +{prm['n']}（现在 {p.power}）")
        elif e == "chaos":
            pick = self.rng.choice(["damage", "heal", "draw"])
            if pick == "damage":
                if p.turns <= 1:
                    self.log("  混沌：伤害，但第一回合不能造成伤害")
                else:
                    d = self.hit_hero(foe, 3)
                    self.log(f"  混沌：{foe.name}受到 {d} 伤害")
            elif pick == "heal":
                self.log("  混沌：回血")
                self.heal(p, 3)
            else:
                self.log("  混沌：抽 2 张")
                self.draw(p, 2)
        elif e == "dispel":
            foe.shields = []
            self.log(f"  {foe.name}的护盾全部消失")
        elif e == "peek":
            p.known_defense = foe.defense
            if foe.defense:
                self.log(f"  {p.name}看到了对方的防御纹盖牌")
            else:
                self.log("  对方防御纹是空的")
            self.draw(p, 1)
        elif e in ("field_ward", "field_fortify"):
            slots = [i for i, f in enumerate(p.fields) if isinstance(f, Field)]
            if not slots:
                self.log("  没有生效的己方纹域，效果落空")
                return
            i = slots[self.ask(p, "target_own_field", "选择己方纹域",
                               [p.fields[i].describe() for i in slots])]
            if e == "field_ward":
                p.fields[i].ward = True
            else:
                p.fields[i].durability += prm["amount"]
            self.log(f"  {p.fields[i].describe()}")
        elif e == "seal":
            theirs = foe.live_beasts()
            if not theirs:
                self.log("  对方没有纹兽，效果落空")
                return
            i = theirs[self.ask(p, "target_enemy_beast", "选择敌方纹兽", [b.describe() for _, b in theirs])][0]
            foe.beasts[i].sealed = 1
        elif e == "storm":
            self.first_turn_guard(p)
            d = self.hit_hero(foe, prm["amount"])
            self.log(f"  {foe.name}受到 {d} 伤害")
            for i, _ in foe.live_beasts():
                self.hit_beast(foe, i, prm["amount"])
        elif e == "break_defense":
            if foe.defense:
                foe.grave.append(foe.defense)
                self.log(f"  摧毁了对方防御纹里的【{foe.defense.name}】")
                foe.defense = None
            else:
                self.log("  对方防御纹是空的")
        else:
            raise ValueError(f"未知效果 {e}")
