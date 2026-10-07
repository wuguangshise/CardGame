"""Normalize generated images for the game's existing asset interfaces."""
import argparse
from pathlib import Path
from PIL import Image, ImageOps

parser = argparse.ArgumentParser()
parser.add_argument('source')
parser.add_argument('destination')
parser.add_argument('width', type=int)
parser.add_argument('height', type=int)
parser.add_argument('--transparent', action='store_true')
args = parser.parse_args()
image = Image.open(args.source).convert('RGBA')
size = (args.width, args.height)
if args.transparent:
    alpha = image.getchannel('A')
    if alpha.getextrema()[0] == 255:
        raise SystemExit('Expected actual transparent pixels')
    box = alpha.getbbox()
    if not box:
        raise SystemExit('Empty sprite')
    image = image.crop(box)
    fitted = ImageOps.contain(image, (int(size[0]*.90), int(size[1]*.90)), Image.Resampling.LANCZOS)
    image = Image.new('RGBA', size)
    image.alpha_composite(fitted, ((size[0]-fitted.width)//2, (size[1]-fitted.height)//2))
else:
    image = ImageOps.fit(image, size, Image.Resampling.LANCZOS)
destination = Path(args.destination)
destination.parent.mkdir(parents=True, exist_ok=True)
image.save(destination, optimize=True)
print(f'{destination}: {image.size}, alpha={image.getchannel("A").getextrema()}')
