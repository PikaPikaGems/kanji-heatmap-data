#!/usr/bin/env python3
"""
Builds output/similar-kanjis.json: for each shipped kanji, the visually most
similar shipped kanji, ordered most-similar first (max 10 each).

Similarity is "shares the same conspicuous components, in the same place":

  1. Component set per kanji comes from yagays' radical-level decomposition
     (raw/structure-info/yagays/.../kanji2radical.json) — the human-perceived
     2-3 part split (時 -> 日, 寺), NOT a primitive explosion (寸 土 日). The
     ~70 kanji it lacks fall back to raw/kanji_components.txt. Radical-variant
     glyphs are normalised so the two sources line up (⺡ -> 氵 etc.).

  2. Components are IDF-weighted over the shipped set, so sharing a rare,
     distinctive component (寺 in 時/詩/持/待/特) counts far more than sharing a
     ubiquitous one (日, 口, 木). This is the main quality lever over a plain
     shared-count metric.

  3. Score is a weighted cosine of the two component vectors, with a bonus when
     a shared component sits in the same left/right or top/bottom slot
     (yagays' positional files) — so 時 and 詩 (寺 on the right) rank above a
     kanji that merely contains 寺 elsewhere.

Only kanji in input/filtered_kanji.json are considered, as targets and as
candidates. Iteration is sorted so the output is deterministic.

Run from the project root: python3 src/build_similar_kanjis.py
"""

import json
import math
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(__file__))

from sources import resolve_path

FILTERED_KANJI_PATH = "input/filtered_kanji.json"
COMPONENTS_PATH = "raw/kanji_components.txt"
YAGAYS = "raw/structure-info/yagays/kanji2composition"
RADICAL_PATH = f"{YAGAYS}/kanji2radical.json"
LEFT_RIGHT_PATH = f"{YAGAYS}/kanji2radical_left_right.json"
TOP_BOTTOM_PATH = f"{YAGAYS}/kanji2radical_top_buttom.json"
OUT_PATH = "output/similar-kanjis.json"

# Single strokes carry no visual identity; drop them so they neither match nor
# inflate the vector norm. (IDF already down-weights them; this is belt-and-braces.)
TRIVIAL_COMPONENTS = set("一丨丿丶乙亅丷")

# Map radical-variant glyphs to one canonical form so the yagays decomposition
# and the kanji_components.txt fallback share a vocabulary.
VARIANT_NORMALIZE = {
    "⺡": "氵", "⺘": "扌", "⺅": "亻", "⺾": "艹", "艸": "艹", "⻌": "辶",
    "⻍": "辶", "⻎": "辶", "⺋": "乚", "⺉": "刂", "⺨": "犭", "⻏": "阝",
    "⻖": "阝", "⺬": "示", "⺮": "竹", "⺳": "罒", "⺺": "聿", "訁": "言",
    "飠": "食", "糹": "糸", "釒": "金", "⻊": "足",
    # radical-supplement forms that look identical to a kanji/component but use a
    # different codepoint — fold them in so e.g. 録/緑 (⺕) match and 受/愛 (⺤) match.
    "⺕": "彐", "⺤": "爪", "⺗": "心", "⺌": "⺌", "⺍": "⺌", "⺦": "丬",
}

MAX_TOTAL = 10
MIN_SCORE = 0.35
SAME_POSITION_BONUS = 0.5


def _normalize(chars):
    return [VARIANT_NORMALIZE.get(c, c) for c in chars]


def load_components_txt(path):
    result = {}
    with open(resolve_path(path), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or ";" not in line:
                continue
            kanji, parts_str = line.split(";", 1)
            result[kanji] = list(parts_str)
    return result


def load_positions(target_kanjis):
    """kanji -> {component: 'L'|'R'|'T'|'B'} from the yagays positional files."""
    with open(resolve_path(LEFT_RIGHT_PATH), encoding="utf-8") as f:
        left_right = json.load(f)
    with open(resolve_path(TOP_BOTTOM_PATH), encoding="utf-8") as f:
        top_bottom = json.load(f)

    positions = {}
    for kanji in target_kanjis:
        slot = {}
        lr = left_right.get(kanji)
        if lr and len(lr) == 2:
            left, right = _normalize(lr)
            slot[left], slot[right] = "L", "R"
        tb = top_bottom.get(kanji)
        if tb and len(tb) == 2:
            top, bottom = _normalize(tb)
            slot[top], slot[bottom] = "T", "B"
        positions[kanji] = slot
    return positions


def load_component_sets(target_kanjis):
    """kanji -> canonical component set (yagays radical, else components.txt)."""
    with open(resolve_path(RADICAL_PATH), encoding="utf-8") as f:
        radical = json.load(f)
    fallback = load_components_txt(COMPONENTS_PATH)

    sets = {}
    for kanji in target_kanjis:
        raw = radical.get(kanji) or fallback.get(kanji) or [kanji]
        # Include the kanji itself as a component: when it appears whole inside
        # another kanji's decomposition (寺 in 時/詩/持, 化 in 花/貨), that shared
        # whole-kanji component (rare → high IDF) makes them rank as similar.
        sets[kanji] = (set(_normalize(raw)) - TRIVIAL_COMPONENTS) | {kanji}
    return sets


def build_similar_kanjis(target_kanjis, component_sets, positions):
    # IDF over the shipped set: rare components weigh more.
    doc_freq = defaultdict(int)
    for parts in component_sets.values():
        for component in parts:
            doc_freq[component] += 1
    total = len(target_kanjis)
    weight = {c: math.log(total / df) for c, df in doc_freq.items()}

    # Squared vector norm per kanji (denominator of the cosine). The kanji's own
    # self-component is excluded here: it lets a containing kanji match (寺→時) via
    # the numerator, but counting its high IDF in the norm would otherwise inflate
    # the denominator and drop a kanji's ordinary radical matches (花→華/芳/苗).
    norm_sq = {
        k: sum(weight[c] ** 2 for c in parts if c != k) or 1e-9
        for k, parts in component_sets.items()
    }

    component_to_kanjis = defaultdict(set)
    for kanji, parts in component_sets.items():
        for component in parts:
            component_to_kanjis[component].add(kanji)

    def score(a, b):
        shared = component_sets[a] & component_sets[b]
        if not shared:
            return 0.0
        pos_a, pos_b = positions[a], positions[b]
        numerator = 0.0
        for c in shared:
            same_slot = pos_a.get(c) is not None and pos_a.get(c) == pos_b.get(c)
            numerator += weight[c] ** 2 * (1 + SAME_POSITION_BONUS * same_slot)
        return numerator / math.sqrt(norm_sq[a] * norm_sq[b])

    result = {}
    for kanji in sorted(target_kanjis):
        candidates = set()
        for component in component_sets[kanji]:
            candidates |= component_to_kanjis[component]
        candidates.discard(kanji)

        scored = [(score(kanji, other), other) for other in candidates]
        scored = [(s, o) for s, o in scored if s >= MIN_SCORE]
        scored.sort(key=lambda so: (-so[0], so[1]))
        result[kanji] = [o for _, o in scored[:MAX_TOTAL]]

    return result, weight


def main():
    with open(resolve_path(FILTERED_KANJI_PATH), encoding="utf-8") as f:
        target_kanjis = set(json.load(f))
    print(f"Loaded {len(target_kanjis)} target kanji")

    component_sets = load_component_sets(target_kanjis)
    positions = load_positions(target_kanjis)
    positioned = sum(1 for k in target_kanjis if positions[k])
    print(f"Component sets for {len(component_sets)} kanji; "
          f"{positioned} have positional (L/R or T/B) data")

    similar, weight = build_similar_kanjis(target_kanjis, component_sets, positions)

    with open(resolve_path(OUT_PATH), mode="w", encoding="utf-8") as f:
        json.dump(similar, f, ensure_ascii=False, separators=(",", ":"))
    print(f"Wrote {OUT_PATH}")

    # --- Statistics ---
    counts = [len(v) for v in similar.values()]
    no_similar = sum(1 for c in counts if c == 0)
    print()
    print("Similar count distribution")
    for lo, hi in [(0, 0), (1, 3), (4, 6), (7, 9), (10, 10)]:
        n = sum(1 for c in counts if lo <= c <= hi)
        print(f"  {f'{lo}-{hi}':>8}  {n:>5} kanji")
    print()
    print(f"  No similar:  {no_similar}")
    print(f"  Mean:        {sum(counts) / len(counts):.1f}")
    print(f"  Max:         {max(counts)}")

    comp_freq = Counter(c for parts in component_sets.values() for c in parts)
    print("\nTop 10 most common components (down-weighted by IDF):")
    for comp, freq in comp_freq.most_common(10):
        print(f"  {comp}  {freq} kanji  (weight {weight[comp]:.2f})")

    examples = ["時", "績", "晴", "微", "末", "牛", "持"]
    print("\nExamples:")
    for kanji in examples:
        if kanji not in similar:
            continue
        parts = "".join(sorted(component_sets[kanji]))
        matches = "  ".join(similar[kanji])
        print(f"  {kanji} [{parts}] -> {matches}")


if __name__ == "__main__":
    main()
