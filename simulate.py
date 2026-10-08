"""电脑对电脑跑很多局，统计职业胜率、先后手胜率和对局长度，用来检查数值。

运行：python3 simulate.py              每种职业组合各 20 局（共 180 局）
      python3 simulate.py 100          每种组合各 100 局
      python3 simulate.py 1 --log      打印一局的完整过程
      python3 simulate.py 30 --skill   上下限：每个职业用新手 / 高手人机，对普通人机打
"""

import argparse
import itertools
from collections import Counter
from multiprocessing import Pool, cpu_count

CLASSES = ["warrior", "archmage", "guardian"]


def one_game(args):
    a, b, seed = args
    from shuangshengwen.ai import AIController
    from shuangshengwen.engine import Game
    g = Game(("甲", "乙"), (AIController(), AIController()), seed=seed, log=lambda *x: None, classes=(a, b))
    w = g.play()
    return a, b, (w.cls if w else None), (w.is_first if w else None), sum(p.turns for p in g.players)


def skill_game(args):
    cls, level, foe, seat, seed = args
    from shuangshengwen.ai import AIController
    from shuangshengwen.engine import Game
    ctrls = [AIController(), AIController()]
    ctrls[seat] = AIController(level=level)
    classes = [foe, foe]
    classes[seat] = cls
    g = Game(("甲", "乙"), tuple(ctrls), seed=seed, log=lambda *x: None, classes=tuple(classes))
    w = g.play()
    return cls, level, w is g.players[seat]


def run_skill(per_pair: int, only: list[str]) -> None:
    """下限 = 新手人机的胜率，上限 = 高手人机的胜率；对手都是普通人机，三个职业轮流当对手、轮流先后手。"""
    jobs = [(c, lv, f, seat, k * 31 + seat * 7 + 3)
            for c in only for lv in ("weak", "strong") for f in CLASSES for seat in (0, 1)
            for k in range(per_pair)]
    with Pool(max(1, cpu_count())) as pool:
        out = pool.map(skill_game, jobs, chunksize=2)
    win, n = Counter(), Counter()
    for c, lv, w in out:
        n[(c, lv)] += 1
        win[(c, lv)] += w
    print(f"共 {len(out)} 局（对手都是普通人机）")
    for c in only:
        lo = win[(c, "weak")] / n[(c, "weak")]
        hi = win[(c, "strong")] / n[(c, "strong")]
        print(f"  {c}：新手 {lo:.0%}，高手 {hi:.0%}，差距 {hi - lo:+.0%}")


def run(per_pair: int) -> None:
    jobs = [(a, b, k * 13 + 7) for a, b in itertools.product(CLASSES, repeat=2) for k in range(per_pair)]
    with Pool(max(1, cpu_count())) as pool:
        out = pool.map(one_game, jobs, chunksize=4)
    res, games, first, turns = Counter(), Counter(), Counter(), []
    for a, b, w, f, t in out:
        turns.append(t)
        if w is None:
            continue
        games[(a, b)] += 1
        res[(a, b, w)] += 1
        first[f] += 1
    print(f"共 {len(out)} 局")
    for a, b in itertools.combinations(CLASSES, 2):
        n = games[(a, b)] + games[(b, a)]
        wa = res[(a, b, a)] + res[(b, a, a)]
        print(f"  {a} 对 {b}：{a} 胜率 {wa / n:.0%}（{n} 局）")
    done = first[True] + first[False]
    print(f"先手胜率：{first[True] / done:.0%}")
    print(f"平均每人回合数：{sum(turns) / len(turns) / 2:.1f}，超时局：{len(out) - done}")


def show_one() -> None:
    from shuangshengwen.ai import AIController
    from shuangshengwen.engine import Game
    g = Game(("甲", "乙"), (AIController(), AIController()), seed=1)
    w = g.play()
    print(f"\n{w.name}获胜" if w else "\n平局")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("n", type=int, nargs="?", default=20, help="每种职业组合打几局")
    ap.add_argument("--log", action="store_true", help="打印一局的完整过程")
    ap.add_argument("--skill", action="store_true", help="测各职业的上下限")
    ap.add_argument("--only", nargs="*", default=CLASSES, help="只测这些职业的上下限")
    a = ap.parse_args()
    show_one() if a.log else run_skill(a.n, a.only) if a.skill else run(a.n)
