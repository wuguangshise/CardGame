"""Check production asset coverage and exercise the actual Pygame loader.

Usage: python tools/check_art.py [--allow-incomplete]
Requires Pillow and pygame-ce.
"""
import argparse
import json
import os
from pathlib import Path
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shuangshengwen.cards import POOL, SPECIES

parser = argparse.ArgumentParser()
parser.add_argument('--allow-incomplete', action='store_true')
args = parser.parse_args()
manifest = json.loads((ROOT / 'assets/art_manifest.json').read_text())
entries = {entry['path']: entry for entry in manifest['assets']}
expected = {f'assets/cards/{card.name}.png' for card in POOL}
expected |= {f'assets/beasts/{species}.png' for species in SPECIES.values()}
expected |= {f'assets/heroes/{cls}.png' for cls in ('warrior', 'archmage', 'guardian')}
expected |= {'assets/backgrounds/battle.png', 'assets/backgrounds/title.png', 'assets/ui/card_back.png'}
expected |= {f'assets/ui/card_frame_{color}.png' for color in ('red', 'green', 'blue')}
expected |= {f'assets/fields/{color}.png' for color in ('red', 'green', 'blue')}
missing = sorted(path for path in expected if not (ROOT / path).is_file())
errors = []
for path, entry in entries.items():
    file = ROOT / path
    if not file.exists():
        if entry['status'] == 'complete':
            errors.append(f'{path}: marked complete but absent')
        continue
    with Image.open(file) as image:
        image.load()
        if image.size != tuple(entry['size']):
            errors.append(f'{path}: wrong size {image.size}')
        if entry.get('transparent'):
            if image.mode != 'RGBA' or image.getchannel('A').getextrema()[0] != 0:
                errors.append(f'{path}: no transparent pixels')
            elif not image.getchannel('A').getbbox():
                errors.append(f'{path}: empty sprite')

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import pygame
pygame.init()
pygame.display.set_mode((1, 1))
from shuangshengwen.gui import art
for path in sorted(expected - set(missing)):
    file = Path(path)
    kind, name = file.parent.name, file.stem
    loaded = art.asset(kind, name, (100, 66) if kind == 'cards' else (80, 60))
    if loaded is None:
        errors.append(f'{path}: game loader returned no image')
canvas = pygame.Surface((1010, 800), pygame.SRCALPHA)
for card in POOL:
    art.draw_card(canvas, card, (0, 0))
art.draw_card_back(canvas, pygame.Rect(150, 0, 124, 176))
for color in ('red', 'green', 'blue'):
    art.draw_field_floor(canvas, pygame.Rect(300, 0, 140, 100), color, color, 1.0)
art.draw_background(canvas, canvas.get_rect(), 'battle', 1.0)
pygame.quit()
print(f'Assets present: {len(expected) - len(missing)}/{len(expected)}')
if missing:
    print('Pending: ' + ', '.join(missing))
for error in errors:
    print('ERROR: ' + error)
if errors or (missing and not args.allow_incomplete):
    raise SystemExit(1)
print('Asset sizes, transparency, names and Pygame loading passed.')
