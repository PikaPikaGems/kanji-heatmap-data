#!/usr/bin/env python3
"""
Builds the canonical kanji lists every other script keys off of.

Reads input/merged_kanji.json and writes two ordered lists of kanji characters
(preserving merged_kanji.json's order):

  input/all_kanjis.json       every kanji in merged_kanji.json (~2400),
                              INCLUDING those marked for removal.
  input/filtered_kanji.json   all_kanjis minus overrides/kanji_to_remove.json —
                              the single source of truth for "which kanji ship".

Before this script existed, the "merged minus kanji_to_remove" filtering was
re-implemented in three places, and one of them keyed off output/kanji_main.json
(a build artifact), creating a build-order dependency. Centralizing it here means
no downstream script depends on a prior build to know the kanji set.

This must run first in the pipeline (see generate.sh): build-representative,
algorithmic-kanji-vocab, and the final build all read input/filtered_kanji.json.

Run from the project root: python3 src/build_filtered_kanji_json.py
"""

import json
import os

from sources import resolve_path


def load_json(rel_path):
    # Required inputs — fail loud if missing (no silent default).
    with open(resolve_path(rel_path), encoding="utf-8") as f:
        return json.load(f)


def write_json(rel_path, data):
    with open(resolve_path(rel_path), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Written: input/{os.path.basename(rel_path)} ({len(data)} kanji)")


def main():
    merged = load_json("input/merged_kanji.json")
    all_kanjis = list(merged.keys())

    to_remove = set(load_json("overrides/kanji_to_remove.json").get("data", []))
    filtered = [k for k in all_kanjis if k not in to_remove]

    write_json("input/all_kanjis.json", all_kanjis)
    write_json("input/filtered_kanji.json", filtered)

    removed = len(all_kanjis) - len(filtered)
    print(f"Removed {removed} kanji ({len(to_remove)} in kanji_to_remove.json).")


if __name__ == "__main__":
    main()
