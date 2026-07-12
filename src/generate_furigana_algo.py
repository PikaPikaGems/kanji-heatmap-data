#!/usr/bin/env python3
"""
Generates overrides/vocab_furigana-algo.json: the algorithm's furigana for EVERY
shipped sample word.

Per the overrides convention, this -algo file is complete and self-contained — it
never looks at the hand-written overrides/vocab_furigana.json. The final build
(kanji_load.dump_all_vocab_furigana) layers that manual file ON TOP of this one
(human wins), and aborts if a word is covered by neither.

This script is the ONLY place furigana is generated or a reading variant is picked.

The word set is computed here exactly as the final build computes it: for each kanji
in input/filtered_kanji.json, up to two sample words by source priority
(overrides/kanji_vocab.json → overrides/kanji_vocab-algo.json → input/kanji_vocab.json;
see build_helpers.get_words). Entries for words no longer shipped are pruned, so this
file always mirrors what the build needs.

Furigana format matches output/vocab_furigana.json:
  "word": [["kanji_span", "reading"], ["kana_span"], ...]

Priority for obtaining the furigana:
  1. input/jmdict-furigana-map.json (JmdictFurigana) – correct per-kanji segments.
     Among a word's reading variants the one matching overrides/vocab_reading-algo.json
     is preferred (words like 上手 have several readings; the naive first pick is
     how じょうて once shipped instead of じょうず).
  2. JMdict (input/scriptin-jmdict-eng.json) reading + regex alignment – fallback
  3. JMdict per-kanji-span lookup – for suffixed headwords JMdict lists only as the
     stem (必須の → 必須 + の, 表彰する → 表彰 + する)

Words covered by none of these are written as [[word]] (no reading) and reported
so they can be hand-curated into overrides/vocab_furigana.json. Also reported:
entries whose reading disagrees with overrides/vocab_reading-algo.json (mostly
jukujikun the map can only lump, and proper nouns the map lacks). Words already
covered by the manual override are excluded from both reports — they're curated.

The map (1) is essential: the alignment fallback cannot split a run of adjacent
kanji (e.g. 天気), so it would otherwise lump the whole reading onto one span
(天気 → てんき) instead of 天 → てん, 気 → き.

For the alignment fallback the reading is aligned to the word by treating kana spans
as literal anchors and kanji spans as regex capture groups, then matched against the
full hiragana reading.

Run from the project root: python3 src/generate_furigana_algo.py
"""

import json
import re

import kanji_load
from build_helpers import get_words
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


def segments_reading(segments):
    """The full hiragana reading a furigana breakdown implies (kana spans included)."""
    return kata_to_hira("".join(s[1] if len(s) == 2 else s[0] for s in segments))


def shipped_sample_words():
    """The exact word set the final build ships furigana for: up to two sample words
    per kanji in input/filtered_kanji.json (see build_helpers.get_words)."""
    kanji_data = kanji_load.load_filtered_kanji_data()
    manual_vocab = kanji_load.load_vocab_override()
    algo_vocab = kanji_load.load_vocab_algo_override()
    automated_vocab = kanji_load.load_automated_kanji_vocab()

    words = set()
    for kanji in kanji_data:
        words.update(get_words(kanji, manual_vocab, algo_vocab, automated_vocab))
    return words


def main():
    furigana_map = load_json("input/jmdict-furigana-map.json")
    word_readings = load_json("overrides/vocab_reading-algo.json")  # disambiguate multi-reading words

    needed = sorted(shipped_sample_words())

    out_path = resolve_path("overrides/vocab_furigana-algo.json")
    cache = load_json("overrides/vocab_furigana-algo.json")
    result = {w: cache[w] for w in needed if w in cache}
    pruned = len(cache) - len(result)

    # Repair pass 1: replace lumped whole-word entries (天気 → てんき) with the map's
    # correct per-kanji segmentation. Jukujikun (lumped in the map too) and
    # already-correct entries are left untouched.
    repaired_lumped = 0
    for word, segments in list(result.items()):
        if is_lumped_multikanji(segments) and word in furigana_map:
            fixed = pick_map_segments(furigana_map[word], word_readings.get(word))
            if fixed != segments:
                result[word] = fixed
                repaired_lumped += 1

    # Repair pass 2: cached entries whose reading contradicts the word's intended
    # reading (overrides/vocab_reading-algo.json) are re-picked from the map when it
    # has a variant with that reading (e.g. a stale 竜馬 → りょうま over りゅうめ).
    repaired_reading = 0
    for word, segments in list(result.items()):
        want = word_readings.get(word)
        if not want or segments_reading(segments) == kata_to_hira(want):
            continue
        if word in furigana_map:
            fixed = pick_map_segments(furigana_map[word], want)
            if fixed != segments and segments_reading(fixed) == kata_to_hira(want):
                result[word] = fixed
                repaired_reading += 1

    # Generate the words not yet covered.
    todo = [w for w in needed if w not in result]
    from_map = 0
    uncovered = []
    for word in todo:
        if word in furigana_map:
            result[word] = pick_map_segments(furigana_map[word], word_readings.get(word))
            from_map += 1
        else:
            uncovered.append(word)

    # Only the leftover words need the full JMdict dump — load it lazily.
    if uncovered:
        print(f"Loading JMdict for {len(uncovered)} uncovered words...")
        readings = load_scriptin_readings()
        for word in uncovered:
            result[word] = generate_furigana(word, readings)

    result = {w: result[w] for w in needed}  # sorted key order for stable diffs

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    print(f"\nWritten: {out_path} ({len(result)} entries)")
    print(f"  pruned entries no longer shipped: {pruned}")
    print(f"  repaired: lumped via map {repaired_lumped}, wrong reading via map {repaired_reading}")
    print(f"  new: from map {from_map}, via JMdict lookup {len(uncovered)}")

    # Quality report over the whole file: what still needs a human eye
    # (candidates for overrides/vocab_furigana.json). Words that manual file
    # already covers are someone's deliberate call — skip them.
    manual_furigana = load_json("overrides/vocab_furigana.json")
    bare = [w for w in result
            if w not in manual_furigana
            and result[w] == [[w]] and any(is_kanji_char(ch) for ch in w)]
    mismatched = [
        w for w in result
        if w not in manual_furigana
        and word_readings.get(w)
        and segments_reading(result[w]) != kata_to_hira(word_readings[w])
    ]
    if bare:
        print(f"  no reading found (need manual furigana): {len(bare)}")
        print(f"    {' '.join(bare)}")
    if mismatched:
        print(f"  reading differs from vocab_reading-algo (jukujikun lumps / proper nouns / check by hand): {len(mismatched)}")
        for w in mismatched:
            print(f"    {w}: {segments_reading(result[w])} vs intended {word_readings[w]}")


if __name__ == "__main__":
    main()
