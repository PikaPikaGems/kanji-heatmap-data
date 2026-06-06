#!/usr/bin/env python3
"""
Task: Better Sample Vocabulary
Selects two sample words per kanji and writes supplementary override files.

Selection rules:
- Word must be >= 2 characters (hiragana included)
- Must contain at least one kanji
- Prefer fewer kanji in word (minimum 1)
- 2-3 chars ideal (no preference between them); 4 okay; 5 allowed; 6+ not allowed

Source priority (tier → fewer kanji → length):
  1. v3 words tagged 🌱
  2. v3 words tagged ☘️
  3. v3 words tagged 🌷
  4. textbook words (raw/kanji-textbook-words/)
  5. v3 words tagged 📚 or other

Sources:
  raw/kanji-words/v3/[kanji].json          → [{w, r, t, j?, k?, e}]
  raw/kanji-textbook-words/[kanji].json    → {kanji: {word: [reading, meaning]}}

Run from the project root: python3 src/algorithmic-kanji-vocab-overrides.py
"""

import json
import os


def resolve_path(path):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    return os.path.join(project_root, path)


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

TEXTBOOK_TAG = '__textbook__'

TAG_PRIORITY = {
    '🌱': 0,
    '☘️': 1,
    '🌷': 2,
    TEXTBOOK_TAG: 3,
    '📚': 4,
    '🦉': 5,
}
DEFAULT_TAG_PRIORITY = 4  # unknown v3 tags treated like 📚


def is_kanji_char(ch):
    code = ord(ch)
    return any(start <= code <= end for start, end in KANJI_RANGES)


def is_japanese_char(ch):
    code = ord(ch)
    return any(start <= code <= end for start, end in JAPANESE_RANGES)


def kanji_count(word):
    return sum(1 for ch in word if is_kanji_char(ch))


def is_all_japanese(word):
    return bool(word) and all(is_japanese_char(ch) for ch in word)


def word_score(word, tag):
    """Lower is better. Tuple for lexicographic comparison."""
    kc = kanji_count(word)
    n = len(word)
    ts = TAG_PRIORITY.get(tag, DEFAULT_TAG_PRIORITY)
    extra_kanji = kc - 1  # 0 = best (exactly 1 kanji)
    length_penalty = 0 if n <= 3 else (1 if n == 4 else 2)  # 2-3 ideal, 4 okay, 5 allowed
    return (ts, extra_kanji, length_penalty)


def is_valid_candidate(word, reading):
    if not word or not reading or reading == '-':
        return False
    if len(word) < 2 or len(word) > 5:
        return False
    if kanji_count(word) < 1:
        return False
    if not is_all_japanese(word):
        return False
    return True


def load_v3_candidates(kanji):
    path = resolve_path(f'raw/kanji-words/v3/{kanji}.json')
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    results = []
    for entry in data:
        w = entry.get('w', '')
        r = entry.get('r', '')
        t = entry.get('t', '')
        e = entry.get('e', '')
        if is_valid_candidate(w, r):
            results.append((w, r, t, e))
    return results


def load_textbook_candidates(kanji):
    path = resolve_path(f'raw/kanji-textbook-words/{kanji}.json')
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    inner = data.get(kanji, {})
    results = []
    for word, val in inner.items():
        if not isinstance(val, list) or len(val) < 1:
            continue
        r = val[0] if len(val) >= 1 else ''
        e = val[1] if len(val) >= 2 else ''
        if is_valid_candidate(word, r):
            results.append((word, r, TEXTBOOK_TAG, e))
    return results


def select_vocab_for_kanji(kanji):
    """Return up to 2 best (word, reading, tag, meaning) tuples for this kanji."""
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

    all_candidates.sort(key=lambda x: word_score(x[0], x[2]))
    return all_candidates[:2]


def main():
    with open(resolve_path('output/kanji_main.json'), encoding='utf-8') as f:
        kanji_main = json.load(f)

    with open(resolve_path('input/vocab_meaning.json'), encoding='utf-8') as f:
        existing_meanings = json.load(f)

    with open(resolve_path('input/vocab_furigana.json'), encoding='utf-8') as f:
        existing_furigana = json.load(f)

    with open(resolve_path('input/kanji_vocab.json'), encoding='utf-8') as f:
        existing_kanji_vocab = json.load(f)
    existing_vocab_words = set(w for words in existing_kanji_vocab.values() for w in words)

    all_kanji = list(kanji_main.keys())

    kanji_vocab_result = {}
    vocab_meaning_result = {}
    vocab_reading_result = {}
    no_furigana_words = []
    no_furigana_seen = set()

    selected_all = []  # (word, tag) for stats

    for kanji in all_kanji:
        selected = select_vocab_for_kanji(kanji)
        if not selected:
            continue

        kanji_vocab_result[kanji] = [w for w, r, t, e in selected]

        for w, r, t, e in selected:
            selected_all.append((w, t))
            if r and r != '-':
                vocab_reading_result[w] = r
            if e and w not in existing_meanings:
                vocab_meaning_result[w] = e
            if w not in existing_furigana and w not in no_furigana_seen:
                no_furigana_words.append(w)
                no_furigana_seen.add(w)

    os.makedirs(resolve_path('overrides'), exist_ok=True)

    def write_json(rel_path, data):
        path = resolve_path(rel_path)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Written: {path} ({len(data)} entries)")

    write_json('overrides/kanji_vocab-algo.json', kanji_vocab_result)
    write_json('overrides/vocab_meaning-algo.json', vocab_meaning_result)
    write_json('overrides/vocab_reading-algo.json', vocab_reading_result)
    write_json('overrides/vocab-with-no-furigana.json', no_furigana_words)

    total = len(selected_all)
    without_vocab = [k for k in all_kanji if k not in kanji_vocab_result]
    with_one  = sum(1 for v in kanji_vocab_result.values() if len(v) == 1)
    with_two  = sum(1 for v in kanji_vocab_result.values() if len(v) >= 2)

    tier_labels = {
        '🌱': '🌱  v3',
        '☘️': '☘️  v3',
        '🌷': '🌷  v3',
        TEXTBOOK_TAG: '📖  textbook',
        '📚': '📚  v3',
        '🦉': '🦉  v3',
    }
    from collections import Counter
    tier_counts  = Counter(t for _, t in selected_all)
    length_counts = Counter(len(w) for w, _ in selected_all)
    kanji_counts  = Counter(kanji_count(w) for w, _ in selected_all)
    new_words = sum(1 for w, _ in selected_all if w not in existing_vocab_words)

    print(f"\n{'─'*40}")
    print(f"  Kanji processed:   {len(all_kanji)}")
    print(f"  With 2 words:      {with_two}")
    print(f"  With 1 word:       {with_one}")
    print(f"  With 0 words:      {len(without_vocab)}")
    print(f"  Total words:       {total}")

    print(f"\n  Source / tier breakdown")
    for tag, label in tier_labels.items():
        n = tier_counts.get(tag, 0)
        print(f"    {label}: {n}  ({n/total*100:.1f}%)")

    print(f"\n  Word length")
    for l in sorted(length_counts):
        print(f"    {l} chars: {length_counts[l]}  ({length_counts[l]/total*100:.1f}%)")

    print(f"\n  Kanji per word")
    for k in sorted(kanji_counts):
        print(f"    {k} kanji: {kanji_counts[k]}  ({kanji_counts[k]/total*100:.1f}%)")

    print(f"\n  Not in input/kanji_vocab.json: {new_words}/{total}  ({new_words/total*100:.1f}%)")
    print(f"{'─'*40}")

    if without_vocab:
        print(f"\nNo-vocab kanji: {''.join(without_vocab)}")


if __name__ == '__main__':
    main()
