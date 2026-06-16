#!/usr/bin/env python3
"""
Shows what would change in japanese_study_words-algo.json if 🌷 were added to
the special rule (single-kanji word with top tag wins outright), with the
additional constraint that the winning word must have a resolved meaning.

Compares the current overrides/japanese_study_words-algo.json against a
simulated run with 🌷 included.

Run from project root: python3 src/diff_study_words.py
"""

import sys
sys.path.insert(0, "src")

from sources import load_json, v3_candidates, textbook_candidates, TEXTBOOK_TAG
from japanese import kanji_count
from build_representative_study_word_algo import (
    is_valid_candidate,
    TAG_PRIORITY,
    DEFAULT_TAG_PRIORITY,
    SHIPPED,
    load_kanji_list,
    load_jmdict_meanings,
    load_scriptin_meanings,
    load_ai_meanings,
    word_score,
)


TOP_TAGS_CURRENT = {"🌱", "☘️"}
TOP_TAGS_NEW     = {"🌱", "☘️", "🌷"}


def resolve_meaning(word, entry_meaning, jmdict, scriptin, ai_meanings):
    return entry_meaning or jmdict.get(word) or scriptin.get(word) or ai_meanings.get(word, "")


def get_candidates(kanji):
    def valid(w, r):
        return is_valid_candidate(w, r, kanji)

    seen = {}
    cands = []
    for entry in v3_candidates(kanji, valid):
        w = entry[0]
        if w not in seen:
            seen[w] = len(cands)
            cands.append(entry)
    for entry in textbook_candidates(kanji, valid):
        w = entry[0]
        if w not in seen:
            seen[w] = len(cands)
            cands.append(entry)
        else:
            idx = seen[w]
            ex = cands[idx]
            if TAG_PRIORITY.get(entry[2], DEFAULT_TAG_PRIORITY) < TAG_PRIORITY.get(ex[2], DEFAULT_TAG_PRIORITY):
                cands[idx] = entry
    return cands


def best_single_kanji(cands, top_tags, jmdict, scriptin, ai_meanings):
    priority = [
        x for x in cands
        if kanji_count(x[0]) == 1
        and x[2] in top_tags
        and resolve_meaning(x[0], x[3], jmdict, scriptin, ai_meanings)
    ]
    if not priority:
        return None
    priority.sort(key=lambda x: word_score(x[0], x[2], x[3]))
    return priority[0]


def fmt(entry):
    if entry is None:
        return "None"
    word, _reading, meaning, tag = entry[0], entry[1], entry[2], entry[3]
    return f"{word} ({meaning or 'no meaning'}, {tag})"


def main():
    all_kanji = load_kanji_list()
    SHIPPED.update(all_kanji)

    jmdict      = load_jmdict_meanings()
    scriptin    = load_scriptin_meanings()
    ai_meanings = load_ai_meanings()

    manual_words = {k: v.strip() for k, v in load_json("raw/manual-inspections.json", {}).get("replaceKanjiStudyWords", {}).items()}

    current = load_json("overrides/japanese_study_words-algo.json", {})

    changes = []
    for kanji in all_kanji:
        cands = get_candidates(kanji)

        cur = current.get(kanji)
        cur_word = cur[0] if cur else None

        winner_current = best_single_kanji(cands, TOP_TAGS_CURRENT, jmdict, scriptin, ai_meanings)
        winner_new     = best_single_kanji(cands, TOP_TAGS_NEW,     jmdict, scriptin, ai_meanings)

        if kanji in manual_words:
            continue  # manual override always wins regardless of special rule

        if winner_new is None:
            continue
        new_word = winner_new[0]
        if new_word == cur_word:
            continue
        if winner_current and winner_current[0] == new_word:
            continue

        changes.append((kanji, cur, winner_new))

    print(f"{len(changes)} entries would change if 🌷 is added to the special rule:\n")
    for i, (kanji, old, new) in enumerate(changes, 1):
        meaning = resolve_meaning(new[0], new[3], jmdict, scriptin, ai_meanings)
        new_with_meaning = [new[0], new[1], meaning, new[2]]
        print(f"{i}. {kanji}: {fmt(old)} -> {fmt(new_with_meaning)}")


if __name__ == "__main__":
    main()
