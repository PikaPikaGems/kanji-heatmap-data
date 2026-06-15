#!/usr/bin/env python3
"""
Diffs the production representative study words against the experimental freq-ranks
run, entry by entry:

    A = overrides/japanese_study_words-algo.json       (production, build_representative_study_word_algo.py)
    B = overrides/japanese_study_words-algo-alt.json    (experiment, build_representative_study_word_algo_alt.py)

Buckets every kanji into: same word, changed word, only-A (B has none), only-B
(A has none), neither. Each entry is shown as  `tag kanji → word ~ reading  meaning`.

A dedicated "suru → non-suru" section surfaces a known production quirk: rare kanji
fall back to textbook headwords stored as verbs (識別する), whereas freq-ranks lists
the bare noun (識別). This lists every kanji where A is a 〜する word and B isn't.

Run from project root: python3 src/compare_study_words.py
"""

from sources import load_json

A_PATH = "overrides/japanese_study_words-algo.json"
B_PATH = "overrides/japanese_study_words-algo-alt.json"


def word_of(entry):
    """The word from a [word, reading, meaning, tag] entry, or None."""
    return entry[0] if entry else None


def _side(entry):
    """'{tag} {word}' for one side of a comparison, or '— (none)'."""
    if not entry:
        return "— (none)"
    word, _reading, _meaning, tag = (list(entry) + ["", "", "", ""])[:4]
    return f"{tag} {word}"


def _meaning(entry):
    return (list(entry) + ["", "", "", ""])[2] if entry else ""


def fmt_pair(kanji, ea, eb):
    """KANJI : TIER WORD → TIER WORD  (meaning_A → meaning_B)."""
    return f"{kanji} : {_side(ea)} → {_side(eb)}  ({_meaning(ea)} → {_meaning(eb)})"


def fmt_one(kanji, entry):
    """KANJI : TIER WORD  (meaning) — for sections with only one side."""
    return f"{kanji} : {_side(entry)}  ({_meaning(entry)})"


def is_suru(word):
    return bool(word) and word.endswith("する") and len(word) > 2


def main():
    a = load_json(A_PATH, {})
    b = load_json(B_PATH, {})
    kanji = list(dict.fromkeys(list(a) + list(b)))  # union, preserves A's order

    same, changed, only_a, only_b, neither = [], [], [], [], []
    suru_to_noun = []

    for k in kanji:
        aw, bw = word_of(a.get(k)), word_of(b.get(k))
        if aw and bw:
            (same if aw == bw else changed).append(k)
        elif aw and not bw:
            only_a.append(k)
        elif bw and not aw:
            only_b.append(k)
        else:
            neither.append(k)
        if is_suru(aw) and bw and not is_suru(bw):
            suru_to_noun.append(k)

    total = len(kanji)
    print(f"Comparing study words")
    print(f"  A (production): {A_PATH}")
    print(f"  B (freq-ranks): {B_PATH}")
    print(f"{'─'*60}")
    print(f"  Kanji total:        {total}")
    print(f"  Same word:          {len(same)}  ({len(same)/total*100:.1f}%)")
    print(f"  Changed word:       {len(changed)}")
    print(f"  Only A has a word:  {len(only_a)}   (B = freq-ranks has none)")
    print(f"  Only B has a word:  {len(only_b)}   (A = production has none)")
    print(f"  Neither:            {len(neither)}")
    print(f"  A 〜する → B non-suru: {len(suru_to_noun)}")
    print(f"{'─'*60}")

    def section_pair(title, ks):
        if not ks:
            return
        print(f"\n{title} ({len(ks)}):")
        for k in ks:
            print(f"  {fmt_pair(k, a.get(k), b.get(k))}")

    def section_one(title, ks):
        if not ks:
            return
        print(f"\n{title} ({len(ks)}):")
        for k in ks:
            print(f"  {fmt_one(k, a.get(k) or b.get(k))}")

    section_pair("A 〜する  →  B non-suru noun", suru_to_noun)
    section_pair("Changed word (A → B)", changed)
    section_one("Only A (production) has a word — B/freq-ranks empty", only_a)
    section_one("Only B (freq-ranks) has a word — A/production empty", only_b)


if __name__ == "__main__":
    main()
