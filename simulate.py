"""电脑对电脑跑很多局，统计职业胜率、先后手胜率和对局长度，用来检查数值。

运行：python3 simulate.py              每种职业组合各 20 局（共 180 局）
      python3 simulate.py 100          每种组合各 100 局
      python3 simulate.py 1 --log      打印一局的完整过程
      python3 simulate.py 30 --skill   上下限：每个职业用新手 / 高手人机，对普通人机打
"""

import argparse
import itertools
import json
import statistics
from collections import Counter
from multiprocessing import Pool, cpu_count

CLASSES = ["warrior", "archmage", "guardian"]


def one_game(args):
    a, b, seed, level, advanced = args
    from shuangshengwen.ai import AIController
    from shuangshengwen.engine import Game
    g = Game(("甲", "乙"), (AIController(level=level, seed=seed*2), AIController(level=level, seed=seed*2+1)), seed=seed, log=lambda *x: None, classes=(a, b), advanced=advanced)
    w = g.play()
    return a, b, (w.cls if w else None), (w.is_first if w else None), sum(p.turns for p in g.players), g.stats


def skill_game(args):
    cls, level, foe, seat, seed = args
    from shuangshengwen.ai import AIController
    from shuangshengwen.engine import Game
    ctrls = [AIController(seed=seed*2), AIController(seed=seed*2+1)]
    ctrls[seat] = AIController(level=level, seed=seed*2+seat+17)
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
    with Pool(min(8, max(1, cpu_count()))) as pool:
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


def run(per_pair: int, level="normal", seed=7, advanced=False, workers=None, output=None) -> dict:
    jobs = [(a, b, k * 13 + seed, level, advanced)
            for a, b in itertools.product(CLASSES, repeat=2) for k in range(per_pair)]
    with Pool(workers or min(8, max(1, cpu_count()))) as pool:
        out = pool.map(one_game, jobs, chunksize=2)
    res, games, first, turns, actions = Counter(), Counter(), Counter(), [], Counter()
    for a, b, w, f, t, stats in out:
        turns.append(t)
        actions.update(stats)
        if w is None:
            continue
        games[(a, b)] += 1
        res[(a, b, w)] += 1
        first[f] += 1
    report = {"games": len(out), "seed": seed, "ai": level, "advanced": advanced,
              "matchups": {}, "actions_per_game": {k: v / len(out) for k, v in actions.items()}}
    print(f"共 {len(out)} 局，{level}人机，seed={seed}，{'进阶' if advanced else '新手'}模式")
    for a, b in itertools.combinations(CLASSES, 2):
        n = games[(a, b)] + games[(b, a)]
        wa = res[(a, b, a)] + res[(b, a, a)]
        rate = wa/n if n else None
        report["matchups"][f"{a}/{b}"] = {"wins": wa, "decided": n, "rate": rate}
        print(f"  {a} 对 {b}：{a} 胜率 {rate:.1%}（{n} 局）" if n else f"  {a} 对 {b}：无完成对局")
    done = first[True] + first[False]
    report.update(first_winrate=first[True]/done if done else None,
                  mean_rounds=statistics.mean(turns)/2, median_rounds=statistics.median(turns)/2,
                  timeouts=len(out)-done)
    print(f"先手胜率：{report['first_winrate']:.1%}" if done else "没有完成对局")
    print(f"平均每人回合数：{report['mean_rounds']:.1f}，超时局：{report['timeouts']}")
    print("每局行动均值：" + "，".join(f"{k}={v:.2f}" for k, v in report["actions_per_game"].items()))
    if output:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    return report


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
    ap.add_argument("--level", choices=["normal", "strong", "weak"], default="normal")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--advanced", action="store_true")
    ap.add_argument("--workers", type=int, default=min(8, max(1, cpu_count())))
    ap.add_argument("--json", help="保存统计JSON")
    a = ap.parse_args()
    if a.n < 1 or a.workers < 1:
        ap.error("局数和worker数必须大于0")
    show_one() if a.log else run_skill(a.n, a.only) if a.skill else run(a.n, a.level, a.seed, a.advanced, a.workers, a.json)
