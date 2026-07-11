"""Single source of truth for study-word readings and meanings, from JMdict.

Resolves a word (as written, e.g. 空 or 高い) to its common reading(s) and a short
English meaning, using input/scriptin-jmdict-eng.json ONLY. Word pools (v3c,
freq-ranks, textbook) supply candidate words and frequency tags; their own
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
  Only clearly-common extra readings join the first (common, not demoted, and
  ≥2 senses unless the first reading itself has just one — keeps 前 → まえ・ぜん
  and 毎 → ごと・まい but not 字 → じ・あざ). PREFERRED_FIRST_KANA patches the
  numerals where JMdict's flattened `common` boolean hides that よん/なな lead
  (し/しち are avoided for superstition; no in-file signal survives conversion).

Meanings (senses ordered as in JMdict; glosses joined ", "; capped ~150 chars):
  one reading   up to 2 senses joined with " · "  (語 → "word, term · language")
  two readings  first sense of each as "[n] ..." blocks aligned with the split
                readings ("[1] sky, the air, the heavens [2] emptiness, being
                empty"); identical blocks collapse to one plain string (四 —
                both し and よん mean "four, 4").
  The meaning sense separator is plain · U+00B7, distinct from the reading
  separator ・ U+30FB, so splitting readings on ・ never touches meanings.
"""

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

# Words whose leading reading JMdict's flattened `common` flag gets wrong.
# Keyed by the word as written; value must be one of the word's common kana.
PREFERRED_FIRST_KANA = {"四": "よん", "七": "なな"}

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
        self._index = {}
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
            else:
                # the word is itself a kana form (pure-kana word)
                kana_form = next(
                    (k for k in entry.get("kana", []) if k.get("text") == word), None)
                if kana_form is None:
                    continue
                word_common = bool(kana_form.get("common"))
                kana_forms = [kana_form]

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
                    "senses": senses,
                    "entry_senses": entry_senses,
                    "_order": (entry_index, kana_index),
                })

        candidates.sort(key=lambda c: (
            not c["common"],
            not c["standalone"],
            c["demoted"],
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
        ranked = self.reading_candidates(word)
        if not ranked:
            return None
        first = ranked[0]

        extras = [c for c in ranked[1:]
                  if c["common"] and not c["demoted"]
                  and (len(c["senses"]) >= 2 or len(first["senses"]) == 1)]
        picked = [first] + extras
        preferred = PREFERRED_FIRST_KANA.get(word)
        if preferred:
            for i, c in enumerate(picked):
                if c["kana"] == preferred and i != 0:
                    picked.insert(0, picked.pop(i))
                    break
        picked = picked[:MAX_READINGS]

        return {
            "reading": "・".join(c["kana"] for c in picked),
            "readings": [c["kana"] for c in picked],
            "meaning": _format_meaning(picked),
            "standalone": first["standalone"],
            "word_class": _word_class(first),
            "common": first["common"],
        }


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
    if len(set(blocks)) == 1:
        return blocks[0]  # readings share the sense (四: し/よん) — no [n] needed
    return " ".join(f"[{i}] {b}" for i, b in enumerate(blocks, 1))
