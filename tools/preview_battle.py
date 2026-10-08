"""Capture actual GUI event playback as an animated GIF (headless supported).

python tools/preview_battle.py --output /tmp/battle-preview.gif
"""
import argparse
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='/tmp/cardgame-battle-preview.gif')
    args = parser.parse_args()
    import pygame
    from PIL import Image
    from shuangshengwen.ai import AIController
    from shuangshengwen.cards import new_pool, starter_deck
    from shuangshengwen.engine import Beast, Game
    from shuangshengwen.gui import art
    from shuangshengwen.gui.app import GUI

    gui = GUI(timer=False)
    # Use an available CJK font on Linux; the game still uses system fonts normally.
    fontpath = os.environ.get('CARDGAME_PREVIEW_FONT')
    if fontpath:
        for size in range(8, 100):
            for bold in (False, True):
                art._fonts[(size, bold)] = pygame.font.Font(fontpath, size)
    game = Game(('林皇', '赭祭'), (AIController(seed=3), AIController(seed=4)), seed=2,
                classes=('warrior', 'guardian'), log=gui.on_log, events=gui.on_event)
    gui.game, gui.me = game, game.players[0]
    a, b = game.players
    a.cls, b.cls = 'warrior', 'guardian'
    a.turns = b.turns = 3
    a.deck, b.deck = starter_deck('warrior'), starter_deck('guardian')
    a.hand, b.hand = new_pool()[:4], new_pool()[:4]
    a.beasts = [Beast(2, 2, 2, 2, 2, sick=False), Beast(1, 1, 1, 1, 1, sick=False)]
    b.beasts = [Beast(3, 1, 3, 1, 1, sick=False), None]
    frames = []
    durations = []
    last_frame = time.monotonic()
    original_render = gui.render
    def capture(overlay=None):
        nonlocal last_frame
        now = time.monotonic()
        durations.append(max(10, round((now-last_frame)*1000)))
        last_frame = now
        original_render(overlay)
        raw = pygame.image.tobytes(gui.screen, 'RGB')
        img = Image.frombytes('RGB', gui.screen.get_size(), raw).resize((768, 480))
        frames.append(img)
    gui.render = capture
    gui.clock = pygame.time.Clock()
    def get(name): return next(c for c in new_pool() if c.name == name)
    gui.wait(.25)
    c = get('奥术飞弹'); a.hand.append(c)
    game.ask = lambda p, kind, prompt, opts: 1 if kind == 'target_damage' else 0
    game.act_play(a, c)  # Includes the impact of a beast that dies.
    gui.wait(.35)
    game.ask = lambda p, kind, prompt, opts: 0
    c = get('燃魂'); a.hand.append(c)
    game.act_play(a, c)
    gui.wait(.35)
    game.act_attack(a, 0, ('hero',))
    gui.wait(.35)
    c = get('青藤'); a.hand.append(c)
    game.act_evolve(a, 0, 1, c)
    gui.wait(.35)
    a.beasts[1] = Beast(1, 1, 1, 1, 1)
    c = get('迅斩'); a.hand.append(c)
    game.act_evolve(a, 0, 1, c)
    gui.wait(.8)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    # Share one palette so unchanged background pixels compress across frames.
    atlas = Image.new('RGB', (160*8, 100))
    for index in range(8):
        atlas.paste(frames[min(len(frames)-1, index*(len(frames)-1)//7)].resize((160, 100)), (index*160, 0))
    palette = atlas.quantize(colors=128)
    indexed = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
    indexed[0].save(args.output, save_all=True, append_images=indexed[1:], duration=durations, loop=0, optimize=True)
    print(f'{args.output}: {len(frames)} frames')
    # Export key frames for inspection without needing GIF playback.
    for n, fraction in enumerate((.22, .47, .9)):
        frames[min(len(frames)-1, int(len(frames)*fraction))].save(str(Path(args.output).with_suffix(''))+f'-{n}.png')
    pygame.quit()


if __name__ == '__main__':
    main()
