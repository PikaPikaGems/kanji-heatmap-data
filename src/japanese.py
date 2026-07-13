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


# Corpus word lists contain phrase fragments that pass every structural check:
# a demonstrative glued to a noun (この人, その様) and a standalone word with a
# trailing particle (今も, 常に, 事になる). Both selection algorithms reject them
# via the two helpers below — a study/sample word must be a word, not a word
# plus grammar.

# Kana prefixes that glue a modifier onto a noun without making a new word:
# demonstratives (この人, その様) and the bare adjective いい (いい人, いい子).
FRAGMENT_PREFIXES = (
    "この", "その", "あの", "どの", "こんな", "そんな", "あんな", "どんな",
    "いい",
)

# Trailing particle chunks (longest first, so になる wins over に). Deliberately
# NOT here: か (誰か is a real word), ば (conditional, 例えば), い (adjective
# okurigana, 赤い/高い), bare ない (少ない/危ない are real adjectives — only the
# particle+ない compounds がない/もない/でもない are safe to match).
PARTICLE_TAILS = (
    "でもない", "ではない", "じゃない",
    "になる", "にする", "となる", "とする", "がある", "もある", "がない", "もない",
    "にでも", "には", "にも", "とも", "でも", "から", "まで", "など", "って", "たち",
    "に", "も", "は", "が", "を", "と", "で", "へ", "や", "の", "て",
)


def particle_attached_stem(word):
    """The all-kanji stem of a word that is just kanji + a trailing particle chunk
    (常に → 常, 事になる → 事, 本当に → 本当), or None when the word isn't shaped
    like that (高い, 例えば, 神様). Shape check only — the caller decides whether
    the stem is a real standalone word (常/つね yes → 常に is 常+に; 特 is only a
    prefix → 特に is a genuine adverb)."""
    for tail in PARTICLE_TAILS:
        if word.endswith(tail):
            stem = word[: -len(tail)]
            if stem and all(is_kanji_char(c) for c in stem):
                return stem
            return None
    return None


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


RENDAKU = {
    'が': 'か', 'ぎ': 'き', 'ぐ': 'く', 'げ': 'け', 'ご': 'こ',
    'ざ': 'さ', 'じ': 'し', 'ず': 'す', 'ぜ': 'せ', 'ぞ': 'そ',
    'だ': 'た', 'ぢ': 'ち', 'づ': 'つ', 'で': 'て', 'ど': 'と',
    'ば': 'は', 'び': 'ひ', 'ぶ': 'ふ', 'べ': 'へ', 'ぼ': 'ほ',
    'ぱ': 'は', 'ぴ': 'ひ', 'ぷ': 'ふ', 'ぺ': 'へ', 'ぽ': 'ほ',
}
GEMINATING_MORA = set('つちくき')


def _derendaku(reading):
    """Devoice the first kana (連濁): が→か, ど→と. Leaves unvoiced readings alone."""
    return RENDAKU.get(reading[0], reading[0]) + reading[1:] if reading else reading


def _gemination_equivalent(a, b):
    """True if one reading is the gemination (促音) of the other: げっ↔げつ, きっ↔き.

    The contracted form ends in っ; the base ends in the same stem, optionally plus a
    geminating mora (つ/ち/く/き). Only fires when one side ends in っ, so genuinely
    distinct readings (が vs かく) are never collapsed.
    """
    if not a.endswith('っ'):
        a, b = b, a
    if not a.endswith('っ'):
        return False
    stem = a[:-1]
    return b == stem or any(b == stem + mora for mora in GEMINATING_MORA)


def readings_equivalent(r1, r2):
    """True if two kanji readings are phonologically the same once rendaku (連濁) and
    gemination (促音) are accounted for — so げつ/げっ (月曜/月謝) and と/ど (土地/土曜)
    count as one reading, while genuinely distinct readings (画: が/かく) stay apart."""
    if not r1 or not r2:
        return False
    if r1 == r2:
        return True
    d1, d2 = _derendaku(r1), _derendaku(r2)
    return d1 == d2 or _gemination_equivalent(d1, d2)


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
