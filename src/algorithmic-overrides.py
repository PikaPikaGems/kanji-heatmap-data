# Context
# We use src/kanji_build_output_jsons.py to generate the final output json files given the json files from the /input and /overrides folder
# The current kanji information we are storing in our output json can be improved (some are incorrect etc)
# Write now we have overrides/ folder where we manually add information to override existing information
# This is good but not every scalable. We want to generate new override json files algorithmically
# That will be override existing data (we keep the manually handcrafted (by a human) overrides, which we will use as the final overrides)
# The goal of the following tasks is to algorithmically generate supplementary overrides files.

# Task: Better Sample Vocabulary
# output: overrides/kanji_vocab-algo.json

# Task: More Trustworthy Furigana
# output: overrides/vocab_furigana-algo.json

# Task: Additional required vocab definitions from new kanji_vocab-algo.json
# output overrides/vocab_meaning-algo.json

#!/usr/bin/env python3
f"""
Task 1: Better Kanji Keywords
Generates overrides/keywords-algo.json

Pipeline (low → high priority):
  base input data → kanji_main.json → keywords-algo.json → keywords.json (manual)

For each kanji we prefer the simplest meaningful available keyword:
  - candidates from raw/kanji-keywords-j.json
  - candidates from raw/kanji-keywords-w.json
  - candidates from raw/kanji-keywords-k.json (sort by word length)
  - current keyword from output/kanji_main.json

A greedy uniqueness pass (sorted by fewest candidates first) ensures no two kanji
share the same keyword in the algo output. Manual overrides (keywords.json) are
reserved up-front so they don't create conflicts after being applied on top.

Run from the project root: python3 src/algorithmic-overrides.py
"""

import json
import re
import os
import random

# Seed with a specific integer
random.seed(42)
USE_RANDOMNESS = False

def resolve_path(path):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    return os.path.join(project_root, path)


def is_valid_keyword(phrase):
    """Valid: lowercase roman-alphabet word or phrase (letters and spaces only)."""
    return bool(re.match(r'^[a-z]+( [a-z]+)*$', phrase.strip()))


def parse_raw_candidates(raw_value):
    """Split comma-separated raw string into valid lowercase candidates."""
    parts = [p.strip().lower() for p in raw_value.split(',')]
    return [p for p in parts if is_valid_keyword(p)]


def task1_better_kanji_keywords():
    with open(resolve_path('raw/kanji-keywords-k.json'), encoding='utf-8') as f:
        keywords_k = json.load(f)  # {kanji: "WORD1, PHRASE, WORD2"}

    with open(resolve_path("raw/kanji-keywords-j.json"), encoding="utf-8") as f:
        keywords_j = json.load(f)

    with open(resolve_path("raw/kanji-keywords-w.json"), encoding="utf-8") as f:
        keywords_w = json.load(f)

    with open(resolve_path('output/kanji_main.json'), encoding='utf-8') as f:
        kanji_main = json.load(f)  # {kanji: [keyword, on, kun, jlpt, ranks]}

    with open(resolve_path('overrides/keywords.json'), encoding='utf-8') as f:
        manual_overrides = json.load(f)  # {kanji: "keyword"} — highest priority

    all_kanji = list(kanji_main.keys())

    # Reserve keywords claimed by manual overrides so we don't assign them to other kanji
    # (after manual overrides are applied on top, those kanji will use the manual value,
    # but other kanji must not end up sharing that keyword)
    reserved_by_manual = set(v.lower().strip() for v in manual_overrides.values()
    if is_valid_keyword(v.lower().strip()))

    # Build candidate list per kanji in priority order:
    candidate_map = {}
    for kanji in all_kanji:

        pj_keyword = (keywords_j.get(kanji, '') or '').strip().lower()
        pj = [pj_keyword] if is_valid_keyword(pj_keyword) else []

        pk = parse_raw_candidates(keywords_k.get(kanji, ''))
        pk1 = pk[:1]
        pk2 = pk[1:]
        pw = keywords_w.get(kanji, [])
        pw1 = pw[:1]
        pw2 = pw[1:]
        sortedRest = sorted(pk2 + pw2, key=lambda word: len(word))
        priority_options = pj + pk1 + pw1
        shuffled = random.sample(priority_options,len(priority_options)) if USE_RANDOMNESS else priority_options
        pre_candidates = shuffled + sortedRest
        candidates = []
        for c in pre_candidates:
            if c not in candidates:
                candidates.append(c)

        current = (kanji_main[kanji][0] or '').strip().lower()
        if current and is_valid_keyword(current) and current not in candidates:
            candidates.append(current)

        candidate_map[kanji] = candidates

    # Greedy unique assignment.
    # Sort ascending by candidate count: kanji with fewer options are served first so
    # a many-option kanji never steals the sole keyword of a one-option kanji.
    sorted_kanji = sorted(all_kanji, key=lambda k: len(candidate_map[k]))

    used_keywords = set(reserved_by_manual)  # pre-block manual-override keywords
    result = {}

    inspectJson = {}

    def updateInspectJson(kanji, previous, current, candidates, isManual):
        info = "✍️" if isManual else ""
        count = len(candidates)
        if previous == current:
            return

        if len(candidates) <= 1:
            inspectJson[kanji] = f"{info} {current} ← {previous}"
            return

        all = ",".join(candidates)

        inspectJson[kanji] = f"{count}{info}: {current} ← {previous} ← {all}"

    for kanji in sorted_kanji:
        previous = kanji_main[kanji][0]
        candidates = candidate_map[kanji]
        # candidates = sorted(candidate_map[kanji], key=lambda word: len(word))

        # If this kanji has a manual override, skip assigning it here — the manual
        # override will take precedence in the build pipeline regardless.
        if kanji in manual_overrides.keys():
            candidate = manual_overrides[kanji]
            updateInspectJson(kanji, previous, candidate, candidates, True)
            result[kanji] = candidate
            continue

        for candidate in candidates:
            if candidate not in used_keywords:
                used_keywords.add(candidate)
                result[kanji] = candidate
                updateInspectJson(kanji, previous, candidate, candidates, False)
                break

    # Restore original kanji order for readability
    ordered_result = {k: result[k] for k in all_kanji if k in result}

    # Stats
    unassigned = [k for k in all_kanji if k not in result and k not in manual_overrides]
    changed = [k for k in ordered_result if kanji_main[k][0] != ordered_result[k]]
    ordered_changed = {k: result[k] for k in changed}
    print(f"Total kanji:                  {len(all_kanji)}")
    print(f"Covered by manual overrides:  {len(manual_overrides)}")
    print(f"Assigned by algo:             {len(ordered_result)}")
    print(f"Keywords updated vs current:  {len(changed)}")
    print(f"Unassigned (no candidate):    {len(unassigned)}")

    print("\n\nChanged kanji")
    print("".join(changed))

    print("\n\nUnassigned kanji")
    print("".join(unassigned))

    print("\n\nSanity Check")

    ordered_all = {k: result.get(k, manual_overrides.get(k, k)) for k in all_kanji}
    all_keywords = set(ordered_all)
    print("keywords + kanji without keywords:", len(all_keywords), "===", len(all_kanji))

    if unassigned:
        print("\n\nUnassigned kanji (no valid candidate found — need manual review):")
        for k in unassigned:
            keywords = keywords_k.get(k, keywords_j.get(k, 'NULL'))
            print(f"  {k}  current={kanji_main[k][0]!r}  raw={keywords!r}")

    out_path = resolve_path('overrides/keywords-algo.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(ordered_changed, f, ensure_ascii=False, indent=4)
    print(f"\nOutput written to: {out_path}")

    out_path = resolve_path("overrides/debug-keywords.json")
    ordered_inspectJson = {k: inspectJson[k] for k in all_kanji if k in inspectJson}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(ordered_inspectJson, f, ensure_ascii=False, indent=4)
    print(f"\nOutput written to: {out_path}")

if __name__ == '__main__':
    task1_better_kanji_keywords()
