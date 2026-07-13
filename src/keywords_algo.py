#!/usr/bin/env python3
"""
Task 1: Better Kanji Keywords
Generates overrides/keywords-algo.json

Pipeline (low → high priority):
  base input data → base keyword → keywords-algo.json → keywords.json (manual)

For each kanji we prefer the simplest meaningful available keyword:
  - candidates from raw/kanji-keywords-j.json
  - candidates from raw/kanji-keywords-w.json
  - candidates from raw/kanji-keywords-k.json (sort by word length)
  - the base keyword derived directly from input/merged_kanji.json

A greedy uniqueness pass (sorted by fewest candidates first) ensures no two kanji
share the same keyword in the algo output. Manual overrides (keywords.json) are
reserved up-front so they don't create conflicts after being applied on top.

The "base keyword" is computed from input/merged_kanji.json with the SAME logic the
final build uses (kanji_extract.get_keyword, no overrides), rather than read back
from output/kanji_main.json. That removes the build → keywords-algo → build cycle:
this script no longer depends on a prior build artifact.

Run from the project root: python3 src/keywords_algo.py
"""

import json

from sources import resolve_path, load_json
from keyword_sources import is_valid_keyword, base_keyword, raw_candidates


def task1_better_kanji_keywords():
    with open(resolve_path('raw/kanji-keywords-k.json'), encoding='utf-8') as f:
        keywords_k = json.load(f)  # {kanji: "WORD1, PHRASE, WORD2"}

    with open(resolve_path("raw/kanji-keywords-j.json"), encoding="utf-8") as f:
        keywords_j = json.load(f)

    with open(resolve_path("raw/kanji-keywords-w.json"), encoding="utf-8") as f:
        keywords_w = json.load(f)

    with open(resolve_path('overrides/keywords.json'), encoding='utf-8') as f:
        manual_overrides = json.load(f)  # {kanji: "keyword"} — highest priority

    # Canonical kanji set + raw kanji data (no build artifact dependency).
    all_kanji = load_json('input/filtered_kanji.json', [])
    merged = load_json('input/merged_kanji.json', {})

    # base_keyword(kanji, merged) is the keyword the build derives from raw data with
    # no overrides applied — the non-circular replacement for kanji_main[kanji][0].
    base_keywords = {k: (base_keyword(k, merged) or '') for k in all_kanji}

    # Reserve keywords claimed by manual overrides so we don't assign them to other kanji
    # (after manual overrides are applied on top, those kanji will use the manual value,
    # but other kanji must not end up sharing that keyword)
    reserved_by_manual = set(v.lower().strip() for v in manual_overrides.values()
    if is_valid_keyword(v.lower().strip()))

    # Build candidate list per kanji in priority order (j → k → w → rest by length),
    # then fall back to the base keyword.
    candidate_map = {}
    for kanji in all_kanji:
        candidates = raw_candidates(kanji, keywords_j, keywords_w, keywords_k)
        current = (base_keywords[kanji] or '').strip().lower()
        if current and is_valid_keyword(current) and current not in candidates:
            candidates.append(current)
        candidate_map[kanji] = candidates

    # Greedy unique assignment.
    # Sort ascending by candidate count: kanji with fewer options are served first so
    # a many-option kanji never steals the sole keyword of a one-option kanji.
    sorted_kanji = sorted(all_kanji, key=lambda k: len(candidate_map[k]))

    used_keywords = set(reserved_by_manual)  # pre-block manual-override keywords
    result = {}

    inspect_json = {}

    def update_inspect_json(kanji, previous, current, candidates, is_manual):
        info = "✍️" if is_manual else ""
        count = len(candidates)
        if previous == current:
            return

        if len(candidates) <= 1:
            inspect_json[kanji] = f"{info} {current} ← {previous}"
            return

        joined = ",".join(candidates)

        inspect_json[kanji] = f"{count}{info}: {current} ← {previous} ← {joined}"

    for kanji in sorted_kanji:
        previous = base_keywords[kanji]
        candidates = candidate_map[kanji]
        # candidates = sorted(candidate_map[kanji], key=lambda word: len(word))

        # If this kanji has a manual override, skip assigning it here — the manual
        # override will take precedence in the build pipeline regardless.
        if kanji in manual_overrides.keys():
            candidate = manual_overrides[kanji]
            update_inspect_json(kanji, previous, candidate, candidates, True)
            result[kanji] = candidate
            continue

        for candidate in candidates:
            if candidate not in used_keywords:
                used_keywords.add(candidate)
                result[kanji] = candidate
                update_inspect_json(kanji, previous, candidate, candidates, False)
                break

    # Restore original kanji order for readability
    ordered_result = {k: result[k] for k in all_kanji if k in result}

    # Stats
    unassigned = [k for k in all_kanji if k not in result and k not in manual_overrides]
    changed = [k for k in ordered_result if base_keywords[k] != ordered_result[k]]
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
            print(f"  {k}  current={base_keywords[k]!r}  raw={keywords!r}")

    out_path = resolve_path('overrides/keywords-algo.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(ordered_changed, f, ensure_ascii=False, indent=4)
    print(f"\nOutput written to: {out_path}")

    out_path = resolve_path("debug/debug-keywords.json")
    ordered_inspect_json = {k: inspect_json[k] for k in all_kanji if k in inspect_json}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(ordered_inspect_json, f, ensure_ascii=False, indent=4)
    print(f"\nOutput written to: {out_path}")

if __name__ == '__main__':
    task1_better_kanji_keywords()
