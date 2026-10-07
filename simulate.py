"""电脑对电脑跑很多局，统计胜率和对局长度，用来检查数值。

运行：python3 simulate.py           跑 300 局
      python3 simulate.py 1000 --log 1    跑 1000 局，并打印第 1 局的完整过程
"""

import argparse
import itertools
from collections import Counter

from shuangshengwen.ai import AIController
from shuangshengwen.engine import Game


def run(n: int, show: int | None = None):
    wins, turns, firsts, hp_left = Counter(), [], Counter(), []
    classes = ["warrior", "archmage", "guardian"]
    pairs = list(itertools.product(classes, classes))
    for k in range(n):
        cls = pairs[k % len(pairs)]
        log = print if show == k + 1 else (lambda *a, **kw: None)
        g = Game(("甲", "乙"), (AIController(), AIController()), seed=k, log=log, classes=cls)
        w = g.play()
        total = sum(p.turns for p in g.players)
        turns.append(total)
        if w is None:
            wins["平局/超时"] += 1
            continue
        wins[f"{w.cls}"] += 1
        firsts["先手赢" if w.is_first else "后手赢"] += 1
        hp_left.append(w.hp)
    print(f"共 {n} 局（职业轮流对战）")
    print("胜场（按赢家职业）：", dict(wins))
    print("先后手：", dict(firsts))
    print(f"平均总回合数：{sum(turns) / len(turns):.1f}（每人约 {sum(turns) / len(turns) / 2:.1f} 回合）")
    print(f"总回合数分布：最短 {min(turns)}，最长 {max(turns)}")
    if hp_left:
        print(f"赢家平均剩余血量：{sum(hp_left) / len(hp_left):.1f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("n", type=int, nargs="?", default=300)
    ap.add_argument("--log", type=int, help="打印第几局的完整过程")
    a = ap.parse_args()
    run(a.n, a.log)
