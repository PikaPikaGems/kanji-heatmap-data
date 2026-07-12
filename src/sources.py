"""Shared data loading for the kanji-data scripts.

Project-relative path resolution, JSON loading, the raw word-source readers
(textbook words, JMdict gloss extraction) and the freq-ranks composite corpus
frequency. The readers return unfiltered raw tuples — each caller applies its
own validity rules, which differ between the sample-vocab and
representative-word selection algorithms.
"""

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


# Internal tag marking a candidate as coming from the textbook word source rather
# than a corpus frequency band. Shared so both selection algorithms agree on the value.
TEXTBOOK_TAG = "__textbook__"


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


def textbook_candidates(kanji, keep, subdir=TEXTBOOK_SUBDIR):
    """Textbook (word, reading, TEXTBOOK_TAG, meaning) tuples passing keep().

    The caller supplies a `keep(word, reading)` validity predicate. The entries'
    JLPT level is dropped here — callers that need it (the representative-word
    algorithm's scoring) read load_textbook_entries directly.

    subdir selects which textbook folder under raw/ to read (see load_textbook_entries).
    """
    return [
        (w, r, TEXTBOOK_TAG, e)
        for w, r, e, _jlpt in load_textbook_entries(kanji, subdir)
        if keep(w, r)
    ]


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
# Word-meaning resolution (single source of truth for source precedence)
# ---------------------------------------------------------------------------
#
# The final build needs "the English meaning of a word" (to emit it). Rather than
# hard-code a source ordering at the call site, resolve_meaning() fixes the
# precedence in ONE place; the caller passes whichever source maps it has loaded
# (absent ones are skipped). Precedence, most authoritative first:
#
#   common   jmdict common-form meanings (input/jmdict-vocab-meaning.json)
#   custom   hand-curated input/vocab_meaning.json + overrides/vocab_meaning.json
#   algo     overrides/vocab_meaning-algo.json (sample-vocab algorithm output)
#   jmdict_full  any JMdict form (broader than `common`) — gap-filler


def resolve_meaning(
    word,
    *,
    common=None,
    custom=None,
    algo=None,
    jmdict_full=None,
):
    """First available meaning for `word` across the given source maps, in the fixed
    precedence above. Each argument is a {word: meaning} dict or None. Returns None
    when no source has a (non-empty) meaning."""
    for src in (common, custom, algo, jmdict_full):
        if src:
            meaning = src.get(word)
            if meaning:
                return meaning
    return None
