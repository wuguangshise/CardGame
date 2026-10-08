"""Regression checks for sacrifice/evolution and its real GUI entry points."""
import os
import unittest
from unittest.mock import Mock

from shuangshengwen.ai import AIController
from shuangshengwen.cards import POOL
from shuangshengwen.engine import Beast, Game, RuleError


def fixture():
    game = Game(('A', 'B'), (AIController(), AIController()), seed=4, log=lambda *a: None,
                classes=('warrior', 'guardian'))
    player = game.players[0]
    player.beasts = [Beast(1, 2, 1, 2, 2), Beast(2, 2, 2, 2, 2)]
    player.hand = [next(c for c in POOL if c.name == '重锤')]
    player.power = 0
    player.turns = 2
    return game, player, player.hand[0]


class EvolutionRules(unittest.TestCase):
    def test_level_two_is_free_and_consumes_material(self):
        game, player, card = fixture()
        survivor = player.beasts[0]
        self.assertEqual(game.evolution_cost(player, 0, 1, card), 0)
        game.act_evolve(player, 0, 1, card)
        self.assertIs(player.beasts[0], survivor)
        self.assertEqual((survivor.level, survivor.atk, survivor.hp), (2, 3, 3))
        self.assertIsNone(player.beasts[1])
        self.assertNotIn(card, player.hand)
        self.assertIn(card, player.grave)
        self.assertEqual(player.power, 0)

    def test_level_three_pays_original_price_and_keeps_snapshot(self):
        game, player, card = fixture()
        player.beasts[0].level = 2
        player.power = 5
        game.act_evolve(player, 0, 1, card)
        self.assertEqual(player.beasts[0].level, 3)
        self.assertEqual(player.power, 5 - card.cost)
        self.assertIsNotNone(player.beasts[0].l2_snapshot)
        self.assertEqual(player.beasts[0].l3_rounds, 2)

    def test_failures_never_change_hand_order_or_resources(self):
        for scenario in ('poor', 'material_level', 'same_slot', 'missing', 'max_level', 'index'):
            with self.subTest(scenario=scenario):
                game, player, card = fixture()
                player.hand.append(next(c for c in POOL if c.name == '薄盾'))
                target, material = 0, 1
                if scenario == 'poor': player.beasts[0].level = 2
                if scenario == 'material_level': player.beasts[1].level = 2
                if scenario == 'same_slot': material = 0
                if scenario == 'missing': player.beasts[1] = None
                if scenario == 'max_level': player.beasts[0].level = 3
                if scenario == 'index': material = -1
                hand, beasts, grave, power = list(player.hand), list(player.beasts), list(player.grave), player.power
                with self.assertRaises(RuleError): game.act_evolve(player, target, material, card)
                self.assertEqual(player.hand, hand)
                self.assertEqual(player.beasts, beasts)
                self.assertEqual(player.grave, grave)
                self.assertEqual(player.power, power)


class EvolutionGUI(unittest.TestCase):
    def setUp(self):
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        os.environ['SDL_AUDIODRIVER'] = 'dummy'
        try:
            import pygame
        except ImportError:
            self.skipTest('pygame not installed')
        from shuangshengwen.gui.app import GUI
        self.gui = GUI(seed=4, timer=False, animations=False)
        self.game, self.player, self.card = fixture()
        self.gui.game, self.gui.me = self.game, self.player
        self.gui.modal = Mock(return_value=0)

    def tearDown(self):
        import pygame
        pygame.quit()

    def test_card_drag_confirms_evolution(self):
        self.gui.drop_card(self.card, self.gui.slot_rects[('me', 'beast', 0)].center)
        self.assertEqual(self.player.beasts[0].level, 2)
        self.assertIn('献祭', self.gui.modal.call_args.args[0])

    def test_cancel_keeps_everything(self):
        self.gui.modal.return_value = 1
        self.gui.drop_card(self.card, self.gui.slot_rects[('me', 'beast', 0)].center)
        self.assertEqual(self.player.beasts[0].level, 1)
        self.assertIsNotNone(self.player.beasts[1])
        self.assertIn(self.card, self.player.hand)

    def test_material_drag_preserves_destination(self):
        survivor = self.player.beasts[1]
        self.gui.drag = ('attack', 0)
        self.gui.release(self.gui.slot_rects[('me', 'beast', 1)].center)
        self.assertIs(self.player.beasts[1], survivor)
        self.assertEqual(survivor.level, 2)
        self.assertIsNone(self.player.beasts[0])

    def test_upgrade_button_and_right_click(self):
        for entry in ('button', 'right_click'):
            with self.subTest(entry=entry):
                game, player, card = fixture()
                self.gui.game, self.gui.me = game, player
                self.gui.render()
                self.gui.modal.reset_mock()
                if entry == 'button': self.gui.press(self.gui.evolve_buttons[0].center)
                else: self.gui.right_click(self.gui.slot_rects[('me', 'beast', 0)].center)
                self.assertEqual(player.beasts[0].level, 2)
                self.assertEqual(self.gui.modal.call_count, 2)

    def test_no_material_explains_without_consuming(self):
        self.player.beasts[1] = None
        self.gui.act(self.gui.choose_evolution, 0)
        self.assertIn('另一只1级纹兽', self.gui.toast[0])
        self.assertIn(self.card, self.player.hand)
        self.gui.modal.assert_not_called()

    def test_choose_card_cancel(self):
        self.gui.modal.return_value = len(self.player.hand)
        self.gui.choose_evolution(0)
        self.assertEqual(self.player.beasts[0].level, 1)
        self.assertIsNotNone(self.player.beasts[1])

    def test_modal_card_cancel_button_and_escape(self):
        import pygame
        from shuangshengwen.gui.app import GUI
        # Queue the cancel click after the first modal frame creates its buttons.
        self.gui.modal = GUI.modal.__get__(self.gui)
        pygame.event.clear()
        self.gui.clock = Mock()
        self.gui.clock.tick.side_effect = lambda _: pygame.event.post(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(640, 480)))
        self.assertEqual(self.gui.modal('Choose', ['Card', '取消'], cards=[self.card]), 1)
        pygame.event.clear()
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        self.assertEqual(self.gui.modal('Confirm', ['升级', '取消']), 1)
