"""Shared data loading for the kanji-data scripts.

Project-relative path resolution, JSON loading, the raw word-source readers
(textbook words, JMdict gloss extraction) and the freq-ranks composite corpus
frequency. The readers return unfiltered raw tuples — each caller applies its
own validity rules, which differ between the sample-vocab and
representative-word selection algorithms.
"""

import functools
import json
import os

# Textbook word-pool folder under raw/. Only kanji-textbook-words-min exists (the
# untrimmed kanji-textbook-words dir was deleted 2026-07-12); the TEXTBOOK_SUBDIR
# env var remains as an escape hatch for pointing at an experimental sibling.
TEXTBOOK_SUBDIR = os.environ.get("TEXTBOOK_SUBDIR", "kanji-textbook-words-min")


def resolve_path(rel_path):
    """Resolve a path relative to the project root (the parent of src/)."""
    src_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(src_dir), rel_path)


def load_json(rel_path, default=None):
    """Load JSON at a project-relative path; return `default` ({} if None) if absent."""
    full = resolve_path(rel_path)
    if not os.path.exists(full):
        return {} if default is None else default
    with open(full, encoding="utf-8") as f:
        return json.load(f)


def write_json(rel_path, data, *, indent=None, separators=None, ensure_ascii=False):
    """Write `data` as JSON to a project-relative path, creating parent dirs.

    `indent` / `separators` are passed straight to json.dump so each caller keeps
    its file's existing on-disk format (compact for output/*, indented for
    overrides/*). Returns the resolved absolute path.
    """
    full = resolve_path(rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        json.dump(
            data, f, indent=indent, separators=separators, ensure_ascii=ensure_ascii
        )
    return full


# The full JMdict dump (input/scriptin-jmdict-eng.json, ~100MB parsed). Several
# build steps need it in one process (the resolver, the furigana readings lookup,
# and the meaning index all run inside the final build), so parse it once and
# memoize. Callers must treat the result as READ-ONLY — it is a shared object.
JMDICT_PATH = "input/scriptin-jmdict-eng.json"


@functools.lru_cache(maxsize=1)
def load_jmdict():
    """Load and memoize the full JMdict (input/scriptin-jmdict-eng.json)."""
    return load_json(JMDICT_PATH, {})


# Internal tag marking a candidate as coming from the textbook word source rather
# than a corpus frequency band. Shared so both selection algorithms agree on the value.
TEXTBOOK_TAG = "__textbook__"


# The freq-ranks `tier` column mapped to its display emoji (most frequent 🌱 → rarest
# 🦉). Shared so both selection algorithms and their reports use identical glyphs; each
# script still layers its own numeric ordering on top (study-word TIER_BAND, sample-vocab
# TAG_PRIORITY). A tier the column doesn't name falls back to DEFAULT_FREQ_TIER_TAG.
FREQ_TIER_TAG = {
    "BASIC": "🌱", "COMMON": "☘️", "FLUENT": "🌷",
    "ADVANCED": "📚", "NICHE": "🌶️", "UNRANKED": "🦉",
}
DEFAULT_FREQ_TIER_TAG = "🦉"


# ---------------------------------------------------------------------------
# freq-ranks corpus data (raw/freq-ranks/*.tsv)
# ---------------------------------------------------------------------------
#
# Each TSV lists the words starting with its key character (kanji AND kana files),
# with a frequency RANK per corpus (lower = more frequent; NA = absent), a
# precomputed `tier` band and JLPT level. Both selection algorithms rank
# same-tier words by the composite frequency below, so it lives here.

# Per-corpus weight in the composite frequency; 0 drops a corpus. SPOKEN/everyday
# corpora (conversation, subtitles) weigh more than WRITTEN ones (web, wiki) —
# a learner's word is better drawn from speech than from text.
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


def parse_rank(value):
    """Parse a corpus rank cell: int rank, or None for NA/blank/garbage."""
    if not value or value == "NA":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def freq_key(row):
    """Composite corpus frequency for a freq-ranks row — LOWER is better.

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
        r = parse_rank(row.get(col))
        if r is None:
            continue
        num += weight * r
        den += weight
        present += 1
    if den == 0:
        return float("inf")
    return (num / den) * (1 + COVERAGE_PENALTY * (weighted_total - present))


def corpus_coverage(row):
    """How many weighted corpora the word appears in (non-NA, weight > 0)."""
    return sum(
        1 for col, weight in CORPUS_WEIGHTS.items()
        if weight > 0 and parse_rank(row.get(col)) is not None
    )


def load_textbook_entries(kanji, subdir=TEXTBOOK_SUBDIR):
    """Raw (word, reading, meaning, jlpt) tuples from raw/{subdir}/{kanji}.json.

    Each file value is [reading, meaning, jlptLevel?, tags?] — jlptLevel is a
    numeric string ("5" = N5 .. "1" = N1), absent or null when untagged, so
    `jlpt` comes back as int 5..1 or None. The trailing tags field ("kaishi",
    "uk") is not used by any caller and is dropped.

    subdir selects the textbook word pool (default kanji-textbook-words-min)."""
    data = load_json(f"raw/{subdir}/{kanji}.json", {})
    inner = data.get(kanji, {})
    entries = []
    for word, val in inner.items():
        if not isinstance(val, list) or len(val) < 1:
            continue
        reading = val[0] if len(val) >= 1 else ""
        meaning = val[1] if len(val) >= 2 else ""
        jlpt = parse_rank(val[2]) if len(val) >= 3 else None
        entries.append((word, reading, meaning, jlpt))
    return entries


def _english_glosses(sense):
    return [
        g["text"]
        for g in sense.get("gloss", [])
        if g.get("lang") == "eng" and g.get("text")
    ]


def jmdict_word_definition(entry, word, definition_count=3):
    """English glosses from the senses of `entry` that apply to `word` (appliesToKanji
    is '*' or names the word), joined to at most `definition_count`. None if no sense
    applies. This is the appliesToKanji-correct definition for a specific writing."""
    applicable = []
    for sense in entry.get("sense", []):
        applies_to = sense.get("appliesToKanji", [])
        if "*" in applies_to or word in applies_to:
            applicable.extend(_english_glosses(sense))
    return ", ".join(applicable[:definition_count]) if applicable else None


def jmdict_entry_gloss(entry, word=None, definition_count=3):
    """English meaning for a JMdict entry, joined to at most `definition_count` glosses.

    When `word` is given, prefer the senses that apply to it (see jmdict_word_definition).
    This stops a multi-writing entry from giving every form the first sense's meaning
    when that sense only applies to a sibling form (e.g. 配う borrowing 配る's "to
    distribute"). Falls back to the entry's first English sense when no sense applies to
    the word (rare), so a meaning is never lost. Returns None only when the entry has no
    English gloss at all.
    """
    if word is not None:
        applicable = jmdict_word_definition(entry, word, definition_count)
        if applicable is not None:
            return applicable

    # word is None, or no sense applied to it: fall back to the first English sense.
    for sense in entry.get("sense", []):
        glosses = _english_glosses(sense)
        if glosses:
            return ", ".join(glosses[:definition_count])
    return None


# ---------------------------------------------------------------------------
# Word-meaning source: JMdict (input/scriptin-jmdict-eng.json), single source
# ---------------------------------------------------------------------------
#
# The final build needs "the English meaning of a word" (to emit it). Every gloss
# comes from JMdict — the same appliesToKanji-aware gloss the sample-vocab algorithm
# builds (jmdict_entry_gloss). build_jmdict_meaning_index turns the loaded JMdict
# into the two maps the resolver needs; the only override layer above it is the
# (now empty, kept for future) overrides/vocab_meaning.json manual hatch.


def build_jmdict_meaning_index(jmdict, definition_count=3):
    """From loaded JMdict (`jmdict` = input/scriptin-jmdict-eng.json), build:

      gloss     {form: english gloss}  — every kanji/kana surface form, appliesToKanji
                aware (the sample-vocab algorithm's jmdict_entry_gloss). A form that is
                itself flagged common is glossed first, so a writing shared with a rarer
                homograph (お店, 万歳, 中身) gets the common sense, not the obscure one.
                Note this must key on the *form's* own common flag, not the entry's: 万歳
                is a rare alt-writing of the common 万年 ("ten thousand years") entry, so
                an entry-level check would wrongly stamp that gloss onto 万歳.
      is_common {form: bool}           — whether that form is flagged common by JMdict.

    Returns (gloss, is_common).
    """
    gloss = {}
    is_common = {}

    def consume(entry, *, common_forms_only):
        has_gloss = jmdict_entry_gloss(entry) is not None
        for form in entry.get("kanji", []) + entry.get("kana", []):
            t = form.get("text", "")
            if not t:
                continue
            common = bool(form.get("common"))
            if common:
                is_common[t] = True
            elif t not in is_common:
                is_common[t] = False
            if common_forms_only and not common:
                continue
            if has_gloss and t not in gloss:
                m = jmdict_entry_gloss(entry, t, definition_count)
                if m:
                    gloss[t] = m

    words = jmdict.get("words", [])
    for entry in words:  # pass 1: common forms only, earliest common entry wins
        consume(entry, common_forms_only=True)
    for entry in words:  # pass 2: everything else fills the gaps
        consume(entry, common_forms_only=False)
    return gloss, is_common
