#!/usr/bin/env python3
"""
Generates overrides/vocab_furigana-algo.json from src/overrides/vocab-with-no-furigana.json.

For each word, uses JMdict data to build a furigana breakdown matching the format
of input/vocab_furigana.json:
  "word": [["kanji_span", "reading"], ["kana_span"], ...]

Priority for obtaining the furigana:
  1. input/jmdict-furigana-map.json (JmdictFurigana) – correct per-kanji segments
  2. JMdict (input/scriptin-jmdict-eng.json) reading + regex alignment – fallback
  3. JMdict per-kanji-span lookup – for suffixed headwords JMdict lists only as the
     stem (必須の → 必須 + の, 表彰する → 表彰 + する)

Words covered by none of these are written as [[word]] (no reading) and reported
so they can be hand-curated into overrides/vocab_furigana.json (the authoritative
manual override applied at build time).

The map (1) is essential: the alignment fallback cannot split a run of adjacent
kanji (e.g. 天気), so it would otherwise lump the whole reading onto one span
(天気 → てんき) instead of 天 → てん, 気 → き. The map is validated against the
hand-curated input/vocab_furigana.json (100% agreement) before being trusted.

For the alignment fallback the reading is aligned to the word by treating kana spans
as literal anchors and kanji spans as regex capture groups, then matched against the
full hiragana reading.

Run from the project root: python3 src/generate_furigana_algo.py
"""

import json
import re

from sources import resolve_path, load_json
from japanese import is_kanji_char, kata_to_hira, segment_word

# NOTE: the full JMdict dump (108MB) is only needed for the words NOT covered by
# input/jmdict-furigana-map.json. It is loaded lazily inside main() so the common
# case (everything in the map) runs without it.


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


def load_scriptin_readings():
    """Build a kanji-form → hiragana reading lookup from input/scriptin-jmdict-eng.json.

    For each JMdict entry, each kanji form is mapped to the first kana form that
    applies to it (appliesToKanji). First entry wins for words listed in several
    entries, matching JMdict's ordering (most common entry first).
    """
    data = load_json("input/scriptin-jmdict-eng.json", {})
    lookup = {}
    for entry in data.get("words", []):
        kana_forms = entry.get("kana", [])
        for kanji_form in entry.get("kanji", []):
            text = kanji_form.get("text")
            if not text or text in lookup:
                continue
            for kana in kana_forms:
                applies = kana.get("appliesToKanji", ["*"])
                if "*" in applies or text in applies:
                    lookup[text] = kata_to_hira(kana.get("text", ""))
                    break
    return lookup


def generate_furigana(word, readings):
    """
    Generate the furigana segment list for a word.

    Returns a list of:
      ["kanji_chars", "hiragana_reading"]  – for kanji spans
      ["kana_chars"]                        – for kana spans (no furigana needed)
    Falls back to [[word, reading]] (or [[word]] with no reading found) if the
    word cannot be segmented.
    """
    spans = segment_word(word)

    # No kanji at all — nothing to annotate
    if not any(k for _, k in spans):
        return [[word]]

    # Whole-word JMdict reading aligned across the spans
    reading = readings.get(word)
    if reading:
        aligned = align_reading(word, reading)
        if aligned is not None:
            return aligned

    # Per-span lookup: JMdict often lists only the stem of a suffixed headword
    # (必須の → 必須, 表彰する → 表彰), so look up each kanji span on its own.
    parts = []
    for text, kanji_span in spans:
        if kanji_span:
            span_reading = readings.get(text)
            if span_reading is None:
                parts = None
                break
            parts.append([text, span_reading])
        else:
            parts.append([text])
    if parts is not None:
        return parts

    # No usable segmentation: whole word with its reading, or bare if none found
    if reading:
        return [[word, reading]]
    return [[word]]


def pick_map_segments(variants, want_reading=None):
    """Pick furigana segments from a JmdictFurigana entry ({reading: segments}).

    Prefer the variant whose reading matches the word's known reading (handles words
    with multiple readings); otherwise take the first. Segments are already in the
    vocab_furigana format, so they are returned as-is.
    """
    if want_reading:
        if want_reading in variants:
            return variants[want_reading]
        want_h = kata_to_hira(want_reading)
        for reading, segments in variants.items():
            if kata_to_hira(reading) == want_h:
                return segments
    return next(iter(variants.values()))


def is_lumped_multikanji(segments):
    """True if furigana is a single whole-word block over >=2 kanji (天気 → てんき),
    which is what the alignment fallback wrongly produces for pure-kanji compounds."""
    return (
        len(segments) == 1
        and len(segments[0]) == 2
        and sum(1 for ch in segments[0][0] if is_kanji_char(ch)) >= 2
    )


def main():
    words = load_json("overrides/vocab-with-no-furigana.json", [])
    furigana_map = load_json("input/jmdict-furigana-map.json")
    word_readings = load_json("overrides/vocab_reading-algo.json")  # disambiguate multi-reading words

    out_path = resolve_path("overrides/vocab_furigana-algo.json")
    result = load_json("overrides/vocab_furigana-algo.json")

    # Repair pass: replace existing lumped whole-word entries (天気 → てんき) with the
    # map's correct per-kanji segmentation. Jukujikun (lumped in the map too) and
    # already-correct entries are left untouched.
    repaired = 0
    for word, segments in list(result.items()):
        if is_lumped_multikanji(segments) and word in furigana_map:
            fixed = pick_map_segments(furigana_map[word], word_readings.get(word))
            if fixed != segments:
                result[word] = fixed
                repaired += 1

    # Classify the still-unprocessed words by source.
    todo = [w for w in words if w not in result]
    from_map = 0
    uncovered = []
    for word in todo:
        if word in furigana_map:
            result[word] = pick_map_segments(furigana_map[word], word_readings.get(word))
            from_map += 1
        else:
            uncovered.append(word)

    # Only the leftover words need the full JMdict dump — load it lazily.
    fallbacks = []
    if uncovered:
        print(f"Loading JMdict for {len(uncovered)} uncovered words...")
        readings = load_scriptin_readings()
        for word in uncovered:
            segments = generate_furigana(word, readings)
            result[word] = segments
            if is_lumped_multikanji(segments) or (
                segments == [[word]] and any(is_kanji_char(ch) for ch in word)
            ):
                fallbacks.append(word)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    print(f"\nWritten: {out_path} ({len(result)} entries)")
    print(f"  repaired lumped entries via map: {repaired}")
    print(f"  new: from map {from_map}, via JMdict lookup {len(uncovered)}")
    if fallbacks:
        print(f"  whole-word / no-reading fallbacks (need manual furigana): {len(fallbacks)}")
        for word in fallbacks:
            print(f"    {word}")


if __name__ == "__main__":
    main()
