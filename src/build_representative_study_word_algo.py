#!/usr/bin/env python3
"""
Selects one unique representative study word per kanji.
Each word appears at most once across all kanjis (first-come-first-served by kanji order).

Constraints:
  - Word must START with the target kanji (first character = kanji)
  - Max 2 kanji characters in the word
  - All characters must be Japanese (hiragana/katakana/kanji)
  - Each word is assigned to at most one kanji

Rule 1 – source priority (lower index wins):
  0. v3 tag 🌱
  1. v3 tag ☘️
  2. v3 tag 🌷
  3. textbook words  (📖)
  4. v3 tag 📚
  5. unknown tag  (🤔)
  6. v3 tag 🦉

  If the same word appears in both v3 and textbook sources, the entry with the
  better (lower) tag priority wins.

Rule 2 – word quality within a source tier (lower score wins):
  Score tuple: (source_tier, word_type, length)
  word_type 0 → single-char kanji
  word_type 1 → 1 kanji + kana only
  word_type 2 → exactly 2 kanji (prefer shorter length)

Fallback (no candidates remain after applying constraints + uniqueness):
  - Relaxed search: word only needs to contain the kanji, not start with it
  - Source: textbook words only
  - Prioritizes shorter words first, then word_score
  - These kanjis show up in the "Words NOT starting with kanji" stat (~59 kanjis,
    mostly rare/classical with no words starting with them in the textbook data)

Last-resort fallback (no candidates even after relaxed search):
  - raw/ai-generated/japanese-study-words-ai.json  → {kanji: [word, reading, meaning, tag]}
  - Also subject to uniqueness: skipped if word already used by another kanji
  - Not subject to constraint checking (may produce words with >2 kanji for rare kanjis)

English meaning (resolved after word selection):
  - Taken from the source entry if present
  - Otherwise looked up in input/jmdict-vocab-meaning.json
  - Otherwise looked up in input/scriptin-jmdict-eng.json (first sense, up to 3 glosses)
  - Otherwise looked up in raw/ai-generated/vocab-meanings-ai.json (first element of value array)

Sources:
  input/filtered_kanji.json                        → [kanji]  (the kanji set to process)
  raw/kanji-words/v3/[kanji].json                  → [{w, r, t, j?, k?, e}]
  raw/kanji-textbook-words/[kanji].json            → {kanji: {word: [reading, meaning]}}
  input/jmdict-vocab-meaning.json                  → {word: meaning}
  input/scriptin-jmdict-eng.json                   → JMdict JSON (words[].kanji/kana/sense)
  raw/ai-generated/vocab-meanings-ai.json          → {word: [meaning, frequency_label]}
  raw/ai-generated/japanese-study-words-ai.json    → {kanji: [word, reading, meaning, tag]}
  raw/manual-inspections.json                      → {replaceKanjiStudyWords: {kanji: word}}
  input/jmdict-furigana-map.json                   → {word: {reading: segments}}  (override readings)

Output: overrides/japanese_study_words-algo.json
  { kanji: [word, reading, meaning, tag] }   (null when no valid word found)

Run from project root: python3 src/build_representative_study_word_algo.py
"""

from collections import Counter

from sources import (
    load_json,
    write_json,
    jmdict_entry_gloss,
    v3_candidates,
    textbook_candidates,
    TEXTBOOK_TAG,
)
from japanese import is_all_japanese, kanji_count

# ---------------------------------------------------------------------------
# Scoring / prioritisation
# ---------------------------------------------------------------------------

# NOTE: word_score / is_valid_candidate here intentionally differ from the
# same-named functions in algorithmic_kanji_vocab_overrides.py — this algorithm
# requires the word to START with the kanji and scores by word-type, while the
# sample-vocab algorithm only requires the kanji to appear anywhere.

TAG_PRIORITY = {
    "🌱": 0,
    "☘️": 1,
    "🌷": 2,
    TEXTBOOK_TAG: 3,
    "📚": 4,
    "🦉": 6,
}
DEFAULT_TAG_PRIORITY = 5  # unknown tag → between 📚 and 🦉


def word_score(word, tag):
    """Lower is better. Tuple: (source_tier, word_type, length)."""
    ts = TAG_PRIORITY.get(tag, DEFAULT_TAG_PRIORITY)
    n = len(word)
    kc = kanji_count(word)

    if n == 1:
        word_type = 0  # single-char kanji
    elif kc == 1:
        word_type = 1  # 1 kanji + kana only
    else:
        word_type = 2  # exactly 2 kanji (3+ are excluded)

    return (ts, word_type, n)


def is_valid_candidate(word, reading, target_kanji):
    if not word or not reading or reading == "-" or "," in reading:
        return False
    if not word or word[0] != target_kanji:
        return False
    if not is_all_japanese(word):
        return False
    kc = kanji_count(word)
    if kc < 1 or kc > 2:
        return False
    return True


def is_valid_fallback_candidate(word, reading, target_kanji):
    """Like is_valid_candidate but only requires the kanji to appear anywhere in the word."""
    if not word or not reading or reading == "-" or "," in reading:
        return False
    if target_kanji not in word:
        return False
    if not is_all_japanese(word):
        return False
    kc = kanji_count(word)
    if kc < 1 or kc > 2:
        return False
    return True


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_v3_candidates(kanji):
    return v3_candidates(kanji, lambda w, r: is_valid_candidate(w, r, kanji))


def load_textbook_candidates(kanji):
    return textbook_candidates(kanji, lambda w, r: is_valid_candidate(w, r, kanji))


def load_textbook_candidates_fallback(kanji):
    """Relaxed: word only needs to contain the kanji, not start with it."""
    return textbook_candidates(kanji, lambda w, r: is_valid_fallback_candidate(w, r, kanji))


OUTPUT_TEXTBOOK_TAG = "📖"
OVERRIDE_TAG = "✏️"  # manual study-word override (from raw/manual-inspections.json)


def select_word_for_kanji(kanji, used_words=None):
    """Return the best [word, reading, meaning, tag] for this kanji, or None.

    used_words: set of words already assigned to other kanjis — these are skipped.
    """
    if used_words is None:
        used_words = set()

    v3 = load_v3_candidates(kanji)
    textbook = load_textbook_candidates(kanji)

    seen = {}  # word -> index in all_candidates
    all_candidates = []
    for entry in v3:
        w = entry[0]
        if w not in seen:
            seen[w] = len(all_candidates)
            all_candidates.append(entry)
    for entry in textbook:
        w = entry[0]
        if w not in seen:
            seen[w] = len(all_candidates)
            all_candidates.append(entry)
        else:
            idx = seen[w]
            existing = all_candidates[idx]
            if TAG_PRIORITY.get(entry[2], DEFAULT_TAG_PRIORITY) < TAG_PRIORITY.get(existing[2], DEFAULT_TAG_PRIORITY):
                all_candidates[idx] = entry

    all_candidates.sort(key=lambda x: word_score(x[0], x[2]))

    # Try regular candidates (word starts with kanji), skip already-used words
    for w, r, t, e in all_candidates:
        if w not in used_words:
            display_tag = OUTPUT_TEXTBOOK_TAG if t == TEXTBOOK_TAG else t
            return [w, r, e, display_tag]

    # Fallback: relaxed search (kanji anywhere in word), textbook only, shorter words first
    # (59): 宏雰紘稔輔肇亨喬槙峻蕉欣禎斐尭馨彬匡欽佑惇脩甫暉允瑛皓洸怜悌侃侑琳瑚瑳瑶詢洵倖誼諄晏莉晨碩熙燎燦滉蓉恕迪綸麟柾裟頌眸伶
    fallback = load_textbook_candidates_fallback(kanji)
    fallback.sort(key=lambda x: (len(x[0]), word_score(x[0], x[2])))
    for w, r, t, e in fallback:
        if w not in used_words:
            return [w, r, e, OUTPUT_TEXTBOOK_TAG]

    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_kanji_list():
    # input/filtered_kanji.json is the canonical kanji set (merged_kanji minus
    # kanji_to_remove), produced by src/build_filtered_kanji_json.py.
    return load_json("input/filtered_kanji.json", [])


def load_jmdict_meanings():
    return load_json("input/jmdict-vocab-meaning.json", {})


def load_scriptin_meanings():
    data = load_json("input/scriptin-jmdict-eng.json", {})
    lookup = {}
    for entry in data.get("words", []):
        for form in entry.get("kanji", []) + entry.get("kana", []):
            t = form.get("text", "")
            if t and t not in lookup:
                meaning = jmdict_entry_gloss(entry, t)  # appliesToKanji-aware per form
                if meaning:
                    lookup[t] = meaning
    return lookup


def load_ai_meanings():
    data = load_json("raw/ai-generated/vocab-meanings-ai.json", {})
    return {word: val[0] for word, val in data.items() if isinstance(val, list) and val}


def load_ai_words():
    return load_json("raw/ai-generated/japanese-study-words-ai.json", {})


def load_manual_replace_words():
    data = load_json("raw/manual-inspections.json", {})
    return {k: v.strip() for k, v in data.get("replaceKanjiStudyWords", {}).items()}


def load_jmdict_readings():
    data = load_json("input/jmdict-furigana-map.json", {})
    return {word: next(iter(readings)) for word, readings in data.items() if readings}


def main():
    all_kanji = load_kanji_list()
    jmdict = load_jmdict_meanings()
    scriptin = load_scriptin_meanings()
    ai_meanings = load_ai_meanings()
    ai_words = load_ai_words()
    manual_words = load_manual_replace_words()
    jmdict_readings = load_jmdict_readings()

    result = {}
    used_words = set()  # enforces uniqueness across all kanjis

    for kanji in all_kanji:
        entry = select_word_for_kanji(kanji, used_words)

        if entry and not entry[2]:
            entry[2] = jmdict.get(entry[0]) or scriptin.get(entry[0]) or ai_meanings.get(entry[0], "")

        if entry is None:
            ai_entry = ai_words.get(kanji)
            if ai_entry and ai_entry[0] not in used_words:
                entry = ai_entry

        result[kanji] = entry

        if entry:
            used_words.add(entry[0])

    # --- Apply manual word overrides from raw/manual-inspections.json ---
    for kanji, word in manual_words.items():
        if kanji not in result:
            continue
        reading = jmdict_readings.get(word, "")
        meaning = jmdict.get(word) or scriptin.get(word) or ai_meanings.get(word, "")
        result[kanji] = [word, reading, meaning, OVERRIDE_TAG]

    # Overrides are applied without the per-selection uniqueness check above, so a
    # manual word can collide with one already chosen for another kanji. Fail loudly
    # here (at the source) instead of downstream in kanji_load.
    word_to_kanjis = {}
    for kanji, entry in result.items():
        if entry:
            word_to_kanjis.setdefault(entry[0], []).append(kanji)
    collisions = {w: ks for w, ks in word_to_kanjis.items() if len(ks) > 1}
    if collisions:
        raise ValueError(
            "Duplicate representative study words after applying "
            "replaceKanjiStudyWords from raw/manual-inspections.json — each word "
            f"must map to exactly one kanji: {collisions}"
        )

    out_path = write_json("overrides/japanese_study_words-algo.json", result, indent=2)
    print(f"Written: {out_path}")

    print_report(result, all_kanji)


def print_report(result, all_kanji):
    """Print selection statistics: tier/length/kanji-count breakdowns plus anomaly
    lists (no-word, no-meaning, not-starting-with-kanji, overlaps). Read-only over
    `result` — it does not affect the written output file."""
    selected_flat = [v for v in result.values() if v is not None]
    total = len(selected_flat)
    with_word = sum(1 for v in result.values() if v is not None)
    without   = sum(1 for v in result.values() if v is None)

    words         = [e[0] for e in selected_flat]
    tags          = [e[3] for e in selected_flat]
    length_counts = Counter(len(w) for w in words)
    kc_counts     = Counter(kanji_count(w) for w in words)
    tag_counts    = Counter(tags)

    # Per-tag and per-length groups: (kanji, entry) pairs preserving result order
    tag_groups    = {}
    length_groups = {}
    for k, v in result.items():
        if v is None:
            continue
        tag_groups.setdefault(v[3], []).append((k, v))
        length_groups.setdefault(len(v[0]), []).append((k, v))

    def kanji_compact(pairs):
        return ''.join(k for k, _ in pairs)

    display_tag_priority = {
        OVERRIDE_TAG: 0, "🌱": 1, "☘️": 2, "🌷": 3,
        OUTPUT_TEXTBOOK_TAG: 4, "📚": 5, "🦉": 7,
    }

    def print_entries(pairs):
        for k, v in sorted(pairs, key=lambda x: display_tag_priority.get(x[1][3], DEFAULT_TAG_PRIORITY)):
            print(f"{v[3]} {k} → {v[0]} ~ {v[1]} {v[2]}")

    tag_labels = {
        OVERRIDE_TAG: "✏️  manual",
        "🌱": "🌱  v3",
        "☘️": "☘️  v3",
        "🌷": "🌷  v3",
        OUTPUT_TEXTBOOK_TAG: "📖  textbook",
        "📚": "📚  v3",
        "🦉": "🦉  v3",
    }

    print(f"\n{'─'*44}")
    print(f"  Kanji processed:   {len(all_kanji)}")
    no_meaning = sum(1 for v in result.values() if v is not None and not v[2])
    no_reading = sum(1 for v in result.values() if v is not None and not v[1])

    print(f"  With word:         {with_word}")
    print(f"  Without word:      {without}")
    print(f"  No meaning:        {no_meaning}")
    print(f"  No reading:        {no_reading}")

    known_tags = set(tag_labels.keys())
    unknown_pairs = [(k, v) for k, v in result.items()
                     if v is not None and v[3] not in known_tags]
    n_unknown = len(unknown_pairs)

    print(f"\n  Tag / source breakdown")
    for tag, label in tag_labels.items():
        n = tag_counts.get(tag, 0)
        pct = n / total * 100 if total else 0
        pairs = tag_groups.get(tag, [])
        if tag == "🦉":
            print(f"    {label}: {n}  ({pct:.1f}%)  {kanji_compact(pairs)}")
            print_entries(pairs)
        else:
            print(f"    {label}: {n}  ({pct:.1f}%)")
        if tag == "📚":
            pct_u = n_unknown / total * 100 if total else 0
            print(f"    🤔  unknown: {n_unknown}  ({pct_u:.1f}%)  {kanji_compact(unknown_pairs)}")
            print_entries(unknown_pairs)

    print(f"\n  Word length")
    for length in sorted(length_counts):
        n = length_counts[length]
        pct = n / total * 100 if total else 0
        if length >= 4:
            pairs = length_groups.get(length, [])
            print(f"    {length} chars: {n}  ({pct:.1f}%)  {kanji_compact(pairs)}")
            print_entries(pairs)
        else:
            print(f"    {length} chars: {n}  ({pct:.1f}%)")

    kc_groups = {}
    for k, v in result.items():
        if v is None:
            continue
        kc_groups.setdefault(kanji_count(v[0]), []).append((k, v))

    print(f"\n  Kanji per word")
    for kc in sorted(kc_counts):
        n = kc_counts[kc]
        pct = n / total * 100 if total else 0
        if kc >= 3:
            pairs = kc_groups.get(kc, [])
            print(f"    {kc} kanji: {n}  ({pct:.1f}%)  {kanji_compact(pairs)}")
            print_entries(pairs)
        else:
            print(f"    {kc} kanji: {n}  ({pct:.1f}%)")

    print(f"{'─'*44}")

    if without:
        no_vocab = [k for k, v in result.items() if v is None]
        print(f"\nNo-word kanji ({without}): {''.join(no_vocab)}")

    print(f"")
    no_meaning = [k for k, v in result.items() if v is not None and not v[2]]
    print(f"No meaning kanji ({len(no_meaning)}): {''.join(no_meaning)}")

    for k, v in result.items():
        if v is not None and not v[2]:
            print(k, v)

    starts_with = [(k, v) for k, v in result.items() if v is not None and v[0].startswith(k)]
    not_starts_with = [(k, v) for k, v in result.items() if v is not None and not v[0].startswith(k)]
    print(f"\n  Words starting with kanji:     {len(starts_with)}")
    print(f"  Words NOT starting with kanji: {len(not_starts_with)}")

    if not_starts_with:
        print(f"\nKanji whose study word does NOT start with it ({len(not_starts_with)}):")
        print(f"  {''.join(k for k, _ in not_starts_with)}")
        print_entries(not_starts_with)

    # --- Overlap check ---
    from collections import defaultdict
    word_to_kanjis = defaultdict(list)
    for k, v in result.items():
        if v:
            word_to_kanjis[v[0]].append(k)
    overlapping = {w: ks for w, ks in word_to_kanjis.items() if len(ks) > 1}
    print(f"\n  Overlapping study words: {len(overlapping)}")
    for w, ks in overlapping.items():
        print(f"    {w}: {''.join(ks)}")

if __name__ == "__main__":
    main()
