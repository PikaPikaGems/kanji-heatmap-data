"""Shared data loading for the kanji-data scripts.

Project-relative path resolution, JSON loading, and the raw word-source readers
(v3 kanji-words, textbook words, JMdict gloss extraction). The readers return
unfiltered raw tuples — each caller applies its own validity rules, which differ
between the sample-vocab and representative-word selection algorithms.
"""

import json
import os


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
        json.dump(data, f, indent=indent, separators=separators, ensure_ascii=ensure_ascii)
    return full


# Internal tag marking a candidate as coming from the textbook word source rather
# than a v3 frequency band. Shared so both selection algorithms agree on the value.
TEXTBOOK_TAG = "__textbook__"


def load_v3_entries(kanji):
    """Raw (word, reading, tag, meaning) tuples from raw/kanji-words/v3/{kanji}.json."""
    data = load_json(f"raw/kanji-words/v3/{kanji}.json", [])
    return [
        (e.get("w", ""), e.get("r", ""), e.get("t", ""), e.get("e", ""))
        for e in data
    ]


def v3_candidates(kanji, keep):
    """v3 (word, reading, tag, meaning) tuples whose (word, reading) passes keep()."""
    return [e for e in load_v3_entries(kanji) if keep(e[0], e[1])]


def textbook_candidates(kanji, keep):
    """Textbook (word, reading, TEXTBOOK_TAG, meaning) tuples passing keep().

    Each selection algorithm supplies its own `keep(word, reading)` predicate — the
    validity rules differ (representative-word requires the word to start with the
    kanji; sample-vocab only requires it to contain the kanji)."""
    return [
        (w, r, TEXTBOOK_TAG, e)
        for w, r, e in load_textbook_entries(kanji)
        if keep(w, r)
    ]


def load_textbook_entries(kanji):
    """Raw (word, reading, meaning) tuples from raw/kanji-textbook-words/{kanji}.json."""
    data = load_json(f"raw/kanji-textbook-words/{kanji}.json", {})
    inner = data.get(kanji, {})
    entries = []
    for word, val in inner.items():
        if not isinstance(val, list) or len(val) < 1:
            continue
        reading = val[0] if len(val) >= 1 else ""
        meaning = val[1] if len(val) >= 2 else ""
        entries.append((word, reading, meaning))
    return entries


def _english_glosses(sense):
    return [g["text"] for g in sense.get("gloss", [])
            if g.get("lang") == "eng" and g.get("text")]


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
# Several scripts need "the English meaning of a word": the sample-vocab algorithm
# (to decide a word is eligible), fetch_missing (to decide a word still needs one),
# and the final build (to emit it). They used to each hard-code their own source
# ordering, which could disagree. resolve_meaning() fixes the precedence in ONE
# place; callers just pass whichever source maps they have loaded (absent ones are
# skipped). Precedence, most authoritative first:
#
#   common   jmdict common-form meanings (input/jmdict-vocab-meaning.json)
#   custom   hand-curated input/vocab_meaning.json + overrides/vocab_meaning.json
#   algo     overrides/vocab_meaning-algo.json (sample-vocab algorithm output)
#   external overrides/vocab_meaning-external-dict.json (Jotoba/Jisho cache)
#   ai       raw/ai-generated/vocab-meanings-ai.json
#   jmdict_full  any JMdict form (broader than `common`) — gap-filler
#   jsw      japanese_study_words-algo meanings — gap-filler


def resolve_meaning(word, *, common=None, custom=None, algo=None,
                    external=None, ai=None, jmdict_full=None, jsw=None):
    """First available meaning for `word` across the given source maps, in the fixed
    precedence above. Each argument is a {word: meaning} dict or None. Returns None
    when no source has a (non-empty) meaning."""
    for src in (common, custom, algo, external, ai, jmdict_full, jsw):
        if src:
            meaning = src.get(word)
            if meaning:
                return meaning
    return None


def ai_meaning_map(ai_raw):
    """Normalize raw/ai-generated/vocab-meanings-ai.json ({word: [meaning, ...]} or
    {word: meaning}) to a flat {word: meaning} map."""
    return {
        w: (v[0] if isinstance(v, list) else v)
        for w, v in ai_raw.items()
        if (v[0] if isinstance(v, list) else v)
    }


def jsw_meaning_map(jsw_algo):
    """{word: meaning} from japanese_study_words-algo.json entries ([word, reading,
    meaning, tag]), skipping entries with no meaning."""
    return {
        entry[0]: entry[2]
        for entry in jsw_algo.values()
        if entry and len(entry) >= 3 and entry[2]
    }
