#!/usr/bin/env python3
"""
Generates overrides/vocab_furigana-algo.json from src/overrides/vocab-with-no-furigana.json.

For each word, uses GiNZA (spacy + sudachi) and JMdict to build a furigana breakdown
matching the format of input/vocab_furigana.json:
  "word": [["kanji_span", "reading"], ["kana_span"], ...]

Priority for obtaining the furigana:
  1. raw/ai-generated/vocab-furigana-ai.json    – hand-curated overrides
  2. input/jmdict-furigana-map.json (JmdictFurigana) – correct per-kanji segments
  3. JMdict (jamdict) reading + regex alignment  – fallback
  4. GiNZA / SudachiPy morphological analysis    – fallback

The map (2) is essential: the alignment fallback cannot split a run of adjacent
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

# NOTE: spacy / ginza / jamdict are heavy and only needed for the words NOT covered
# by input/jmdict-furigana-map.json. They are imported lazily inside main() so the
# common case (everything in the map) runs without them.


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
    """Return the first kana reading from JMdict, or None if not found or unavailable."""
    try:
        result = jam.lookup(word)
    except Exception:
        return None
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
    ai_furigana = load_json("raw/ai-generated/vocab-furigana-ai.json")
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
    from_ai = from_map = 0
    needs_ginza = []
    for word in todo:
        if word in ai_furigana:
            result[word] = ai_furigana[word]
            from_ai += 1
        elif word in furigana_map:
            result[word] = pick_map_segments(furigana_map[word], word_readings.get(word))
            from_map += 1
        else:
            needs_ginza.append(word)

    # Only the leftover words need the heavy morphological tooling — import it lazily.
    fallbacks = []
    if needs_ginza:
        print(f"Loading GiNZA + JMdict for {len(needs_ginza)} uncovered words...")
        import spacy
        import ginza  # noqa: F401  — registers the ja_ginza pipeline as a side effect
        from jamdict import Jamdict

        nlp = spacy.load("ja_ginza")
        jam = Jamdict()
        for i, word in enumerate(needs_ginza):
            if i % 200 == 0:
                print(f"  {i}/{len(needs_ginza)}...")
            try:
                segments = generate_furigana(word, nlp, jam)
                result[word] = segments
                if is_lumped_multikanji(segments):
                    fallbacks.append(word)
            except Exception as exc:
                print(f"  ERROR {word!r}: {exc}")
                result[word] = [[word]]

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    print(f"\nWritten: {out_path} ({len(result)} entries)")
    print(f"  repaired lumped entries via map: {repaired}")
    print(f"  new: from map {from_map}, from ai {from_ai}, via GiNZA {len(needs_ginza)}")
    if fallbacks:
        print(f"  GiNZA whole-word fallbacks (uncovered, may need manual furigana): {len(fallbacks)}")


if __name__ == "__main__":
    main()
