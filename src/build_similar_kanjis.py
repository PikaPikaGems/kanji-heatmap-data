#!/usr/bin/env python3

import json
import sys
import os
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))

from sources import resolve_path

COMPONENTS_PATH = "raw/kanji_components.txt"
FILTERED_KANJI_PATH = "input/filtered_kanji.json"
OUT_PATH = "output/similar-kanjis.json"

IGNORED_COMPONENTS = {"丨", "丿", "一", "丶", "丷"}


def load_components(path):
    result = {}
    with open(resolve_path(path), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or ";" not in line:
                continue
            kanji, parts_str = line.split(";", 1)
            result[kanji] = list(parts_str)
    return result


MAX_PER_COMPONENT = 10
MAX_TOTAL = 20


def build_similar_kanjis(target_kanjis, components_map):
    parts_sets = {k: set(v) - IGNORED_COMPONENTS for k, v in components_map.items()}

    # component -> set of target kanjis that contain it
    component_to_kanjis = defaultdict(set)
    for kanji in target_kanjis:
        for part in parts_sets.get(kanji, set()):
            component_to_kanjis[part].add(kanji)

    result = {}
    # sorted() so the output's key order is stable (target_kanjis is a set).
    for kanji in sorted(target_kanjis):
        query_parts = parts_sets.get(kanji, set())
        if not query_parts:
            result[kanji] = []
            continue

        seen = set()
        candidates = []

        def overlap(k):
            k_parts = parts_sets.get(k, set())
            shared = len(query_parts & k_parts)
            smaller = min(len(query_parts), len(k_parts))
            return shared / smaller if smaller else 0

        # Iterate parts in a stable order. query_parts is a set, and the per-component
        # cap + dedup below make the collected candidate set order-dependent, so
        # without sorting the output varies run-to-run with the hash seed.
        for part in sorted(query_parts):
            group = [k for k in component_to_kanjis[part] if k != kanji]
            group.sort(key=lambda k: (-overlap(k), k))

            taken = 0
            for candidate in group:
                if taken >= MAX_PER_COMPONENT:
                    break
                if candidate not in seen:
                    seen.add(candidate)
                    candidates.append(candidate)
                    taken += 1

        candidates.sort(key=lambda k: (-overlap(k), k))
        result[kanji] = [k for k in candidates if overlap(k) >= 0.5][:MAX_TOTAL]

    return result


def main():
    with open(resolve_path(FILTERED_KANJI_PATH), encoding="utf-8") as f:
        target_kanjis = set(json.load(f))
    print(f"Loaded {len(target_kanjis)} target kanji")

    components_map = load_components(COMPONENTS_PATH)
    parts_sets = {k: set(v) - IGNORED_COMPONENTS for k, v in components_map.items()}
    print(f"Loaded components for {len(components_map)} kanji")

    covered = sum(1 for k in target_kanjis if k in components_map)
    print(f"{covered}/{len(target_kanjis)} target kanji have component data")

    similar = build_similar_kanjis(target_kanjis, components_map)

    with open(resolve_path(OUT_PATH), mode="w", encoding="utf-8") as f:
        json.dump(similar, f, ensure_ascii=False, separators=(",", ":"))

    print(f"Wrote {OUT_PATH}")

    # --- Statistics ---
    counts = [len(v) for v in similar.values()]
    counts_nonzero = [c for c in counts if c > 0]
    no_similar = sum(1 for c in counts if c == 0)
    buckets = [(0, 0), (1, 5), (6, 10), (11, 15), (16, 19), (20, 20)]
    print()
    print(f"{'Similar count distribution':}")
    for lo, hi in buckets:
        label = f"{lo}–{hi}" if hi != float("inf") else f"{lo}+"
        n = sum(1 for c in counts if lo <= c <= hi)
        print(f"  {label:>10}  {n:>5} kanji")
    print()
    print(f"  No similar:  {no_similar}")
    if counts_nonzero:
        print(f"  Min (nonzero): {min(counts_nonzero)}")
    print(f"  Median:        {sorted(counts)[len(counts)//2]}")
    print(f"  Mean:          {sum(counts)/len(counts):.1f}")
    print(f"  Max:           {max(counts)}")
    most = max(similar, key=lambda k: len(similar[k]))
    least = min((k for k in similar if similar[k]), key=lambda k: len(similar[k]))
    print(f"  Most similar:  {most} ({len(similar[most])} matches) — components: {''.join(components_map.get(most, []))}")
    print(f"  Fewest similar:{least} ({len(similar[least])} match) — components: {''.join(components_map.get(least, []))}")

    # Top-10 most frequent components across target kanjis
    from collections import Counter
    comp_freq = Counter(p for k in target_kanjis for p in parts_sets.get(k, set()))
    print()
    print("Top 10 most common components (by kanji count):")
    for comp, freq in comp_freq.most_common(10):
        print(f"  {comp}  {freq} kanji")

    # Spot-check examples
    examples = ["訳", "木", "寺", "五", "言", "時"]
    print()
    print("Examples:")
    for kanji in examples:
        if kanji not in similar:
            continue
        q_parts = parts_sets.get(kanji, set())
        print(f"\n  {kanji}  components=[{' '.join(q_parts)}]")
        for candidate in similar[kanji]:
            c_parts = parts_sets.get(candidate, set())
            shared = q_parts & c_parts
            smaller = min(len(q_parts), len(c_parts))
            score = len(shared) / smaller if smaller else 0
            print(f"    {candidate}  overlap={score:.0%}  shared=[{' '.join(shared)}]  all=[{' '.join(c_parts)}]")


if __name__ == "__main__":
    main()
