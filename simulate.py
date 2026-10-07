"""电脑对电脑跑很多局，统计职业胜率、先后手胜率和对局长度，用来检查数值。

运行：python3 simulate.py              每种职业组合各 20 局（共 180 局）
      python3 simulate.py 100          每种组合各 100 局
      python3 simulate.py 1 --log      打印一局的完整过程
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
    a = ap.parse_args()
    show_one() if a.log else run(a.n)
