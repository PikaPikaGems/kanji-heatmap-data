#!/usr/bin/env python3
"""
EXPERIMENTAL alternative to build_representative_study_word_algo.py.

Same job — pick ONE unique representative study word per kanji — but driven by the
multi-corpus frequency dataset in raw/freq-ranks/{kanji}.tsv instead of the v3
emoji-tag bands + textbook words. Output goes to a SEPARATE file so it never
clobbers the production overrides/japanese_study_words-algo.json:

    overrides/japanese_study_words-algo-alt.json   { kanji: [word, reading, meaning, tag] }

Why a different dataset?
  raw/freq-ranks/{kanji}.tsv lists every word whose FIRST character is that kanji,
  with a frequency RANK (lower = more frequent; NA = absent) in each of 14 corpora,
  plus a precomputed `tier` band and the English gloss inline. Two signals fall out
  of this that the v3 tags don't expose directly:
    1. coverage — how many of the 14 corpora the word appears in at all. Fundamental
       words show up nearly everywhere; niche words in one or two corpora. With
       ~60-70% NA per column, coverage alone separates core from fringe vocabulary.
    2. corpus mix — the 14 corpora split into SPOKEN/everyday (CEJC conversation,
       drama/anime/netflix/youtube subtitles, slice-of-life) vs WRITTEN (BCCWJ,
       CommonCrawl, NWJC web, Wikipedia). A learner's representative word is usually
       better drawn from the spoken side, so corpora are weighted (CORPUS_WEIGHTS).

Constraints (identical to the production algo):
  - word's first character is the target kanji (the file is keyed this way already)
  - at most 2 kanji characters in the word
  - all characters Japanese
  - each word assigned to at most one kanji (first-come-first-served by kanji order)

Ranking (two selectable modes via RANK_MODE):
  "tier_then_freq"  primary band is the dataset's own `tier` column (BASIC > COMMON >
                    FLUENT > ADVANCED > NICHE > UNRANKED), mirroring the v3 bands so
                    output is directly comparable to the production algo; the weighted
                    corpus frequency only breaks ties WITHIN a tier.
  "pure_freq"       ignore the tier column; rank purely by the composite frequency
                    (weighted mean rank inflated by a coverage penalty). More radical.

Score tuple (lower wins), shared shape with the production algo so the two are easy
to diff:  (band, word_type, no_meaning, agreement, all_shipped, freq_key, length)
  band       tier band (tier mode) or 0 (pure mode — freq_key carries the ordering)
  word_type  0 single-char kanji, 1 = 1 kanji + kana, 2 = exactly 2 kanji
  agreement  0 if present in both spoken+written halves (bonus on), else 1
  freq_key   weighted_mean_corpus_rank * (1 + COVERAGE_PENALTY * missing_corpora)

Optional ranking refinements (each a toggle near the top, all designed NOT to outrank
word_type — single-kanji / short-word preference is always preserved):
  USE_JLPT_PROMOTION    lift N4/N5-tagged words up the tier BAND (word_type still
                        decides within the band, so a 2-kanji N5 word can't beat a
                        single-kanji word)
  DROP_SINGLE_CORPUS    discard words attested in only one corpus, unless that would
                        leave the kanji word-less
  USE_AGREEMENT_BONUS   reward words frequent in both spoken AND written corpora

Reading + meaning are attached AFTER selection (freq-ranks has no reading column):
  reading  input/jmdict-furigana-map.json, then a kana-only token from `other_forms`
  meaning  the row's english_gloss, else jmdict / scriptin / ai-generated caches

Run from project root: python3 src/build_representative_study_word_algo_alt.py
"""

import csv
from collections import Counter

from sources import load_json, write_json
from japanese import is_all_japanese, is_japanese_char, is_kanji_char, kanji_count
from build_representative_study_word_algo import (
    load_kanji_list,
    load_jmdict_meanings,
    load_scriptin_meanings,
    load_ai_meanings,
    load_jmdict_readings,
)

# ---------------------------------------------------------------------------
# Experiment knobs
# ---------------------------------------------------------------------------

# "tier_then_freq": dataset tier column is the primary band (comparable to v3).
# "pure_freq":      composite corpus frequency is the only ranking signal.
RANK_MODE = "tier_then_freq"

# Per-corpus weight in the composite frequency. 0 drops a corpus entirely. The
# default favours SPOKEN/everyday corpora over WRITTEN ones, since a learner's
# representative word is better drawn from conversation/subtitles than web/wiki.
# Swap in EQUAL_WEIGHTS or WRITTEN_WEIGHTS below to compare.
CORPUS_COLUMNS = [
    "CEJC_all_conversations", "CEJC_small_talk_zatsudan",      # spoken — conversation
    "BCCWJ_LUW_compound", "BCCWJ_SUW_short_unit",              # written — balanced corpus
    "CommonCrawl_CC100", "NWJC_web_corpus", "Wikipedia_v2",    # written — web / wiki
    "DaveDoebrick_SliceOfLife", "jiten_all_media", "jiten_drama",
    "Shoui_anime_jdrama", "MarvNC_youtube_v3", "Shoui_netflix",
    "DaveDoebrick_netflix_no_names",                           # spoken — subtitles / media
]

SPOKEN_WEIGHTS = {
    "CEJC_all_conversations": 2.0, "CEJC_small_talk_zatsudan": 2.0,
    "BCCWJ_LUW_compound": 1.0, "BCCWJ_SUW_short_unit": 1.0,
    "CommonCrawl_CC100": 0.5, "NWJC_web_corpus": 0.5, "Wikipedia_v2": 0.5,
    "DaveDoebrick_SliceOfLife": 2.0, "jiten_all_media": 1.5, "jiten_drama": 2.0,
    "Shoui_anime_jdrama": 1.5, "MarvNC_youtube_v3": 1.5, "Shoui_netflix": 1.5,
    "DaveDoebrick_netflix_no_names": 1.5,
}
EQUAL_WEIGHTS = {c: 1.0 for c in CORPUS_COLUMNS}
WRITTEN_WEIGHTS = {c: (2.0 if c in {
    "BCCWJ_LUW_compound", "BCCWJ_SUW_short_unit", "CommonCrawl_CC100",
    "NWJC_web_corpus", "Wikipedia_v2"} else 0.5) for c in CORPUS_COLUMNS}

CORPUS_WEIGHTS = SPOKEN_WEIGHTS

# Each corpus a word is MISSING from inflates its mean rank by this fraction, so a
# word seen across many corpora beats an equally-ranked word seen in only one.
COVERAGE_PENALTY = 0.15

# Which corpora count as spoken vs written (the two "halves"). Used by the
# single-corpus distrust filter and the spoken/written agreement bonus.
SPOKEN_COLUMNS = {
    "CEJC_all_conversations", "CEJC_small_talk_zatsudan", "DaveDoebrick_SliceOfLife",
    "jiten_all_media", "jiten_drama", "Shoui_anime_jdrama", "MarvNC_youtube_v3",
    "Shoui_netflix", "DaveDoebrick_netflix_no_names",
}
WRITTEN_COLUMNS = {
    "BCCWJ_LUW_compound", "BCCWJ_SUW_short_unit", "CommonCrawl_CC100",
    "NWJC_web_corpus", "Wikipedia_v2",
}

# --- Optional ranking refinements (all independent of the representative-word
# rules: word_type / length / ≤2-kanji / starts-with-kanji / uniqueness still apply) ---

# JLPT promotion: hard-lift beginner-tagged words up the tier band. jlpt_level is
# mostly NA but reliable when present (5 = N5 easiest .. 1 = N1). A word at level
# >= JLPT_PROMOTE_MIN_LEVEL has its band forced to JLPT_PROMOTED_BAND, so easy words
# float to the top — but only the BAND moves, so word_type still decides within it
# (a 2-kanji N5 word never beats a single-kanji word).
USE_JLPT_PROMOTION = True
JLPT_PROMOTE_MIN_LEVEL = 4   # promote N4 (4) and N5 (5)
JLPT_PROMOTED_BAND = 0       # target band (0 = same as BASIC)

# Single-corpus distrust: drop words that appear in only one weighted corpus,
# regardless of rank (a single corpus is weak evidence a word is worth teaching).
# Applied as a filter with a safety net — if it would leave a kanji with NO
# candidates, the filter is skipped for that kanji so it isn't left word-less.
DROP_SINGLE_CORPUS = True
MIN_CORPUS_COVERAGE = 2      # require presence in >= this many weighted corpora

# Agreement bonus: reward words present in BOTH the spoken and written halves —
# genuinely universal vocabulary. A tiebreaker placed AFTER word_type, so it never
# overrides the single-kanji / short-word preference.
USE_AGREEMENT_BONUS = True

# Tier band ordering (the dataset's frequency tier; lower = more frequent/basic).
TIER_BAND = {
    "BASIC": 0, "COMMON": 1, "FLUENT": 2, "ADVANCED": 3, "NICHE": 4, "UNRANKED": 5,
}
DEFAULT_TIER_BAND = 5

# Emoji written into each entry's tag slot, by freq-ranks tier — so the experiment's
# output uses the same frequency-band glyphs as the production algo (🌱 most frequent
# → 🦉 rarest), making the two directly comparable.
TIER_TAG = {
    "BASIC": "🌱", "COMMON": "☘️", "FLUENT": "🌷",
    "ADVANCED": "📚", "NICHE": "🌶️", "UNRANKED": "🦉",
}
DEFAULT_TIER_TAG = "🦉"  # untagged / unknown tier → rarest band

# Special rule (tier mode only): a single-kanji word in a top tier wins outright,
# mirroring the production algo's "single-kanji word with top tag wins" rule.
TOP_TIERS = {"BASIC", "COMMON"}

# TSV column layout (raw/freq-ranks/*.tsv).
COL_WORD = "japanese_word"
COL_GLOSS = "english_gloss"
COL_TIER = "tier"
COL_OTHER_FORMS = "other_forms"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def read_freq_rows(kanji):
    """Rows from raw/freq-ranks/{kanji}.tsv as dicts keyed by column name. [] if absent."""
    from sources import resolve_path
    import os
    path = resolve_path(f"raw/freq-ranks/{kanji}.tsv")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def _rank(value):
    """Parse a corpus rank cell: int rank, or None for NA/blank/garbage."""
    if not value or value == "NA":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def freq_key(row):
    """Composite corpus frequency for a row — LOWER is better.

    Weighted mean of the per-corpus ranks the word actually has, inflated by
    COVERAGE_PENALTY for every weighted corpus it is missing from. Infinity when the
    word appears in no weighted corpus at all (kept only as a last resort)."""
    num = den = 0.0
    present = 0
    weighted_total = 0
    for col in CORPUS_COLUMNS:
        w = CORPUS_WEIGHTS.get(col, 0.0)
        if w <= 0:
            continue
        weighted_total += 1
        r = _rank(row.get(col))
        if r is None:
            continue
        num += w * r
        den += w
        present += 1
    if den == 0:
        return float("inf")
    mean_rank = num / den
    missing = weighted_total - present
    return mean_rank * (1 + COVERAGE_PENALTY * missing)


def coverage(row):
    """How many WEIGHTED corpora the word appears in (non-NA, weight > 0)."""
    return sum(
        1 for col in CORPUS_COLUMNS
        if CORPUS_WEIGHTS.get(col, 0.0) > 0 and _rank(row.get(col)) is not None
    )


def in_both_halves(row):
    """True if the word appears in at least one spoken AND one written corpus."""
    spoken = any(_rank(row.get(c)) is not None for c in SPOKEN_COLUMNS)
    written = any(_rank(row.get(c)) is not None for c in WRITTEN_COLUMNS)
    return spoken and written


def jlpt_level(row):
    """Parsed JLPT level (5 = N5 easiest .. 1 = N1), or None when untagged (NA)."""
    return _rank(row.get("jlpt_level"))


def effective_band(row):
    """Tier band for scoring, after the optional JLPT promotion. In pure_freq mode the
    base band is 0; JLPT promotion can still pull a tagged word below 0 so it leads."""
    base = TIER_BAND.get(row.get(COL_TIER, ""), DEFAULT_TIER_BAND) if RANK_MODE == "tier_then_freq" else 0
    if USE_JLPT_PROMOTION:
        lvl = jlpt_level(row)
        if lvl is not None and lvl >= JLPT_PROMOTE_MIN_LEVEL:
            return min(base, JLPT_PROMOTED_BAND)
    return base


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

SHIPPED = set()  # filtered_kanji.json; populated in main()


def has_nonshipped_kanji(word):
    """1 if `word` contains a kanji we don't ship, else 0 (sorts all-shipped first)."""
    return 1 if any(is_kanji_char(c) and c not in SHIPPED for c in word) else 0


def word_type(word):
    """0 single-char kanji, 1 = 1 kanji + kana only, 2 = exactly 2 kanji."""
    if len(word) == 1:
        return 0
    return 1 if kanji_count(word) == 1 else 2


def row_score(row):
    """Lower wins. Mirrors the production algo's tuple shape for easy diffing, with two
    optional extras that NEVER outrank word_type (so the single-kanji / short-word
    preference is preserved):

        (band, word_type, no_meaning, agreement, all_shipped, freq_key, length)

    band       tier band after optional JLPT promotion (effective_band)
    agreement  0 if present in both spoken+written halves (bonus on), else 1
    """
    word = row[COL_WORD]
    no_meaning = 0 if row.get(COL_GLOSS, "").strip() else 1
    agreement = 0 if (USE_AGREEMENT_BONUS and in_both_halves(row)) else 1
    return (effective_band(row), word_type(word), no_meaning, agreement,
            has_nonshipped_kanji(word), freq_key(row), len(word))


def is_valid_row(row, kanji):
    word = row.get(COL_WORD, "")
    if not word or word[0] != kanji:
        return False
    if not is_all_japanese(word):
        return False
    kc = kanji_count(word)
    return 1 <= kc <= 2


def select_row_for_kanji(kanji, used_words):
    """Best raw TSV row for `kanji` under the constraints, skipping used words. None
    if the kanji has no freq-ranks file or no valid unused row."""
    rows = [r for r in read_freq_rows(kanji) if is_valid_row(r, kanji)
            and r[COL_WORD] not in used_words]
    if not rows:
        return None

    # Single-corpus distrust: drop thinly-attested words, but keep them if dropping
    # would leave this kanji with nothing (rare kanji often only have such words).
    if DROP_SINGLE_CORPUS:
        broad = [r for r in rows if coverage(r) >= MIN_CORPUS_COVERAGE]
        if broad:
            rows = broad

    if RANK_MODE == "tier_then_freq":
        # Special rule: a single-kanji word in a top tier wins outright.
        top = [r for r in rows
               if word_type(r[COL_WORD]) <= 1 and r.get(COL_TIER) in TOP_TIERS]
        if top:
            return min(top, key=row_score)

    return min(rows, key=row_score)


# ---------------------------------------------------------------------------
# Reading / meaning resolution (attached after selection)
# ---------------------------------------------------------------------------

def _kana_only(text):
    return bool(text) and all(is_japanese_char(c) and not is_kanji_char(c) for c in text)


def resolve_reading(word, row, jmdict_readings):
    """Reading from the furigana map, else a kana-only token from `other_forms`, else ''."""
    if word in jmdict_readings:
        return jmdict_readings[word]
    for form in (row.get(COL_OTHER_FORMS, "") or "").split(";"):
        form = form.strip()
        if _kana_only(form):
            return form
    return ""


def resolve_meaning(word, row, jmdict, scriptin, ai_meanings):
    """The row's inline gloss, else the jmdict / scriptin / ai caches."""
    gloss = row.get(COL_GLOSS, "").strip()
    if gloss:
        return gloss
    return jmdict.get(word) or scriptin.get(word) or ai_meanings.get(word, "")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    all_kanji = load_kanji_list()
    SHIPPED.update(all_kanji)
    jmdict = load_jmdict_meanings()
    scriptin = load_scriptin_meanings()
    ai_meanings = load_ai_meanings()
    jmdict_readings = load_jmdict_readings()

    result = {}
    used_words = set()  # enforces uniqueness across all kanji

    for kanji in all_kanji:
        row = select_row_for_kanji(kanji, used_words)
        if row is None:
            result[kanji] = None
            continue
        word = row[COL_WORD]
        reading = resolve_reading(word, row, jmdict_readings)
        meaning = resolve_meaning(word, row, jmdict, scriptin, ai_meanings)
        tag = TIER_TAG.get(row.get(COL_TIER, ""), DEFAULT_TIER_TAG)
        result[kanji] = [word, reading, meaning, tag]
        used_words.add(word)

    out_path = write_json("overrides/japanese_study_words-algo-alt.json", result, indent=2)
    print(f"Written: {out_path}")
    toggles = ", ".join(name for on, name in (
        (USE_JLPT_PROMOTION, f"jlpt>=N{JLPT_PROMOTE_MIN_LEVEL}"),
        (DROP_SINGLE_CORPUS, f"drop<{MIN_CORPUS_COVERAGE}-corpus"),
        (USE_AGREEMENT_BONUS, "spoken+written-bonus"),
    ) if on) or "none"
    print(f"  config: mode={RANK_MODE}, weights={_weights_name()}, toggles=[{toggles}]")

    print_report(result, all_kanji)


def _weights_name():
    for name, table in (("SPOKEN", SPOKEN_WEIGHTS), ("EQUAL", EQUAL_WEIGHTS),
                        ("WRITTEN", WRITTEN_WEIGHTS)):
        if CORPUS_WEIGHTS is table:
            return name
    return "custom"


def print_report(result, all_kanji):
    """Selection statistics: coverage, tier mix, word-shape, and anomaly lists.
    Read-only over `result`."""
    selected = [(k, v) for k, v in result.items() if v is not None]
    without = [k for k, v in result.items() if v is None]
    total = len(selected)

    length_counts = Counter(len(v[0]) for _, v in selected)
    kc_counts = Counter(kanji_count(v[0]) for _, v in selected)
    no_reading = [k for k, v in selected if not v[1]]
    no_meaning = [k for k, v in selected if not v[2]]

    print(f"\n{'─'*44}")
    print(f"  Kanji processed:   {len(all_kanji)}")
    print(f"  With word:         {total}")
    print(f"  Without word:      {len(without)}")
    print(f"  No reading:        {len(no_reading)}")
    print(f"  No meaning:        {len(no_meaning)}")

    print(f"\n  Word length")
    for n in sorted(length_counts):
        print(f"    {n} chars: {length_counts[n]}  ({length_counts[n]/total*100:.1f}%)")

    print(f"\n  Kanji per word")
    for n in sorted(kc_counts):
        print(f"    {n} kanji: {kc_counts[n]}  ({kc_counts[n]/total*100:.1f}%)")
    print(f"{'─'*44}")

    if without:
        print(f"\nNo-word kanji ({len(without)}): {''.join(without)}")

    # Overlap check (uniqueness should already guarantee none).
    word_to_kanjis = {}
    for k, v in selected:
        word_to_kanjis.setdefault(v[0], []).append(k)
    overlapping = {w: ks for w, ks in word_to_kanjis.items() if len(ks) > 1}
    print(f"\n  Overlapping study words: {len(overlapping)}")
    for w, ks in overlapping.items():
        print(f"    {w}: {''.join(ks)}")


if __name__ == "__main__":
    main()
