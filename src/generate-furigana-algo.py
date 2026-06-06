#!/usr/bin/env python3
"""
Generates overrides/vocab_furigana-algo.json from src/overrides/vocab-with-no-furigana.json.

For each word, uses GiNZA (spacy + sudachi) and JMdict to build a furigana breakdown
matching the format of input/vocab_furigana.json:
  "word": [["kanji_span", "reading"], ["kana_span"], ...]

Priority for obtaining the reading:
  1. JMdict (jamdict) – most reliable for dictionary headwords
  2. GiNZA / SudachiPy – morphological analysis fallback

The reading is aligned to the word by treating kana spans as literal anchors and
kanji spans as regex capture groups, then matched against the full hiragana reading.

Run from the project root: python3 src/generate-furigana-algo.py
"""

import json
import os
import re

import spacy
import ginza
from sudachipy import dictionary
from jamdict import Jamdict
from spacy.tokens import Token


KANJI_RANGES = [
    (0x4E00, 0x9FFF),
    (0x3400, 0x4DBF),
    (0x20000, 0x2A6DF),
    (0x2A700, 0x2B73F),
    (0x2B740, 0x2B81F),
    (0x2B820, 0x2CEAF),
    (0x2CEB0, 0x2EBEF),
]


def resolve_path(path):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    return os.path.join(project_root, path)


def is_kanji(ch):
    code = ord(ch)
    return any(s <= code <= e for s, e in KANJI_RANGES)


def kata_to_hira(text):
    """Convert katakana characters to hiragana."""
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


def segment_word(word):
    """
    Split word into contiguous spans of (text, is_kanji_span).
    Kanji and non-kanji (hiragana, katakana, etc.) alternate as separate spans.
    """
    if not word:
        return []
    spans = []
    current = word[0]
    current_is_kanji = is_kanji(word[0])
    for ch in word[1:]:
        k = is_kanji(ch)
        if k == current_is_kanji:
            current += ch
        else:
            spans.append((current, current_is_kanji))
            current = ch
            current_is_kanji = k
    spans.append((current, current_is_kanji))
    return spans


def align_reading(word, reading):
    """
    Align a full hiragana reading to a mixed kanji/kana word using regex anchoring.

    Kana spans in the word are treated as literal anchors in the regex; kanji spans
    become capture groups. Returns a list of segments:
      - [kanji_span, matched_reading]  for each kanji span
      - [kana_span]                    for each kana span
    Returns None if alignment fails.
    """
    spans = segment_word(word)
    if not spans:
        return None

    # Pure kana word — no furigana needed
    if not any(k for _, k in spans):
        return [[word]]

    pattern_parts = []
    for text, kanji_span in spans:
        if kanji_span:
            pattern_parts.append("(.+?)")
        else:
            pattern_parts.append(re.escape(kata_to_hira(text)))

    match = re.fullmatch("".join(pattern_parts), kata_to_hira(reading))
    if not match:
        return None

    result = []
    group_idx = 1
    for text, kanji_span in spans:
        if kanji_span:
            result.append([text, match.group(group_idx)])
            group_idx += 1
        else:
            result.append([text])
    return result


def ginza_reading(nlp, word):
    """Concatenate per-token readings (hiragana) from GiNZA for the given word."""
    doc = nlp(word)
    parts = []
    for token in doc:
        readings = token.morph.get("Reading")
        if readings:
            parts.append(kata_to_hira(readings[0]))
        else:
            # For tokens with no Reading morph (e.g. punctuation, unknown), keep as-is
            parts.append(kata_to_hira(token.text))
    return "".join(parts)


def jamdict_reading(jam, word):
    """Return the first kana reading from JMdict, or None if not found."""
    result = jam.lookup(word)
    if result and result.entries:
        for entry in result.entries:
            if entry.kana_forms:
                return kata_to_hira(entry.kana_forms[0].text)
    return None


def generate_furigana(word, nlp, jam):
    """
    Generate the furigana segment list for a word.

    Returns a list of:
      ["kanji_chars", "hiragana_reading"]  – for kanji spans
      ["kana_chars"]                        – for kana spans (no furigana needed)
    Falls back to [[word, reading]] if alignment cannot be determined.
    """
    spans = segment_word(word)

    # No kanji at all — nothing to annotate
    if not any(k for _, k in spans):
        return [[word]]

    jm = jamdict_reading(jam, word)
    gz = ginza_reading(nlp, word)

    for reading in (jm, gz):
        if reading:
            aligned = align_reading(word, reading)
            if aligned is not None:
                return aligned

    # Alignment failed for both sources: return whole word with best available reading
    reading = jm or gz or word
    return [[word, kata_to_hira(reading)]]


def main():
    print("Loading GiNZA model...")
    nlp = spacy.load("ja_ginza")

    print("Loading JMdict...")
    jam = Jamdict()

    words_path = resolve_path("src/overrides/vocab-with-no-furigana.json")
    with open(words_path, encoding="utf-8") as f:
        words = json.load(f)

    print(f"Processing {len(words)} words...")

    result = {}
    fallbacks = []

    for i, word in enumerate(words):
        if i % 200 == 0:
            print(f"  {i}/{len(words)}...")
        try:
            segments = generate_furigana(word, nlp, jam)
            result[word] = segments
            # Track words that fell back to whole-word grouping
            if len(segments) == 1 and len(segments[0]) == 2 and is_kanji(segments[0][0][0]):
                spans = segment_word(word)
                if len(spans) == 1:
                    fallbacks.append(word)
        except Exception as exc:
            print(f"  ERROR {word!r}: {exc}")
            result[word] = [[word]]

    out_path = resolve_path("overrides/vocab_furigana-algo.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    print(f"\nWritten: {out_path} ({len(result)} entries)")
    if fallbacks:
        print(f"Whole-word fallbacks ({len(fallbacks)} — may need manual review):")
        for w in fallbacks[:30]:
            print(f"  {w}")
        if len(fallbacks) > 30:
            print(f"  ... and {len(fallbacks) - 30} more")


if __name__ == "__main__":
    main()
