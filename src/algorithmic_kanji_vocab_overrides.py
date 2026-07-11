#!/usr/bin/env python3
"""
Task: Better Sample Vocabulary
Selects up to two sample words per kanji and writes overrides/kanji_vocab-algo.json,
vocab_meaning-algo.json and vocab_reading-algo.json. (Furigana for the selected
words is generated afterwards by src/generate_furigana_algo.py, which computes the
shipped word set itself.)

Selection rules:
- Word must be >= 2 characters (hiragana included)
- Must contain at least one kanji
- Prefer fewer kanji in word (minimum 1)
- 2-3 chars ideal (no preference between them); 4 okay; 5 allowed; 6+ not allowed
- A meaning must be available from some known source — either the candidate's own
  meaning or one of the local dictionaries (input/vocab_meaning.json, jmdict cache,
  japanese_study_words-algo). Words with no definition anywhere are never selected.
- A dictionary reading must exist (furigana map, or JMdict whole-word / per-span) —
  v3 corpus phrase fragments like 犬五匹 or 森様御夫妻 that would ship bare furigana
  are ignored as if they didn't exist (see has_dictionary_reading).

Kanji listed in overrides/kanji_to_remove.json are skipped entirely.

Source priority (lower tier wins; ties broken by fewer kanji → length band [2-3
ideal, 4 ok, 5 max] → has-reading → has-meaning → shorter overall [2 beats 3]).
Hand-curated picks live in overrides/kanji_vocab.json and win at BUILD time
(build_helpers.get_words), not here. The primary pool is the freq-ranks corpus
dataset (raw/freq-ranks/*.tsv, indexed once so a word counts for EVERY kanji it
contains, not just the one it starts with), whose tier column maps onto the same
emoji bands the old v3 pool used. The two fallbacks only fill a slot when no
freq-ranks/textbook candidate exists and never displace a primary word:
   0. freq-ranks tier BASIC 🌱   (most frequent band; beats ☘️ even with more kanji)
   1. freq-ranks tier COMMON ☘️
   2. freq-ranks tier FLUENT 🌷
   3. textbook words             raw/kanji-textbook-words/
   4. freq-ranks tier ADVANCED 📚 (or unknown)
   5. freq-ranks NICHE 🌶️ / UNRANKED 🦉
   6. current production words   input/kanji_vocab.json           (fallback)
   7. full JMdict                input/scriptin-jmdict-eng.json   (fallback)

Deduplication: if a word appears in both freq-ranks and textbook, keep whichever
gives the better (lower) score — so a textbook word isn't unfairly penalised just
because it also appears in the corpus data under a lower-priority tier.

Second-word diversity: after the best word is chosen, the second pick prefers a word
in which the kanji takes a DIFFERENT reading than in the first word (e.g. 考える/考慮
over 考える/考え) — but only when that second word is itself high-frequency (🌱☘️🌷).
Below that band frequency wins: the more common (usually same-reading) word is kept
rather than dropping a tier for variety. Ties fall back to "fewest shared kanji",
which also prevents two near-identical words (e.g. 烏賊 / 烏賊墨) being chosen together.
Per-kanji readings come from input/jmdict-furigana-map.json; readings differing only by
rendaku (連濁) or gemination (促音) — げつ/げっ, と/ど — count as the SAME reading, while
genuinely distinct readings (画: が/かく) stay apart. As a last resort, if the pair is
still redundant (one word contains the other, or an identical kanji set, e.g. 入る/入れる),
a different-reading word from down to the 📚 tier may replace the second.

Phrase exclusion: words where a grammatical particle (て で に を が は も へ と) appears
between two kanji sequences are treated as verbal phrases and excluded, so true
compound words are preferred over phrases like 診て貰う.

Proper-noun demotion: place names, personal names, companies and era names
(北京, 佐藤, 講談社, 嘉永) score below every ordinary word regardless of frequency
tier — they teach a label rather than vocabulary, and JmdictFurigana deliberately
excludes name readings so their furigana is unreliable. They are demoted, not
banned: a kanji whose only real usage IS names (媛 → 愛媛県, 浩 → 浩二) still gets
one. Detection is heuristic — JMdict tags most famous places as plain nouns — via
gloss patterns ("(city", "surname", " era (", …) and katakana readings on all-kanji
words (北京 → ペキン).

Sources:
  input/filtered_kanji.json                → [kanji]  (the kanji set to process)
  raw/freq-ranks/*.tsv                     → corpus frequency rows (word, gloss,
                                             tier, other_forms with kana spelling)
  raw/kanji-textbook-words/[kanji].json    → {kanji: {word: [reading, meaning]}}
  input/kanji_vocab.json                   → {kanji: [word, ...]}   (existing fallback)
  input/scriptin-jmdict-eng.json           → JMdict                 (jmdict fallback)
  input/jmdict-furigana-map.json           → {word: {reading: segments}}  (readings)
  Meaning sources (a word is eligible only if one has its meaning):
    input/vocab_meaning.json, input/jmdict-vocab-meaning.json,
    overrides/japanese_study_words-algo.json

Outputs (overrides/): kanji_vocab-algo.json, vocab_meaning-algo.json,
  vocab_reading-algo.json

Run from the project root: python3 src/algorithmic_kanji_vocab_overrides.py
"""

import csv
import glob
import json
import unicodedata

from sources import (
    resolve_path,
    load_json,
    write_json,
    jmdict_entry_gloss,
    textbook_candidates,
    TEXTBOOK_TAG,
    freq_key,
)
from japanese import is_all_japanese, is_kanji_char, kanji_count, reading_of_kanji_in_segments, segment_word

# NOTE: word_score / is_valid_candidate here intentionally differ from the
# same-named functions in build_representative_study_word_algo.py — this algorithm
# only requires the kanji to appear anywhere in the word and scores by length
# bands + reading/meaning availability, while that one requires a starting kanji.

EXISTING_TAG = '__existing__'
JMDICT_TAG = '__jmdict__'

PHRASE_PARTICLES = set('てでにをがはもへと')

TAG_PRIORITY = {
    '🌱': 0,           # most frequent band — strictly preferred over ☘️
    '☘️': 1,
    '🌷': 2,
    TEXTBOOK_TAG: 3,
    '📚': 4,
    '🦉': 5,
    '🌶️': 5,
    EXISTING_TAG: 6,  # current production words (input/kanji_vocab.json): last-resort fallback
    JMDICT_TAG: 7,    # full JMdict: last-resort for rare kanji with no other valid word
}
DEFAULT_TAG_PRIORITY = 4  # unknown v3 tags treated like 📚

# Tiers <= this are "primary" (v3 + textbook). The fallback tiers above (existing,
# jmdict) only fill a slot when no primary candidate is available — they never
# displace a primary word for diversity.
PRIMARY_TIER_MAX = 5

# Reading-diversity for the second word is only pursued when that word is itself
# high-frequency (🌱☘️🌷, tier <= 2); below that band, frequency/tier wins and the
# more common (usually same-reading) word is kept rather than dropping a tier.
HIGH_FREQ_TIER_MAX = 2

# Last-resort band for breaking up a redundant pair: when the only high-frequency
# second word merely repeats the first (e.g. 入る/入れる), a different-reading word
# from down to this tier (textbook 📖 = 3, 📚 = 4) may replace it instead.
EXTENDED_TIER_MAX = 4

# JMdict kanji-form tags to skip: search-only forms and phonetic (ateji) spellings,
# neither of which is a good representative sample word.
JMDICT_EXCLUDE_TAGS = {'sK', 'ateji'}


def _fmt_tag(tag):
    # ☘️ and ✍️ are VS16 sequences (base char + U+FE0F) that macOS renders NARROWER
    # than single-codepoint emoji, which breaks column alignment on the rows they appear
    # in (every other tag/medal is a single, uniform-width emoji). Remap them to
    # single-codepoint look-alikes (🍀 clover, 📝 memo) so all glyphs share one width.
    return {
        "☘️": "☘️ ",
        "🌶️": "🌶️ ",
        "✏️": "✏️ ",
        TEXTBOOK_TAG: "📖",
        EXISTING_TAG: "📋",
        JMDICT_TAG: "📕",
    }.get(tag, tag)


def _display_width(s):
    """Terminal display width: CJK and emoji (incl. VS16 sequences) count as 2 columns."""
    w = 0
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        cp = ord(c)
        nxt = s[i + 1] if i + 1 < n else ''
        if nxt == '️':  # emoji presentation: base + VS16 renders wide (☘️ ✍️)
            w += 2
            i += 2
            continue
        if 0xFE00 <= cp <= 0xFE0F or unicodedata.combining(c):  # stray VS / combining marks
            i += 1
            continue
        eaw = unicodedata.east_asian_width(c)
        if eaw in ('W', 'F') or cp >= 0x1F000:  # wide CJK + emoji plane (🥇🌱 etc.)
            w += 2
        else:
            w += 1
        i += 1
    return w


def _pad(s, target_width):
    return s + ' ' * max(0, target_width - _display_width(s))


def has_phrase_bridge(word):
    """True if a grammatical particle appears between two kanji sections."""
    saw_kanji = False
    saw_bridge = False
    for ch in word:
        if is_kanji_char(ch):
            if saw_bridge:
                return True
            saw_kanji = True
        elif saw_kanji and ch in PHRASE_PARTICLES:
            saw_bridge = True
    return False


# Kanji we ship (input/filtered_kanji.json); populated in main(). Sample words
# whose every kanji ships are preferred, so a kanji's example doesn't drag in an
# unshipped partner (玉 → 玉葱[葱 unshipped]) when an all-shipped option exists.
SHIPPED = set()

# Words the furigana step (generate_furigana_algo.py) can actually read; populated
# in main(). FURIGANA_MAP_WORDS = keys of input/jmdict-furigana-map.json;
# READABLE_FORMS = every JMdict kanji form that has a kana reading. A candidate
# readable by neither route would ship bare [[word]] furigana (v3 corpus phrase
# fragments like 犬五匹, 森様御夫妻), so it is ignored as if it didn't exist.
FURIGANA_MAP_WORDS = set()
READABLE_FORMS = set()


def has_dictionary_reading(word):
    """True if a real reading exists for `word` somewhere the furigana generator
    looks: the furigana map, a whole-word JMdict kana form, or — mirroring the
    per-span fallback — a JMdict kana form for every kanji span (必須の → 必須+の)."""
    if word in FURIGANA_MAP_WORDS or word in READABLE_FORMS:
        return True
    return all(
        not is_kanji_span or text in READABLE_FORMS
        for text, is_kanji_span in segment_word(word)
    )


def has_nonshipped_kanji(word):
    """1 if `word` contains a kanji we don't ship, else 0 (sorts all-shipped first)."""
    return 1 if any(is_kanji_char(c) and c not in SHIPPED for c in word) else 0


# Gloss fragments that mark a proper noun. JMdict tags most famous places as plain
# nouns, so detection has to lean on how their glosses are written: geography and
# name entries carry parenthesised annotations ("Nara (city, prefecture)",
# "Satô (surname)", "Kaei era (1848...)", "Kodansha (publisher)").
PROPER_NOUN_GLOSS_FRAGMENTS = (
    'surname', 'given name', 'place name', 'family name',
    '(city', 'city in', 'City)', '(prefecture', 'prefecture)', 'Prefecture',
    '(province', 'former province', 'province)', '(country', '(district',
    '(island', 'ward of', '(region',
    ' era (', 'era name', 'Emperor ',
    '(company', 'company)', '(publisher', 'publisher)', '(organization',
    'organisation)', 'conglomerate', '(manufacturer', 'manufacturing company',
    '(deity', '(god of', 'Bodhisattva',
    '(China)', '(Japan)', '(South Korea)', '(North Korea)', '(UK)', '(USA)',
    '(France)', '(Germany)', '(Russia)', '(Taiwan)', '(Brazil)', '(Bulgaria)',
)
# Deliberately NOT flagged: bare country-name glosses ("Japan", "South Korea",
# "Taiwan") — words like 日本/韓国/台湾 are legitimate everyday vocabulary. The
# parenthesised forms above only catch entries where the country is an annotation
# on a foreign place name ("Busan (South Korea)").

# Resolved gloss per word for proper-noun detection; populated in main(). Needed
# because v3/textbook candidate entries often carry a bare gloss ("Shinano") while
# the dictionaries' richer one ("Shinano (former province ...)") is what reveals
# the name-ness. Module-level for word_score's sake, like SHIPPED above.
PN_GLOSS_LOOKUP = {}


def is_proper_noun(word, e="", r=""):
    """1 if the candidate looks like a proper noun (place, person, company, era).

    Two heuristic signals: gloss fragments (candidate's own gloss plus the resolved
    dictionary gloss), and a katakana reading on an all-kanji word (北京 → ペキン),
    which marks foreign place names. Heuristic by necessity — JMdict has no
    reliable tag for these (北京/奈良 are tagged plain 'n').
    """
    for gloss in (e, PN_GLOSS_LOOKUP.get(word)):
        if gloss and any(frag in gloss for frag in PROPER_NOUN_GLOSS_FRAGMENTS):
            return 1
    if (
        r and r != '-'
        and all(is_kanji_char(c) for c in word)
        and all('ァ' <= c <= 'ヶ' or c == 'ー' for c in r)
    ):
        return 1
    return 0


def word_score(word, tag, e="", r=""):
    """Lower is better. Tuple for lexicographic comparison."""
    kc = kanji_count(word)
    n = len(word)
    ts = TAG_PRIORITY.get(tag, DEFAULT_TAG_PRIORITY)
    extra_kanji = kc - 1  # 0 = best (exactly 1 kanji)
    length_penalty = 0 if n <= 3 else (1 if n == 4 else 2)  # 2-3 ideal, 4 okay, 5 allowed
    no_reading_penalty = 0 if (r and r != '-') else 1
    no_meaning_penalty = 0 if e else 1
    # Proper nouns lead the tuple: they lose to ANY ordinary word, whatever the
    # tier, and are picked only when a kanji has nothing else (媛 → 愛媛県).
    # all_shipped (has_nonshipped) is a LATE tiebreaker — after tier, kanji-count,
    # length, reading and meaning — so an all-shipped word is preferred only among
    # otherwise-equal candidates (玉葱☘️ → 玉子☘️). A kanji whose only good word has an
    # unshipped partner keeps it rather than dropping to a structurally worse word.
    return (is_proper_noun(word, e, r), ts, extra_kanji, length_penalty,
            no_reading_penalty, no_meaning_penalty, has_nonshipped_kanji(word), n)


def is_valid_candidate(word, kanji):
    if not word:
        return False
    if len(word) < 2 or len(word) > 5:
        return False
    if not is_all_japanese(word):
        return False
    if has_phrase_bridge(word):
        return False
    return kanji in word


# Emoji tag per freq-ranks tier — the same glyphs (and TAG_PRIORITY slots) the old
# v3 pool used, so scoring, reports and the shipped tags stay comparable.
FREQ_TIER_TAG = {
    'BASIC': '🌱', 'COMMON': '☘️', 'FLUENT': '🌷',
    'ADVANCED': '📚', 'NICHE': '🌶️', 'UNRANKED': '🦉',
}
DEFAULT_FREQ_TIER_TAG = '🦉'


def _kana_spelling(other_forms):
    """First kana-only token from a TSV `other_forms` cell ("御金; おかね" → おかね).

    Used as the candidate's reading: the furigana generator only treats it as a
    HINT to disambiguate multi-reading words (the furigana map stays authoritative),
    and a katakana token marks foreign proper nouns (北京 → ペキン) for demotion."""
    for token in (other_forms or '').split(';'):
        token = token.strip()
        if token and is_all_japanese(token) and kanji_count(token) == 0:
            return token
    return ''


def build_freq_candidate_index(target_kanji):
    """{kanji: [(word, reading, tag, meaning), ...]} over ALL raw/freq-ranks/*.tsv.

    Each TSV lists words starting with its key character (kanji AND kana files),
    so one pass over every file, registering each word under every target kanji
    it contains, yields the contains-anywhere pool this algorithm needs (比較 is
    stored in 比.tsv but must count for 較; お金 lives in お.tsv).

    Buckets are sorted by composite corpus frequency: word_score ties within a
    tier then resolve most-frequent-first (日 must prefer 日本 over 一日), which
    the raw file order can't provide — one kanji's words come from many files."""
    index = {}
    seen = set()  # (kanji, word) — defensive dedupe across files
    for path in sorted(glob.glob(resolve_path('raw/freq-ranks/*.tsv'))):
        with open(path, encoding='utf-8') as f:
            for row in csv.DictReader(f, delimiter='\t'):
                word = row.get('japanese_word', '')
                candidate = None  # built lazily, once per word
                for ch in set(word):
                    if ch not in target_kanji or not is_valid_candidate(word, ch):
                        continue
                    if (ch, word) in seen:
                        continue
                    seen.add((ch, word))
                    if candidate is None:
                        candidate = (freq_key(row), (
                            word,
                            _kana_spelling(row.get('other_forms')),
                            FREQ_TIER_TAG.get(row.get('tier', ''), DEFAULT_FREQ_TIER_TAG),
                            (row.get('english_gloss') or '').strip(),
                        ))
                    index.setdefault(ch, []).append(candidate)
    return {
        ch: [cand for _fk, cand in sorted(bucket, key=lambda pair: pair[0])]
        for ch, bucket in index.items()
    }


def load_textbook_candidates(kanji):
    return textbook_candidates(kanji, lambda w, r: is_valid_candidate(w, kanji))


def load_existing_candidates(kanji, existing_kanji_vocab, existing_meanings):
    """Current production words for this kanji (input/kanji_vocab.json).

    Used as a last-resort source so a kanji isn't left word-less just because the
    v3/textbook pools have nothing valid (e.g. rare name kanji like 鵬 → 大鵬).
    Reading is left blank; these words already carry furigana in the shipped data.
    """
    results = []
    for word in existing_kanji_vocab.get(kanji, []):
        if is_valid_candidate(word, kanji):
            e = existing_meanings.get(word, '')
            results.append((word, '', EXISTING_TAG, e))
    return results


def _pick_reading(kana_list, form_text):
    """Best kana reading for a given kanji form: respect appliesToKanji, prefer common."""
    applicable = [
        ka for ka in kana_list
        if '*' in (ka.get('appliesToKanji') or ['*']) or form_text in (ka.get('appliesToKanji') or [])
    ] or kana_list
    for ka in applicable:
        if ka.get('common'):
            return ka.get('text', '')
    return applicable[0].get('text', '') if applicable else ''


def build_jmdict_candidate_index(target_kanji):
    """Index JMdict (input/scriptin-jmdict-eng.json) as a fallback candidate source.

    Returns (index, word_meaning, readable_forms):
      index        {kanji: [(word, reading, JMDICT_TAG, meaning), ...]} for every
                   >=2-char JMdict word containing a target kanji. Search-only (sK)
                   and ateji forms are skipped. Rescues rare kanji whose only real
                   vocabulary lives in the full dictionary (楠 → 石楠花, 凜 → 凜々).
      word_meaning {word: meaning} for every JMdict form (kept for callers that
                   need to resolve meanings outside the index).
      readable_forms  every kanji form that has a kana reading (gloss or not) —
                   feeds READABLE_FORMS / has_dictionary_reading.
    """
    data = load_json('input/scriptin-jmdict-eng.json', {})
    index = {}
    word_meaning = {}
    readable_forms = set()
    seen = {}  # kanji -> set of words already added (dedupe across entries)
    for entry in data.get('words', []):
        if entry.get('kana'):
            readable_forms.update(
                k.get('text', '') for k in entry.get('kanji', [])
            )
        if jmdict_entry_gloss(entry) is None:  # entry has no English gloss at all
            continue
        kana_list = entry.get('kana', [])
        for form in entry.get('kanji', []) + kana_list:
            t = form.get('text', '')
            if t and t not in word_meaning:
                meaning = jmdict_entry_gloss(entry, t)  # appliesToKanji-aware per form
                if meaning:
                    word_meaning[t] = meaning
        for k in entry.get('kanji', []):
            text = k.get('text', '')
            if len(text) < 2 or (JMDICT_EXCLUDE_TAGS & set(k.get('tags', []))):
                continue
            meaning = jmdict_entry_gloss(entry, text)  # appliesToKanji-aware per form
            if not meaning:
                continue
            reading = _pick_reading(kana_list, text)
            for ch in set(text):
                if ch in target_kanji and is_valid_candidate(text, ch):
                    bucket = seen.setdefault(ch, set())
                    if text in bucket:
                        continue
                    bucket.add(text)
                    index.setdefault(ch, []).append((text, reading, JMDICT_TAG, meaning))
    readable_forms.discard('')
    return index, word_meaning, readable_forms


def kanji_reading_in_word(kanji, word, word_reading, furigana_map):
    """The reading of `kanji` within `word`, via the JMdict furigana map.

    Returns None when the word has no furigana entry or an irregular (jukujikun)
    reading that can't be segmented per kanji (e.g. 石楠花 → None).
    """
    entry = furigana_map.get(word)
    if not entry:
        return None
    segments = entry.get(word_reading) if word_reading else None
    if segments is None:
        segments = next(iter(entry.values()), None)
    return reading_of_kanji_in_segments(kanji, segments)


def is_redundant_pair(w1, w2):
    """Two words that teach the same thing: one contains the other (答える/答え), or
    they share an identical kanji set and differ only in kana (入る/入れる)."""
    if w1 in w2 or w2 in w1:
        return True
    return {c for c in w1 if is_kanji_char(c)} == {c for c in w2 if is_kanji_char(c)}


RENDAKU = {
    'が': 'か', 'ぎ': 'き', 'ぐ': 'く', 'げ': 'け', 'ご': 'こ',
    'ざ': 'さ', 'じ': 'し', 'ず': 'す', 'ぜ': 'せ', 'ぞ': 'そ',
    'だ': 'た', 'ぢ': 'ち', 'づ': 'つ', 'で': 'て', 'ど': 'と',
    'ば': 'は', 'び': 'ひ', 'ぶ': 'ふ', 'べ': 'へ', 'ぼ': 'ほ',
    'ぱ': 'は', 'ぴ': 'ひ', 'ぷ': 'ふ', 'ぺ': 'へ', 'ぽ': 'ほ',
}
GEMINATING_MORA = set('つちくき')


def _derendaku(reading):
    """Devoice the first kana (連濁): が→か, ど→と. Leaves unvoiced readings alone."""
    return RENDAKU.get(reading[0], reading[0]) + reading[1:] if reading else reading


def _gemination_equivalent(a, b):
    """True if one reading is the gemination (促音) of the other: げっ↔げつ, きっ↔き.

    The contracted form ends in っ; the base ends in the same stem, optionally plus a
    geminating mora (つ/ち/く/き). Only fires when one side ends in っ, so genuinely
    distinct readings (が vs かく) are never collapsed.
    """
    if not a.endswith('っ'):
        a, b = b, a
    if not a.endswith('っ'):
        return False
    stem = a[:-1]
    return b == stem or any(b == stem + mora for mora in GEMINATING_MORA)


def readings_equivalent(r1, r2):
    """True if two kanji readings are phonologically the same once rendaku (連濁) and
    gemination (促音) are accounted for — so げつ/げっ (月曜/月謝) and と/ど (土地/土曜)
    count as one reading, while genuinely distinct readings (画: が/かく) stay apart."""
    if not r1 or not r2:
        return False
    if r1 == r2:
        return True
    d1, d2 = _derendaku(r1), _derendaku(r2)
    return d1 == d2 or _gemination_equivalent(d1, d2)


def _gather_sorted_candidates(kanji, known_meaning_words, existing_kanji_vocab, existing_meanings, freq_index, jmdict_index):
    """All valid candidates for `kanji`, deduped per word (best score kept) and
    sorted best-first. Only words with a meaning available somewhere are kept."""
    freq = freq_index.get(kanji, [])
    textbook = load_textbook_candidates(kanji)
    existing = load_existing_candidates(kanji, existing_kanji_vocab, existing_meanings)
    jmdict = jmdict_index.get(kanji, [])

    candidates = [
        c for c in (freq + textbook + existing + jmdict)
        if (c[3] or c[0] in known_meaning_words)  # c[3] = own meaning, c[0] = word
        and has_dictionary_reading(c[0])  # unreadable corpus fragments don't exist
    ]

    best_by_word = {}
    for w, r, t, e in candidates:
        if w not in best_by_word or word_score(w, t, e, r) < word_score(w, best_by_word[w][2], best_by_word[w][3], best_by_word[w][1]):
            best_by_word[w] = (w, r, t, e)

    return sorted(best_by_word.values(), key=lambda x: word_score(x[0], x[2], x[3], x[1]))


def _make_second_score(kanji, first, first_reading, furigana_map):
    """Build the sort key for choosing the second word: reward a DIFFERENT kanji
    reading, but only when the candidate is itself high-frequency (🌱☘️🌷)."""
    first_kanji_set = {ch for ch in first[0] if is_kanji_char(ch)}

    def second_score(entry):
        ws = word_score(entry[0], entry[2], entry[3], entry[1])  # ws[0] = proper-noun flag
        shared = len(first_kanji_set & {ch for ch in entry[0] if is_kanji_char(ch)})
        cand_reading = kanji_reading_in_word(kanji, entry[0], entry[1], furigana_map)
        high_band = TAG_PRIORITY.get(entry[2], DEFAULT_TAG_PRIORITY) <= HIGH_FREQ_TIER_MAX
        different_reading = (
            first_reading is not None
            and cand_reading is not None
            and not readings_equivalent(cand_reading, first_reading)
        )
        reading_bonus = 0 if (high_band and different_reading) else 1
        # The proper-noun flag stays in front: reading-diversity credit must not
        # rescue a name (済州 offering さい never beats an ordinary same-reading word).
        return (ws[0], reading_bonus, shared) + ws[1:]

    return second_score


def _pick_second_word(kanji, first, first_reading, all_candidates, furigana_map, second_score):
    """Pick the second word, preferring a primary (v3/textbook) candidate, then
    breaking up a redundant pair (入る/入れる) by reaching down to textbook/📚."""
    # Prefer a primary (v3/textbook) second word; only fall back to existing/jmdict
    # when no primary candidate remains, so rare words never displace good ones.
    remaining = all_candidates[1:]
    primary_remaining = [
        e for e in remaining
        if TAG_PRIORITY.get(e[2], DEFAULT_TAG_PRIORITY) <= PRIMARY_TIER_MAX
    ]
    second = min(primary_remaining or remaining, key=second_score)

    # Last resort for redundant pairs (入る/入れる, 答える/答え): if the second word
    # merely repeats the first and no high-frequency word offered a different reading,
    # reach down to textbook/📚 for a different-reading word rather than ship the pair.
    if first_reading is not None and is_redundant_pair(first[0], second[0]):
        alt = []
        for e in remaining:
            if TAG_PRIORITY.get(e[2], DEFAULT_TAG_PRIORITY) > EXTENDED_TIER_MAX:
                continue
            if is_redundant_pair(first[0], e[0]):
                continue
            if is_proper_noun(e[0], e[3], e[1]):  # a name never rescues diversity (信じる → 信濃)
                continue
            cand_reading = kanji_reading_in_word(kanji, e[0], e[1], furigana_map)
            if cand_reading is not None and not readings_equivalent(cand_reading, first_reading):
                alt.append(e)
        if alt:
            second = min(alt, key=second_score)

    return second


def _log_diversity_replacement(kanji, first, first_reading, second, all_candidates, furigana_map, second_score, replace_logs):
    """Record when a lower-tier word beat a 🌱/☘️ word for reading diversity, so the
    report can show each pick's per-kanji reading (八十→はち vs 八つ当たり→や)."""
    if replace_logs is None:
        return
    top_freq_band = TAG_PRIORITY['☘️']  # 🌱/☘️ are the two most-frequent tiers
    if TAG_PRIORITY.get(second[2], DEFAULT_TAG_PRIORITY) <= top_freq_band:
        return
    passed_over = [
        e for e in all_candidates[1:]
        if TAG_PRIORITY.get(e[2], DEFAULT_TAG_PRIORITY) <= top_freq_band and e[0] != second[0]
    ]
    if not passed_over:
        return
    best_passed = min(passed_over, key=second_score)
    second_kr = kanji_reading_in_word(kanji, second[0], second[1], furigana_map)
    passed_kr = kanji_reading_in_word(kanji, best_passed[0], best_passed[1], furigana_map)
    replace_logs.append((kanji, first, first_reading, second, second_kr, best_passed, passed_kr))


def select_vocab_for_kanji(kanji, known_meaning_words, existing_kanji_vocab, existing_meanings, freq_index, jmdict_index, furigana_map, replace_logs=None):
    """Return up to 2 best (word, reading, tag, meaning) tuples for this kanji.

    Only words with a meaning available somewhere are considered: either the
    candidate carries its own meaning (e) or the word is in known_meaning_words.
    """
    all_candidates = _gather_sorted_candidates(
        kanji, known_meaning_words, existing_kanji_vocab, existing_meanings, freq_index, jmdict_index
    )
    if not all_candidates:
        return []

    first = all_candidates[0]
    if len(all_candidates) == 1:
        return [first]

    first_reading = kanji_reading_in_word(kanji, first[0], first[1], furigana_map)
    second_score = _make_second_score(kanji, first, first_reading, furigana_map)
    second = _pick_second_word(kanji, first, first_reading, all_candidates, furigana_map, second_score)
    _log_diversity_replacement(
        kanji, first, first_reading, second, all_candidates, furigana_map, second_score, replace_logs
    )
    return [first, second]


def _print_replace_logs(logs):
    """Print aligned table of replacements: rows buffered first so columns can be padded."""
    if not logs:
        return
    def cell(medal, entry, kanji_reading):
        # word, its full reading, and 「the kanji's own reading」 — the diversity signal.
        return f"{medal} {_fmt_tag(entry[2])} 「{kanji_reading or '?'}」 {entry[0]} ~ {entry[1] or '?'}"

    rows = []
    for kanji, first, fr, second, sr, best_passed, pr in logs:
        c1 = cell('🥇', first, fr)
        c2 = cell('🥈', second, sr)
        c3 = cell('🙅', best_passed, pr)
        rows.append((kanji, c1, c2, c3))

    w1 = max(_display_width(c1) for _, c1, _, _ in rows)
    w2 = max(_display_width(c2) for _, _, c2, _ in rows)

    for i, (kanji, c1, c2, c3) in enumerate(rows, 1):
        print(f"{i:03d}. {kanji}  →  {_pad(c1, w1 + 3)}{_pad(c2, w2 + 3)}{c3}")
    print(f"\n  Replaced ({len(rows)}): {''.join(kanji for kanji, *_ in rows)}")


def main():
    # input/filtered_kanji.json is the canonical kanji set (merged_kanji minus
    # kanji_to_remove), produced by src/build_filtered_kanji_json.py. Reading it
    # here (instead of output/kanji_main.json) removes the dependency on a prior
    # build and keeps this script's kanji set identical to the other algo scripts'.
    with open(resolve_path('input/filtered_kanji.json'), encoding='utf-8') as f:
        all_kanji = json.load(f)
    SHIPPED.update(all_kanji)  # enable the all-shipped sample-word preference

    with open(resolve_path('input/vocab_meaning.json'), encoding='utf-8') as f:
        existing_meanings = json.load(f)

    with open(resolve_path('input/kanji_vocab.json'), encoding='utf-8') as f:
        existing_kanji_vocab = json.load(f)
    existing_vocab_words = set(w for words in existing_kanji_vocab.values() for w in words)

    # A word is only eligible if a meaning is available from some known source.
    # Words missing from all of these fall back to the word itself in the final
    # build, which prints them in its "Word meaning Not Found" report.
    jmdict_cache  = load_json('input/jmdict-vocab-meaning.json', {})
    jsw_algo      = load_json('overrides/japanese_study_words-algo.json', {})
    jsw_words = {
        entry[0] for entry in jsw_algo.values()
        if entry and len(entry) >= 3 and entry[2]
    }
    known_meaning_words = (
        set(existing_meanings) | set(jmdict_cache) | jsw_words
    )

    # Primary pool: the freq-ranks corpus dataset, indexed once contains-anywhere.
    freq_index = build_freq_candidate_index(set(all_kanji))

    # Full JMdict, indexed once as a last-resort candidate source for rare kanji.
    jmdict_index, jmdict_word_meanings, readable_forms = build_jmdict_candidate_index(set(all_kanji))
    READABLE_FORMS.update(readable_forms)

    # Resolved glosses for proper-noun detection: JMdict's full gloss is the most
    # revealing ("Shinano (former province ...)"), so it overlays the local caches.
    # Non-string values (structured entries) are skipped.
    for gloss_src in (existing_meanings, jmdict_cache, jmdict_word_meanings):
        PN_GLOSS_LOOKUP.update(
            (w, m) for w, m in gloss_src.items() if isinstance(m, str)
        )

    # Per-kanji furigana, used to give the second word a different reading and to
    # know which words the furigana step can read at all.
    furigana_map = load_json('input/jmdict-furigana-map.json', {})
    FURIGANA_MAP_WORDS.update(furigana_map)

    kanji_vocab_result = {}
    vocab_meaning_result = {}
    vocab_reading_result = {}

    selected_all = []  # (word, tag, kanji) for stats
    replace_logs = []

    for kanji in all_kanji:
        selected = select_vocab_for_kanji(kanji, known_meaning_words, existing_kanji_vocab, existing_meanings, freq_index, jmdict_index, furigana_map, replace_logs)
        if not selected:
            continue

        kanji_vocab_result[kanji] = [w for w, r, t, e in selected]

        for w, r, t, e in selected:
            selected_all.append((w, t, kanji))
            if r and r != '-':
                vocab_reading_result[w] = r
            if e and w not in existing_meanings:
                vocab_meaning_result[w] = e

    _print_replace_logs(replace_logs)

    def write_and_report(rel_path, data):
        path = write_json(rel_path, data, indent=4)
        print(f"Written: {path} ({len(data)} entries)")

    write_and_report('overrides/kanji_vocab-algo.json', kanji_vocab_result)
    write_and_report('overrides/vocab_meaning-algo.json', vocab_meaning_result)
    write_and_report('overrides/vocab_reading-algo.json', vocab_reading_result)

    print_report(selected_all, kanji_vocab_result, all_kanji, existing_vocab_words)


def print_report(selected_all, kanji_vocab_result, all_kanji, existing_vocab_words):
    """Print selection statistics: tier/length/kanji-count breakdowns and the
    1-word / 📚 / 🦉 / 3+kanji / 5-char / no-word word groups. Read-only over the
    selection results — it does not affect the written output files."""
    total = len(selected_all)
    unique = len({w for w, _, _ in selected_all})
    without_vocab = [k for k in all_kanji if k not in kanji_vocab_result]
    with_one  = sum(1 for v in kanji_vocab_result.values() if len(v) == 1)
    with_two  = sum(1 for v in kanji_vocab_result.values() if len(v) >= 2)

    # label = display-glyph + source + plain-language meaning (the freq-ranks tiers
    # 🌱→🦉 run most-frequent → rarest).
    tier_labels = {
        "🌱": "🌱  freq-ranks BASIC — most frequent (core everyday words)",
        "☘️": "🍀  freq-ranks COMMON — very frequent",
        "🌷": "🌷  freq-ranks FLUENT — frequent / common",
        TEXTBOOK_TAG: "📖  textbook — from raw/kanji-textbook-words/",
        "📚": "📚  freq-ranks ADVANCED — less common",
        "🦉": "🦉  freq-ranks UNRANKED — rare",
        "🌶️": "🌶️  freq-ranks NICHE — same tier as 🦉",
        EXISTING_TAG: "📋  existing — current production word (fallback)",
        JMDICT_TAG: "📕  jmdict — pulled from full JMdict (last resort)",
    }
    from collections import Counter

    display_tag = _fmt_tag

    tier_counts  = Counter(t for _, t, _ in selected_all)
    length_counts = Counter(len(w) for w, _, _ in selected_all)
    kanji_counts  = Counter(kanji_count(w) for w, _, _ in selected_all)
    new_words = sum(1 for w, _, _ in selected_all if w not in existing_vocab_words)

    print(f"\n{'─'*40}")
    print(f"  Kanji processed:   {len(all_kanji)}")
    print(f"  With 2 words:      {with_two}")
    print(f"  With 1 word:       {with_one}")
    print(f"  With 0 words:      {len(without_vocab)}")
    print(f"  Total words:       {total}  (kanji→word assignments)")
    print(f"  Unique words:      {unique}  ({total - unique} shared across >1 kanji)")

    print(f"\n  Source / tier breakdown")
    for tag, label in tier_labels.items():
        n = tier_counts.get(tag, 0)
        print(f"    {label}: {n}  ({n/total*100:.1f}%)")

    print(f"\n  Word length")
    for l in sorted(length_counts):
        print(f"    {l} chars: {length_counts[l]}  ({length_counts[l]/total*100:.1f}%)")

    print(f"\n  Kanji per word")
    for k in sorted(kanji_counts):
        print(f"    {k} kanji: {kanji_counts[k]}  ({kanji_counts[k]/total*100:.1f}%)")

    print(f"\n  Not in input/kanji_vocab.json: {new_words}/{total}  ({new_words/total*100:.1f}%)")
    print(f"{'─'*40}")

    def sort_key(item):
        w, t, _ = item
        return (TAG_PRIORITY.get(t, DEFAULT_TAG_PRIORITY), len(w), w)

    def print_word_group(title, items):
        if not items:
            return
        items = sorted(items, key=sort_key)
        print(f"\n  {title} ({len(items)}):")
        for w, t, k in items:
            print(f"    {k} {display_tag(t)} {w}")
        print(f"  {''.join(k for _, _, k in items)}")

    one_word_kanji = {k for k, v in kanji_vocab_result.items() if len(v) == 1}
    print_word_group("With 1 word",  [(w, t, k) for w, t, k in selected_all if k in one_word_kanji])
    print_word_group("📚  v3",       [(w, t, k) for w, t, k in selected_all if t == '📚'])
    print_word_group("🦉  v3",       [(w, t, k) for w, t, k in selected_all if t == '🦉'])
    print_word_group("3+ kanji words", [(w, t, k) for w, t, k in selected_all if kanji_count(w) >= 3])
    print_word_group("5-char words", [(w, t, k) for w, t, k in selected_all if len(w) == 5])

    if without_vocab:
        print(f"\n  With 0 words ({len(without_vocab)}):")
        print(f"  {''.join(sorted(without_vocab))}")


if __name__ == '__main__':
    main()
