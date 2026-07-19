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
Textbook words (raw/kanji-textbook-words-min, which carry their own JLPT level)
are merged in as a mid band — they mostly matter for the ~219 kanji that have
no freq-ranks file at all.

Special rule – single-kanji word in a top tier wins outright:
  If any candidate contains exactly one kanji (行 or 行く), sits in a top tier
  (BASIC/COMMON), and is a standalone JMdict word, it is chosen immediately —
  the study word should show THIS kanji as a word when the kanji is one.
  Within this group, normal word scoring applies, except that the bare kanji
  wins TIES through band/JLPT/class: 一 (not 一つ) — both BASIC N5 — while
  高い (N5) still beats 高 (N1) and 語る (verb) still beats 語.

Phrase fragments are rejected before scoring (resolver.is_phrase_fragment):
  demonstrative + noun (この人, その様) and standalone-word + particle chunks
  (常に, 今も, 事になる — the learner should study 常/今/事). Genuine adverbs
  survive: 特に (特 alone is not a standalone word), 更に (更 reads こう).

Word scoring (lower tuple wins):
    (validity, stage, band, jlpt, class, type, shipped, freq, len)
  validity  0 standalone JMdict word · 1 affix-only entry (新/しん) · 2 not in
            JMdict — outranks everything, so a real word from a lower tier always
            wins first. A kanji whose only pick is validity 1 or 2 has it DROPPED
            after selection (see below): it ships no study word rather than a
            non-word (affix-only) or an empty meaning (no JMdict entry)
  stage     words STARTING with the kanji beat words merely containing it
            (the textbook contains-pool safety net below)
  band      frequency tier band (textbook words sit at ADVANCED level)
  jlpt      N5 easiest first, untagged last — the strongest "teach this first"
            signal (空 N5 beats 空く N4; 高い N5 beats 高 N1); from the word's
            freq-ranks row, or the textbook's own jlpt field for textbook words
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
  readings (see jmdict_resolver.py). Words JMdict only knows as a rare writing
  get a gated second chance via resolve_fallback — usually-kana words carry a
  "[⚠️ often kana only]" marker (諄い/くどい), unshipped-glyph variants don't
  (充塡: canonical 充填 uses 填, which we don't ship), and ✏️ manual picks
  resolve ungated (昂ぶる). Words JMdict doesn't know at all get an empty meaning;
  together with affix-only picks (妃 卿 哉) they are logged and then DROPPED from
  the output before writing — the kanji ships no study word rather than a non-word.

Sources:
  intermediate/filtered_kanji.json              → [kanji]  (the kanji set to process)
  raw/freq-ranks/[kanji].tsv             → tab-separated corpus frequency rows
  raw/kanji-textbook-words-min/[kanji].json → {kanji: {word: [reading, meaning, jlpt, tags]}}
  input/scriptin-jmdict-eng.json         → JMdict JSON (words[].kanji/kana/sense)
  overrides/resolver_hints.json          → {replaceKanjiStudyWords: {kanji: word}} ✏️ pins
  input/jmdict-furigana-map.json         → {word: {reading: segments}}  (fallback readings)

The manual {kanji: word} pins in overrides/japanese_study_words.json are NOT read
here — they are merged onto this file's output at BUILD time
(kanji_load.dump_kanji_representative_words), reusing this module's
resolve_manual_pin_entries() so the reading/meaning derivation lives in one place.
Keeping the -algo output free of that override matches kanji_vocab / keywords: the
algo file is pure, the manual override merges later, and a collision throws for a
human to fix.

Output: overrides/japanese_study_words-algo.json
  { kanji: [word, reading, meaning, tag] }   (null when no valid word found)
  tag = tier emoji (🌱☘️🌷📚🌶️🦉), 📖 textbook, ✏️ manual override (replaceKanjiStudyWords)

Run from project root: python3 src/japanese_study_words_algo.py
"""

import csv
import os

from sources import (
    load_json,
    write_json,
    resolve_path,
    load_textbook_entries,
    freq_key,
    corpus_coverage,
    parse_rank,
    FREQ_TIER_TAG as TIER_TAG,
    DEFAULT_FREQ_TIER_TAG as DEFAULT_TIER_TAG,
)
from japanese import is_all_japanese, is_kanji_char, kanji_count
from jmdict_resolver import JmdictResolver, CLASS_OTHER

# ---------------------------------------------------------------------------
# Scoring / prioritisation
# ---------------------------------------------------------------------------

# NOTE: word_score / is_valid_candidate here intentionally differ from the
# same-named functions in kanji_vocab_algo.py — this algorithm
# requires the word to START with the kanji and scores by word-shape, while the
# sample-vocab algorithm only requires the kanji to appear anywhere.

# Frequency tier band from the freq-ranks `tier` column (lower = more frequent).
# Textbook words slot in at ADVANCED level: real corpus evidence of the first
# three tiers should beat a textbook appearance, but a curated textbook word
# beats NICHE/UNRANKED corpus noise.
TIER_BAND = {
    "BASIC": 0, "COMMON": 1, "FLUENT": 2, "ADVANCED": 3, "NICHE": 4, "UNRANKED": 5,
}
DEFAULT_TIER_BAND = 5
TEXTBOOK_BAND = 3

# The tier → tag-emoji map lives in sources (shared with kanji_vocab_algo); this
# script keeps its own numeric TIER_BAND above. TIER_TAG/DEFAULT_TIER_TAG are the
# imported aliases (see the sources import at the top).

# Bands eligible for the special rule (single-kanji standalone word wins outright).
TOP_BANDS = {TIER_BAND["BASIC"], TIER_BAND["COMMON"]}

# Distrust words attested in fewer weighted corpora than this — dropped unless
# that would leave the kanji with no candidates at all. (The composite frequency
# itself — freq_key, CORPUS_WEIGHTS — is shared with the sample-vocab algorithm
# and lives in sources.py.)
MIN_CORPUS_COVERAGE = 2

# TSV column names (raw/freq-ranks/*.tsv).
COL_WORD = "japanese_word"
COL_TIER = "tier"
COL_JLPT = "jlpt_level"

# JLPT levels run 5 (N5, easiest) .. 1 (N1); untagged sorts after all of them.
JLPT_UNTAGGED_RANK = 5


# The canonical kanji set (intermediate/filtered_kanji.json, written by
# build_filtered_kanji_json.py): ALL_KANJI keeps the frequency order main() iterates
# in; SHIPPED is the same set frozen for membership tests. Loaded once at import —
# fixed constants, never mutated (main() aborts loudly if the file was missing).
# Used to prefer study words whose every kanji ships, so a word doesn't drag in an
# unshipped partner (e.g. 麻 → 麻痺[痺 unshipped]) when an all-shipped option exists.
ALL_KANJI = load_json("intermediate/filtered_kanji.json", [])
SHIPPED = frozenset(ALL_KANJI)


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


# stage values: candidates that START with the kanji rank before those that
# merely CONTAIN it (textbook relaxed search — rare/classical kanji nothing
# starts with, e.g. 斐 → 甲斐).
STAGE_STARTS_WITH = 0
STAGE_CONTAINS = 1


def load_freq_candidates(kanji, resolver):
    """Valid freq-ranks candidates for `kanji`: {word, stage, band, tag, jlpt_rank, freq}.

    Words attested in fewer than MIN_CORPUS_COVERAGE corpora are dropped unless
    they resolve as standalone JMdict words (曖昧さ is real despite one corpus —
    the coverage filter exists to kill corpus junk, and junk never resolves) or
    dropping them would empty the pool (rare kanji often only have such words)."""
    rows = [r for r in read_freq_rows(kanji) if is_valid_word(r.get(COL_WORD, ""), kanji)]
    broad = [
        r for r in rows
        if corpus_coverage(r) >= MIN_CORPUS_COVERAGE
        or resolver_validity(resolver.resolve(r[COL_WORD])) == 0
    ]
    if broad:
        rows = broad
    candidates = []
    for row in rows:
        jlpt = parse_rank(row.get(COL_JLPT))
        candidates.append({
            "word": row[COL_WORD],
            "stage": STAGE_STARTS_WITH,
            "band": TIER_BAND.get(row.get(COL_TIER, ""), DEFAULT_TIER_BAND),
            "tag": TIER_TAG.get(row.get(COL_TIER, ""), DEFAULT_TIER_TAG),
            "jlpt_rank": JLPT_UNTAGGED_RANK if jlpt is None else 5 - jlpt,
            "freq": freq_key(row),
        })
    return candidates


def _textbook_cand(word, stage, jlpt):
    return {
        "word": word,
        "stage": stage,
        "band": TEXTBOOK_BAND,
        "tag": OUTPUT_TEXTBOOK_TAG,
        "jlpt_rank": JLPT_UNTAGGED_RANK if jlpt is None else 5 - jlpt,
        "freq": float("inf"),
    }


def load_textbook_candidates(kanji):
    """Textbook candidates containing `kanji`, same dict shape as freq ones;
    words starting with the kanji get STAGE_STARTS_WITH, the rest STAGE_CONTAINS.
    The pool's own JLPT level feeds the score's jlpt slot, same as freq-ranks'."""
    return [
        _textbook_cand(w, STAGE_STARTS_WITH if w[0] == kanji else STAGE_CONTAINS, jlpt)
        for w, _r, _e, jlpt in load_textbook_entries(kanji)
        if is_all_japanese(w) and kanji in w and 1 <= kanji_count(w) <= 2
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
OVERRIDE_TAG = "✏️"  # manual study-word override (replaceKanjiStudyWords in overrides/resolver_hints.json)


def frequency_tag(kanji, word):
    """The real frequency-tier badge for `word` (🌱☘️🌷📚🌶️🦉 / 📖), tagged the same
    way the algo tags a non-pinned pick: its own freq-ranks row (keyed by the word's
    first character) decides the tier; a word no corpus ranks falls back to 📖 when
    the kanji's textbook pool lists it, else 🦉 (UNRANKED).

    Used at build time to REPLACE the ✏️ manual-override tag with a real badge in the
    OUTPUT json — logs keep ✏️ (see print_report) to mark which picks were manual."""
    for row in read_freq_rows(word[0]):
        if row.get(COL_WORD) == word:
            return TIER_TAG.get(row.get(COL_TIER, ""), DEFAULT_TIER_TAG)
    if any(w == word for w, _r, _e, _j in load_textbook_entries(kanji)):
        return OUTPUT_TEXTBOOK_TAG
    return DEFAULT_TIER_TAG


def select_word_for_kanji(kanji, used_words, resolver):
    """Return the best [word, "", "", tag] for this kanji, or None. Reading and
    meaning are attached later by the caller (always from the resolver).

    used_words: set of words already assigned to other kanjis — these are skipped.
    """
    merged = {}  # word → candidate; later sources win: freq-ranks over textbook
    for cand in load_textbook_candidates(kanji) + load_freq_candidates(kanji, resolver):
        merged[cand["word"]] = cand
    resolved_bare = resolver.resolve(kanji)
    if resolved_bare is not None and resolved_bare["standalone"]:
        merged.setdefault(kanji, bare_kanji_candidate(kanji))
    candidates = [
        c for c in merged.values()
        if c["word"] not in used_words
        and not resolver.is_phrase_fragment(c["word"])  # 常に, 今も, この人
    ]

    scored = sorted(
        ((word_score(c, resolver.resolve(c["word"])), c) for c in candidates),
        key=lambda pair: pair[0],
    )
    if not scored:
        return None

    # Special rule: a single-kanji standalone word in a top band wins outright —
    # when the kanji IS a common word, that word represents it best (毎 over 毎日).
    # The validity gate keeps affix-only entries out (同じ must beat bare 同).
    special = [
        (score, cand) for score, cand in scored
        if (kanji_count(cand["word"]) == 1 and cand["band"] in TOP_BANDS
            and resolver_validity(resolver.resolve(cand["word"])) == 0)
    ]
    if special:
        best_score, best = special[0]
        # Within the special rule the bare kanji wins TIES: when it matches the
        # best qualifying word through band/JLPT/class (一 vs 一つ — both BASIC,
        # N5, class other), the kanji itself is the word to study (一/いち).
        # Real differences still decide: 高い (N5) keeps beating 高 (N1), and
        # 語る (verb) keeps beating 語 on word class.
        for score, cand in special:
            if cand["word"] == kanji and score[:5] == best_score[:5]:
                return [cand["word"], "", "", cand["tag"]]
        return [best["word"], "", "", best["tag"]]

    best = scored[0][1]
    return [best["word"], "", "", best["tag"]]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_manual_replace_words():
    data = load_json("overrides/resolver_hints.json", {})
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


def attach_reading_meaning(entry, resolver, shipped, jmdict_readings):
    """Overwrite entry's reading/meaning ([1]/[2]) from the resolver — the pools'
    own r/e fields inform selection only and must never reach the output. Words whose
    writing JMdict tags rare get a gated second chance (諄い/くどい ⚠️, 充塡/じゅうてん);
    manual ✏️ picks resolve ungated. A word that resolves nowhere gets an empty
    meaning (and, in the algo path, is dropped from the output below — see the
    post-pins non-word removal). Mutates and returns `entry`.

    This is the single derivation used for BOTH the algo's own picks and the manual
    pins (replaceKanjiStudyWords here, japanese_study_words.json at build time via
    resolve_manual_pin_entries), so reading/meaning are derived identically."""
    resolved = resolver.resolve(entry[0]) or resolver.resolve_fallback(
        entry[0], shipped=shipped, manual=entry[3] == OVERRIDE_TAG)
    if resolved:
        entry[1] = resolved["reading"]
        entry[2] = resolved["meaning"]
    else:
        entry[1] = jmdict_readings.get(entry[0], "")
        entry[2] = ""
    return entry


def apply_manual_pins(result, pins, resolve_pin):
    """Apply a {kanji: word} manual-pin map to `result`, expanding each pin into a
    full [word, reading, meaning, tag] entry via `resolve_pin`. A pin for an
    unshipped kanji (not in result) is skipped."""
    for kanji, word in pins.items():
        if kanji not in result:
            continue
        result[kanji] = resolve_pin(word)


def resolve_manual_pin_entries(pins):
    """Turn a {kanji: word} manual-pin map into {kanji: [word, reading, meaning, ✏️]},
    deriving reading/meaning exactly as the algo does (attach_reading_meaning).

    The build step (kanji_load.dump_kanji_representative_words) calls this to merge
    overrides/japanese_study_words.json onto the -algo output WITHOUT re-running the
    whole selection, so that override file can stay a plain {kanji: word} map and the
    derivation logic lives here only. Builds its own resolver/readings context because
    it runs in a separate process from main(); SHIPPED is the module-level constant."""
    resolver = JmdictResolver()
    jmdict_readings = load_jmdict_readings()
    return {
        kanji: attach_reading_meaning([word, "", "", OVERRIDE_TAG],
                                      resolver, SHIPPED, jmdict_readings)
        for kanji, word in pins.items()
    }


def main():
    all_kanji = ALL_KANJI  # loaded once at module level (with SHIPPED)
    if not all_kanji:
        raise SystemExit(
            "intermediate/filtered_kanji.json missing or empty — "
            "run src/build_filtered_kanji_json.py first"
        )
    manual_words = load_manual_replace_words()
    jmdict_readings = load_jmdict_readings()
    resolver = JmdictResolver()

    result = {}
    used_words = set()  # enforces uniqueness across all kanjis

    for kanji in all_kanji:
        entry = select_word_for_kanji(kanji, used_words, resolver)

        # Reduce a 2-kanji 〜する/〜な headword to its bare noun (解剖する → 解剖).
        if entry:
            entry = strip_junk_suffix(entry, used_words, resolver)

        if entry:
            entry = attach_reading_meaning(entry, resolver, SHIPPED, jmdict_readings)
            used_words.add(entry[0])

        result[kanji] = entry

    # --- Apply replaceKanjiStudyWords manual pins (overrides/resolver_hints.json) ---
    # Reading/meaning are derived here, so the override file is just {kanji: word}.
    # The other manual source, overrides/japanese_study_words.json, is NOT applied
    # here — it merges onto this file's output at build time (see the module docstring
    # and kanji_load.dump_kanji_representative_words).
    def resolve_pin(word):
        return attach_reading_meaning([word, "", "", OVERRIDE_TAG],
                                      resolver, SHIPPED, jmdict_readings)

    apply_manual_pins(result, manual_words, resolve_pin)  # resolver_hints.json

    # Pins are applied without the per-selection uniqueness check above, so a manual
    # word can collide with one already chosen for another kanji. Fail loudly here
    # (at the source) instead of downstream in kanji_load.
    word_to_kanjis = {}
    for kanji, entry in result.items():
        if entry:
            word_to_kanjis.setdefault(entry[0], []).append(kanji)
    collisions = {w: ks for w, ks in word_to_kanjis.items() if len(ks) > 1}
    if collisions:
        raise ValueError(
            "Duplicate representative study words after applying replaceKanjiStudyWords "
            "pins (overrides/resolver_hints.json) — each word must map to exactly "
            f"one kanji: {collisions}"
        )

    # --- Drop non-words (computed AFTER overrides, so pinned fixes count) -------
    # Two kinds of pick are not real standalone study words and are removed from
    # the output entirely — the kanji then ships no study word (joins "Without
    # word") rather than a bad one. Both are logged first, so a curator can add a
    # real word to replaceKanjiStudyWords (overrides/resolver_hints.json) if wanted.
    no_entry = [(k, v) for k, v in result.items() if v and not v[2]]
    non_standalone = [
        (k, v) for k, v in result.items()
        if v and (r := resolver.resolve(v[0])) is not None and not r["standalone"]
    ]

    print(f"\n  Study words with NO JMdict entry ({len(no_entry)}) — DROPPED:")
    print("  JMdict doesn't know these words at all (they resolve nowhere and would")
    print("  ship an empty meaning), so they are removed and the kanji ships no study")
    print("  word. Add a real word in replaceKanjiStudyWords (overrides/resolver_hints.json).")
    for k, v in no_entry:
        print(f"    {v[3]} {k} → {v[0]}")

    print(f"\n  Study words that are not standalone words ({len(non_standalone)}) — DROPPED:")
    print("  JMdict lists these only as a prefix/suffix/counter (e.g. 妃/ひ 'princess'")
    print("  is a suffix), never used on their own, so they are removed and the kanji")
    print("  ships no study word. Add a real word in replaceKanjiStudyWords")
    print("  (overrides/resolver_hints.json).")
    for k, v in non_standalone:
        print(f"    {v[3]} {k} → {v[0]} ~ {v[1]} {v[2]}")

    for k, _ in no_entry + non_standalone:
        result[k] = None

    out_path = write_json("overrides/japanese_study_words-algo.json", result, indent=2)
    print(f"Written: {out_path}")

    # Reporting is diagnostic-only (stdout, writes no file). Imported here (late) so
    # the report module's top-level `import japanese_study_words_algo` sees this module
    # fully loaded — avoids an import cycle.
    import study_words_report
    study_words_report.print_report(result, all_kanji, resolver)


if __name__ == "__main__":
    main()
