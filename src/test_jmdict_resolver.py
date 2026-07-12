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
    KANA_ONLY_MARKER,
)
from sources import load_json

# word → expected ・-joined reading string
GOLDEN_READINGS = {
    # multi-reading homographs (separate entries or kana siblings)
    "空": "そら・から",
    "四": "よん・し",      # readingOrder hint (JMdict lists し first)
    "七": "なな・しち",    # readingOrder hint — overrides/resolver_hints.json
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
    "本": "ほん",          # もと belongs to 元 (its entry's leading form) — not 本
    "一": "いち・ひと",
    "方": "ほう・かた",
}

# word → expected exact meaning string (subset of GOLDEN_READINGS words)
GOLDEN_MEANINGS = {
    "空": "[1] sky, the air, the heavens [2] emptiness, being empty",
    "四": "four, 4",                     # identical [n] blocks collapse
    "一": "one, 1",                      # near-duplicate blocks (one, 1 / one) collapse
    "入る": "to enter, to come in, to go in",  # both readings' senses share "to enter"
    "方": "direction, way, side",
    "語": "word, term · language",       # 2 senses, · U+00B7 separator
    "書く": "to write, to compose, to pen · to draw, to paint",
}

# resolve_fallback cases: rare writings resolve() rejects on purpose.
# word → (kwargs, expected reading or None, expected meaning or None).
# `shipped` is filled in main() from input/filtered_kanji.json.
GOLDEN_FALLBACK = {
    # usually-kana, no common kanji sibling → resolves with the ⚠️ marker
    "諄い": ({}, "くどい",
             "repetitious, long-winded, tedious · heavy (taste), (overly) rich, "
             "strong" + KANA_ONLY_MARKER),
    "亦": ({}, "また",
           "again, once more, once again · also, too, as well" + KANA_ONLY_MARKER),
    "於いて": ({}, "おいて",
               "at (a time or place), in, on · in (a situation, matter, etc.), "
               "on (a point), when it comes to" + KANA_ONLY_MARKER),
    # glyph variant: canonical 充填 uses 填, which we don't ship — no marker
    "充塡": ({"shipped": True}, "じゅうてん",
             "filling (up), replenishing, filling in (a tooth)"),
    # manual override (✏️): human picked the writing, resolve without gates
    "昂ぶる": ({"manual": True}, "たかぶる",
               "to become aroused (of emotions, nerves, etc.), to become excited, "
               "to become stirred up · to be proud, to be haughty, to be pompous"),
    # ひめ's common writing is 姫 (shipped) — 媛 must stay unresolved
    "媛": ({"shipped": True}, None, None),
    # sK search-only form of 渡る — must stay unresolved
    "亘る": ({"shipped": True}, None, None),
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

    shipped = set(load_json("input/filtered_kanji.json", []))
    for word, (kwargs, expected_reading, expected_meaning) in GOLDEN_FALLBACK.items():
        if kwargs.get("shipped"):
            kwargs = dict(kwargs, shipped=shipped)
        result = resolver.resolve_fallback(word, **kwargs)
        got_reading = result["reading"] if result else None
        got_meaning = result["meaning"] if result else None
        if got_reading != expected_reading:
            failures.append(
                f"fallback {word}: expected reading {expected_reading!r}, "
                f"got {got_reading!r}")
        elif got_meaning != expected_meaning:
            failures.append(
                f"fallback {word}: expected meaning {expected_meaning!r}, "
                f"got {got_meaning!r}")

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

    total = (len(GOLDEN_READINGS) + len(GOLDEN_MEANINGS) + len(GOLDEN_FALLBACK)
             + len(GOLDEN_SHAPE))
    if failures:
        print(f"FAIL — {len(failures)} of {total} golden checks:")
        for f in failures:
            print(f"  {f}")
        raise SystemExit(1)
    print(f"OK — all {total} golden checks passed")


if __name__ == "__main__":
    main()
