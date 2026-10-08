"""Rules that matter for resource economy, evolution risk and actual animation targets."""
import os
import unittest
from collections import Counter
from unittest.mock import Mock

from shuangshengwen.ai import AIController
from shuangshengwen.cards import BLUE, GREEN, RED, POOL, build_deck, starter_deck
from shuangshengwen.engine import Beast, Game, GameOver, RuleError


def card(name):
    return next(c for c in starter_deck('archmage') if c.name == name)


def fixture(events=None):
    game = Game(('A', 'B'), (AIController(seed=3), AIController(seed=4)), seed=2,
                classes=('warrior', 'guardian'), log=lambda _: None, events=events)
    game.players[0].turns = 2
    return game, game.players[0], game.players[1]


class BalanceRules(unittest.TestCase):
    def test_red_addon_has_limited_piercing_full_piercing_cards_still_work(self):
        from shuangshengwen.engine import Shield
        g, a, b = fixture()
        b.shields = [Shield(8, 2)]
        g.hit_hero(b, 5, pierce=2)
        self.assertEqual(b.hp, 13)
        self.assertEqual(b.shield_total(), 5)
        g.hit_hero(b, 3, pierce=True)
        self.assertEqual(b.hp, 10)
        self.assertEqual(b.shield_total(), 5)
        addon = card('迅斩')
        g.addon_trait(a, addon)
        g.addon_trait(a, addon)
        self.assertEqual(a.pierce_amount, 2)
        g.start_turn(a)
        self.assertEqual(a.pierce_amount, 0)

    def test_income_is_one_from_second_turn_and_accumulates(self):
        g, a, _ = fixture()
        a.turns, a.power = 0, 5
        g.start_turn(a)
        self.assertEqual(a.power, 5)
        g.start_turn(a)
        self.assertEqual(a.power, 6)
        g.start_turn(a)
        self.assertEqual(a.power, 7)

    def test_decks_have_identity_and_independent_duplicate_cards(self):
        ratios = {'warrior': {RED: 14, GREEN: 10, BLUE: 8},
                  'guardian': {RED: 10, GREEN: 14, BLUE: 8},
                  'archmage': {RED: 10, GREEN: 10, BLUE: 12}}
        for cls, expected in ratios.items():
            deck = starter_deck(cls)
            self.assertEqual(Counter(c.color for c in deck), expected)
            self.assertEqual(len(set(map(id, deck))), 32)
            self.assertLessEqual(max(Counter(c.name for c in deck).values()), 2)
        names = [c.name for c in starter_deck('warrior')]
        names[:3] = ['迅斩']*3
        with self.assertRaises(ValueError): build_deck(names)

    def test_beginner_skips_bans_advanced_keeps_them(self):
        for advanced, total in ((False, 32), (True, 30)):
            g, _, _ = fixture()
            g.advanced = advanced
            g.setup()
            for p in g.players:
                self.assertEqual(len(p.deck)+len(p.hand), total)

    def test_small_material_still_gives_stats_and_evolving_does_not_refresh_attack(self):
        g, a, _ = fixture()
        a.beasts = [Beast(1, 1, 1, 1, 1, attacked=True), Beast(1, 1, 1, 1, 1)]
        c = card('迅斩'); a.hand = [c]
        g.act_evolve(a, 0, 1, c)
        b = a.beasts[0]
        self.assertEqual((b.atk, b.hp), (3, 2))
        self.assertTrue(b.attacked)
        self.assertEqual(b.shield_total(), 1)

    def test_l3_reversion_keeps_wounds_and_can_kill(self):
        for damage in (1, 3):
            g, a, _ = fixture()
            b = Beast(1, 2, 2, 2, 2, level=2)
            a.beasts = [b, Beast(1, 1, 1, 1, 1)]
            c = card('生机'); a.hand = [c]
            g.act_evolve(a, 0, 1, c)
            b.hp -= damage
            b.l3_rounds = 1
            g.end_turn(a)
            if damage == 1:
                self.assertIs(a.beasts[0], b)
                self.assertEqual((b.level, b.hp, b.max_hp), (2, 1, 2))
            else:
                self.assertIsNone(a.beasts[0])

    def test_seal_blocks_next_turn_instead_of_expiring_at_its_start(self):
        g, a, b = fixture()
        b.turns = 1
        b.beasts[0] = Beast(1, 2, 1, 2, 2, sick=False)
        c = card('封印'); a.hand = [c]
        g.act_play(a, c)
        g.start_turn(b)
        with self.assertRaises(RuleError): g.act_attack(b, 0, ('hero',))
        g.end_turn(b)
        self.assertEqual(b.beasts[0].sealed, 0)

    def test_chain_discount_caps_and_lethal_card_goes_to_grave(self):
        g, a, b = fixture()
        a.cls, a.chain = 'archmage', 8
        c = card('洞察')
        self.assertEqual(g.card_cost(a, c), 1)
        a.chain, b.hp = 1, 1
        a.hand = [c]
        with self.assertRaises(GameOver): g.act_play(a, c)
        self.assertIn(c, a.grave)
        self.assertNotIn(c, a.hand)
        self.assertIsNone(g._effect_source)


class BattleEvents(unittest.TestCase):
    def test_ai_does_not_trust_shields_against_piercing_attack(self):
        from shuangshengwen.engine import Shield
        g, a, b = fixture()
        b.hp = 3
        b.shields = [Shield(9, 2)]
        b.beasts[0] = Beast(1, 3, 1, 3, 3)
        target = g.defense_window(b, ('hero',), 3, pierce=True)
        self.assertEqual(target, ('beast', 0))
        self.assertIsNone(g.defense_context)

    def test_spell_source_and_killed_beast_impact_are_preserved(self):
        events = []
        g, a, b = fixture(events.append)
        b.beasts[0] = Beast(3, 1, 3, 1, 1)
        g.ask = lambda p, kind, prompt, opts: 1
        c = card('奥术飞弹'); a.hand = [c]
        g.act_play(a, c)
        strike = next(e for e in events if e['kind'] == 'strike')
        impact = next(e for e in events if e['kind'] == 'impact')
        self.assertIs(strike['source'][1][1], c)
        self.assertEqual(strike['target'], ('beast', 0))
        self.assertIsNone(b.beasts[0])
        self.assertEqual(impact['amount'], 3)
        self.assertEqual(impact['entity'].hp, -2)

    def test_block_redirects_projectile_before_damage(self):
        events = []
        g, a, b = fixture(events.append)
        b.beasts[0] = Beast(1, 3, 1, 3, 3)
        g.ask = lambda p, kind, prompt, opts: 1
        g.act_attack(a, None, ('hero',))
        strike = next(e for e in events if e['kind'] == 'strike')
        self.assertEqual(strike['target'], ('beast', 0))
        self.assertEqual(b.hp, 15)

    def test_ai_trials_do_not_trigger_real_visual_callbacks(self):
        events = Mock()
        g, a, _ = fixture(events)
        c = card('迅斩'); a.hand = [c]
        g.ctrl[0]._try(g, a, ('play', 0))
        events.assert_not_called()

    def test_flight_endpoints_and_gui_handles_spell_death(self):
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        os.environ['SDL_AUDIODRIVER'] = 'dummy'
        import pygame
        from shuangshengwen.gui.app import GUI
        from shuangshengwen.gui.effects import Flight
        f = Flight((5, 6), (400, 300))
        self.assertEqual(f.position(0), (5, 6))
        self.assertAlmostEqual(f.position(1)[0], 400)
        self.assertAlmostEqual(f.position(1)[1], 300)
        gui = GUI(timer=False)
        g, a, b = fixture(gui.on_event)
        gui.game, gui.me = g, a
        gui.wait = lambda _: gui.render()
        gui.wait_overlay = lambda _, overlay: gui.render(overlay)
        c = card('魔力风暴'); a.hand = [c]
        b.beasts[0] = Beast(1, 1, 1, 1, 1)
        g.act_play(a, c)
        gui.render()
        self.assertTrue(gui.bursts)
        self.assertTrue(any(p[2].startswith('−') for p in gui.popups))
        self.assertIsNone(b.beasts[0])
        pygame.quit()
