#!/usr/bin/env python3
"""
Furigana generation for shipped sample words.

The final build (kanji_load.dump_all_vocab_furigana) is the only caller that ships
furigana: it generates algo furigana here, then layers overrides/vocab_furigana.json
on top (human wins), and aborts if a word is covered by neither.

This module is the ONLY place furigana is generated or a reading variant is picked.

Furigana format matches output/vocab_furigana.json:
  "word": [["kanji_span", "reading"], ["kana_span"], ...]

Priority for obtaining the furigana:
  1. input/jmdict-furigana-map.json (JmdictFurigana) – correct per-kanji segments.
     Among a word's reading variants the one matching a reading hint is preferred
     (words like 上手 have several readings; the naive first pick is how じょうて
     once shipped instead of じょうず). Hints come from freq-ranks other_forms kana,
     falling back to JMdict's primary reading — the same signals the sample-vocab
     algo uses when it records a candidate reading.
  2. JMdict (input/scriptin-jmdict-eng.json) reading + regex alignment – fallback
  3. JMdict per-kanji-span lookup – for suffixed headwords JMdict lists only as the
     stem (必須の → 必須 + の, 表彰する → 表彰 + する)

Words covered by none of these are returned as [[word]] (no reading) so the final
build can fail loudly (or a human can pin them in overrides/vocab_furigana.json).

The map (1) is essential: the alignment fallback cannot split a run of adjacent
kanji (e.g. 天気), so it would otherwise lump the whole reading onto one span
(天気 → てんき) instead of 天 → てん, 気 → き.

Optional CLI (diagnostics only — does not write a cache):
  python3 src/generate_furigana_algo.py
"""

import csv
import functools
import glob
import re

from sources import resolve_path, load_json, load_jmdict
from japanese import is_kanji_char, kana_spelling, kata_to_hira, segment_word

# NOTE: the full JMdict dump (108MB) is only needed for the words NOT covered by
# input/jmdict-furigana-map.json. It is loaded lazily inside build_furigana_for_words.


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


@functools.lru_cache(maxsize=1)
def load_scriptin_readings():
    """Build a kanji-form → hiragana reading lookup from input/scriptin-jmdict-eng.json.

    For each JMdict entry, each kanji form is mapped to the first kana form that
    applies to it (appliesToKanji). First entry wins for words listed in several
    entries, matching JMdict's ordering (most common entry first). Memoized because
    the furigana build asks for it twice (reading hints + uncovered-word fallback);
    the returned dict is shared, so callers must treat it as read-only.
    """
    data = load_jmdict()
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


def build_reading_hints(words=None):
    """{word: reading} hints for disambiguating multi-reading furigana-map entries.

    Prefers freq-ranks `other_forms` kana (same signal the sample-vocab algo stores
    on candidates), then fills gaps from JMdict's primary reading. If `words` is
    given, only those keys are returned.
    """
    hints = {}
    for path in sorted(glob.glob(resolve_path("raw/freq-ranks/*.tsv"))):
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                word = row.get("japanese_word", "")
                if not word or word in hints:
                    continue
                if words is not None and word not in words:
                    continue
                kana = kana_spelling(row.get("other_forms", ""))
                if kana:
                    hints[word] = kata_to_hira(kana)

    needed = None if words is None else [w for w in words if w not in hints]
    if needed or words is None:
        jmdict = load_scriptin_readings()
        if words is None:
            for word, reading in jmdict.items():
                hints.setdefault(word, reading)
        else:
            for word in needed:
                if word in jmdict:
                    hints[word] = jmdict[word]
    return hints


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


def build_furigana_for_words(words, word_readings=None):
    """Generate furigana segments for every word in `words`.

    `word_readings` is an optional {word: reading} hint map for multi-variant
    furigana-map entries; when omitted, hints are built via build_reading_hints.
    Returns {word: segments} in the same key order as `words`.
    """
    needed = list(words)
    word_set = set(needed)
    furigana_map = load_json("input/jmdict-furigana-map.json")
    if word_readings is None:
        word_readings = build_reading_hints(word_set)

    result = {}
    uncovered = []
    for word in needed:
        if word in furigana_map:
            result[word] = pick_map_segments(furigana_map[word], word_readings.get(word))
        else:
            uncovered.append(word)

    if uncovered:
        print(f"Loading JMdict for {len(uncovered)} uncovered words...")
        readings = load_scriptin_readings()
        for word in uncovered:
            result[word] = generate_furigana(word, readings)

    return {w: result[w] for w in needed}


def main():
    """Diagnostic only: report bare / hard-to-align words; does not write a cache."""
    import kanji_load
    from build_helpers import get_words

    kanji_data = kanji_load.load_filtered_kanji_data()
    manual_vocab = kanji_load.load_vocab_override()
    algo_vocab = kanji_load.load_vocab_algo_override()
    automated_vocab = kanji_load.load_automated_kanji_vocab()
    needed = sorted({
        w
        for kanji in kanji_data
        for w in get_words(kanji, manual_vocab, algo_vocab, automated_vocab)
    })

    word_readings = build_reading_hints(set(needed))
    result = build_furigana_for_words(needed, word_readings)
    manual_furigana = load_json("overrides/vocab_furigana.json")

    bare = [
        w for w in result
        if w not in manual_furigana
        and result[w] == [[w]] and any(is_kanji_char(ch) for ch in w)
    ]
    mismatched = [
        w for w in result
        if w not in manual_furigana
        and word_readings.get(w)
        and segments_reading(result[w]) != kata_to_hira(word_readings[w])
    ]
    print(f"Furigana for {len(result)} shipped sample words (not written; final build ships)")
    if bare:
        print(f"  no reading found (need manual furigana): {len(bare)}")
        print(f"    {' '.join(bare)}")
    if mismatched:
        print(f"  reading differs from hint (jukujikun lumps / proper nouns / check by hand): {len(mismatched)}")
        for w in mismatched:
            print(f"    {w}: {segments_reading(result[w])} vs intended {word_readings[w]}")
    if not bare and not mismatched:
        print("  all readable; no hint mismatches outside manual overrides")


if __name__ == "__main__":
    main()
