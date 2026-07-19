#!/usr/bin/env python3
"""
Task: Better Sample Vocabulary
Selects up to two sample words per kanji and writes overrides/kanji_vocab-algo.json.
English glosses are no longer emitted here — the final build resolves every gloss
straight from JMdict. Furigana for the selected words is generated on the fly by
the final build (kanji_load.dump_all_vocab_furigana → generate_furigana_algo).

Selection rules:
- Word must be >= 2 characters (hiragana included)
- Must contain at least one kanji
- Prefer fewer kanji in word (minimum 1)
- 2-3 chars ideal (no preference between them); 4 okay; 5 allowed; 6+ not allowed
- Meaning/reading availability is NOT scored or pre-filtered here. Every source
  supplies a gloss and the furigana map is the authoritative reading, so a candidate
  is never penalised for a blank meaning/reading. The final build is the single hard gate:
  kanji_load.dump_all_vocab_meanings raises if any shipped word has no resolvable
  meaning, and dump_all_vocab_furigana raises if any has no reading — so a data gap
  fails the build loudly (fix it in overrides/vocab_meaning.json / vocab_furigana.json)
  instead of being silently pre-filtered and drifting from what the build resolves.

Kanji listed in overrides/kanji_to_remove.json are skipped entirely.

Source priority (lower effective tier wins, where effective_tier = tag priority +
kanji-count surcharge [1–2:+0, 3:+1, 4–5:+5]; ties broken by fewer kanji → length
band [2-3 ideal, 4 ok, 5 max] → all-shipped → shorter overall [2 beats 3]).
Hand-curated picks live in overrides/kanji_vocab.json and win at BUILD time
(build_helpers.get_words), not here. The primary pool is the freq-ranks corpus
dataset (raw/freq-ranks/*.tsv, indexed once so a word counts for EVERY kanji it
contains, not just the one it starts with), whose tier column maps onto the
emoji bands below. Fallbacks (existing / JMdict) are hard-gated: they may fill
the FIRST slot only when no freq-ranks/textbook candidate exists, and they
never fill the second slot (ship one word rather than pad with obscure junk):
   0. freq-ranks tier BASIC 🌱   (most frequent band; beats ☘️ even with more kanji)
   1. freq-ranks tier COMMON ☘️
   2. freq-ranks tier FLUENT 🌷
   3. textbook words             raw/kanji-textbook-words-min/
   4. freq-ranks tier ADVANCED 📚 (or unknown)
   5. freq-ranks NICHE 🌶️ / UNRANKED 🦉
   6. current production words   input/kanji_vocab.json           (1st-slot fallback only)
   7. full JMdict                input/scriptin-jmdict-eng.json   (1st-slot fallback only)

Deduplication: if a word appears in both freq-ranks and textbook, keep whichever
gives the better (lower) score — so a textbook word isn't unfairly penalised just
because it also appears in the corpus data under a lower-priority tier.

Second-word diversity: after the best word is chosen, the second pick prefers a word
in which the kanji takes a DIFFERENT reading than in the first word (e.g. 考える/考慮
over 考える/考え) — but only when that second word is itself high-frequency (🌱☘️🌷,
tier ≤ 2) OR tagged JLPT N5–N2. Below that band frequency wins: the more common
(usually same-reading) word is kept rather than dropping a tier for variety. Ties
fall back to "fewest shared kanji", which also prevents two near-identical words
(e.g. 烏賊 / 烏賊墨) being chosen together. Per-kanji readings come from
input/jmdict-furigana-map.json; readings differing only by rendaku (連濁) or
gemination (促音) — げつ/げっ, と/ど — count as the SAME reading, while genuinely
distinct readings (画: が/かく) stay apart. As a last resort, if the pair is still
redundant (one word contains the other, or an identical kanji set, e.g. 入る/入れる),
a different-reading word from down to the 📚 tier may replace the second.

Kanji-count surcharge on tier: longer compounds must earn their slot —
  1–2 kanji → +0,  3 kanji → +1,  4–5 kanji → +5
so a ☘️ 2-kanji word beats a 🌱 3-kanji word, and 4+ kanji only survive when no
shorter peer exists at a comparable frequency band.

Phrase exclusion: words where a grammatical particle (て で に を が は も へ と) appears
between two kanji sequences are treated as verbal phrases and excluded, so true
compound words are preferred over phrases like 診て貰う. Two more fragment shapes
are rejected via resolver.is_phrase_fragment: demonstrative + noun (この人, その様)
and standalone-word + trailing particle (今も, 常に, 事になる — the learner should
see 今/常/仕事, not a word with grammar stuck to it). Genuine adverbs survive the
particle test: 特に (特 alone is not a standalone word), 更に (更 alone reads こう).
Also excluded: JMdict `exp` entries shaped as noun + が/を/に + kana verb
(音がする, 恋をする, ご覧になる) — plain `exp` alone is too broad (挨拶, 女の子, 違う).

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
  raw/kanji-textbook-words-min/[kanji].json → {kanji: {word: [reading, meaning, jlpt, tags]}}
  input/kanji_vocab.json                   → {kanji: [word, ...]}   (existing fallback)
  input/scriptin-jmdict-eng.json           → JMdict                 (jmdict fallback)
  input/jmdict-furigana-map.json           → {word: {reading: segments}}  (readings)

Outputs: overrides/kanji_vocab-algo.json

Run from the project root: python3 src/kanji_vocab_algo.py
"""

import csv
import glob
import json
from typing import NamedTuple

from sources import (
    resolve_path,
    load_json,
    load_jmdict,
    write_json,
    jmdict_entry_gloss,
    load_textbook_entries,
    TEXTBOOK_TAG,
    FREQ_TIER_TAG,
    DEFAULT_FREQ_TIER_TAG,
    freq_key,
    parse_rank,
)
from japanese import (
    is_all_japanese, is_kanji_char, kanji_count, reading_of_kanji_in_segments,
    readings_equivalent,
)
from jmdict_resolver import JmdictResolver

# NOTE: word_score / is_valid_candidate here intentionally differ from the
# same-named functions in japanese_study_words_algo.py — this algorithm
# only requires the kanji to appear anywhere in the word and scores by length
# bands + reading/meaning availability, while that one requires a starting kanji.

EXISTING_TAG = '__existing__'
JMDICT_TAG = '__jmdict__'


class Candidate(NamedTuple):
    """A sample-word candidate. Field order matches the (word, reading, tag, meaning)
    4-tuples every candidate source historically emitted, so this stays index- and
    unpack-compatible (a NamedTuple IS a tuple); use the named fields going forward.
    Score it with score_candidate() rather than shuffling fields into word_score()."""
    word: str
    reading: str
    tag: str
    meaning: str

PHRASE_PARTICLES = set('てでにをがはもへと')

TAG_PRIORITY = {
    '🌱': 0,           # most frequent band — strictly preferred over ☘️
    '☘️': 1,
    '🌷': 2,
    TEXTBOOK_TAG: 3,
    '📚': 4,
    '🦉': 5,
    '🌶️': 5,
    EXISTING_TAG: 6,  # current production words: 1st-slot fallback only
    JMDICT_TAG: 7,    # full JMdict: 1st-slot fallback only
}
DEFAULT_TAG_PRIORITY = 4  # unknown tags treated like 📚

# Tiers <= this are "primary" (freq-ranks + textbook, incl. NICHE/UNRANKED).
# Fallbacks (existing / jmdict) may fill the FIRST slot only when no primary
# candidate exists, and never fill the second slot.
PRIMARY_TIER_MAX = 5

# Reading-diversity for the second word is only pursued when that word is itself
# high-frequency (🌱☘️🌷, tier <= 2) OR JLPT N5–N2; below that band, frequency/tier
# wins and the more common (usually same-reading) word is kept rather than
# dropping a tier for variety.
HIGH_FREQ_TIER_MAX = 2
# JLPT levels (5=N5 … 1=N1) that also unlock the different-reading preference.
# N5–N3 alone only moves different-reading ~+0.6pp; including N2 is ~+2.0pp.
DIVERSITY_JLPT_LEVELS = {5, 4, 3, 2}

# Last-resort band for breaking up a redundant pair: when the only high-frequency
# second word merely repeats the first (e.g. 入る/入れる), a different-reading word
# from down to this tier (textbook 📖 = 3, 📚 = 4) may replace it instead.
EXTENDED_TIER_MAX = 4

# Added to tag priority so longer compounds must outrank shorter peers on frequency:
# a ☘️ 2-kanji word (tier 1) beats a 🌱 3-kanji word (tier 0+1=1, then extra_kanji),
# and 4–5 kanji need a large gap to survive.
def kanji_count_surcharge(kc):
    if kc <= 2:
        return 0
    if kc == 3:
        return 1
    return 5  # 4–5; 6+ already rejected by is_valid_candidate

# JMdict kanji-form tags to skip: search-only forms and phonetic (ateji) spellings,
# neither of which is a good representative sample word.
JMDICT_EXCLUDE_TAGS = {'sK', 'ateji'}

# Particles that mark "noun + particle + kana verb" expressions (音がする, 恋をする,
# ご覧になる). に is included so ご覧になる is caught with the が/を set.
EXP_PHRASE_PARTICLES = set('がをに')


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


def has_particle_before_kana(word):
    """True if が/を/に sits after a kanji-bearing prefix with a kana-only tail.

    Catches 音がする / 恋をする / ご覧になる. Alone this is too broad (曲がる,
    召し上がる, 肺がん) — pair with the JMdict `exp` gate in is_exp_particle_phrase.
    """
    for i, ch in enumerate(word):
        if ch not in EXP_PHRASE_PARTICLES or i == 0 or i + 1 >= len(word):
            continue
        before, after = word[:i], word[i + 1:]
        if any(is_kanji_char(c) for c in before) and after and not any(is_kanji_char(c) for c in after):
            return True
    return False


# Kanji we ship (input/filtered_kanji.json); populated in main(). Sample words
# whose every kanji ships are preferred, so a kanji's example doesn't drag in an
# unshipped partner (玉 → 玉葱[葱 unshipped]) when an all-shipped option exists.
SHIPPED = set()

# JmdictResolver over the same loaded JMdict as the candidate index; populated in
# main(). is_valid_candidate uses it to reject phrase fragments (この人, 今も).
RESOLVER = None

# Kanji forms whose JMdict entry carries partOfSpeech `exp`; populated in main()
# from the same JMdict load. Used with has_particle_before_kana to drop true
# phrases (音がする) without banning keepers tagged exp alone (挨拶, 女の子).
JMDICT_EXP_WORDS = set()

# {word: jlpt_level (5..1)} for every freq-ranks row that carries one; populated
# by build_freq_candidate_index. Used for the report's JLPT breakdown and for the
# second-word reading-diversity JLPT unlock.
WORD_JLPT = {}


def is_exp_particle_phrase(word):
    """JMdict expression shaped as noun + が/を/に + kana verb (音がする, ご覧になる)."""
    return word in JMDICT_EXP_WORDS and has_particle_before_kana(word)


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
    ts = TAG_PRIORITY.get(tag, DEFAULT_TAG_PRIORITY) + kanji_count_surcharge(kc)
    extra_kanji = kc - 1  # 0 = best (exactly 1 kanji)
    length_penalty = 0 if n <= 3 else (1 if n == 4 else 2)  # 2-3 ideal, 4 okay, 5 allowed
    # Proper nouns lead the tuple: they lose to ANY ordinary word, whatever the
    # tier, and are picked only when a kanji has nothing else (媛 → 愛媛県).
    # all_shipped (has_nonshipped) is a LATE tiebreaker — after tier, kanji-count
    # and length — so an all-shipped word is preferred only among otherwise-equal
    # candidates (玉葱☘️ → 玉子☘️). A kanji whose only good word has an unshipped
    # partner keeps it rather than dropping to a structurally worse word.
    # (Reading/meaning availability is NOT scored: every source supplies a gloss and
    # the furigana map is the authoritative reading; the final build is the hard gate
    # that fails loudly on a genuinely missing meaning/reading.)
    return (is_proper_noun(word, e, r), ts, extra_kanji, length_penalty,
            has_nonshipped_kanji(word), n)


def score_candidate(c):
    """word_score for a Candidate — keeps the field→argument mapping in ONE place
    (word_score's positional signature is word, tag, meaning, reading — NOT the
    candidate's field order, which is the transposition this wrapper prevents)."""
    return word_score(c.word, c.tag, c.meaning, c.reading)


def is_valid_candidate(word, kanji):
    if not word:
        return False
    if len(word) < 2 or len(word) > 5:
        return False
    if not is_all_japanese(word):
        return False
    if has_phrase_bridge(word):
        return False
    if is_exp_particle_phrase(word):
        return False
    if RESOLVER is not None and RESOLVER.is_phrase_fragment(word):
        return False
    return kanji in word


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
    """{kanji: [Candidate, ...]} over ALL raw/freq-ranks/*.tsv.

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
                jlpt = parse_rank(row.get('jlpt_level'))
                if word and jlpt is not None:
                    WORD_JLPT.setdefault(word, jlpt)
                candidate = None  # built lazily, once per word
                for ch in set(word):
                    if ch not in target_kanji or not is_valid_candidate(word, ch):
                        continue
                    if (ch, word) in seen:
                        continue
                    seen.add((ch, word))
                    if candidate is None:
                        candidate = (freq_key(row), Candidate(
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
    results = []
    for w, r, e, jlpt in load_textbook_entries(kanji):
        if not is_valid_candidate(w, kanji):
            continue
        if jlpt is not None:
            WORD_JLPT.setdefault(w, jlpt)
        results.append(Candidate(w, r, TEXTBOOK_TAG, e))
    return results


def load_existing_candidates(kanji, existing_kanji_vocab, word_glosses):
    """Current production words for this kanji (input/kanji_vocab.json).

    Used as a last-resort source so a kanji isn't left word-less just because the
    freq-ranks/textbook pools have nothing valid (e.g. rare name kanji like 鵬 → 大鵬).
    Reading is left blank; these words already carry furigana in the shipped data.
    """
    results = []
    for word in existing_kanji_vocab.get(kanji, []):
        if is_valid_candidate(word, kanji):
            e = word_glosses.get(word, '')
            results.append(Candidate(word, '', EXISTING_TAG, e))
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


def build_jmdict_candidate_index(target_kanji, data):
    """Index JMdict (`data` = loaded scriptin-jmdict-eng.json) as a fallback source.

    Returns (index, word_meaning):
      index        {kanji: [Candidate, ...]} (each tagged JMDICT_TAG) for every
                   >=2-char JMdict word containing a target kanji. Search-only (sK)
                   and ateji forms are skipped. Rescues rare kanji whose only real
                   vocabulary lives in the full dictionary (楠 → 石楠花, 凜 → 凜々).
      word_meaning {word: meaning} for every JMdict form (kept for callers that
                   need to resolve meanings outside the index).
    """
    index = {}
    word_meaning = {}
    seen = {}  # kanji -> set of words already added (dedupe across entries)
    for entry in data.get('words', []):
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
                    index.setdefault(ch, []).append(Candidate(text, reading, JMDICT_TAG, meaning))
    return index, word_meaning


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


def _gather_sorted_candidates(kanji, existing_kanji_vocab, word_glosses, freq_index, jmdict_index):
    """All valid candidates for `kanji`, deduped per word (best score kept) and
    sorted best-first. Meaning/reading availability is not filtered here — missing
    either just costs score (see word_score); the final build is the hard gate."""
    freq = freq_index.get(kanji, [])
    textbook = load_textbook_candidates(kanji)
    existing = load_existing_candidates(kanji, existing_kanji_vocab, word_glosses)
    jmdict = jmdict_index.get(kanji, [])

    candidates = freq + textbook + existing + jmdict

    best_by_word = {}
    for cand in candidates:
        if cand.word not in best_by_word or score_candidate(cand) < score_candidate(best_by_word[cand.word]):
            best_by_word[cand.word] = cand

    return sorted(best_by_word.values(), key=score_candidate)


def _make_second_score(kanji, first, first_reading, furigana_map):
    """Build the sort key for choosing the second word: reward a DIFFERENT kanji
    reading when the candidate is high-frequency (🌱☘️🌷) or JLPT N5–N2."""
    first_kanji_set = {ch for ch in first.word if is_kanji_char(ch)}

    def second_score(entry):
        ws = score_candidate(entry)  # ws[0] = proper-noun flag
        shared = len(first_kanji_set & {ch for ch in entry.word if is_kanji_char(ch)})
        cand_reading = kanji_reading_in_word(kanji, entry.word, entry.reading, furigana_map)
        tier = TAG_PRIORITY.get(entry.tag, DEFAULT_TAG_PRIORITY)
        jlpt = WORD_JLPT.get(entry.word)
        diversity_eligible = tier <= HIGH_FREQ_TIER_MAX or jlpt in DIVERSITY_JLPT_LEVELS
        different_reading = (
            first_reading is not None
            and cand_reading is not None
            and not readings_equivalent(cand_reading, first_reading)
        )
        reading_bonus = 0 if (diversity_eligible and different_reading) else 1
        # The proper-noun flag stays in front: reading-diversity credit must not
        # rescue a name (済州 offering さい never beats an ordinary same-reading word).
        return (ws[0], reading_bonus, shared) + ws[1:]

    return second_score


def _is_primary_tag(tag):
    return TAG_PRIORITY.get(tag, DEFAULT_TAG_PRIORITY) <= PRIMARY_TIER_MAX


def _pick_second_word(kanji, first, first_reading, all_candidates, furigana_map, second_score):
    """Pick a primary second word, or None if none remain.

    Existing/JMdict never fill the second slot. For redundant pairs (入る/入れる),
    reach down to textbook/📚 for a different-reading primary rather than ship the pair.
    """
    remaining = all_candidates[1:]
    primary_remaining = [e for e in remaining if _is_primary_tag(e.tag)]
    if not primary_remaining:
        return None
    second = min(primary_remaining, key=second_score)

    # Last resort for redundant pairs (入る/入れる, 答える/答え): if the second word
    # merely repeats the first and no high-frequency word offered a different reading,
    # reach down to textbook/📚 for a different-reading word rather than ship the pair.
    if first_reading is not None and is_redundant_pair(first.word, second.word):
        alt = []
        for e in remaining:
            if TAG_PRIORITY.get(e.tag, DEFAULT_TAG_PRIORITY) > EXTENDED_TIER_MAX:
                continue
            if is_redundant_pair(first.word, e.word):
                continue
            if is_proper_noun(e.word, e.meaning, e.reading):  # a name never rescues diversity (信じる → 信濃)
                continue
            cand_reading = kanji_reading_in_word(kanji, e.word, e.reading, furigana_map)
            if cand_reading is not None and not readings_equivalent(cand_reading, first_reading):
                alt.append(e)
        if alt:
            second = min(alt, key=second_score)

    return second


def _log_diversity_replacement(kanji, first, first_reading, second, all_candidates, furigana_map, second_score, replace_logs):
    """Record when a lower-tier word beat a 🌱/☘️ word for reading diversity, so the
    report can show each pick's per-kanji reading (八十→はち vs 八つ当たり→や)."""
    if replace_logs is None or second is None:
        return
    top_freq_band = TAG_PRIORITY['☘️']  # 🌱/☘️ are the two most-frequent tiers
    if TAG_PRIORITY.get(second.tag, DEFAULT_TAG_PRIORITY) <= top_freq_band:
        return
    passed_over = [
        e for e in all_candidates[1:]
        if TAG_PRIORITY.get(e.tag, DEFAULT_TAG_PRIORITY) <= top_freq_band and e.word != second.word
    ]
    if not passed_over:
        return
    best_passed = min(passed_over, key=second_score)
    second_kr = kanji_reading_in_word(kanji, second.word, second.reading, furigana_map)
    passed_kr = kanji_reading_in_word(kanji, best_passed.word, best_passed.reading, furigana_map)
    replace_logs.append((kanji, first, first_reading, second, second_kr, best_passed, passed_kr))


def select_vocab_for_kanji(kanji, existing_kanji_vocab, word_glosses, freq_index, jmdict_index, furigana_map, replace_logs=None):
    """Return up to 2 best Candidate(word, reading, tag, meaning) for this kanji.

    First slot prefers any primary (freq-ranks/textbook) candidate; existing/JMdict
    only win when the primary pool is empty, and never fill the second slot.
    """
    all_candidates = _gather_sorted_candidates(
        kanji, existing_kanji_vocab, word_glosses, freq_index, jmdict_index
    )
    if not all_candidates:
        return []

    primary = [e for e in all_candidates if _is_primary_tag(e.tag)]
    if not primary:
        # True last resort: one fallback word, no obscure second pad.
        return [all_candidates[0]]

    first = primary[0]
    # Second slot is primary-only (existing/JMdict never pad).
    primary_pool = [first] + [e for e in primary if e.word != first.word]
    if len(primary_pool) == 1:
        return [first]

    first_reading = kanji_reading_in_word(kanji, first.word, first.reading, furigana_map)
    second_score = _make_second_score(kanji, first, first_reading, furigana_map)
    second = _pick_second_word(kanji, first, first_reading, primary_pool, furigana_map, second_score)
    if second is None:
        return [first]
    _log_diversity_replacement(
        kanji, first, first_reading, second, primary_pool, furigana_map, second_score, replace_logs
    )
    return [first, second]


def main():
    # input/filtered_kanji.json is the canonical kanji set (merged_kanji minus
    # kanji_to_remove), produced by src/build_filtered_kanji_json.py. Reading it
    # here (instead of output/kanji_main.json) removes the dependency on a prior
    # build and keeps this script's kanji set identical to the other algo scripts'.
    with open(resolve_path('input/filtered_kanji.json'), encoding='utf-8') as f:
        all_kanji = json.load(f)
    SHIPPED.update(all_kanji)  # enable the all-shipped sample-word preference

    with open(resolve_path('input/kanji_vocab.json'), encoding='utf-8') as f:
        existing_kanji_vocab = json.load(f)
    existing_vocab_words = set(w for words in existing_kanji_vocab.values() for w in words)

    # One JMdict load feeds both the resolver (phrase-fragment detection needs it
    # BEFORE any candidate indexing) and the fallback candidate index.
    jmdict_data = load_jmdict()
    global RESOLVER
    RESOLVER = JmdictResolver(jmdict_data)

    # exp POS forms — needed before indexing so is_valid_candidate can drop
    # noun+particle+kana phrases (音がする) without banning every `exp` word.
    JMDICT_EXP_WORDS.clear()
    for entry in jmdict_data.get('words', []):
        if any('exp' in s.get('partOfSpeech', []) for s in entry.get('sense', [])):
            for form in entry.get('kanji', []):
                t = form.get('text', '')
                if t:
                    JMDICT_EXP_WORDS.add(t)

    # Primary pool: the freq-ranks corpus dataset, indexed once contains-anywhere.
    freq_index = build_freq_candidate_index(set(all_kanji))

    # Full JMdict, indexed once as a last-resort candidate source for rare kanji.
    jmdict_index, jmdict_word_meanings = build_jmdict_candidate_index(set(all_kanji), jmdict_data)

    # Resolved glosses for proper-noun detection, straight from JMdict's full gloss
    # ("Shinano (former province ...)" is what reveals the name-ness).
    PN_GLOSS_LOOKUP.update(
        (w, m) for w, m in jmdict_word_meanings.items() if isinstance(m, str)
    )

    # Per-kanji furigana, used to give the second word a different reading.
    furigana_map = load_json('input/jmdict-furigana-map.json', {})

    kanji_vocab_result = {}

    selected_all = []  # (word, tag, kanji, reading) for stats
    word_gloss = {}    # {word: gloss} for selected words, for the report only
    replace_logs = []

    for kanji in all_kanji:
        selected = select_vocab_for_kanji(kanji, existing_kanji_vocab, jmdict_word_meanings, freq_index, jmdict_index, furigana_map, replace_logs)
        if not selected:
            continue

        kanji_vocab_result[kanji] = [c.word for c in selected]

        for c in selected:
            selected_all.append((c.word, c.tag, kanji, c.reading if c.reading and c.reading != '-' else ''))
            if c.word not in word_gloss:
                g = c.meaning or jmdict_word_meanings.get(c.word, '')
                word_gloss[c.word] = g if isinstance(g, str) else str(g)

    # Reporting is diagnostic-only (stdout, writes no file). Imported here (late) so
    # the report module's top-level `import kanji_vocab_algo` sees this module fully
    # loaded — avoids an import cycle.
    import kanji_vocab_report as report

    report.print_replace_logs(replace_logs)

    def write_and_report(rel_path, data):
        path = write_json(rel_path, data, indent=4)
        print(f"Written: {path} ({len(data)} entries)")

    write_and_report('overrides/kanji_vocab-algo.json', kanji_vocab_result)

    report.print_report(
        selected_all, kanji_vocab_result, all_kanji, existing_vocab_words,
        word_gloss, furigana_map,
    )


if __name__ == '__main__':
    main()
