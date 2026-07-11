#!/usr/bin/env python3
"""
Builds output/similar-kanjis.json: for each shipped kanji, the most similar
shipped kanji, ordered most-similar first (max 10 each).

Two data sources, covering two disjoint groups of shipped kanji:

  1. The 1945 jouyou kanji (raw/similarity/*.csv, from Lars Yencken's kanji-
     confusion dataset) already have two independent, precomputed top-10
     neighbor lists:
       - stroke-edit-distance  (shape / stroke-count similarity)
       - Yeh & Li radical overlap  (shared-component similarity)
     These measure different kinds of confusability: on average only ~2 of a
     kanji's top-10 stroke-distance neighbors also show up in its top-10
     radical neighbors. Checked against raw/similarity/flashcards.csv (284
     human-curated confusable pairs), stroke-distance alone catches ~51% of
     the known pairs, radical alone ~35%, the two merged ~54-58% -- so both
     are used. They're combined by reciprocal rank fusion (RRF) rather than
     by raw score: the two files' scores aren't on a comparable scale
     (stroke-distance runs much higher throughout), so sorting by raw score
     just lets stroke-distance crowd out radical matches. RRF compares RANK
     within each source instead, which tested best-or-tied against the
     flashcards ground truth at every cutoff tried.

  2. The remaining ~480 shipped kanji (jinmeiyo / rarer kanji outside jouyou)
     have no Yencken data at all. For these, raw/structure-info/kanjidict.txt
     gives a simple fallback: kanji sharing the exact same phonetic component
     when the kanji has one recorded (a tight, high-quality signal -- e.g.
     阪 -> 板,飯,坂,反,販,版), else other SHIPPED kanji sharing the same radical
     + IDS structural shape (⿰/⿱/⿳/...), ordered by closest stroke count since
     that tier has no similarity score to rank by.

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

MIN_SCORE (per-source floor before merging) and MAX_TOTAL (hard cap) mirror
the old (deleted) component-cosine algorithm's cutoffs, for continuity.

Run from the project root: python3 src/build_similar_kanji.py
"""

import unicodedata
from collections import defaultdict

import sources

SIMILARITY_DIR = "raw/similarity"
STROKE_EDIT_DISTANCE_PATH = f"{SIMILARITY_DIR}/jyouyou__strokeEditDistance.csv"
YEH_LI_RADICAL_PATH = f"{SIMILARITY_DIR}/jyouyou__yehAndLiRadical.csv"
KANJIDICT_PATH = "raw/structure-info/kanjidict.txt"
FILTERED_KANJI_PATH = "input/filtered_kanji.json"
OUT_PATH = "output/similar-kanjis.json"

MIN_SCORE = 0.35  # per-source floor before merging; strips near-zero padding neighbors
MAX_TOTAL = 10  # hard cap on the final list -- matches each source file's own top-10 ceiling
RRF_K = 5  # reciprocal-rank-fusion constant; result is insensitive to this (tested 1, 5, 60)


def parse_similarity_csv(path):
    """kanji -> [(neighbor, score), ...] from a raw/similarity/*.csv file.

    Each line is "pivot neighbor1 score1 neighbor2 score2 ...". Re-sorted by
    score descending defensively, though the source files already ship sorted.
    """
    neighbors = {}
    with open(sources.resolve_path(path), encoding="utf-8") as f:
        for line in f:
            fields = line.split()
            if not fields:
                continue
            pivot, rest = fields[0], fields[1:]
            pairs = [(rest[i], float(rest[i + 1])) for i in range(0, len(rest) - 1, 2)]
            pairs.sort(key=lambda pair: -pair[1])
            neighbors[pivot] = pairs
    return neighbors


def rank_fusion_merge(pivots, sed_neighbors, yeh_neighbors, filtered):
    """Merge stroke-distance and radical neighbor lists via reciprocal rank fusion.

    Each source is floored independently first (a candidate must score >=
    MIN_SCORE in that source, and be a shipped kanji, to be considered at
    all). Every surviving candidate then earns 1/(RRF_K + rank + 1) from each
    list it appears in (rank is 0-based within that source's own floored,
    re-sorted list) -- comparing rank rather than raw score means neither
    source can dominate just because its numbers happen to run higher.
    Summed scores are sorted descending and capped at MAX_TOTAL.
    """
    result = {}
    for pivot in pivots:
        sed_list = [n for n, s in sed_neighbors.get(pivot, []) if s >= MIN_SCORE and n in filtered]
        yeh_list = [n for n, s in yeh_neighbors.get(pivot, []) if s >= MIN_SCORE and n in filtered]

        fused = defaultdict(float)
        for rank, kanji in enumerate(sed_list):
            fused[kanji] += 1 / (RRF_K + rank + 1)
        for rank, kanji in enumerate(yeh_list):
            fused[kanji] += 1 / (RRF_K + rank + 1)

        ordered = sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))
        result[pivot] = [kanji for kanji, _ in ordered[:MAX_TOTAL]]
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
    """Similarity fallback for shipped kanji with no Yencken data (non-jouyou).

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

    sed = parse_similarity_csv(STROKE_EDIT_DISTANCE_PATH)
    yeh = parse_similarity_csv(YEH_LI_RADICAL_PATH)
    jouyou_pivots = set(sed) & filtered
    print(f"{len(jouyou_pivots)} kanji have Yencken similarity data (stroke-distance + radical)")

    similar = rank_fusion_merge(jouyou_pivots, sed, yeh, filtered)

    gap = sorted(filtered - jouyou_pivots)
    print(f"{len(gap)} kanji fall back to the kanjidict.txt radical/phonetic heuristic")
    kanjidict = parse_kanjidict(KANJIDICT_PATH)
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

    examples = ["時", "阪", "誰", "頃", "岡", "一"]
    print("\nExamples:")
    for kanji in examples:
        if kanji in similar:
            print(f"  {kanji} -> {'  '.join(similar[kanji])}")


if __name__ == "__main__":
    main()
