"""Single source of truth for study-word readings and meanings, from JMdict.

Resolves a word (as written, e.g. 空 or 高い) to its common reading(s) and a short
English meaning, using input/scriptin-jmdict-eng.json ONLY. Word pools
(freq-ranks, textbook) supply candidate words and frequency tags; their own
reading/meaning fields must never reach the output — this module replaces them.

Readings (up to MAX_READINGS, most common first, joined with ・ U+30FB):
  A word like 空 has homograph readings in two JMdict shapes: separate entries
  sharing the written form (空 = そら / から / くう / うろ) and kana siblings
  within one entry (四 = し / よん / よ). Candidates are every (entry, kana form)
  pair for the word, minus irregular/outdated forms, ranked by:
    1. common       both the word's form and the kana form are marked common
    2. standalone   the FIRST applicable sense has a non-affix part of speech —
                    puts real words (空/そら) above prefix entries (新/しん),
                    whose noun senses are trailing trivia ("Xin dynasty")
    3. not demoted  literary/archaic/dated-only entries (書/ふみ "form") sink
    4. entry sense count  desc — the everyday reading has the fat entry
                    (はいる 13 senses vs いる 5; しょ 4 vs ふみ 3)
    5. file order   within one entry JMdict curates kana order well
                    (きょう before こんにち, あした before あす)
  Only clearly-common extra readings join the first: common, not demoted,
  ≥2 senses unless the first reading itself has just one (keeps 前 → まえ・ぜん
  and 毎 → ごと・まい but not 字 → じ・あざ), and the word must be its entry's
  LEADING kanji form — もと's entry lists 元 first with 本 as an alternative
  writing, so もと belongs to 元 and never rides along on 本. The readingOrder
  map in overrides/resolver_hints.json patches the numerals where JMdict's
  flattened `common` boolean hides that よん/なな lead (し/しち are avoided for
  superstition; no in-file signal survives conversion).

Meanings (senses ordered as in JMdict; glosses joined ", "; capped ~150 chars):
  one reading   up to 2 senses joined with " · "  (語 → "word, term · language")
  two readings  first sense of each as "[n] ..." blocks aligned with the split
                readings ("[1] sky, the air, the heavens [2] emptiness, being
                empty"); blocks that mean the same thing — identical, or same
                leading gloss — collapse to one plain string (四 "four, 4";
                一 "one, 1"; 入る "to enter, to come in, to go in").
  The meaning sense separator is plain · U+00B7, distinct from the reading
  separator ・ U+30FB, so splitting readings on ・ never touches meanings.
"""

from japanese import (
    is_kanji_char,
    segment_word,
    FRAGMENT_PREFIXES,
    particle_attached_stem,
)
from sources import load_json

# Readings per word: 2 keeps the display tight; JMdict rarely has a third
# reading worth teaching.
MAX_READINGS = 2

MEANING_MAX_CHARS = 150  # safety cap, not a target — shapes above stay shorter
MAX_GLOSSES_PER_SENSE = 3
MAX_SENSES_SINGLE_READING = 2

# Form-level tags that disqualify a writing/reading pairing outright.
# NOTE: gikun is NOT here — 今日/きょう, 明日/あした, 昨日/きのう are gikun.
BAD_KANJI_TAGS = {"rK", "sK", "oK", "iK", "io"}   # rare/search/outdated/irregular writings
BAD_KANA_TAGS = {"ok", "ik", "sk"}                # outdated/irregular/search-only kana

# Parts of speech that do not make a word standalone (affixes, counters,
# particles, auxiliaries, unclassified).
AFFIX_POS = {"pref", "suf", "n-pref", "n-suf", "ctr", "prt", "aux", "aux-v",
             "aux-adj", "unc"}

# A candidate whose every applicable sense carries one of these is a
# literary/archaic form (書/ふみ) — ranked below living readings.
DEMOTE_MISC = {"form", "arch", "dated", "obs", "rare", "obsc", "poet"}

# Hand-maintained per-word corrections live OUTSIDE the code, in
# overrides/resolver_hints.json:
#   readingOrder  {word: kana} — which reading leads when JMdict's flattened
#                 `common` flag gets it wrong (四: よん, 七: なな)
#   meanings      {word: meaning} — full replacement for a generated meaning
HINTS_PATH = "overrides/resolver_hints.json"

# Appended to resolve_fallback meanings for usually-kana words (諄い, 亦, 於いて),
# warning that the kanji writing shown is not how the word is normally written.
KANA_ONLY_MARKER = " [⚠️ often kana only]"

# Kanji-form tags resolve() rejects that resolve_fallback tolerates. sK stays
# excluded outside manual mode: search-only forms are hidden writings that
# belong to another word entirely (亘る is an sK form of 渡る).
FALLBACK_KANJI_TAGS = {"rK", "oK", "iK", "io"}

# word_class values (lower = preferred as a study word)
CLASS_VERB = 0
CLASS_ADJECTIVE = 1
CLASS_OTHER = 2

_VERB_POS_PREFIXES = ("v1", "v5", "vk", "vz", "vi", "vt", "vs-i", "vs-s")
_ADJ_POS = {"adj-i", "adj-ix", "adj-na", "adj-f"}


def _english_glosses(sense):
    return [g["text"] for g in sense.get("gloss", [])
            if g.get("lang") == "eng" and g.get("text")]


def _sense_applies(sense, word, kana_text):
    applies_kanji = sense.get("appliesToKanji", [])
    applies_kana = sense.get("appliesToKana", [])
    return (("*" in applies_kanji or word in applies_kanji)
            and ("*" in applies_kana or kana_text in applies_kana))


class JmdictResolver:
    """Word → readings/meaning/word-shape lookups over one loaded JMdict."""

    def __init__(self, data=None):
        if data is None:
            data = load_json("input/scriptin-jmdict-eng.json", {})
        hints = load_json(HINTS_PATH, {})
        self._preferred_first_kana = hints.get("readingOrder", {})
        self._meaning_overrides = hints.get("meanings", {})
        self._index = {}
        self._resolve_cache = {}  # selection scoring resolves the same words repeatedly
        for entry in data.get("words", []):
            for form in entry.get("kanji", []) + entry.get("kana", []):
                text = form.get("text")
                if text:
                    self._index.setdefault(text, []).append(entry)

    # -- candidate readings ------------------------------------------------

    def reading_candidates(self, word):
        """Ranked candidate readings for `word` (best first), deduped by kana.

        Each candidate: {kana, common, standalone, demoted, senses, entry_senses}.
        senses = the JMdict senses (with English glosses) applying to this
        (word, kana) pairing, in JMdict order.
        """
        candidates = []
        for entry_index, entry in enumerate(self._index.get(word, [])):
            kanji_form = next(
                (k for k in entry.get("kanji", []) if k.get("text") == word), None)
            if kanji_form is not None:
                if set(kanji_form.get("tags", [])) & BAD_KANJI_TAGS:
                    continue
                word_common = bool(kanji_form.get("common"))
                kana_forms = entry.get("kana", [])
                # Is `word` this entry's canonical (leading) writing? もと's entry
                # lists 元 first with 本 as an alternative — so もと belongs to 元,
                # and must not ride along as an extra reading of 本.
                canonical = entry["kanji"][0].get("text") == word
            else:
                # the word is itself a kana form (pure-kana word)
                kana_form = next(
                    (k for k in entry.get("kana", []) if k.get("text") == word), None)
                if kana_form is None:
                    continue
                word_common = bool(kana_form.get("common"))
                kana_forms = [kana_form]
                canonical = True  # pure-kana word: kana IS the writing

            # Entry-level sense count ranks ACROSS entries; within one entry the
            # file's kana order decides, so siblings tie here by construction.
            entry_senses = sum(
                1 for s in entry.get("sense", [])
                if _english_glosses(s)
                and ("*" in s.get("appliesToKanji", [])
                     or word in s.get("appliesToKanji", []))
            )

            for kana_index, kana in enumerate(kana_forms):
                if kanji_form is not None:
                    applies = kana.get("appliesToKanji", [])
                    if "*" not in applies and word not in applies:
                        continue
                if set(kana.get("tags", [])) & BAD_KANA_TAGS:
                    continue
                senses = [s for s in entry.get("sense", [])
                          if _sense_applies(s, word, kana["text"])
                          and _english_glosses(s)]
                if not senses:
                    continue
                standalone = any(p not in AFFIX_POS
                                 for p in senses[0].get("partOfSpeech", []))
                demoted = all(set(s.get("misc", [])) & DEMOTE_MISC for s in senses)
                candidates.append({
                    "kana": kana["text"],
                    "common": word_common and bool(kana.get("common")),
                    "standalone": standalone,
                    "demoted": demoted,
                    "canonical": canonical,
                    "senses": senses,
                    "entry_senses": entry_senses,
                    "_order": (entry_index, kana_index),
                })

        candidates.sort(key=lambda c: (
            not c["common"],
            not c["standalone"],
            c["demoted"],
            not c["canonical"],  # 本: ほん must outrank もと (whose home is 元)
            -c["entry_senses"],
            c["_order"],
        ))
        seen, ranked = set(), []
        for c in candidates:
            if c["kana"] not in seen:
                seen.add(c["kana"])
                ranked.append(c)
        return ranked

    # -- public resolution ---------------------------------------------------

    def resolve(self, word):
        """Reading/meaning/shape for `word`, or None when JMdict doesn't know it.

        Returns {reading, readings, meaning, standalone, word_class, common}:
          reading     "そら・から" (・-joined, most common first)
          readings    ["そら", "から"]
          meaning     one string; "[n]" blocks align with the split readings
          standalone  True when the word works as a standalone word (its best
                      reading's first sense is not affix-only)
          word_class  CLASS_VERB < CLASS_ADJECTIVE < CLASS_OTHER
          common      True when the best reading is a JMdict-common pairing
        """
        if word in self._resolve_cache:
            return self._resolve_cache[word]
        result = self._resolve(word)
        self._resolve_cache[word] = result
        return result

    def _resolve(self, word):
        ranked = self.reading_candidates(word)
        if not ranked:
            return None
        first = ranked[0]

        extras = [c for c in ranked[1:]
                  if c["common"] and not c["demoted"] and c["canonical"]
                  and (len(c["senses"]) >= 2 or len(first["senses"]) == 1)]
        picked = [first] + extras
        preferred = self._preferred_first_kana.get(word)
        if preferred:
            for i, c in enumerate(picked):
                if c["kana"] == preferred and i != 0:
                    picked.insert(0, picked.pop(i))
                    break
        picked = picked[:MAX_READINGS]

        return {
            "reading": "・".join(c["kana"] for c in picked),
            "readings": [c["kana"] for c in picked],
            "meaning": self._meaning_overrides.get(word) or _format_meaning(picked),
            "standalone": first["standalone"],
            "word_class": _word_class(first),
            "common": first["common"],
        }


    def pos_profile(self, word):
        """All partOfSpeech tags across the best reading's senses ([] when JMdict
        doesn't know the word). Feed to classify_pos for report tallies."""
        ranked = self.reading_candidates(word)
        if not ranked:
            return []
        return [p for s in ranked[0]["senses"] for p in s.get("partOfSpeech", [])]

    # -- phrase-fragment detection -------------------------------------------

    def is_phrase_fragment(self, word):
        """True for corpus "words" that are really a word plus grammar: a
        demonstrative glued to a noun (この人, その様) or a standalone word with
        a trailing particle chunk (常に = 常+に, 今も = 今+も, 事になる).

        JMdict listing the combination doesn't save it — 常に and 今も are real
        entries, but the learner should study 常 and 今. The particle test needs
        the stem to be a standalone word AND the combination to read as
        stem-reading + particle, which is what separates fragments from genuine
        adverbs: 特に survives because 特 alone is not a standalone word, and
        更に survives because 更 alone reads こう, not さら.

        A kanji+の+kanji possessive (心の内, 自分の力, 又の日) is likewise a
        fragment unless JMdict marks the whole thing common — that keeps the
        genuinely lexicalised ones (世の中, 身の上)."""
        if word.startswith(FRAGMENT_PREFIXES):
            return True
        if self._is_no_possessive_fragment(word):
            return True
        stem = particle_attached_stem(word)
        if stem is None:
            return False
        resolved_stem = self.resolve(stem)
        if resolved_stem is None or not resolved_stem["standalone"]:
            return False
        word_candidates = self.reading_candidates(word)
        if not word_candidates:
            return True  # unresolvable kanji+particle string is junk outright
        if not any(c["common"] for c in word_candidates):
            # Corpus-frequent but JMdict-marginal (誰が, whose only JMdict entry
            # is the archaic たが): word + grammar, never sample-worthy.
            return True
        # A fragment reads as EXACTLY stem-reading + the particle kana
        # (常に = つね+に, 何て = なん+て). Requiring the full composition —
        # checked against every reading candidate, in case an archaic entry
        # outranks the plain one — keeps real okurigana words like 手当て
        # (てあて is not てあて+て) and 全て (すべて is not ぜん+て).
        tail = word[len(stem):]
        return any(c["kana"] == sr + tail
                   for c in word_candidates
                   for sr in resolved_stem["readings"])

    def _is_no_possessive_fragment(self, word):
        """True for kanji+の+kanji words (心の内) that JMdict doesn't mark common."""
        spans = segment_word(word)
        has_no_bridge = any(
            span == ("の", False) and spans[i - 1][1] and spans[i + 1][1]
            for i, span in enumerate(spans[1:-1], 1)
        )
        if not has_no_bridge:
            return False
        resolved = self.resolve(word)
        return resolved is None or not resolved["common"]

    # -- last-resort resolution for rare writings ----------------------------

    def resolve_fallback(self, word, shipped=None, manual=False):
        """Reading/meaning for a word resolve() rejects because its kanji writing
        is tagged rare/outdated (rK/oK/io), or None. Same shape as resolve().

        A rare writing is accepted only when it genuinely belongs to `word`
        rather than to a different common kanji:
          - usually-kana words with no common kanji sibling (諄い/くどい,
            亦/また, 於いて/おいて): the word's real "common form" is the kana,
            so no other kanji owns it. KANA_ONLY_MARKER is appended.
          - glyph variants whose canonical writing uses a kanji outside
            `shipped` (充塡: canonical 充填 uses 填; we ship the jōyō 塡, so
            充塡 is the only writing we can teach). No marker — the word is
            normally written in kanji, just with the other glyph.
          - manual=True: a human picked this writing (✏️ overrides, 昂ぶる) —
            resolve it without gates, marker only if usually kana.
        Everything else returns None — 媛 stays unresolved because ひめ is
        written 姫, and 亘る (sK) because it belongs to 渡る.
        """
        for entry in self._index.get(word, []):
            kanji_form = next(
                (k for k in entry.get("kanji", []) if k.get("text") == word), None)
            if kanji_form is None:
                continue
            tags = set(kanji_form.get("tags", []))
            if not manual and not tags <= FALLBACK_KANJI_TAGS:
                continue

            kana_forms = [
                k for k in entry.get("kana", [])
                if not (set(k.get("tags", [])) & BAD_KANA_TAGS)
                and ("*" in k.get("appliesToKanji", ["*"])
                     or word in k.get("appliesToKanji", []))
            ]
            kana = next((k for k in kana_forms if k.get("common")),
                        kana_forms[0] if kana_forms else None)
            if kana is None:
                continue
            senses = [s for s in entry.get("sense", [])
                      if _sense_applies(s, word, kana["text"])
                      and _english_glosses(s)]
            if not senses:
                continue

            usually_kana = "uk" in senses[0].get("misc", [])
            common_kanji_sibling = any(
                k.get("common") for k in entry.get("kanji", []))
            canonical = entry["kanji"][0].get("text", "")
            glyph_variant = (
                shipped is not None and canonical != word
                and any(is_kanji_char(c) and c not in shipped for c in canonical)
                and all(not is_kanji_char(c) or c in shipped for c in word)
            )
            if not (manual or glyph_variant
                    or (usually_kana and not common_kanji_sibling)):
                continue

            candidate = {"kana": kana["text"], "senses": senses}
            meaning = self._meaning_overrides.get(word)
            if not meaning:
                meaning = _format_meaning([candidate])
                if usually_kana:
                    meaning += KANA_ONLY_MARKER
            return {
                "reading": kana["text"],
                "readings": [kana["text"]],
                "meaning": meaning,
                "standalone": any(p not in AFFIX_POS
                                  for p in senses[0].get("partOfSpeech", [])),
                "word_class": _word_class(candidate),
                "common": False,  # the writing is rare even when the word isn't
            }
        return None


def classify_pos(pos_tags):
    """Coarse POS bucket for report tallies: verb / i-adjective / na-adjective /
    adjective (other) / noun / other. Priority mirrors _word_class — a word with
    both verb and noun senses counts as a verb."""
    if any(p.startswith(_VERB_POS_PREFIXES) for p in pos_tags):
        return "verb"
    if any(p in ("adj-i", "adj-ix") for p in pos_tags):
        return "i-adjective"
    if "adj-na" in pos_tags:
        return "na-adjective"
    if any(p in _ADJ_POS for p in pos_tags):
        return "adjective (other)"
    if any(p == "n" or p in ("n-adv", "n-t") for p in pos_tags):
        return "noun"
    return "other"


def _word_class(candidate):
    pos_tags = [p for s in candidate["senses"] for p in s.get("partOfSpeech", [])]
    if any(p.startswith(_VERB_POS_PREFIXES) for p in pos_tags):
        return CLASS_VERB
    if any(p in _ADJ_POS for p in pos_tags):
        return CLASS_ADJECTIVE
    return CLASS_OTHER


def _format_meaning(picked):
    for glosses_per_sense in range(MAX_GLOSSES_PER_SENSE, 0, -1):
        meaning = _build_meaning(picked, glosses_per_sense)
        if len(meaning) <= MEANING_MAX_CHARS:
            return meaning
    return meaning  # even 1 gloss each overflows (very rare) — ship it anyway


def _build_meaning(picked, glosses_per_sense):
    def sense_text(sense):
        return ", ".join(_english_glosses(sense)[:glosses_per_sense])

    if len(picked) == 1:
        senses = picked[0]["senses"][:MAX_SENSES_SINGLE_READING]
        return " · ".join(sense_text(s) for s in senses)

    blocks = [sense_text(c["senses"][0]) for c in picked]
    # Readings that mean the same thing get ONE meaning, not [n] blocks: exact
    # duplicates (四: し/よん both "four, 4") and near-duplicates whose leading
    # gloss matches (一: "one, 1"/"one", 入る: "to enter, ..."/"to enter, ...").
    first_glosses = {_english_glosses(c["senses"][0])[0].strip().lower() for c in picked}
    if len(set(blocks)) == 1 or len(first_glosses) == 1:
        return max(blocks, key=len)  # keep the richest phrasing of the shared sense
    return " ".join(f"[{i}] {b}" for i, b in enumerate(blocks, 1))
