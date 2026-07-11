#!/usr/bin/env python3
"""Golden tests for jmdict_resolver against hand-checked readings/meanings.

Every case below was verified by hand (2026-07-11) — they encode the product
decisions for representative study words: which reading leads, when a second
reading is shown, and the meaning string shapes. If a JMdict data update breaks
one, decide whether the data or the heuristic changed and update deliberately.

Run from project root: python3 src/test_jmdict_resolver.py
"""

from jmdict_resolver import (
    JmdictResolver,
    CLASS_VERB,
    CLASS_ADJECTIVE,
    CLASS_OTHER,
)

# word → expected ・-joined reading string
GOLDEN_READINGS = {
    # multi-reading homographs (separate entries or kana siblings)
    "空": "そら・から",
    "四": "よん・し",      # PREFERRED_FIRST_KANA (JMdict lists し first)
    "七": "なな・しち",    # PREFERRED_FIRST_KANA
    "九": "きゅう・く",
    "入る": "はいる・いる",
    "前": "まえ・ぜん",
    "毎": "ごと・まい",
    "今日": "きょう・こんにち",  # gikun readings must not be filtered out
    "明日": "あした・あす",
    "昨日": "きのう・さくじつ",
    # single-reading: the wrong-reading regressions this resolver exists to fix
    "書": "しょ",          # not ふみ (literary "form" entry)
    "字": "じ",            # not あざ (1-sense "section of village")
    "語": "ご",
    "高い": "たかい",
    "大きい": "おおきい",
    "新しい": "あたらしい",
    "小さい": "ちいさい",
    "同じ": "おなじ",
    "会う": "あう",
    "分かる": "わかる",
    "語る": "かたる",
    "書く": "かく",
    "田舎": "いなか",
}

# word → expected exact meaning string (subset of GOLDEN_READINGS words)
GOLDEN_MEANINGS = {
    "空": "[1] sky, the air, the heavens [2] emptiness, being empty",
    "四": "four, 4",                     # identical [n] blocks collapse
    "語": "word, term · language",       # 2 senses, · U+00B7 separator
    "書く": "to write, to compose, to pen · to draw, to paint",
}

# word → (word_class, standalone)
GOLDEN_SHAPE = {
    "書く": (CLASS_VERB, True),
    "分かる": (CLASS_VERB, True),
    "高い": (CLASS_ADJECTIVE, True),
    "同じ": (CLASS_ADJECTIVE, True),
    "空": (CLASS_OTHER, True),
    "高": (CLASS_OTHER, True),    # 高/たか is a real (if weak) standalone noun
    "新": (None, False),          # 新/しん leads with a pref sense — not standalone
    "同": (None, False),          # 同/どう likewise
}


def main():
    resolver = JmdictResolver()
    failures = []

    for word, expected in GOLDEN_READINGS.items():
        result = resolver.resolve(word)
        got = result["reading"] if result else None
        if got != expected:
            failures.append(f"reading {word}: expected {expected!r}, got {got!r}")

    for word, expected in GOLDEN_MEANINGS.items():
        result = resolver.resolve(word)
        got = result["meaning"] if result else None
        if got != expected:
            failures.append(f"meaning {word}: expected {expected!r}, got {got!r}")

    for word, (expected_class, expected_standalone) in GOLDEN_SHAPE.items():
        result = resolver.resolve(word)
        if result is None:
            failures.append(f"shape {word}: no JMdict resolution at all")
            continue
        if expected_class is not None and result["word_class"] != expected_class:
            failures.append(
                f"shape {word}: expected class {expected_class}, "
                f"got {result['word_class']}")
        if result["standalone"] != expected_standalone:
            failures.append(
                f"shape {word}: expected standalone={expected_standalone}, "
                f"got {result['standalone']}")

    total = len(GOLDEN_READINGS) + len(GOLDEN_MEANINGS) + len(GOLDEN_SHAPE)
    if failures:
        print(f"FAIL — {len(failures)} of {total} golden checks:")
        for f in failures:
            print(f"  {f}")
        raise SystemExit(1)
    print(f"OK — all {total} golden checks passed")


if __name__ == "__main__":
    main()
