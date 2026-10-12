#!/usr/bin/env python3
"""
Builds output/similar-kanjis.json: for each shipped kanji, its most similar
kanji, most similar first: MAX_TOTAL shipped kanji, plus up to MAX_UNSHIPPED
kanji we don't ship that look almost the same.

Candidates:

  - Shipped kanji.
  - Unshipped kanji only when their glyph is within MAX_UNSHIPPED_DIST of
    this kanji's (nearest_unshipped in glyph-neighbors.json). Rare kanji and
    old forms count too (撤 撒, 栗 粟, 錬 鍊, 黒 黑). The app shows them
    without a keyword.

Order of each list:

  1. Human-judged lookalikes from raw/similarity/flashcards.csv (Yencken's
     White Rabbit flashcard distractors), used in both directions.

  2. The rest, shipped or not, ranked by weighted reciprocal-rank fusion (score =
     sum of weight / (RRF_K + rank)) of four measures, each read as a ranked
     neighbor list per kanji:

     - raw/similarity/glyph-neighbors.json: chamfer distance between rendered
       glyphs (src/build_glyph_neighbors.py). Covers every shipped kanji and
       catches whole-shape lookalikes (午 牛, 人 入, 未 末, 土 士).
     - raw/similarity/dkanjistat.json: Kanjistat optimal-transport distance
       over KanjiVG structure. Jōyō only (~20 neighbors each); rewards kanji
       built from similar parts (飯 販 版 飼).
     - raw/similarity/jyouyou__strokeEditDistance.csv: Yencken's stroke edit
       distance. 1945 old jōyō only (10 neighbors each); catches simple pairs
       (一 二, 人 入).
     - raw/structure-info/kanjidict.txt: kanji with the same sound part
       (phonetic component), closest stroke count first. Shares a big chunk
       of the shape and often the reading (伽 加 架 賀, 綺 騎 奇), and covers
       many non-jōyō kanji the first two measures miss.

     Each measure is made symmetric first (a pair counts if either kanji lists
     the other), so a lookalike seen from one side shows up on both.

The weights were tuned against raw/similarity/poolexp_judgements.yaml (native
speakers picking the most confusable kanji from a pool), which is kept out of
the inputs so it stays a fair check. The stats at the end report it.

Non-jōyō kanji are ranked by the glyph and sound-part measures only, since
the other two cover jōyō kanji only (dkanjistat does include official forms
we don't ship, such as 剝).

Run from the project root: python3 src/build_similar_kanji.py
"""

import unicodedata
from collections import defaultdict

import sources

SIMILARITY_DIR = "raw/similarity"
GLYPH_PATH = f"{SIMILARITY_DIR}/glyph-neighbors.json"
DKANJISTAT_PATH = f"{SIMILARITY_DIR}/dkanjistat.json"
STROKE_EDIT_PATH = f"{SIMILARITY_DIR}/jyouyou__strokeEditDistance.csv"
FLASHCARDS_PATH = f"{SIMILARITY_DIR}/flashcards.csv"
POOLEXP_PATH = f"{SIMILARITY_DIR}/poolexp_judgements.yaml"
KANJIDICT_PATH = "raw/structure-info/kanjidict.txt"
FILTERED_KANJI_PATH = "intermediate/filtered_kanji.json"
OUT_PATH = "output/similar-kanjis.json"

MAX_TOTAL = 10
MAX_UNSHIPPED = 3
MAX_UNSHIPPED_DIST = 0.35  # px; 未 末 0.15, 土 士 0.19, 鳴 嗚 0.23 pass, 午 牛 0.71 wouldn't
RRF_K = 10
WEIGHTS = {"glyph": 1.0, "dkanjistat": 1.0, "stroke_edit": 0.5, "sound_part": 1.0}


def symmetric_ranks(pairs, eligible):
    """{kanji: {neighbor: rank}} from (a, b, similarity) triples, higher = closer.

    A pair keeps its best similarity from either direction; each kanji's
    neighbors are then ranked 1, 2, ... by that similarity. Kanji outside
    `eligible` are dropped before ranking.
    """
    best = defaultdict(dict)
    for a, b, sim in pairs:
        if a == b or a not in eligible or b not in eligible:
            continue
        for x, y in ((a, b), (b, a)):
            if sim > best[x].get(y, float("-inf")):
                best[x][y] = sim
    ranks = {}
    for kanji, neighbors in best.items():
        ordered = sorted(neighbors, key=lambda n: (-neighbors[n], n))
        ranks[kanji] = {n: i + 1 for i, n in enumerate(ordered)}
    return ranks


def nearest_pairs(nearest):
    """(a, b, -distance) from {a: {b: distance}}."""
    return [(a, b, -d) for a, nbrs in nearest.items() for b, d in nbrs.items()]


def stroke_edit_pairs():
    """(a, b, similarity) from Yencken's `pivot n1 s1 n2 s2 ...` lines."""
    pairs = []
    with open(sources.resolve_path(STROKE_EDIT_PATH), encoding="utf-8") as f:
        for line in f:
            fields = line.split()
            for b, sim in zip(fields[1::2], fields[2::2]):
                pairs.append((fields[0], b, float(sim)))
    return pairs


def sound_part_pairs(eligible):
    """(a, b, -stroke gap) for eligible kanji sharing a sound part.

    kanjidict.txt is kanjium's tab-separated kanji dictionary (see
    raw/structure-info/SOURCES.md): column 3 is the phonetic component (blank
    when there is none), column 11 the stroke count. Some kanji appear twice,
    as a unified and a compatibility codepoint (祐 U+7950 / U+FA4F), so CJK
    fields are NFKC-normalized to merge them.
    """
    groups = defaultdict(set)
    strokes = {}
    with open(sources.resolve_path(KANJIDICT_PATH), encoding="utf-8") as f:
        for line in f:
            fields = line.rstrip("\n").split("\t")
            if not fields or not fields[0]:
                continue
            kanji = unicodedata.normalize("NFKC", fields[0])
            phonetic = unicodedata.normalize("NFKC", fields[3])
            if phonetic and kanji in eligible:
                groups[phonetic].add(kanji)
                strokes[kanji] = int(fields[11])
    return [
        (a, b, -abs(strokes[a] - strokes[b]))
        for group in groups.values()
        for a in group
        for b in group
        if a != b
    ]


def flashcard_pairs(shipped):
    """{kanji: [lookalike, ...]} from `id pivot distractors` lines, both ways."""
    human = defaultdict(list)
    with open(sources.resolve_path(FLASHCARDS_PATH), encoding="utf-8") as f:
        for line in f:
            fields = line.split()
            if len(fields) < 3:
                continue
            pivot = fields[1]
            for other in fields[2]:
                if pivot in shipped and other in shipped and pivot != other:
                    for x, y in ((pivot, other), (other, pivot)):
                        if y not in human[x]:
                            human[x].append(y)
    return human


def unshipped_lookalikes(nearest_unshipped):
    """{kanji: {unshipped: distance}}, up to MAX_UNSHIPPED within MAX_UNSHIPPED_DIST."""
    result = {}
    for kanji, nearest in nearest_unshipped.items():
        close = sorted(
            ((other, dist) for other, dist in nearest.items() if dist <= MAX_UNSHIPPED_DIST),
            key=lambda pair: (pair[1], pair[0]),
        )[:MAX_UNSHIPPED]
        if close:
            result[kanji] = dict(close)
    return result


def fused_scores(measures, kanji):
    scores = defaultdict(float)
    for name, ranks in measures.items():
        for neighbor, rank in ranks.get(kanji, {}).items():
            scores[neighbor] += WEIGHTS[name] / (RRF_K + rank)
    return scores


def parse_poolexp():
    """Records of {pivot, distractors, selected} from the YAML-ish file.

    The file is a flat stream of `---`-separated records whose values are
    either a quoted string or a list of quoted strings, so a tiny parser
    avoids a YAML dependency.
    """
    records, record, key = [], {}, None
    with open(sources.resolve_path(POOLEXP_PATH), encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if line == "---":
                if record:
                    records.append(record)
                record, key = {}, None
            elif line.startswith("- "):
                record[key].append(_unquote(line[2:]))
            elif ":" in line:
                key, _, value = line.partition(":")
                value = value.strip()
                record[key] = _unquote(value) if value else []
    if record:
        records.append(record)
    return records


def _unquote(value):
    return value.strip().strip('"').encode("ascii").decode("unicode_escape")


def report(similar, human, measures, shipped):
    counts = [sum(k in shipped for k in v) for v in similar.values()]
    print()
    print("Shipped similar count distribution")
    for lo, hi in [(0, 0), (1, 3), (4, 6), (7, 9), (10, 10)]:
        n = sum(1 for c in counts if lo <= c <= hi)
        print(f"  {f'{lo}-{hi}':>8}  {n:>5} kanji")
    print(f"\n  Mean:        {sum(counts) / len(counts):.1f}")
    unshipped = [(kanji, k) for kanji, v in similar.items() for k in v if k not in shipped]
    print(f"\n  Unshipped lookalikes: {len(unshipped)} for {len({p[0] for p in unshipped})} kanji")
    print("  " + " ".join(f"{a}{b}" for a, b in unshipped[:40]))

    # Held-out check: for each judgement, does our score put the pool kanji
    # the participant picked first? Ties at the top count as misses.
    hits = total = 0
    for record in parse_poolexp():
        pivot, pool = record["pivot"], record["distractors"]
        if pivot not in shipped or not all(k in shipped for k in pool):
            continue
        scores = fused_scores(measures, pivot)
        for k in human.get(pivot, []):
            scores[k] += 1
        values = [scores.get(k, 0.0) for k in pool]
        top = max(values)
        total += 1
        hits += top > 0 and values.count(top) == 1 and pool[values.index(top)] in record["selected"]
    print(f"\n  poolexp: our top pick matches the human pick in {hits}/{total} ({hits / total:.1%})")

    examples = ["午", "人", "一", "未", "土", "鳥", "飯", "思", "投", "寺", "阪", "頷", "綺", "伽", "嬉", "撤", "栗", "黒"]
    print("\nExamples:")
    for kanji in examples:
        if kanji in similar:
            print(f"  {kanji} -> {'  '.join(similar[kanji])}")


def main():
    shipped = set(sources.load_json(FILTERED_KANJI_PATH))
    print(f"Loaded {len(shipped)} shipped kanji")

    glyph = sources.load_json(GLYPH_PATH)
    glyph_nearest = glyph["nearest"]
    stale = sorted(shipped - set(glyph_nearest))
    if stale:
        raise SystemExit(
            f"{GLYPH_PATH} has no entry for {len(stale)} shipped kanji ({''.join(stale[:20])}...). "
            "Rerun src/build_glyph_neighbors.py."
        )

    lookalikes = unshipped_lookalikes(glyph["nearest_unshipped"])
    eligible = shipped | {other for close in lookalikes.values() for other in close}
    print(f"{len(eligible) - len(shipped)} unshipped kanji are a close lookalike of a shipped one")

    measures = {
        "glyph": symmetric_ranks(nearest_pairs(glyph_nearest) + nearest_pairs(lookalikes), eligible),
        "dkanjistat": symmetric_ranks(
            nearest_pairs(sources.load_json(DKANJISTAT_PATH)["nearest"]), eligible
        ),
        "stroke_edit": symmetric_ranks(stroke_edit_pairs(), eligible),
        "sound_part": symmetric_ranks(sound_part_pairs(eligible), eligible),
    }
    for name, ranks in measures.items():
        print(f"{name}: neighbors for {len(ranks)} kanji")
    human = flashcard_pairs(shipped)
    print(f"flashcards: human lookalikes for {len(human)} kanji")

    similar = {}
    for kanji in sorted(shipped):
        result = list(human.get(kanji, []))[:MAX_TOTAL]
        # This kanji's own close unshipped lookalikes, plus the best shipped
        # kanji until there are MAX_TOTAL shipped, all in score order.
        own_lookalikes = lookalikes.get(kanji, {})
        scores = fused_scores(measures, kanji)
        shipped_count = len(result)
        for neighbor in sorted(scores, key=lambda n: (-scores[n], n)):
            if neighbor in result:
                continue
            if neighbor in shipped and shipped_count < MAX_TOTAL:
                result.append(neighbor)
                shipped_count += 1
            elif neighbor in own_lookalikes:
                result.append(neighbor)
        similar[kanji] = result

    sources.write_json(OUT_PATH, similar, separators=(",", ":"))
    print(f"Wrote {OUT_PATH}")
    report(similar, human, measures, shipped)


if __name__ == "__main__":
    main()
