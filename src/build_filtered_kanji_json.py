#!/usr/bin/env python3
"""
Builds the canonical kanji lists every other script keys off of.

Reads input/merged_kanji.json and writes two ordered lists of kanji characters:

  input/all_kanjis.json       every kanji in merged_kanji.json (~2400),
                              INCLUDING those marked for removal; merged order.
  input/filtered_kanji.json   all_kanjis minus overrides/kanji_to_remove.json,
                              ordered by frequency (Google → JPDB → Netflix) —
                              the single source of truth for "which kanji ship"
                              AND the order downstream scripts iterate. Because
                              build_representative_study_word_algo assigns shared
                              study words first-come-first-served by this order,
                              frequency-ordering gives common kanji first pick.

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
import utils
import kanji_load

# JPDB writes "4001+" (mapped to this sentinel) for ~1100 rare kanji past its
# 4000-deep list; treat it as "no JPDB rank" for ordering.
JPDB_SENTINEL = 50_000


def load_json(rel_path):
    # Required inputs — fail loud if missing (no silent default).
    with open(resolve_path(rel_path), encoding="utf-8") as f:
        return json.load(f)


def write_json(rel_path, data):
    with open(resolve_path(rel_path), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Written: input/{os.path.basename(rel_path)} ({len(data)} kanji)")


def _google_rank(info):
    return utils.to_int(info.get("frequency", {}).get("ultimate", {}).get("google"))


def _netflix_rank(info):
    freq = info.get("frequency", {}).get("ohTalkWhoNetflix", {})
    return utils.to_int(freq.get("rank1224"))


def order_by_frequency(filtered, merged, original_order):
    """Order `filtered` by frequency, preferring Google, then JPDB, then Netflix.

    Each source's rank is normalized to [0, 1] by that source's own max rank
    among the filtered kanji, so a kanji ranked only by a fallback source still
    slots in at a comparable position — e.g. 頬/撫/睨 are common in JPDB but
    absent from Google's (formal-web) list, and must not be dumped at the end.
    Kanji with no rank in any source sort last, keeping merged_kanji.json order
    via the stable index tiebreak.
    """
    jpdb = kanji_load.load_jpdb_frequency()

    def jpdb_rank(kanji):
        rank = jpdb.get(kanji)
        return rank if rank and rank != JPDB_SENTINEL else None

    google = {k: _google_rank(merged.get(k, {})) for k in filtered}
    netflix = {k: _netflix_rank(merged.get(k, {})) for k in filtered}
    jp = {k: jpdb_rank(k) for k in filtered}

    g_max = max((v for v in google.values() if v), default=1)
    j_max = max((v for v in jp.values() if v), default=1)
    n_max = max((v for v in netflix.values() if v), default=1)

    index = {k: i for i, k in enumerate(original_order)}

    def freq_key(kanji):
        if google[kanji]:
            return google[kanji] / g_max
        if jp[kanji]:
            return jp[kanji] / j_max
        if netflix[kanji]:
            return netflix[kanji] / n_max
        return 1.0

    return sorted(filtered, key=lambda k: (freq_key(k), index[k]))


def main():
    merged = load_json("input/merged_kanji.json")
    all_kanjis = list(merged.keys())

    to_remove = set(load_json("overrides/kanji_to_remove.json").get("data", []))
    filtered = [k for k in all_kanjis if k not in to_remove]
    filtered = order_by_frequency(filtered, merged, all_kanjis)

    write_json("input/all_kanjis.json", all_kanjis)
    write_json("input/filtered_kanji.json", filtered)

    removed = len(all_kanjis) - len(filtered)
    print(f"Removed {removed} kanji ({len(to_remove)} in kanji_to_remove.json).")
    print("filtered_kanji.json ordered by frequency (Google → JPDB → Netflix).")


if __name__ == "__main__":
    main()
