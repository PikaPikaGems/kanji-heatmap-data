#!/usr/bin/env python3
"""
Manual-inspection tool: lists every shipped kanji whose STUDY word or SAMPLE
words contain a NON-shipped kanji (a character not in output/kanji_main.json).

These are the assignments where a kanji's chosen example word drags in another
character the dataset doesn't ship — useful for deciding whether to bring a
removed kanji back, remove more, or pick a different word.

Reads the shipped artifacts directly, so it reflects exactly what ships
(all manual + algo overrides already applied by the build):
  output/kanji_main.json                 -> the shipped kanji set
  output/kanji_representative_words.json  -> [word, reading, meaning, tag] per kanji
  output/kanji_extended.json              -> sample words at index 9

Each offending non-shipped kanji is tagged:
  [removed]  it is in overrides/kanji_to_remove.json  (could be brought back)
  [external] not in input/merged_kanji.json at all     (no data to ship)

Run from the project root: python3 src/inspect_nonshipped_words.py
"""

import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))

import japanese
from sources import load_json

SAMPLE_WORDS_INDEX = 9


def main():
    main_data = load_json("output/kanji_main.json", {})
    shipped = set(main_data)
    rep = load_json("output/kanji_representative_words.json", {})
    ext = load_json("output/kanji_extended.json", {})
    removed = set(load_json("overrides/kanji_to_remove.json", {}).get("data", []))
    merged = set(load_json("input/merged_kanji.json", {}))

    def nonshipped_in(word):
        return [c for c in word if japanese.is_kanji_char(c) and c not in shipped]

    def tag(c):
        if c in removed:
            return "removed"
        if c not in merged:
            return "external"
        return "missing"  # not shipped, not removed, yet in merged — unexpected

    def annotate(chars):
        return "  ".join(f"{c}[{tag(c)}]" for c in chars)

    # --- study words (one per kanji; the word starts with the kanji) ---
    study_hits = []
    for kanji in main_data:  # iterate in shipped order
        entry = rep.get(kanji)
        if not entry:
            continue
        bad = nonshipped_in(entry[0])
        if bad:
            study_hits.append((kanji, entry, bad))

    # --- sample words (up to two per kanji; kanji may appear anywhere) ---
    sample_hits = []
    for kanji in main_data:
        entry = ext.get(kanji)
        if not entry or len(entry) <= SAMPLE_WORDS_INDEX:
            continue
        for word in entry[SAMPLE_WORDS_INDEX] or []:
            bad = nonshipped_in(word)
            if bad:
                sample_hits.append((kanji, word, bad))

    print("=" * 72)
    print(f"STUDY-WORD assignments whose word uses a non-shipped kanji: {len(study_hits)}")
    print("=" * 72)
    for i, (k, entry, bad) in enumerate(study_hits, 1):
        word, reading, meaning, wtag = entry[0], entry[1], entry[2], entry[3]
        print(f"{i:>3}. {k} → {word} ({reading}) [{wtag}] {meaning}")
        print(f"        non-shipped: {annotate(bad)}")

    print()
    print("=" * 72)
    print(f"SAMPLE-WORD assignments whose word uses a non-shipped kanji: {len(sample_hits)}")
    print("=" * 72)
    for i, (k, word, bad) in enumerate(sample_hits, 1):
        print(f"{i:>3}. {k} → {word:<8}  non-shipped: {annotate(bad)}")

    # --- summary ---
    tag_counts = Counter()
    distinct = {}
    for _, _, bad in study_hits:
        for c in bad:
            tag_counts[tag(c)] += 1
            distinct[c] = tag(c)
    for _, _, bad in sample_hits:
        for c in bad:
            tag_counts[tag(c)] += 1
            distinct[c] = tag(c)

    removed_distinct = sorted(c for c, t in distinct.items() if t == "removed")
    ext_distinct = sorted(c for c, t in distinct.items() if t == "external")

    print()
    print("-" * 72)
    print(f"study assignments : {len(study_hits)}")
    print(f"sample assignments: {len(sample_hits)}")
    print(f"TOTAL             : {len(study_hits) + len(sample_hits)}")
    print(f"non-shipped occurrences by source: {dict(tag_counts)}")
    print(f"distinct REMOVED kanji pulled in ({len(removed_distinct)}) — "
          f"candidates to bring back: {''.join(removed_distinct)}")
    print(f"distinct EXTERNAL kanji pulled in ({len(ext_distinct)}) — "
          f"no data, can't ship: {''.join(ext_distinct)}")


if __name__ == "__main__":
    main()
