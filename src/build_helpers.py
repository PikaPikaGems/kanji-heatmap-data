"""Importable, side-effect-free helpers for the output build.

kanji_build_output_jsons.py runs the whole build at import time, so its logic
couldn't be reused or unit-tested in isolation. These two functions live here
instead — pure(ish) and parameterised, so they can be imported and tested
without triggering a full build.
"""

import kanji_extract
from japanese import reading_of_kanji_in_segments, readings_equivalent


def get_words(kanji, override_words, override_algo_words, automated_words, count=2):
    """Up to `count` sample words for `kanji`, by source priority:
    manual override > algo override > automated.

    Each of override_words / override_algo_words / automated_words is the full
    {kanji: [word, ...]} map for that source.
    """
    kanji_words = []

    for word in override_words.get(kanji, []):
        if word not in kanji_words:
            kanji_words.append(word)
            if len(kanji_words) == count:
                return kanji_words

    for word in override_algo_words.get(kanji, []):
        if word not in kanji_words:
            kanji_words.append(word)
            if len(kanji_words) == count:
                return kanji_words

    needed = count - len(kanji_words)
    return (
        kanji_words
        + [
            w
            for w in automated_words.get(kanji, [])
            if w not in kanji_words and kanji in w
        ][:needed]
    )


def furigana_stats(kanji_extended, kanji_data, vocab_furigana):
    """Print how often a kanji's two sample words use the same vs different
    readings (on/kun classified via kanji_extract). Diagnostic only.

    kanji_extended: {kanji: [...]} reformatted extended info (words at index 9).
    kanji_data:     full per-kanji info, for on/kun reading lookups.
    vocab_furigana: {word: [[span, reading], ...]} furigana breakdowns.
    """

    def get_kanji_reading_in_word(kanji, word):
        return reading_of_kanji_in_segments(kanji, vocab_furigana.get(word, []))

    def normalize(r):
        return r.replace("-", "").split(".")[0]

    def classify_reading(reading, kanji):
        kanji_info = kanji_data.get(kanji, {})
        on_readings = {normalize(r) for r in (kanji_extract.get_all_on_readings(kanji_info) or [])}
        kun_readings = {normalize(r) for r in (kanji_extract.get_all_kun_readings(kanji_info) or [])}
        norm = normalize(reading)
        if norm in on_readings:
            return "on"
        if norm in kun_readings:
            return "kun"
        for r in on_readings:
            if norm.startswith(r) or r.startswith(norm):
                return "on"
        for r in kun_readings:
            if norm.startswith(r) or r.startswith(norm):
                return "kun"
        return "unknown"

    same = rendaku_same = different_both_on = different_both_kun = different_mixed = different_unknown = skipped = 0

    for kanji, extended in kanji_extended.items():
        words = extended[9]
        if len(words) < 2:
            skipped += 1
            continue
        r1 = get_kanji_reading_in_word(kanji, words[0])
        r2 = get_kanji_reading_in_word(kanji, words[1])
        if r1 is None or r2 is None:
            skipped += 1
            continue
        if r1 == r2:
            same += 1
        elif readings_equivalent(r1, r2):
            # Same reading once 連濁 (げつ/げっ) or 促音 (と/ど) is accounted for —
            # reported alongside the exact count rather than as "different".
            rendaku_same += 1
        else:
            t1, t2 = classify_reading(r1, kanji), classify_reading(r2, kanji)
            if t1 == "on" and t2 == "on":
                different_both_on += 1
            elif t1 == "kun" and t2 == "kun":
                different_both_kun += 1
            elif "unknown" in (t1, t2):
                different_unknown += 1
            else:
                different_mixed += 1

    total = same + rendaku_same + different_both_on + different_both_kun + different_mixed + different_unknown
    if total == 0:
        print("No kanji with 2 sample words and furigana found.")
        return

    equiv_same = same + rendaku_same
    diff = total - equiv_same
    print(f"\n--- Furigana Reading Stats ({total} kanji) ---")
    print(f"  Same reading (exact):          {same:4d} ({same / total * 100:.1f}%)")
    print(f"  Same reading (incl. 連濁/促音): {equiv_same:4d} ({equiv_same / total * 100:.1f}%)  [+{rendaku_same} rendaku/gemination]")
    print(f"  Different reading:             {diff:4d} ({diff / total * 100:.1f}%)")
    if diff:
        print(f"    Both onyomi:     {different_both_on:4d} ({different_both_on / total * 100:.1f}%)")
        print(f"    Both kunyomi:    {different_both_kun:4d} ({different_both_kun / total * 100:.1f}%)")
        print(f"    Mixed on/kun:    {different_mixed:4d} ({different_mixed / total * 100:.1f}%)")
        print(f"    Unknown:         {different_unknown:4d} ({different_unknown / total * 100:.1f}%)")
    if skipped:
        print(f"  Skipped (< 2 words or missing furigana): {skipped}")
    print()
