#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Stack the same crop from several screenshots, labelled, for comparison.

    dev/montage.py OUT.png X Y W H IMAGE...  [--cols N]

Each IMAGE is cropped to the box (X, Y, W, H) and labelled with its file name.
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

parser = argparse.ArgumentParser()
parser.add_argument("out")
parser.add_argument("box", nargs=4, type=int)
parser.add_argument("images", nargs="+")
parser.add_argument("--cols", type=int, default=1)
args = parser.parse_args()

x, y, w, h = args.box
label_h = 22
cols = args.cols
rows = -(-len(args.images) // cols)
sheet = Image.new("RGB", (cols * (w + 8), rows * (h + label_h + 8)), (60, 60, 60))
draw = ImageDraw.Draw(sheet)
for i, path in enumerate(args.images):
    cx, cy = (i % cols) * (w + 8), (i // cols) * (h + label_h + 8)
    tile = Image.open(path).convert("RGB").crop((x, y, x + w, y + h))
    draw.text((cx + 4, cy + 4), Path(path).stem, fill=(255, 255, 255))
    sheet.paste(tile, (cx, cy + label_h))
sheet.save(args.out)
print(args.out)
