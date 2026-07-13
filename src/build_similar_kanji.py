#!/usr/bin/env python3
"""
Builds output/similar-kanjis.json: for each shipped kanji, the most similar
shipped kanji, ordered most-similar first (at most 10 each; lists may be shorter).

Two data sources, covering two disjoint groups of shipped kanji:

  1. ~2134 shipped kanji covered by raw/similarity/dkanjistat.json (Kanjistat
     hierarchical optimal-transport distance over KanjiVG structure; see
     Schuhmacher 2023 / kanjidist-visualiser). Lower distance = more similar.
     Neighbors are kept only when distance <= MAX_DIST and the stroke-count
     gap is <= MAX_STROKE_DELTA, then sorted closest-first and capped at
     MAX_TOTAL. Lists are not padded -- many pivots end up with fewer than 10.

     This replaced the earlier Yencken jouyou CSV merge (stroke-edit-distance
     + Yeh & Li radical overlap via RRF). That merge missed lookalikes that
     fell outside each source's asymmetric top-10 (e.g. 投 missed 役; 寺 saw
     侍 but not 待/特/持/時) and let Yeh radical overlap invent absurd pairs
     for simple kanji (三→霊/震/塗/零, 二→雷). Against flashcards.csv the
     dkanjistat gates land within a few points of the old RRF recall while
     fixing those quality failures. The Yencken CSVs remain under
     raw/similarity/ for reference.

  2. The remaining ~292 shipped kanji absent from dkanjistat fall back to
     raw/structure-info/kanjidict.txt: kanji sharing the exact same phonetic
     component when the kanji has one recorded (a tight, high-quality signal
     -- e.g. 阪 -> 板,飯,坂,反,販,版), else other SHIPPED kanji sharing the
     same radical + IDS structural shape (⿰/⿱/⿳/...), ordered by closest
     stroke count since that tier has no similarity score to rank by.

     The phonetic tier is the one case where a non-shipped kanji can appear in
     the output (e.g. 佑 -> 祐, 伽 -> 珈/迦/駕): an exact shared phonetic
     component is precise enough to be worth surfacing even if that kanji
     isn't part of the shipped set -- the app has a separate keyword fallback
     for unshipped kanji referenced elsewhere, so it's fine for these to point
     outside the 2426. The radical+shape tier stays shipped-only: it's already
     the coarser signal without a phonetic anchor, and opening its much larger
     candidate pool to the full kanjidict universe mostly adds noise rather
     than genuine lookalikes (checked: e.g. 伊 would pick up 什/仂/仆/仇... --
     same radical, not real lookalikes).

Run from the project root: python3 src/build_similar_kanji.py
"""

import unicodedata
from collections import defaultdict

import sources

SIMILARITY_DIR = "raw/similarity"
DKANJISTAT_PATH = f"{SIMILARITY_DIR}/dkanjistat.json"
KANJIDICT_PATH = "raw/structure-info/kanjidict.txt"
FILTERED_KANJI_PATH = "input/filtered_kanji.json"
OUT_PATH = "output/similar-kanjis.json"

MAX_DIST = 0.15  # dkanjistat distance ceiling; lists are not padded below this
MAX_STROKE_DELTA = 4  # reject neighbors whose stroke counts differ by more than this
MAX_TOTAL = 10  # hard cap -- many pivots have fewer survivors after the gates


def dkanjistat_neighbors(pivots, nearest, kanjidict, filtered):
    """Rank shipped neighbors from dkanjistat by ascending distance.

    A neighbor must be shipped, within MAX_DIST, and within MAX_STROKE_DELTA
    stroke counts of the pivot. Stroke counts come from kanjidict.txt; if
    either side is missing a stroke count the stroke gate is skipped for that
    pair (distance still applies).
    """
    result = {}
    for pivot in pivots:
        strokes_pivot = kanjidict[pivot][3] if pivot in kanjidict else None
        candidates = []
        for neighbor, dist in nearest.get(pivot, {}).items():
            if neighbor not in filtered or neighbor == pivot or dist > MAX_DIST:
                continue
            if strokes_pivot is not None and neighbor in kanjidict:
                strokes_nbr = kanjidict[neighbor][3]
                if abs(strokes_nbr - strokes_pivot) > MAX_STROKE_DELTA:
                    continue
            candidates.append((neighbor, dist))
        candidates.sort(key=lambda pair: (pair[1], pair[0]))
        result[pivot] = [kanji for kanji, _ in candidates[:MAX_TOTAL]]
    return result


def parse_kanjidict(path):
    """kanji -> (radical, phonetic_component, ids_shape, stroke_count).

    kanjidict.txt is kanjium's tab-separated kanji dictionary (see
    raw/structure-info/SOURCES.md). Column indices below are fixed by that
    file's format: 1 radical, 3 phonetic component (blank when the kanji isn't
    a phono-semantic compound), 4 IDS structural shape, 11 stroke count.

    70 kanji appear twice in the raw file under two different codepoints: a
    standard CJK Unified Ideograph and a legacy CJK Compatibility Ideograph
    that renders identically (e.g. 祐 as both U+7950 and U+FA4F). NFKC-
    normalizing every CJK field collapses each pair into one dict entry, so a
    phonetic-component group can't end up listing the same-looking kanji twice.
    """
    info = {}
    with open(sources.resolve_path(path), encoding="utf-8") as f:
        for line in f:
            fields = line.rstrip("\n").split("\t")
            if not fields or not fields[0]:
                continue
            kanji = unicodedata.normalize("NFKC", fields[0])
            radical = unicodedata.normalize("NFKC", fields[1])
            phonetic = unicodedata.normalize("NFKC", fields[3])
            info[kanji] = (radical, phonetic, fields[4], int(fields[11]))
    return info


def kanjidict_fallback(target_kanjis, kanjidict, filtered):
    """Similarity fallback for shipped kanji absent from dkanjistat.

    Tier 1: kanji anywhere in kanjidict.txt (shipped or not) sharing the exact
    phonetic component -- tight and high-quality enough that an unshipped
    match is still worth surfacing. Tier 2, used only when the kanji has no
    recorded phonetic component (or no kanji shares it): other SHIPPED kanji
    with the same radical + same IDS structural shape, ordered by closest
    stroke count -- the simplest available tie-break, since this tier has no
    similarity score to rank by. Tier 2 is deliberately kept shipped-only:
    without a phonetic anchor it's already the coarser signal, and its much
    larger candidate pool mostly adds noise, not matches, once opened up to
    every kanji in kanjidict.txt.
    """
    phonetic_index = defaultdict(list)  # full kanjidict.txt universe
    for kanji, (radical, phonetic, shape, _) in kanjidict.items():
        if phonetic:
            phonetic_index[phonetic].append(kanji)

    radical_shape_index = defaultdict(list)  # shipped kanji only
    for kanji in filtered:
        entry = kanjidict.get(kanji)
        if not entry:
            continue
        radical, phonetic, shape, _ = entry
        radical_shape_index[(radical, shape)].append(kanji)

    result = {}
    for kanji in target_kanjis:
        entry = kanjidict.get(kanji)
        if not entry:
            result[kanji] = []
            continue
        radical, phonetic, shape, strokes = entry

        group = phonetic_index.get(phonetic, []) if phonetic else []
        if not group:
            group = radical_shape_index.get((radical, shape), [])

        candidates = [k for k in group if k != kanji]
        candidates.sort(key=lambda k: (abs(kanjidict[k][3] - strokes), k))
        result[kanji] = candidates[:MAX_TOTAL]
    return result


def main():
    filtered = set(sources.load_json(FILTERED_KANJI_PATH))
    print(f"Loaded {len(filtered)} shipped kanji")

    nearest = sources.load_json(DKANJISTAT_PATH)["nearest"]
    kanjidict = parse_kanjidict(KANJIDICT_PATH)

    dkanji_pivots = sorted(k for k in filtered if k in nearest)
    print(f"{len(dkanji_pivots)} kanji have dkanjistat neighbors")

    similar = dkanjistat_neighbors(dkanji_pivots, nearest, kanjidict, filtered)

    gap = sorted(filtered - set(nearest))
    print(f"{len(gap)} kanji fall back to the kanjidict.txt radical/phonetic heuristic")
    similar.update(kanjidict_fallback(gap, kanjidict, filtered))

    similar = {kanji: similar.get(kanji, []) for kanji in sorted(filtered)}

    sources.write_json(OUT_PATH, similar, separators=(",", ":"))
    print(f"Wrote {OUT_PATH}")

    # --- Statistics ---
    counts = [len(v) for v in similar.values()]
    print()
    print("Similar count distribution")
    for lo, hi in [(0, 0), (1, 3), (4, 6), (7, 9), (10, 10)]:
        n = sum(1 for c in counts if lo <= c <= hi)
        print(f"  {f'{lo}-{hi}':>8}  {n:>5} kanji")
    print(f"\n  No similar:  {sum(1 for c in counts if c == 0)}")
    print(f"  Mean:        {sum(counts) / len(counts):.1f}")
    print(f"  Max:         {max(counts)}")

    examples = ["投", "寺", "三", "二", "訳", "時", "阪", "誰", "頃", "岡", "一"]
    print("\nExamples:")
    for kanji in examples:
        if kanji in similar:
            print(f"  {kanji} -> {'  '.join(similar[kanji])}")


if __name__ == "__main__":
    main()
