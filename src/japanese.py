"""Shared Japanese-text helpers.

Unicode ranges, character classification, and kana/segmentation utilities used
across the kanji-data scripts. Pure functions, no file IO (see sources.py for
data loading).
"""

KANJI_RANGES = [
    (0x4E00, 0x9FFF),    # CJK Unified Ideographs
    (0x3400, 0x4DBF),    # Extension A
    (0x20000, 0x2A6DF),  # Extension B
    (0x2A700, 0x2B73F),  # Extension C
    (0x2B740, 0x2B81F),  # Extension D
    (0x2B820, 0x2CEAF),  # Extension E
    (0x2CEB0, 0x2EBEF),  # Extension F
]

HIRAGANA_RANGE = (0x3040, 0x309F)
KATAKANA_RANGE = (0x30A0, 0x30FF)
JAPANESE_RANGES = KANJI_RANGES + [HIRAGANA_RANGE, KATAKANA_RANGE]


def is_kanji_char(ch):
    code = ord(ch)
    return any(lo <= code <= hi for lo, hi in KANJI_RANGES)


def is_japanese_char(ch):
    code = ord(ch)
    return any(lo <= code <= hi for lo, hi in JAPANESE_RANGES)


def kanji_count(word):
    return sum(1 for ch in word if is_kanji_char(ch))


def is_all_japanese(word):
    """True if `word` is non-empty and every character is kanji/hiragana/katakana."""
    return bool(word) and all(is_japanese_char(ch) for ch in word)


def kata_to_hira(text):
    """Convert katakana characters to hiragana; leave everything else unchanged."""
    result = []
    for ch in text:
        code = ord(ch)
        if 0x30A1 <= code <= 0x30F6:
            result.append(chr(code - 0x60))
        elif ch == "ヴ":
            result.append("ゔ")
        else:
            result.append(ch)
    return "".join(result)


def reading_of_kanji_in_segments(kanji, segments):
    """Return the reading attached to the furigana span containing `kanji`, or None.

    `segments` is a furigana breakdown like [["持", "も"], ["ち"], ["場", "ば"]]
    (kana-only spans have no reading element). Returns None when no kanji span
    contains `kanji` — e.g. jukujikun words lumped into a single whole-word span.
    """
    for seg in segments or []:
        if len(seg) >= 2 and kanji in seg[0]:
            return seg[1]
    return None


def segment_word(word):
    """Split a word into contiguous (text, is_kanji_span) spans.

    Kanji and non-kanji (hiragana, katakana, etc.) runs alternate as separate
    spans, e.g. 持ち場 -> [("持", True), ("ち", False), ("場", True)].
    """
    if not word:
        return []
    spans = []
    current = word[0]
    current_is_kanji = is_kanji_char(word[0])
    for ch in word[1:]:
        k = is_kanji_char(ch)
        if k == current_is_kanji:
            current += ch
        else:
            spans.append((current, current_is_kanji))
            current = ch
            current_is_kanji = k
    spans.append((current, current_is_kanji))
    return spans
