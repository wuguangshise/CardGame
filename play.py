"""《双生纹》命令行试玩：你 vs 人机。

运行：python3 play.py
      python3 play.py --seed 42     固定随机种子，方便复现同一局
      python3 play.py --hotseat     两个人在同一台电脑上轮流玩
"""

import argparse

if __name__ == "__main__":
    from startup import prepare_environment
    prepare_environment()

from shuangshengwen.ai import AIController
from shuangshengwen.cards import COLOR_NAME
from shuangshengwen.engine import (
    CLASSES, Beast, Controller, Field, Game, Pending, Player, RuleError,
)


def ask_int(prompt: str, lo: int, hi: int, allow_blank=False):
    while True:
        raw = input(prompt).strip()
        if allow_blank and raw == "":
            return None
        if raw.isdigit() and lo <= int(raw) <= hi:
            return int(raw)
        print(f"  请输入 {lo} 到 {hi} 之间的数字" + ("，直接回车取消" if allow_blank else ""))


def pick_card(me: Player, prompt: str, filt=None):
    cards = [c for c in me.hand if filt is None or filt(c)]
    if not cards:
        print("  没有可用的牌")
        return None
    for i, c in enumerate(cards, 1):
        print(f"    [{i}] {c.label()}")
    i = ask_int(f"  {prompt}（回车取消）> ", 1, len(cards), allow_blank=True)
    return None if i is None else cards[i - 1]


def pick_slot(prompt: str):
    i = ask_int(f"  {prompt}（1 或 2，回车取消）> ", 1, 2, allow_blank=True)
    return None if i is None else i - 1


def slot_text(x) -> str:
    if x is None:
        return "空"
    if isinstance(x, Pending):
        return "盖着一张牌"
    return x.describe()


def show_side(game: Game, p: Player, me: bool) -> None:
    shield = f" 盾{p.shield_total()}" if p.shield_total() else ""
    atk = p.hero_atk()
    burn = f" 下回合燃烧{p.burn}" if p.burn else ""
    empty = " 牌库空（受伤翻倍）" if p.deck_empty else ""
    print(f"  【{p.name}】{CLASSES[p.cls]}")
    print(f"    血 {p.hp}{shield}  攻 {atk}  纹力 {p.power}  手牌 {len(p.hand)}  牌库 {len(p.deck)}{burn}{empty}")
    print(f"    纹兽位：1 {slot_text(p.beasts[0])} | 2 {slot_text(p.beasts[1])}")
    print(f"    纹域位：1 {slot_text(p.fields[0])} | 2 {slot_text(p.fields[1])}")
    if p.defense is None:
        d = "空"
    elif me:
        d = f"【{p.defense.name}】现在翻开要 {p.defense_cost()} 纹力，紧急举盾要 {2 * p.defense_cost()}"
    else:
        d = "盖着一张牌"
    print(f"    防御纹：{d}")


def show_board(game: Game, me: Player) -> None:
    foe = game.opp(me)
    print("\n" + "-" * 60)
    show_side(game, foe, False)
    if me.known_defense is not None and foe.defense is me.known_defense:
        print(f"    （洞察：对方防御纹是【{foe.defense.name}】）")
    print()
    show_side(game, me, True)
    print("  你的手牌：")
    for c in me.hand:
        print(f"    {c.label()}")
    print("-" * 60)


MENU = [
    ("打出一张牌", "play"),
    ("合纹（主卡 + 附加卡）", "combo"),
    ("往纹兽位放牌（一红一绿召唤）", "beast"),
    ("进化纹兽", "evolve"),
    ("往纹域位放牌", "field"),
    ("在防御纹盖牌", "set_def"),
    ("翻开防御纹", "flip_def"),
    ("献祭一张牌（+1 纹力）", "sacrifice"),
    ("献祭蓝牌给纹域续命", "extend"),
    ("攻击", "attack"),
]


class HumanController(Controller):
    def choose(self, game, me, kind, prompt, options):
        print(f"\n  {me.name}：{prompt}")
        for i, o in enumerate(options, 1):
            print(f"    [{i}] {o}")
        return ask_int("  > ", 1, len(options)) - 1

    def take_turn(self, game: Game, me: Player) -> None:
        while True:
            show_board(game, me)
            for i, (name, _) in enumerate(MENU, 1):
                print(f"  [{i}] {name}")
            print("  [0] 结束回合")
            k = ask_int("选择操作 > ", 0, len(MENU))
            if k == 0:
                return
            try:
                self.do(game, me, MENU[k - 1][1])
            except RuleError as e:
                print(f"  ✗ {e}")
            if game.winner is not None or any(p.hp <= 0 for p in game.players):
                return

    def do(self, game: Game, me: Player, what: str) -> None:
        foe = game.opp(me)
        if what == "play":
            c = pick_card(me, "选择要打出的牌")
            if c:
                game.act_play(me, c)
        elif what == "combo":
            main = pick_card(me, "选择主卡（付费、生效）")
            if not main:
                return
            addon = pick_card(me, "选择附加卡（免费，只加颜色特性：红=无视护盾，绿=护盾等于纹值，蓝=随机魔法）",
                              lambda c: c is not main)
            if addon:
                game.act_combo(me, main, addon)
        elif what == "beast":
            c = pick_card(me, "选择红牌（纹值=攻击）或绿牌（纹值=血量）", lambda c: c.color != "blue")
            if not c:
                return
            s = pick_slot("放到哪个纹兽位")
            if s is not None:
                game.act_beast_card(me, c, s)
        elif what == "evolve":
            live = me.live_beasts()
            if len(live) < 2:
                raise RuleError("进化需要场上两只纹兽")
            t = pick_slot("哪只纹兽进化")
            if t is None:
                return
            m = 1 - t
            c = pick_card(me, "选择进化用的纹牌（红=+攻，绿=+血，蓝=穿透；升 3 级要付这张牌的费用）")
            if c:
                game.act_evolve(me, t, m, c)
        elif what == "field":
            c = pick_card(me, "选择放入纹域的牌（第一张定类型，第二张定配合方式）")
            if not c:
                return
            s = pick_slot("放到哪个纹域位（已有纹域会被覆盖）")
            if s is not None:
                game.act_field_card(me, c, s)
        elif what == "set_def":
            c = pick_card(me, "选择盖到防御纹的牌（不能是红牌）", lambda c: c.color != "red")
            if c:
                game.act_set_defense(me, c)
        elif what == "flip_def":
            game.act_flip_defense(me)
        elif what == "sacrifice":
            c = pick_card(me, "选择献祭的牌")
            if c:
                game.act_sacrifice(me, c)
        elif what == "extend":
            c = pick_card(me, "选择献祭的蓝牌", lambda c: c.color == "blue")
            if not c:
                return
            s = pick_slot("给哪个纹域续命")
            if s is not None:
                game.act_extend(me, c, s)
        elif what == "attack":
            opts = [("角色", None)] + [(b.describe(), i) for i, b in me.live_beasts()]
            for i, (t, _) in enumerate(opts, 1):
                print(f"    [{i}] {t}")
            a = ask_int("  谁来攻击（回车取消）> ", 1, len(opts), allow_blank=True)
            if a is None:
                return
            targets = [(f"{foe.name}本人", ("hero",))]
            targets += [(f"纹兽 {b.describe()}", ("beast", i)) for i, b in foe.live_beasts()]
            targets += [(f"纹域 {f.describe()}", ("field", i))
                        for i, f in enumerate(foe.fields) if isinstance(f, Field)]
            for i, (t, _) in enumerate(targets, 1):
                print(f"    [{i}] {t}")
            t = ask_int("  攻击谁（回车取消）> ", 1, len(targets), allow_blank=True)
            if t is not None:
                game.act_attack(me, opts[a - 1][1], targets[t - 1][1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int)
    ap.add_argument("--hotseat", action="store_true", help="两个人轮流操作")
    a = ap.parse_args()

    print("《双生纹》测试版 —— 规则见 README.md")
    if a.hotseat:
        game = Game(("玩家一", "玩家二"), (HumanController(), HumanController()), seed=a.seed)
    else:
        game = Game(("你", "人机"), (HumanController(), AIController()), seed=a.seed)
    w = game.play()
    print("\n" + "=" * 60)
    print(f"游戏结束：{w.name}获胜！" if w else "游戏结束：平局")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已退出")
    except EOFError:
        print("\n当前控制台没有可用输入。请在终端运行 python play.py，或双击 start_game.bat 运行图形版。")
    from startup import pause_if_double_clicked
    pause_if_double_clicked()

