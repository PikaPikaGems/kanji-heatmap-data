#!/usr/bin/env python3
"""
Selects one unique representative study word per kanji.
Each word appears at most once across all kanjis (first-come-first-served by kanji order).

Constraints:
  - Word must START with the target kanji (first character = kanji)
  - Max 2 kanji characters in the word
  - All characters must be Japanese (hiragana/katakana/kanji)
  - Each word is assigned to at most one kanji

Candidate pool: raw/freq-ranks/{kanji}.tsv — every word starting with the kanji,
with a frequency rank in each of 14 corpora, a precomputed `tier` band (BASIC >
COMMON > FLUENT > ADVANCED > NICHE > UNRANKED), and a JLPT level where known.
Textbook words (raw/kanji-textbook-words-min) are merged in as a mid band —
they mostly matter for the ~219 kanji that have no freq-ranks file at all.

Special rule – single-kanji word in a top tier wins outright:
  If any candidate contains exactly one kanji (行 or 行く), sits in a top tier
  (BASIC/COMMON), and is a standalone JMdict word, it is chosen immediately —
  the study word should show THIS kanji as a word when the kanji is one.
  Within this group, normal word scoring applies.

Word scoring (lower tuple wins): (validity, band, jlpt, class, type, shipped, freq, len)
  validity  0 standalone JMdict word · 1 affix-only entry (新/しん) · 2 not in
            JMdict — outranks everything: unresolvable words ship empty meanings
            and affix-only entries aren't real standalone words
  band      frequency tier band (textbook words sit at ADVANCED level)
  jlpt      N5 easiest first, untagged last — the strongest "teach this first"
            signal (空 N5 beats 空く N4; 高い N5 beats 高 N1)
  class     verb < adjective < other (語る beats 語 when JLPT ties)
  type      1 kanji + kana < bare single kanji < 2-kanji compound
            (okurigana beats bare kanji: 高い > 高, 書く > 書)
  shipped   words whose every kanji ships sort first
  freq      composite corpus frequency — weighted mean rank across corpora,
            spoken/media corpora weighted up, inflated by a coverage penalty
            for each corpus the word is missing from
  len       shorter wins

Two safety nets ride along in the same scored pool:
  - Textbook words that merely CONTAIN the kanji (not start with it) carry a
    stage penalty: they only win when nothing real starts with the kanji
    (甲斐 for 斐). These show in the "Words NOT starting with kanji" stat.
  - The bare kanji itself joins at UNRANKED band when the pool doesn't already
    list it: if everything else is junk but the kanji is a standalone JMdict
    word (栞/しおり, 李/すもも), it wins via the validity slot. It is never
    forced — kanji JMdict knows only as affixes or not at all stay null.

Reading + meaning (resolved AFTER word selection, via jmdict_resolver):
  Both come from input/scriptin-jmdict-eng.json ONLY — the single source of
  truth. The resolver returns up to 2 common readings joined with ・
  (空 → そら・から) and a short meaning whose [n] blocks align with the split
  readings (see jmdict_resolver.py). Words JMdict doesn't know fall back to
  the furigana map for a reading, get an empty meaning, and are reported.

Sources:
  input/filtered_kanji.json              → [kanji]  (the kanji set to process)
  raw/freq-ranks/[kanji].tsv             → tab-separated corpus frequency rows
  raw/kanji-textbook-words-min/[kanji].json → {kanji: {word: [reading, meaning]}}
  input/scriptin-jmdict-eng.json         → JMdict JSON (words[].kanji/kana/sense)
  raw/manual-inspections.json            → {replaceKanjiStudyWords: {kanji: word}}
  input/jmdict-furigana-map.json         → {word: {reading: segments}}  (fallback readings)

Output: overrides/japanese_study_words-algo.json
  { kanji: [word, reading, meaning, tag] }   (null when no valid word found)
  tag = tier emoji (🌱☘️🌷📚🌶️🦉), 📖 textbook, ✏️ manual override

Run from project root: python3 src/build_representative_study_word_algo.py
"""

import csv
import os
from collections import Counter

from sources import (
    load_json,
    write_json,
    resolve_path,
    jmdict_entry_gloss,
    textbook_candidates,
)
from japanese import is_all_japanese, is_kanji_char, kanji_count
from jmdict_resolver import JmdictResolver, CLASS_OTHER

# ---------------------------------------------------------------------------
# Scoring / prioritisation
# ---------------------------------------------------------------------------

# NOTE: word_score / is_valid_candidate here intentionally differ from the
# same-named functions in algorithmic_kanji_vocab_overrides.py — this algorithm
# requires the word to START with the kanji and scores by word-shape, while the
# sample-vocab algorithm only requires the kanji to appear anywhere.

# Strip a trailing する or な from 2-kanji textbook headwords so the bare noun is
# the representative word (解剖する → 解剖, 真摯な → 真摯) — the inflected forms
# aren't JMdict headwords. Only fires for 2-kanji stems — single-kanji する verbs
# (関する → 関, 察する → 察) are left alone, since the bare kanji is a poor
# standalone word. Reading and meaning re-resolve to the noun afterwards.
STRIP_JUNK_SUFFIXES = True

# Frequency tier band from the freq-ranks `tier` column (lower = more frequent).
# Textbook words slot in at ADVANCED level: real corpus evidence of the first
# three tiers should beat a textbook appearance, but a curated textbook word
# beats NICHE/UNRANKED corpus noise.
TIER_BAND = {
    "BASIC": 0, "COMMON": 1, "FLUENT": 2, "ADVANCED": 3, "NICHE": 4, "UNRANKED": 5,
}
DEFAULT_TIER_BAND = 5
TEXTBOOK_BAND = 3

# Emoji written into each entry's tag slot, by freq-ranks tier (🌱 most frequent
# → 🦉 rarest) — same glyphs the v3 pool used, so the output stays comparable.
TIER_TAG = {
    "BASIC": "🌱", "COMMON": "☘️", "FLUENT": "🌷",
    "ADVANCED": "📚", "NICHE": "🌶️", "UNRANKED": "🦉",
}
DEFAULT_TIER_TAG = "🦉"

# Bands eligible for the special rule (single-kanji standalone word wins outright).
TOP_BANDS = {TIER_BAND["BASIC"], TIER_BAND["COMMON"]}

# --- Composite corpus frequency (ported from the freq-ranks experiment) ---
# Per-corpus weight in the composite frequency; 0 drops a corpus. SPOKEN/everyday
# corpora (conversation, subtitles) weigh more than WRITTEN ones (web, wiki) —
# a learner's representative word is better drawn from speech than from text.
CORPUS_WEIGHTS = {
    "CEJC_all_conversations": 2.0, "CEJC_small_talk_zatsudan": 2.0,
    "BCCWJ_LUW_compound": 1.0, "BCCWJ_SUW_short_unit": 1.0,
    "CommonCrawl_CC100": 0.5, "NWJC_web_corpus": 0.5, "Wikipedia_v2": 0.5,
    "DaveDoebrick_SliceOfLife": 2.0, "jiten_all_media": 1.5, "jiten_drama": 2.0,
    "Shoui_anime_jdrama": 1.5, "MarvNC_youtube_v3": 1.5, "Shoui_netflix": 1.5,
    "DaveDoebrick_netflix_no_names": 1.5,
}

# Each corpus a word is MISSING from inflates its mean rank by this fraction, so a
# word seen across many corpora beats an equally-ranked word seen in only one.
COVERAGE_PENALTY = 0.15

# Distrust words attested in fewer weighted corpora than this — dropped unless
# that would leave the kanji with no candidates at all.
MIN_CORPUS_COVERAGE = 2

# TSV column names (raw/freq-ranks/*.tsv).
COL_WORD = "japanese_word"
COL_TIER = "tier"
COL_JLPT = "jlpt_level"

# JLPT levels run 5 (N5, easiest) .. 1 (N1); untagged sorts after all of them.
JLPT_UNTAGGED_RANK = 5


# Kanji we ship (input/filtered_kanji.json); populated in main(). Used to prefer
# study words whose every kanji ships, so a word doesn't drag in an unshipped
# partner (e.g. 麻 → 麻痺[痺 unshipped]) when an all-shipped option exists.
SHIPPED = set()


def has_nonshipped_kanji(word):
    """1 if `word` contains a kanji we don't ship, else 0 (sorts all-shipped first)."""
    return 1 if any(is_kanji_char(c) and c not in SHIPPED for c in word) else 0


def word_type(word):
    """0 = 1 kanji + kana (高い), 1 = bare single kanji (高), 2 = 2-kanji compound.

    Okurigana beats bare kanji: 高い > 高, 書く > 書 — the inflected form is a
    word a learner can actually use, the bare kanji often reads differently on
    its own."""
    if len(word) == 1:
        return 1
    return 0 if kanji_count(word) == 1 else 2


def resolver_validity(resolved):
    """0 standalone JMdict word · 1 affix-only entry (新/しん, 同/どう) · 2 not in
    JMdict at all (or only as a rare/irregular writing, e.g. 容れる)."""
    if resolved is None:
        return 2
    return 0 if resolved["standalone"] else 1


def word_score(cand, resolved):
    """Lower is better; see the module docstring for the tuple's rationale.

    validity outranks the frequency band on purpose: an unresolvable word ships
    with an empty meaning (rare-kanji writings like 然し, corpus phrase junk like
    廷内で) and an affix-only entry (歳/さい, 匹/ひき) breaks the "study words are
    real standalone words" rule — a real word from a lower tier beats both.
    stage sits between them: a real word merely CONTAINING the kanji (甲斐 for 斐)
    beats junk that starts with it, but never a real starts-with word."""
    w = cand["word"]
    return (
        resolver_validity(resolved),
        cand["stage"],
        cand["band"],
        cand["jlpt_rank"],
        resolved["word_class"] if resolved else CLASS_OTHER,
        word_type(w),
        has_nonshipped_kanji(w),
        cand["freq"],
        len(w),
    )


def is_valid_word(word, target_kanji):
    if not word or word[0] != target_kanji:
        return False
    if not is_all_japanese(word):
        return False
    return 1 <= kanji_count(word) <= 2


# ---------------------------------------------------------------------------
# Candidate loading
# ---------------------------------------------------------------------------

def read_freq_rows(kanji):
    """Rows from raw/freq-ranks/{kanji}.tsv as dicts keyed by column name. [] if absent."""
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
    COVERAGE_PENALTY for every weighted corpus it is missing from. Infinity when
    the word appears in no weighted corpus at all (kept only as a last resort)."""
    num = den = 0.0
    present = 0
    weighted_total = 0
    for col, weight in CORPUS_WEIGHTS.items():
        if weight <= 0:
            continue
        weighted_total += 1
        r = _rank(row.get(col))
        if r is None:
            continue
        num += weight * r
        den += weight
        present += 1
    if den == 0:
        return float("inf")
    return (num / den) * (1 + COVERAGE_PENALTY * (weighted_total - present))


def coverage(row):
    """How many weighted corpora the word appears in (non-NA, weight > 0)."""
    return sum(
        1 for col, weight in CORPUS_WEIGHTS.items()
        if weight > 0 and _rank(row.get(col)) is not None
    )


# stage values: candidates that START with the kanji rank before those that
# merely CONTAIN it (textbook relaxed search — rare/classical kanji nothing
# starts with, e.g. 斐 → 甲斐).
STAGE_STARTS_WITH = 0
STAGE_CONTAINS = 1


def load_freq_candidates(kanji):
    """Valid freq-ranks candidates for `kanji`: {word, stage, band, tag, jlpt_rank, freq}.

    Words attested in fewer than MIN_CORPUS_COVERAGE corpora are dropped unless
    that would empty the pool (rare kanji often only have such words)."""
    rows = [r for r in read_freq_rows(kanji) if is_valid_word(r.get(COL_WORD, ""), kanji)]
    broad = [r for r in rows if coverage(r) >= MIN_CORPUS_COVERAGE]
    if broad:
        rows = broad
    candidates = []
    for row in rows:
        jlpt = _rank(row.get(COL_JLPT))
        candidates.append({
            "word": row[COL_WORD],
            "stage": STAGE_STARTS_WITH,
            "band": TIER_BAND.get(row.get(COL_TIER, ""), DEFAULT_TIER_BAND),
            "tag": TIER_TAG.get(row.get(COL_TIER, ""), DEFAULT_TIER_TAG),
            "jlpt_rank": JLPT_UNTAGGED_RANK if jlpt is None else 5 - jlpt,
            "freq": freq_key(row),
        })
    return candidates


def _textbook_cand(word, stage):
    return {
        "word": word,
        "stage": stage,
        "band": TEXTBOOK_BAND,
        "tag": OUTPUT_TEXTBOOK_TAG,
        "jlpt_rank": JLPT_UNTAGGED_RANK,
        "freq": float("inf"),
    }


def load_textbook_candidates(kanji):
    """Textbook candidates containing `kanji`, same dict shape as freq ones;
    words starting with the kanji get STAGE_STARTS_WITH, the rest STAGE_CONTAINS."""
    entries = textbook_candidates(
        kanji,
        lambda w, r: is_all_japanese(w) and kanji in w and 1 <= kanji_count(w) <= 2,
    )
    return [
        _textbook_cand(w, STAGE_STARTS_WITH if w[0] == kanji else STAGE_CONTAINS)
        for w, _r, _t, _e in entries
    ]


def bare_kanji_candidate(kanji):
    """The kanji itself as a candidate — safety net for kanji whose pool is empty
    or all-junk but that ARE a standalone JMdict word (栞/しおり, 李/すもも).
    No corpus evidence → UNRANKED band, so any real pooled word outscores it."""
    return {
        "word": kanji,
        "stage": STAGE_STARTS_WITH,
        "band": DEFAULT_TIER_BAND,
        "tag": DEFAULT_TIER_TAG,
        "jlpt_rank": JLPT_UNTAGGED_RANK,
        "freq": float("inf"),
    }


OUTPUT_TEXTBOOK_TAG = "📖"
OVERRIDE_TAG = "✏️"  # manual study-word override (from raw/manual-inspections.json)


def select_word_for_kanji(kanji, used_words, resolver):
    """Return the best [word, "", "", tag] for this kanji, or None. Reading and
    meaning are attached later by the caller (always from the resolver).

    used_words: set of words already assigned to other kanjis — these are skipped.
    """
    merged = {}  # word → candidate; later sources win: freq-ranks over textbook
    for cand in load_textbook_candidates(kanji) + load_freq_candidates(kanji):
        merged[cand["word"]] = cand
    resolved_bare = resolver.resolve(kanji)
    if resolved_bare is not None and resolved_bare["standalone"]:
        merged.setdefault(kanji, bare_kanji_candidate(kanji))
    candidates = [c for c in merged.values() if c["word"] not in used_words]

    scored = sorted(
        ((word_score(c, resolver.resolve(c["word"])), c) for c in candidates),
        key=lambda pair: pair[0],
    )
    if not scored:
        return None

    # Special rule: a single-kanji standalone word in a top band wins outright —
    # when the kanji IS a common word, that word represents it best (毎 over 毎日).
    # The validity gate keeps affix-only entries out (同じ must beat bare 同).
    for _score, cand in scored:
        if (kanji_count(cand["word"]) == 1 and cand["band"] in TOP_BANDS
                and resolver_validity(resolver.resolve(cand["word"])) == 0):
            return [cand["word"], "", "", cand["tag"]]

    best = scored[0][1]
    return [best["word"], "", "", best["tag"]]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_kanji_list():
    # input/filtered_kanji.json is the canonical kanji set (merged_kanji minus
    # kanji_to_remove), produced by src/build_filtered_kanji_json.py.
    return load_json("input/filtered_kanji.json", [])


# load_jmdict_meanings / load_scriptin_meanings are no longer used here (the
# resolver replaced them) but build_representative_study_word_algo_alt.py still
# imports them; they go away together with that script.
def load_jmdict_meanings():
    return load_json("input/jmdict-vocab-meaning.json", {})


def load_scriptin_meanings():
    data = load_json("input/scriptin-jmdict-eng.json", {})
    lookup = {}
    for entry in data.get("words", []):
        for form in entry.get("kanji", []) + entry.get("kana", []):
            t = form.get("text", "")
            if t and t not in lookup:
                meaning = jmdict_entry_gloss(entry, t)  # appliesToKanji-aware per form
                if meaning:
                    lookup[t] = meaning
    return lookup


def load_manual_replace_words():
    data = load_json("raw/manual-inspections.json", {})
    return {k: v.strip() for k, v in data.get("replaceKanjiStudyWords", {}).items()}


def load_jmdict_readings():
    data = load_json("input/jmdict-furigana-map.json", {})
    return {word: next(iter(readings)) for word, readings in data.items() if readings}


def strip_junk_suffix(entry, used_words, resolver):
    """Return `entry` with a 2-kanji 〜する/〜な headword reduced to its bare noun
    (解剖する → 解剖, 真摯な → 真摯), or `entry` unchanged when nothing strips.
    Skips the strip if the bare noun is already assigned to another kanji
    (uniqueness), or when JMdict knows the full form but not the stem — stripping
    would trade a resolvable word for an unresolvable one. When it knows neither
    (kyūjitai variants like 充塡する), still strip: the bare noun is the better
    unresolvable word.

    entry is [word, reading, meaning, tag]; the tag (source band) is kept as-is;
    reading/meaning are re-resolved by the caller.
    """
    word, reading, meaning, tag = entry
    for suffix in ("する", "な"):
        if not word.endswith(suffix):
            continue
        stem = word[: -len(suffix)]
        if kanji_count(stem) != 2:        # only 2-kanji stems; leave 関する → 関 alone
            return entry
        if stem in used_words:            # don't create a duplicate with another kanji's word
            return entry
        if resolver.resolve(stem) is None and resolver.resolve(word) is not None:
            return entry
        return [stem, reading, meaning, tag]
    return entry


def main():
    all_kanji = load_kanji_list()
    SHIPPED.update(all_kanji)  # enable the all-shipped study-word preference
    manual_words = load_manual_replace_words()
    jmdict_readings = load_jmdict_readings()
    resolver = JmdictResolver()

    result = {}
    used_words = set()  # enforces uniqueness across all kanjis
    missing_jmdict = []  # selected words JMdict doesn't know (pool r/e never leaks)

    def attach_reading_meaning(entry):
        """Overwrite entry's reading/meaning from the resolver — the pools' own
        r/e fields inform selection only and must never reach the output."""
        resolved = resolver.resolve(entry[0])
        if resolved:
            entry[1] = resolved["reading"]
            entry[2] = resolved["meaning"]
        else:
            entry[1] = jmdict_readings.get(entry[0], "")
            entry[2] = ""
            missing_jmdict.append(entry[0])
        return entry

    for kanji in all_kanji:
        entry = select_word_for_kanji(kanji, used_words, resolver)

        if STRIP_JUNK_SUFFIXES and entry:
            entry = strip_junk_suffix(entry, used_words, resolver)

        if entry:
            entry = attach_reading_meaning(entry)
            used_words.add(entry[0])

        result[kanji] = entry

    # --- Apply manual word overrides from raw/manual-inspections.json ---
    for kanji, word in manual_words.items():
        if kanji not in result:
            continue
        result[kanji] = attach_reading_meaning([word, "", "", OVERRIDE_TAG])

    # Overrides are applied without the per-selection uniqueness check above, so a
    # manual word can collide with one already chosen for another kanji. Fail loudly
    # here (at the source) instead of downstream in kanji_load.
    word_to_kanjis = {}
    for kanji, entry in result.items():
        if entry:
            word_to_kanjis.setdefault(entry[0], []).append(kanji)
    collisions = {w: ks for w, ks in word_to_kanjis.items() if len(ks) > 1}
    if collisions:
        raise ValueError(
            "Duplicate representative study words after applying "
            "replaceKanjiStudyWords from raw/manual-inspections.json — each word "
            f"must map to exactly one kanji: {collisions}"
        )

    out_path = write_json("overrides/japanese_study_words-algo.json", result, indent=2)
    print(f"Written: {out_path}")

    print_report(result, all_kanji)

    print(f"\n  Selected words missing from JMdict ({len(missing_jmdict)}):")
    for word in missing_jmdict:
        print(f"    {word}")

    # Kanji whose ONLY viable pick is an affix-only entry (validity 1) — the user
    # wants standalone study words, so these are candidates for manual overrides.
    non_standalone = [
        (k, v) for k, v in result.items()
        if v and (r := resolver.resolve(v[0])) is not None and not r["standalone"]
    ]
    print(f"\n  Non-standalone picks — affix-only JMdict entries ({len(non_standalone)}):")
    for k, v in non_standalone:
        print(f"    {v[3]} {k} → {v[0]} ~ {v[1]} {v[2][:60]}")


def print_report(result, all_kanji):
    """Print selection statistics: tier/length/kanji-count breakdowns plus anomaly
    lists (no-word, no-meaning, not-starting-with-kanji, overlaps). Read-only over
    `result` — it does not affect the written output file."""
    selected_flat = [v for v in result.values() if v is not None]
    total = len(selected_flat)
    with_word = sum(1 for v in result.values() if v is not None)
    without   = sum(1 for v in result.values() if v is None)

    words         = [e[0] for e in selected_flat]
    tags          = [e[3] for e in selected_flat]
    length_counts = Counter(len(w) for w in words)
    kc_counts     = Counter(kanji_count(w) for w in words)
    tag_counts    = Counter(tags)

    # Per-tag and per-length groups: (kanji, entry) pairs preserving result order
    tag_groups    = {}
    length_groups = {}
    for k, v in result.items():
        if v is None:
            continue
        tag_groups.setdefault(v[3], []).append((k, v))
        length_groups.setdefault(len(v[0]), []).append((k, v))

    def kanji_compact(pairs):
        return ''.join(k for k, _ in pairs)

    display_tag_priority = {
        OVERRIDE_TAG: 0, "🌱": 1, "☘️": 2, "🌷": 3,
        OUTPUT_TEXTBOOK_TAG: 4, "📚": 5, "🦉": 7, "🌶️": 7
    }
    unknown_tag_priority = 6

    def print_entries(pairs):
        for k, v in sorted(pairs, key=lambda x: display_tag_priority.get(x[1][3], unknown_tag_priority)):
            print(f"{v[3]} {k} → {v[0]} ~ {v[1]} {v[2]}")

    tag_labels = {
        OVERRIDE_TAG: "✏️  manual",
        "🌱": "🌱  BASIC",
        "☘️": "☘️  COMMON",
        "🌷": "🌷  FLUENT",
        OUTPUT_TEXTBOOK_TAG: "📖  textbook",
        "📚": "📚  ADVANCED",
        "🦉": "🦉  UNRANKED",
        "🌶️": "🌶️  NICHE",
    }

    print(f"\n{'─'*44}")
    print(f"  Kanji processed:   {len(all_kanji)}")
    no_meaning = sum(1 for v in result.values() if v is not None and not v[2])
    no_reading = sum(1 for v in result.values() if v is not None and not v[1])

    print(f"  With word:         {with_word}")
    print(f"  Without word:      {without}")
    print(f"  No meaning:        {no_meaning}")
    print(f"  No reading:        {no_reading}")

    known_tags = set(tag_labels.keys())
    unknown_pairs = [(k, v) for k, v in result.items()
                     if v is not None and v[3] not in known_tags]
    n_unknown = len(unknown_pairs)

    print(f"\n  Tag / source breakdown")
    for tag, label in tag_labels.items():
        n = tag_counts.get(tag, 0)
        pct = n / total * 100 if total else 0
        pairs = tag_groups.get(tag, [])
        if tag == "🦉" or tag == "🌶️":
            print(f"    {label}: {n}  ({pct:.1f}%)  {kanji_compact(pairs)}")
            print_entries(pairs)
        else:
            print(f"    {label}: {n}  ({pct:.1f}%)")
        if tag == "📚":
            pct_u = n_unknown / total * 100 if total else 0
            print(f"    🤔  unknown: {n_unknown}  ({pct_u:.1f}%)  {kanji_compact(unknown_pairs)}")
            print_entries(unknown_pairs)

    print(f"\n  Word length")
    for length in sorted(length_counts):
        n = length_counts[length]
        pct = n / total * 100 if total else 0
        if length >= 4:
            pairs = length_groups.get(length, [])
            print(f"    {length} chars: {n}  ({pct:.1f}%)  {kanji_compact(pairs)}")
            print_entries(pairs)
        else:
            print(f"    {length} chars: {n}  ({pct:.1f}%)")

    kc_groups = {}
    for k, v in result.items():
        if v is None:
            continue
        kc_groups.setdefault(kanji_count(v[0]), []).append((k, v))

    print(f"\n  Kanji per word")
    for kc in sorted(kc_counts):
        n = kc_counts[kc]
        pct = n / total * 100 if total else 0
        if kc >= 3:
            pairs = kc_groups.get(kc, [])
            print(f"    {kc} kanji: {n}  ({pct:.1f}%)  {kanji_compact(pairs)}")
            print_entries(pairs)
        else:
            print(f"    {kc} kanji: {n}  ({pct:.1f}%)")

    print(f"{'─'*44}")

    if without:
        no_vocab = [k for k, v in result.items() if v is None]
        print(f"\nNo-word kanji ({without}): {''.join(no_vocab)}")

    print(f"")
    no_meaning = [k for k, v in result.items() if v is not None and not v[2]]
    print(f"No meaning kanji ({len(no_meaning)}): {''.join(no_meaning)}")

    for k, v in result.items():
        if v is not None and not v[2]:
            print(k, v)

    starts_with = [(k, v) for k, v in result.items() if v is not None and v[0].startswith(k)]
    not_starts_with = [(k, v) for k, v in result.items() if v is not None and not v[0].startswith(k)]
    print(f"\n  Words starting with kanji:     {len(starts_with)}")
    print(f"  Words NOT starting with kanji: {len(not_starts_with)}")

    if not_starts_with:
        print(f"\nKanji whose study word does NOT start with it ({len(not_starts_with)}):")
        print(f"  {''.join(k for k, _ in not_starts_with)}")
        print_entries(not_starts_with)

    # --- Overlap check ---
    from collections import defaultdict
    word_to_kanjis = defaultdict(list)
    for k, v in result.items():
        if v:
            word_to_kanjis[v[0]].append(k)
    overlapping = {w: ks for w, ks in word_to_kanjis.items() if len(ks) > 1}
    print(f"\n  Overlapping study words: {len(overlapping)}")
    for w, ks in overlapping.items():
        print(f"    {w}: {''.join(ks)}")

if __name__ == "__main__":
    main()
