#!/usr/bin/env python3
"""
Builds raw/similarity/glyph-neighbors.json: for each shipped kanji, the kanji
whose rendered glyph looks most alike, closest first, in two groups:

  nearest           shipped kanji (top KEEP)
  nearest_unshipped other kanji from raw/structure-info/kanjidict.txt
                    (top KEEP_UNSHIPPED, distance <= MAX_UNSHIPPED_DIST)

Not part of generate.sh. Unlike the rest of src/, it needs third-party
packages and a font, so its output is committed and build_similar_kanji.py
reads it like any other raw file. Rerun it when the shipped kanji set changes
(build_similar_kanji.py fails if a shipped kanji is missing from the file).

Needs: numpy, scipy, pillow, and Noto Sans JP (SIL Open Font License):

  curl -L -o NotoSansJP.ttf \
    "https://github.com/google/fonts/raw/main/ofl/notosansjp/NotoSansJP%5Bwght%5D.ttf"
  python3 src/build_glyph_neighbors.py NotoSansJP.ttf

Method: render every kanji at the same size and position (Regular weight,
GRID px), then compare the ink of each pair with a chamfer distance: the mean
distance, in px, from each ink pixel of one glyph to the nearest ink pixel of
the other. The larger of the two directions is kept, so both glyphs must
cover each other (a kanji isn't "close" to one that merely contains it).
This catches whole-shape lookalikes that a component-based measure such as
dkanjistat misses (午 牛, 人 入, 未 末, 土 士, 鳥 島 烏).

Kanji the font has no glyph for are skipped (unshipped) or stop the build
(shipped).

Run from the project root.
"""

import sys
import unicodedata

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

import sources

FILTERED_KANJI_PATH = "intermediate/filtered_kanji.json"
KANJIDICT_PATH = "raw/structure-info/kanjidict.txt"
OUT_PATH = "raw/similarity/glyph-neighbors.json"

GRID = 64  # render size in px
FONT_SIZE = int(GRID * 0.9)
INK_THRESHOLD = 100  # 0-255 grey level that counts as ink
KEEP = 50  # shipped neighbors stored per kanji
KEEP_UNSHIPPED = 10  # unshipped neighbors stored per kanji
MAX_UNSHIPPED_DIST = 0.6  # loose on purpose; build_similar_kanji.py gates tighter
NOT_A_CHARACTER = "\U000f0000"  # private use: renders the font's missing-glyph box


def render(kanji, font):
    image = Image.new("L", (GRID, GRID), 0)
    ImageDraw.Draw(image).text((GRID / 2, GRID / 2), kanji, fill=255, font=font, anchor="mm")
    return np.asarray(image) > INK_THRESHOLD


def unshipped_kanjis(shipped):
    """kanjidict.txt kanji (NFKC-normalized, first-seen order) not shipped."""
    seen = set(shipped)
    result = []
    with open(sources.resolve_path(KANJIDICT_PATH), encoding="utf-8") as f:
        for line in f:
            kanji = unicodedata.normalize("NFKC", line.split("\t")[0])
            if kanji and kanji not in seen:
                seen.add(kanji)
                result.append(kanji)
    return result


def chamfer(ink_a, to_ink_a, ink_b, to_ink_b):
    """[a, b] = max of the two directed mean chamfer distances."""
    a_to_b = (ink_a @ to_ink_b.T) / ink_a.sum(axis=1, keepdims=True)
    b_to_a = (ink_b @ to_ink_a.T) / ink_b.sum(axis=1, keepdims=True)
    return np.maximum(a_to_b, b_to_a.T)


def features(glyphs):
    ink = np.stack([g.ravel() for g in glyphs]).astype(np.float32)
    # Distance from every pixel to the nearest ink pixel of each glyph.
    to_ink = np.stack([ndimage.distance_transform_edt(~g).ravel() for g in glyphs]).astype(np.float32)
    return ink, to_ink


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: python3 src/build_glyph_neighbors.py <NotoSansJP.ttf>")
    font = ImageFont.truetype(sys.argv[1], FONT_SIZE)
    font.set_variation_by_name("Regular")
    missing_box = render(NOT_A_CHARACTER, font)

    def has_glyph(glyph):
        return glyph.any() and not np.array_equal(glyph, missing_box)

    shipped = sources.load_json(FILTERED_KANJI_PATH)
    shipped_glyphs = [render(kanji, font) for kanji in shipped]
    missing = [k for k, g in zip(shipped, shipped_glyphs) if not has_glyph(g)]
    if missing:
        sys.exit(f"Font has no glyph for shipped kanji: {''.join(missing)}")

    others, other_glyphs = [], []
    for kanji in unshipped_kanjis(shipped):
        glyph = render(kanji, font)
        if has_glyph(glyph):
            others.append(kanji)
            other_glyphs.append(glyph)
    print(f"Rendered {len(shipped)} shipped and {len(others)} unshipped kanji")

    ink, to_ink = features(shipped_glyphs)
    other_ink, other_to_ink = features(other_glyphs)
    dist = chamfer(ink, to_ink, ink, to_ink)
    np.fill_diagonal(dist, np.inf)
    other_dist = chamfer(ink, to_ink, other_ink, other_to_ink)

    nearest, nearest_unshipped = {}, {}
    for i, kanji in enumerate(shipped):
        order = np.argsort(dist[i], kind="stable")[:KEEP]
        nearest[kanji] = {shipped[j]: round(float(dist[i, j]), 3) for j in order}
        order = np.argsort(other_dist[i], kind="stable")[:KEEP_UNSHIPPED]
        close = {
            others[j]: round(float(other_dist[i, j]), 3)
            for j in order
            if other_dist[i, j] <= MAX_UNSHIPPED_DIST
        }
        if close:
            nearest_unshipped[kanji] = close

    data = {
        "title": "Glyph chamfer distance between kanji",
        "description": (
            f"Built by src/build_glyph_neighbors.py from Noto Sans JP Regular at {GRID}px. "
            "Value: max of the two directed mean chamfer distances in px (lower = more alike). "
            f"nearest: top {KEEP} shipped neighbors per shipped kanji. "
            f"nearest_unshipped: top {KEEP_UNSHIPPED} other kanjidict.txt kanji within "
            f"{MAX_UNSHIPPED_DIST} px. Closest first."
        ),
        "nearest": nearest,
        "nearest_unshipped": nearest_unshipped,
    }
    sources.write_json(OUT_PATH, data, separators=(",", ":"))
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
