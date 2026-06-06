#!/usr/bin/env python3
"""
Selects one representative study word per kanji.

Constraints:
  - Word must START with the target kanji (first character = kanji)
  - Max 2 kanji characters in the word
  - All characters must be Japanese (hiragana/katakana/kanji)
  - Each kanji gets a unique word (guaranteed by the start-with constraint)

Rule 1 – source priority (lower index wins):
  0. v3 tag 🌱
  1. v3 tag ☘️
  2. v3 tag 🌷
  3. textbook words
  4. v3 tag 📚
  5. v3 tag 🦉

Rule 2 – word quality within a source tier (lower score wins):
  0. single-character word  (the kanji itself)
  1. word with exactly 1 kanji (all other chars are hiragana/katakana)
  2. word with exactly 2 kanji  →  prefer shorter

Sources:
  raw/kanji-words/v3/[kanji].json        → [{w, r, t, j?, k?, e}]
  raw/kanji-textbook-words/[kanji].json  → {kanji: {word: [reading, meaning]}}

Output: output/kanji_study_keywords-algo.json
  { kanji: [word, reading, meaning] }   (null when no valid word found)

Run from project root: python3 src/build-japanese-study-words.py
"""

import json
import os
from collections import Counter

# ---------------------------------------------------------------------------
# Unicode helpers
# ---------------------------------------------------------------------------

KANJI_RANGES = [
    (0x4E00, 0x9FFF),
    (0x3400, 0x4DBF),
    (0x20000, 0x2A6DF),
    (0x2A700, 0x2B73F),
    (0x2B740, 0x2B81F),
    (0x2B820, 0x2CEAF),
    (0x2CEB0, 0x2EBEF),
]

JAPANESE_RANGES = KANJI_RANGES + [
    (0x3040, 0x309F),  # Hiragana
    (0x30A0, 0x30FF),  # Katakana
]


def is_kanji_char(ch):
    code = ord(ch)
    return any(lo <= code <= hi for lo, hi in KANJI_RANGES)


def is_japanese_char(ch):
    code = ord(ch)
    return any(lo <= code <= hi for lo, hi in JAPANESE_RANGES)


def kanji_count(word):
    return sum(1 for ch in word if is_kanji_char(ch))


def is_all_japanese(word):
    return bool(word) and all(is_japanese_char(ch) for ch in word)


# ---------------------------------------------------------------------------
# Scoring / prioritisation
# ---------------------------------------------------------------------------

TEXTBOOK_TAG = "__textbook__"

TAG_PRIORITY = {
    "🌱": 0,
    "☘️": 1,
    "🌷": 2,
    TEXTBOOK_TAG: 3,
    "📚": 4,
    "🦉": 5,
}
DEFAULT_TAG_PRIORITY = 4


def word_score(word, tag):
    """Lower is better. Tuple for lexicographic comparison."""
    ts = TAG_PRIORITY.get(tag, DEFAULT_TAG_PRIORITY)
    n = len(word)
    kc = kanji_count(word)

    if n == 1:
        word_type = 0  # single-char kanji — best
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

def _resolve(rel):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, rel)


def load_v3_candidates(kanji):
    path = _resolve(f"raw/kanji-words/v3/{kanji}.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    results = []
    for entry in data:
        w = entry.get("w", "")
        r = entry.get("r", "")
        t = entry.get("t", "")
        e = entry.get("e", "")
        if is_valid_candidate(w, r, kanji):
            results.append((w, r, t, e))
    return results


def load_textbook_candidates(kanji):
    path = _resolve(f"raw/kanji-textbook-words/{kanji}.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    inner = data.get(kanji, {})
    results = []
    for word, val in inner.items():
        if not isinstance(val, list) or len(val) < 1:
            continue
        r = val[0] if len(val) >= 1 else ""
        e = val[1] if len(val) >= 2 else ""
        if is_valid_candidate(word, r, kanji):
            results.append((word, r, TEXTBOOK_TAG, e))
    return results


def load_textbook_candidates_fallback(kanji):
    """Relaxed: word only needs to contain the kanji, not start with it."""
    path = _resolve(f"raw/kanji-textbook-words/{kanji}.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    inner = data.get(kanji, {})
    results = []
    for word, val in inner.items():
        if not isinstance(val, list) or len(val) < 1:
            continue
        r = val[0] if len(val) >= 1 else ""
        e = val[1] if len(val) >= 2 else ""
        if is_valid_fallback_candidate(word, r, kanji):
            results.append((word, r, TEXTBOOK_TAG, e))
    return results


OUTPUT_TEXTBOOK_TAG = "📖"


def select_word_for_kanji(kanji):
    """Return the best [word, reading, meaning, tag] for this kanji, or None."""
    v3 = load_v3_candidates(kanji)
    textbook = load_textbook_candidates(kanji)

    seen = set()
    all_candidates = []
    for entry in v3:
        if entry[0] not in seen:
            seen.add(entry[0])
            all_candidates.append(entry)
    for entry in textbook:
        if entry[0] not in seen:
            seen.add(entry[0])
            all_candidates.append(entry)

    if not all_candidates:
        # (59): 宏雰紘稔輔肇亨喬槙峻蕉欣禎斐尭馨彬匡欽佑惇脩甫暉允瑛皓洸怜悌侃侑琳瑚瑳瑶詢洵倖誼諄晏莉晨碩熙燎燦滉蓉恕迪綸麟柾裟頌眸伶
        fallback = load_textbook_candidates_fallback(kanji)
        if not fallback:
            return None
        fallback.sort(key=lambda x: word_score(x[0], x[2]))
        w, r, t, e = fallback[0]
        return [w, r, e, OUTPUT_TEXTBOOK_TAG]

    all_candidates.sort(key=lambda x: word_score(x[0], x[2]))
    w, r, t, e = all_candidates[0]
    display_tag = OUTPUT_TEXTBOOK_TAG if t == TEXTBOOK_TAG else t
    return [w, r, e, display_tag]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_kanji_list():
    with open(_resolve("input/merged_kanji.json"), encoding="utf-8") as f:
        merged = json.load(f)
    with open(_resolve("overrides/kanji_to_remove.json"), encoding="utf-8") as f:
        to_remove = json.load(f)
    remove_set = set(to_remove.get("data", []))
    return [k for k in merged.keys() if k not in remove_set]


def main():
    all_kanji = load_kanji_list()

    result = {}
    selected_flat = []  # (word, kanji_count, tag_tier) for stats

    for kanji in all_kanji:
        entry = select_word_for_kanji(kanji)
        result[kanji] = entry

        if entry:
            selected_flat.append(entry)

    out_path = _resolve("overrides/japanese_study_words-algo.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"Written: {out_path}")

    # --- Stats ---
    total = len(selected_flat)
    with_word = sum(1 for v in result.values() if v is not None)
    without   = sum(1 for v in result.values() if v is None)

    words         = [e[0] for e in selected_flat]
    tags          = [e[3] for e in selected_flat]
    length_counts = Counter(len(w) for w in words)
    kc_counts     = Counter(kanji_count(w) for w in words)
    tag_counts    = Counter(tags)

    tag_labels = {
        "🌱": "🌱  v3",
        "☘️": "☘️  v3",
        "🌷": "🌷  v3",
        OUTPUT_TEXTBOOK_TAG: "📖  textbook",
        "📚": "📚  v3",
        "🦉": "🦉  v3",
    }

    print(f"\n{'─'*44}")
    print(f"  Kanji processed:   {len(all_kanji)}")
    print(f"  With word:         {with_word}")
    print(f"  Without word:      {without}")

    print(f"\n  Tag / source breakdown")
    for tag, label in tag_labels.items():
        n = tag_counts.get(tag, 0)
        pct = n / total * 100 if total else 0
        print(f"    {label}: {n}  ({pct:.1f}%)")

    print(f"\n  Word length")
    for length in sorted(length_counts):
        n = length_counts[length]
        pct = n / total * 100 if total else 0
        print(f"    {length} chars: {n}  ({pct:.1f}%)")

    print(f"\n  Kanji per word")
    for kc in sorted(kc_counts):
        n = kc_counts[kc]
        pct = n / total * 100 if total else 0
        print(f"    {kc} kanji: {n}  ({pct:.1f}%)")

    print(f"{'─'*44}")

    if without:
        no_vocab = [k for k, v in result.items() if v is None]
        print(f"\nNo-word kanji ({without}): {''.join(no_vocab)}")


if __name__ == "__main__":
    main()
