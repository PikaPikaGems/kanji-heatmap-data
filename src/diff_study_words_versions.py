#!/usr/bin/env python3
"""Diff two japanese_study_words-algo.json builds (e.g. different v3/textbook source
combos) and print, per kanji, where the selected representative word OR its tier
(the tag: 🌱/☘️/🌷/📖/📚/🤔/🦉/✏️) changed.

Each file maps {kanji: [word, reading, meaning, tag] | null}. Output line per change:

    [kanji] versionAWord versionAWordTier -> versionBWord versionBWordTier

Use "∅" when a side has no word (null entry) or the kanji is absent on that side.

Usage:
    python3 src/diff_study_words_versions.py A.json B.json
    python3 src/diff_study_words_versions.py A.json B.json --tier-only   # only tag changed
    python3 src/diff_study_words_versions.py A.json B.json --word-only   # only word changed
    python3 src/diff_study_words_versions.py A.json B.json --kanji-count-shift
        # kanji whose word gained/lost single-kanji (kanji_count==1) status between A and B
"""

import argparse
import json
import sys

from japanese import kanji_count

NONE = "∅"


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def word_tier(entry):
    """(word, tier) for an entry, or (∅, ∅) when there is no word."""
    if not entry:
        return NONE, NONE
    return entry[0], entry[3]


def entry_kanji_count(entry):
    """kanji_count of an entry's word, or None when there is no word."""
    return kanji_count(entry[0]) if entry else None


def print_word_tier_diff(a, b, kanji_order, args):
    """Default mode: per-kanji word/tier changes."""
    changes = []
    for kanji in kanji_order:
        aw, at = word_tier(a.get(kanji))
        bw, bt = word_tier(b.get(kanji))
        if aw == bw and at == bt:
            continue
        word_changed = aw != bw
        if args.word_only and not word_changed:
            continue
        if args.tier_only and word_changed:
            continue
        changes.append((kanji, aw, at, bw, bt, word_changed))

    for kanji, aw, at, bw, bt, _ in changes:
        print(f"[{kanji}] {aw} {at} -> {bw} {bt}")

    word_changes = sum(1 for c in changes if c[5])
    tier_only = len(changes) - word_changes
    print(f"\n{'─'*44}", file=sys.stderr)
    print(f"  versionA: {args.version_a}", file=sys.stderr)
    print(f"  versionB: {args.version_b}", file=sys.stderr)
    print(f"  kanji compared:    {len(kanji_order)}", file=sys.stderr)
    print(f"  total differences: {len(changes)}", file=sys.stderr)
    print(f"    word changed:    {word_changes}", file=sys.stderr)
    print(f"    tier-only:       {tier_only}", file=sys.stderr)
    print(f"{'─'*44}", file=sys.stderr)


def print_kanji_count_shift(a, b, kanji_order, args):
    """--kanji-count-shift mode: kanji whose word gained or lost single-kanji
    (kanji_count==1) status between A and B, in both directions.

    A "1-kanji word" is one whose word contains exactly one kanji (word_type 0/1,
    e.g. 行 or 行く). This is the "1 kanji" row of the build's "Kanji per word"
    report. Summarised against the count totals so the net change matches that row.
    """
    def fmt(kanji, ea, eb):
        aw = word_tier(ea)[0]
        bw = word_tier(eb)[0]
        at = word_tier(ea)[1]
        bt = word_tier(eb)[1]
        return f"[{kanji}] {aw} {at} -> {bw} {bt}"

    lost, gained = [], []
    for kanji in kanji_order:
        ea, eb = a.get(kanji), b.get(kanji)
        ca, cb = entry_kanji_count(ea), entry_kanji_count(eb)
        if ca == 1 and cb != 1:
            lost.append((kanji, ea, eb))
        elif cb == 1 and ca != 1:
            gained.append((kanji, ea, eb))

    # Within each direction, split by whether the other side has no word at all.
    lost_to_none = [x for x in lost if x[2] is None]
    lost_to_multi = [x for x in lost if x[2] is not None]
    gained_from_none = [x for x in gained if x[1] is None]
    gained_from_multi = [x for x in gained if x[1] is not None]

    def compact(rows):
        return "".join(kanji for kanji, _, _ in rows)

    print(f"=== LOST 1-kanji (1-kanji in A, NOT in B) === ({len(lost)})")
    print(f"  {compact(lost)}")
    print(f"\n  -> became multi-kanji word in B ({len(lost_to_multi)})")
    for kanji, ea, eb in lost_to_multi:
        print(fmt(kanji, ea, eb))
    print(f"\n  -> became no word (∅) in B ({len(lost_to_none)})")
    for kanji, ea, eb in lost_to_none:
        print(fmt(kanji, ea, eb))

    print(f"\n=== GAINED 1-kanji (1-kanji in B, NOT in A) === ({len(gained)})")
    print(f"  {compact(gained)}")
    print(f"\n  <- was a multi-kanji word in A ({len(gained_from_multi)})")
    for kanji, ea, eb in gained_from_multi:
        print(fmt(kanji, ea, eb))
    print(f"\n  <- had no word (∅) in A ({len(gained_from_none)})")
    for kanji, ea, eb in gained_from_none:
        print(fmt(kanji, ea, eb))

    a_one = sum(1 for k in kanji_order if entry_kanji_count(a.get(k)) == 1)
    b_one = sum(1 for k in kanji_order if entry_kanji_count(b.get(k)) == 1)
    print(f"\n{'─'*44}", file=sys.stderr)
    print(f"  versionA: {args.version_a}", file=sys.stderr)
    print(f"  versionB: {args.version_b}", file=sys.stderr)
    print(f"  1-kanji words in A: {a_one}", file=sys.stderr)
    print(f"  1-kanji words in B: {b_one}", file=sys.stderr)
    print(f"  net change (B - A): {b_one - a_one:+d}", file=sys.stderr)
    print(f"  lost (A→not-B):     {len(lost)}  "
          f"(→multi {len(lost_to_multi)}, →∅ {len(lost_to_none)})", file=sys.stderr)
    print(f"  gained (not-A→B):   {len(gained)}  "
          f"(multi→ {len(gained_from_multi)}, ∅→ {len(gained_from_none)})", file=sys.stderr)
    print(f"{'─'*44}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("version_a", help="path to versionA japanese_study_words-algo.json")
    ap.add_argument("version_b", help="path to versionB japanese_study_words-algo.json")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--word-only", action="store_true",
                       help="only show kanji where the WORD changed")
    group.add_argument("--tier-only", action="store_true",
                       help="only show kanji where only the TIER changed (word identical)")
    group.add_argument("--kanji-count-shift", action="store_true",
                       help="show kanji whose word gained/lost single-kanji (kanji_count==1) "
                            "status between A and B, in both directions")
    args = ap.parse_args()

    a = load(args.version_a)
    b = load(args.version_b)

    # Union of kanji, preserving versionA order then any B-only kanji.
    kanji_order = list(a.keys()) + [k for k in b if k not in a]

    if args.kanji_count_shift:
        print_kanji_count_shift(a, b, kanji_order, args)
    else:
        print_word_tier_diff(a, b, kanji_order, args)


if __name__ == "__main__":
    main()
