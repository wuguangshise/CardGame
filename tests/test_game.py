"""冒烟测试：python3 -m unittest"""

import builtins
import random
import unittest

import play
from shuangshengwen.ai import AIController
from shuangshengwen.cards import GREEN, POOL, RED, starter_deck
from shuangshengwen.engine import Beast, Game, RuleError


def quiet(*a, **kw):
    pass


class TestRules(unittest.TestCase):
    def test_pool_and_decks(self):
        self.assertEqual(len(POOL), 40)
        self.assertEqual(len({c.name for c in POOL}), 40)
        for c in POOL:
            lo, hi = (0, 4) if c.color == "blue" else (1, 3)
            self.assertTrue(lo <= c.sigil <= hi, c.name)
        for cls in ("warrior", "archmage", "guardian"):
            self.assertEqual(len(starter_deck(cls)), 32)

    def new_game(self):
        g = Game(("A", "B"), (AIController(), AIController()), seed=1, log=quiet,
                 classes=("warrior", "guardian"))
        g.setup()
        a = g.players[0]
        a.turns = 2
        return g, a

    def test_archmage_chain(self):
        g, a = self.new_game()
        a.cls = "archmage"
        b = g.opp(a)
        b.shields = []
        hp, power = b.hp, 10
        a.power = power
        c1 = next(c for c in POOL if c.name == "灵感")
        c2 = next(c for c in POOL if c.name == "洞察")
        a.hand += [c1, c2]
        self.assertEqual(g.card_cost(a, c1), 2)
        g.act_play(a, c1)
        self.assertEqual(g.card_cost(a, c2), 1)
        g.act_play(a, c2)
        self.assertEqual(a.power, power - 3)
        self.assertEqual(b.hp, hp - 1)

    def test_summon_red_green(self):
        g, a = self.new_game()
        red = next(c for c in starter_deck("warrior") if c.color == RED and c.sigil == 3)
        green = next(c for c in starter_deck("warrior") if c.color == GREEN and c.sigil == 2)
        a.hand += [red, green]
        g.act_beast_card(a, red, 0)
        g.act_beast_card(a, green, 0)
        b = a.beasts[0]
        self.assertIsInstance(b, Beast)
        self.assertEqual((b.atk, b.hp), (3, 2))

    def test_same_color_cannot_summon(self):
        g, a = self.new_game()
        reds = [c for c in starter_deck("warrior") if c.color == RED][:2]
        a.hand += reds
        g.act_beast_card(a, reds[0], 0)
        with self.assertRaises(RuleError):
            g.act_beast_card(a, reds[1], 0)

    def test_no_damage_first_turn(self):
        g, a = self.new_game()
        a.turns = 1
        with self.assertRaises(RuleError):
            g.act_attack(a, None, ("hero",))

    def test_defense_no_red(self):
        g, a = self.new_game()
        red = next(c for c in starter_deck("warrior") if c.color == RED)
        a.hand.append(red)
        with self.assertRaises(RuleError):
            g.act_set_defense(a, red)

    def test_deck_out_doubles_damage(self):
        g, a = self.new_game()
        b = g.players[1]
        b.deck_empty = True
        b.shields = []
        hp = b.hp
        g.hit_hero(b, 2)
        self.assertEqual(b.hp, hp - 4)


class TestFullGames(unittest.TestCase):
    def test_ai_vs_ai(self):
        for seed in range(8):
            g = Game(("A", "B"), (AIController(), AIController()), seed=seed, log=quiet)
            g.play()

    def test_random_human_inputs(self):
        """用随机输入驱动命令行界面，确保不会崩溃。"""
        rng = random.Random(0)
        real_input, real_print = builtins.input, builtins.print
        for seed in range(4):
            count = {"n": 0}

            def fake_input(prompt=""):
                count["n"] += 1
                if count["n"] % 12 == 0:
                    return "0"
                return rng.choice(["", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "x"])

            builtins.input, builtins.print = fake_input, quiet
            try:
                g = Game(("你", "人机"), (play.HumanController(), AIController()), seed=seed, log=quiet)
                g.play(max_turns=30)
            finally:
                builtins.input, builtins.print = real_input, real_print


if __name__ == "__main__":
    unittest.main()


class TestGUI(unittest.TestCase):
    """无窗口模式下检查图形界面能画出来、拖放规则映射正确。"""

    def setUp(self):
        import os
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
        try:
            import pygame  # noqa: F401
        except ImportError:
            self.skipTest("没有安装 pygame")

    def test_render_and_drops(self):
        from shuangshengwen.gui.app import GUI
        gui = GUI(seed=2)
        g = Game(("你", "人机"), (AIController(), AIController()), seed=2, log=gui.on_log,
                 classes=("warrior", "guardian"))
        gui.game, gui.me = g, g.players[0]
        g.current = g.setup()
        g.current = 0
        me = gui.me
        me.turns = 2
        gui.render()
        red = next(c for c in starter_deck("warrior") if c.color == RED and c.cost == 1)
        green = next(c for c in starter_deck("warrior") if c.color == GREEN and c.cost == 1)
        me.hand += [red, green]
        gui.drop_card(red, gui.slot_rects[("me", "beast", 0)].center)
        gui.drop_card(green, gui.slot_rects[("me", "beast", 0)].center)
        self.assertIsInstance(me.beasts[0], Beast)
        c = me.hand[0]
        n = len(me.hand)
        gui.drop_card(c, gui.altar.center)
        self.assertEqual(len(me.hand), n - 1)
        gui.drop_attack(None, gui.enemy_hero)
        self.assertEqual(me.hero_attacks, 0)
        gui.render()
