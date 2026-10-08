"""《双生纹》测试卡池：40 张（红 13、绿 13、蓝 14）。

数值按规则书「数值基准」：1 纹力约等于 1 点有效数值，攻击效率略高于防守。
纹值：红绿 1 到 3，蓝 0 到 4。费用：红绿 0 到 3，蓝 2 到 3。
"""

from dataclasses import dataclass, field
from collections import Counter
import json
from pathlib import Path

RED, GREEN, BLUE = "red", "green", "blue"
COLOR_NAME = {RED: "红", GREEN: "绿", BLUE: "蓝"}

FIRST, SECOND = "先攻", "后发"


@dataclass(eq=False)
class Card:
    name: str
    color: str
    cost: int
    sigil: int
    text: str
    effect: str
    params: dict = field(default_factory=dict)
    keyword: str | None = None

    def label(self) -> str:
        kw = f"【{self.keyword}】" if self.keyword else ""
        return f"{COLOR_NAME[self.color]}·{self.name}（{self.cost}费 纹{self.sigil}）{kw}{self.text}"


def _pool() -> list[Card]:
    C = Card
    return [
        # ---------- 红：攻击 ----------
        C("迅斩", RED, 0, 1, "角色本回合 +1 攻", "buff", {"atk": 1, "rounds": 1}),
        C("战吼", RED, 0, 3, "角色本回合 +1 攻", "buff", {"atk": 1, "rounds": 1}),
        C("试锋", RED, 1, 1, "角色 +1 攻，持续 2 回合", "buff", {"atk": 1, "rounds": 2}),
        C("裂风", RED, 1, 2, "角色 +1 攻，持续 2 回合；先攻：改为 +2", "buff",
          {"atk": 1, "rounds": 2, "kw_atk": 2}, FIRST),
        C("斩兽", RED, 1, 3, "角色本回合攻击纹兽时 +3 攻", "buff", {"atk": 0, "rounds": 1, "vs_beast": 3}),
        C("碎域", RED, 1, 2, "对一个敌方纹域造成 2 点耐久伤害", "field_damage", {"amount": 2}),
        C("烈斩", RED, 2, 2, "角色 +2 攻，持续 2 回合", "buff", {"atk": 2, "rounds": 2}),
        C("破甲", RED, 2, 1, "角色 +1 攻，持续 2 回合；本回合角色攻击无视护盾", "buff",
          {"atk": 1, "rounds": 2, "pierce": True}),
        C("战意", RED, 2, 3, "角色 +1 攻，持续 2 回合；本回合角色攻击后抽 1 张", "buff",
          {"atk": 1, "rounds": 2, "draw_on_attack": True}),
        C("蓄势", RED, 2, 2, "角色 +2 攻，持续 2 回合；后发：改为 +3", "buff",
          {"atk": 2, "rounds": 2, "kw_atk": 3}, SECOND),
        C("狂怒", RED, 3, 3, "角色 +3 攻，只持续本回合；本回合角色攻击后抽 1 张", "buff", {"atk": 3, "rounds": 1, "draw_on_attack": True}),
        C("重锤", RED, 3, 3, "角色本回合 +2 攻，并且攻击无视护盾", "buff",
          {"atk": 2, "rounds": 1, "pierce": True}),
        C("连击", RED, 3, 1, "角色本回合可以再攻击一次", "extra_attack", {}),
        # ---------- 绿：回复与防御 ----------
        C("薄盾", GREEN, 0, 1, "角色获得 1 护盾", "shield", {"amount": 1}),
        C("生机", GREEN, 0, 2, "回复 1 血", "heal", {"amount": 1}),
        C("木盾", GREEN, 1, 1, "角色获得 2 护盾", "shield", {"amount": 2}),
        C("青藤", GREEN, 1, 3, "回复 1 血，角色获得 1 护盾", "heal", {"amount": 1, "shield": 1}),
        C("庇护", GREEN, 1, 3, "一只己方纹兽获得 2 护盾", "beast_shield", {"amount": 2}),
        C("守望", GREEN, 1, 2, "角色获得 2 护盾；后发：改为 3", "shield",
          {"amount": 2, "kw_amount": 3}, SECOND),
        C("铁盾", GREEN, 2, 2, "角色获得 3 护盾", "shield", {"amount": 3}),
        C("疗伤", GREEN, 2, 2, "回复 2 血", "heal", {"amount": 2}),
        C("坚守", GREEN, 2, 1, "角色获得 2 护盾，抽 1 张", "shield", {"amount": 2, "draw": 1}),
        C("荆棘", GREEN, 2, 3, "角色获得 2 护盾；护盾在时，攻击角色的单位受 1 伤害", "shield",
          {"amount": 2, "thorns": True}),
        C("重铠", GREEN, 3, 3, "角色获得 4 护盾", "shield", {"amount": 4}),
        C("甘霖", GREEN, 3, 1, "回复 3 血", "heal", {"amount": 3}),
        C("磐石", GREEN, 3, 2, "角色获得 3 护盾，每只己方纹兽获得 1 护盾", "shield",
          {"amount": 3, "beasts": 1}),
        # ---------- 蓝：魔法 ----------
        C("灵感", BLUE, 2, 1, "抽 3 张", "draw", {"n": 3}),
        C("召唤术", BLUE, 2, 2, "随机召唤一只 1 级纹兽", "summon_random", {}),
        C("奥术飞弹", BLUE, 2, 3, "对一个敌方目标造成 3 伤害，无视护盾", "damage", {"amount": 3, "pierce": True}),
        C("燃魂", BLUE, 2, 2, "燃烧：对方下回合开始受 4 伤害", "burn", {"amount": 4}),
        C("法力回流", BLUE, 2, 0, "获得 4 纹力", "gain_power", {"n": 4}),
        C("混沌", BLUE, 2, 4, "随机一个：对方角色受 4 伤害 / 回 4 血 / 抽 3 张", "chaos", {}),
        C("驱散", BLUE, 2, 1, "移除对方角色的所有护盾，抽 1 张", "dispel", {"draw": 1}),
        C("洞察", BLUE, 2, 2, "查看对方防御纹里的盖牌，抽 2 张", "peek", {"draw": 2}),
        C("免伤符", BLUE, 2, 1, "己方一个纹域下一次受到的伤害变为 0", "field_ward", {}),
        C("加固符", BLUE, 2, 2, "己方一个纹域耐久 +2", "field_fortify", {"amount": 2}),
        C("秘法盾", BLUE, 2, 3, "角色获得 3 护盾，抽 1 张", "shield", {"amount": 3, "draw": 1}),
        C("封印", BLUE, 2, 3, "一只敌方纹兽下回合不能攻击", "seal", {}),
        C("魔力风暴", BLUE, 3, 4, "对方角色和每只敌方纹兽各受 2 伤害，无视护盾", "storm", {"amount": 2}),
        C("破法", BLUE, 2, 0, "摧毁对方防御纹里的盖牌", "break_defense", {}),
    ]


POOL = _pool()

# 32张特色预组；同名最多2张。组合组件有重复，爆发/资源牌先保留单张。
STARTER_DROPS = {
    "warrior": ["荆棘", "磐石", "重铠", "免伤符", "加固符", "洞察", "破法", "混沌", "秘法盾"],
    "guardian": ["迅斩", "战吼", "狂怒", "燃魂", "混沌", "洞察", "免伤符", "加固符", "破法"],
    "archmage": ["斩兽", "碎域", "重锤", "庇护", "甘霖", "磐石", "免伤符", "加固符", "破法"],
}
STARTER_EXTRA = {"warrior": "裂风", "guardian": "青藤", "archmage": "秘法盾"}


def new_pool() -> list[Card]:
    """每个玩家拿一份独立的卡牌对象。"""
    return _pool()


def build_deck(names: list[str]) -> list[Card]:
    """自由构筑不限制配色；每份卡牌都是独立对象。"""
    if len(names) != 32:
        raise ValueError("套牌必须有32张牌")
    if not all(isinstance(name, str) for name in names):
        raise ValueError("套牌必须是卡牌名称列表")
    if any(n > 2 for n in Counter(names).values()):
        raise ValueError("同名卡最多带2张")
    legal = {c.name for c in POOL}
    if set(names) - legal:
        raise ValueError("套牌包含未知卡牌")
    return [next(c for c in new_pool() if c.name == name) for name in names]


def read_deck(path) -> list[str]:
    names = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(names, list):
        raise ValueError("套牌文件必须是包含32个卡名的JSON列表")
    build_deck(names)
    return names


def starter_deck(cls: str) -> list[Card]:
    drops = set(STARTER_DROPS[cls])
    names = [c.name for c in POOL if c.name not in drops] + [STARTER_EXTRA[cls]]
    return build_deck(names)


# 1 级纹兽：攻血决定种类
SPECIES = {
    (1, 1): "灵雀", (1, 2): "石龟", (1, 3): "铁甲虫",
    (2, 1): "疾狐", (2, 2): "苍狼", (2, 3): "棕熊",
    (3, 1): "赤隼", (3, 2): "猎豹", (3, 3): "雷虎",
}

# 纹域：第一张定类型，第二张配合
FIELD_TYPES = {
    RED: "战意纹域",
    GREEN: "守护纹域",
    BLUE: "秘法纹域",
}
