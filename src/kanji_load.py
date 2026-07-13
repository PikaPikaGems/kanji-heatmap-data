import csv
import utils
import os
import sources
import japanese
import constants as const
from typing import Any

IN_MERGED_KANJI_PATH = os.path.join(const.dir_in, "merged_kanji.json")
IN_FILTERED_KANJI_PATH = os.path.join(const.dir_in, "filtered_kanji.json")
IN_KANJI_VOCAB_PATH = os.path.join(const.dir_in, "kanji_vocab.json")
IN_MISSING_COMPONENTS_PATH = os.path.join(const.dir_in, "missing_components.json")
IN_PHONETIC_COMPONENTS_PATH = os.path.join(const.dir_in, "phonetic_components.json")
IN_CUM_USE_PATH = os.path.join(const.dir_in, "cum_use.json")

IN_ALL_VOCAB_MEANING_JM_DICT_PATH = os.path.join(
    const.dir_in, "scriptin-jmdict-eng.json"
)

IN_JITEN_FREQ_PATH = os.path.join(const.dir_raw, "JITEN_FREQUENCY.csv")
IN_JPDB_FREQ_PATH = os.path.join(const.dir_raw, "JPDB_FREQUENCY_2026-02-09.csv")
IN_KKLC_ORDER_PATH = os.path.join(const.dir_raw, "KKLC-ORDER.txt")

IN_KANJI_TO_REMOVE_OVERRIDES_PATH = os.path.join(
    const.dir_overrides, "kanji_to_remove.json"
)
IN_KEYWORD_OVERRIDES_PATH = os.path.join(const.dir_overrides, "keywords.json")
IN_COMPONENT_KEYWORD_OVERRIDES_PATH = os.path.join(
    const.dir_overrides, "component_keyword.json"
)
IN_KEYWORD_OVERRIDES_ALGO_PATH = os.path.join(const.dir_overrides, "keywords-algo.json")
IN_KANJI_PARTS_OVERRIDES_PATH = os.path.join(const.dir_overrides, "kanji_parts.json")
IN_VOCAB_OVERRIDES_PATH = os.path.join(const.dir_overrides, "kanji_vocab.json")
IN_VOCAB_ALGO_OVERRIDES_PATH = os.path.join(const.dir_overrides, "kanji_vocab-algo.json")
IN_VOCAB_FURIGANA_OVERRIDES_PATH = os.path.join(
    const.dir_overrides, "vocab_furigana.json"
)
IN_VOCAB_MEANING_OVERRIDES_PATH = os.path.join(
    const.dir_overrides, "vocab_meaning.json"
)
IN_JAPANESE_STUDY_WORDS_ALGO_PATH = os.path.join(
    const.dir_overrides, "japanese_study_words-algo.json"
)
IN_JAPANESE_STUDY_WORDS_PATH = os.path.join(
    const.dir_overrides, "japanese_study_words.json"
)

OUT_KANJI_MAIN_PATH = os.path.join(const.dir_out, const.outfile_kanji_main)
OUT_KANJI_EXTENDED_PATH = os.path.join(const.dir_out, const.outfile_kanji_extended)
OUT_PART_KEYWORD_PATH = os.path.join(const.dir_out, const.outfile_component_keyword)
OUT_PHONETIC_PATH = os.path.join(const.dir_out, const.outfile_phonetic)

OUT_VOCAB_MEANING_PATH = os.path.join(const.dir_out, const.outfile_vocab_meaning)
OUT_VOCAB_FURIGANA_PATH = os.path.join(const.dir_out, const.outfile_vocab_furigana)

OUT_CUM_USE_PATH = os.path.join(const.dir_out, const.outfile_cum_use)
OUT_KANJI_REPRESENTATIVE_WORDS_PATH = os.path.join(
    const.dir_out, const.outfile_kanji_representative_words
)
OUT_EXTRA_KANJI_KEYWORD_PATH = os.path.join(
    const.dir_out, const.outfile_extra_kanji_keyword
)


# *********************************
# Functions to load json files
# *********************************
def load_keywords_override():
    a = utils.get_data_from_file(IN_KEYWORD_OVERRIDES_ALGO_PATH)
    b = utils.get_data_from_file(IN_KEYWORD_OVERRIDES_PATH)
    result = {**a, **b}
    return result


def load_decomposition_override():
    return utils.get_data_from_file(IN_KANJI_PARTS_OVERRIDES_PATH)


def load_vocab_override():
    return utils.get_data_from_file(IN_VOCAB_OVERRIDES_PATH)


def load_vocab_algo_override():
    return utils.get_data_from_file(IN_VOCAB_ALGO_OVERRIDES_PATH)


def load_aggregated_kanji_data():
    kanji_data: dict[str, dict[Any, Any]] = utils.get_data_from_file(
        IN_MERGED_KANJI_PATH
    )
    # We just put the kanji as part of the value of the dictionary for quick access
    for kanji in kanji_data.keys():
        kanji_data[kanji]["kanji"] = kanji

    return kanji_data


def load_filtered_kanji_data():
    # input/filtered_kanji.json (built by src/build_filtered_kanji_json.py) is the
    # canonical kanji set. We pull full kanji data from merged_kanji.json but keep
    # only the kanji it lists — so "which kanji ship" lives in exactly one place.
    kanji_data = load_aggregated_kanji_data()
    filtered = set(utils.get_data_from_file(IN_FILTERED_KANJI_PATH))
    return {k: v for k, v in kanji_data.items() if k in filtered}


def load_automated_kanji_vocab():
    return utils.get_data_from_file(IN_KANJI_VOCAB_PATH)


def load_jiten_frequency():
    result = {}
    with open(IN_JITEN_FREQ_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            result[row["Kanji"]] = int(row["Rank"])
    return result


def load_jpdb_frequency():
    result = {}
    with open(IN_JPDB_FREQ_PATH, encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2:
                continue
            try:
                result[row[1]] = int(row[0])
            except ValueError:
                # JPDB caps its list at 4000; ranks below that are written as the
                # literal "4001+" (~1100 rare kanji). Give them a sentinel rank.
                result[row[1]] = 50_000

    return result


def load_kklc_order():
    result = {}
    with open(IN_KKLC_ORDER_PATH, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 4 and parts[0] == "Page":
                result[parts[3]] = int(parts[2])
    return result


# *********************************
# Functions to dump created dictionaries to json
# *********************************


def dump_phonetic_components():
    utils.compress_json(IN_PHONETIC_COMPONENTS_PATH, OUT_PHONETIC_PATH)


def dump_part_keyword_with_overrides(kanji_data: dict[str, Any]):
    # Component keywords come from input/missing_components.json (external) plus the
    # tracked overrides/component_keyword.json (hand-maintained), then any keyword
    # override (keywords-algo / keywords.json) whose key is a non-shipped part.
    additional_keywords = utils.get_data_from_file(IN_MISSING_COMPONENTS_PATH)
    own_keywords_override = load_keywords_override()

    for part, keyword in own_keywords_override.items():
        if kanji_data.get(part, None):
            continue

        additional_keywords[part] = keyword

    # Manual component-keyword overrides win (applied last).
    component_overrides = utils.get_data_from_file(IN_COMPONENT_KEYWORD_OVERRIDES_PATH)
    additional_keywords.update(component_overrides)

    utils.dump_json(OUT_PART_KEYWORD_PATH, additional_keywords)


def dump_extra_kanji_keywords(extra_keywords):
    """Keywords for non-shipped kanji that appear inside sample / study words, so the
    frontend can label them even though they have no output/kanji_main.json entry.
    Sourced from the raw keyword files (see keyword_sources); kanji with no keyword in
    any source are omitted."""
    utils.dump_json(OUT_EXTRA_KANJI_KEYWORD_PATH, extra_keywords)


def dump_cum_use():
    def convert_cum_use_point(point):
        [x, y] = point
        return [x, round(float(y), 2)]

    cum_use_data = utils.get_data_from_file(IN_CUM_USE_PATH)

    for key, value in cum_use_data.items():
        cum_use_data[key] = [convert_cum_use_point(point) for point in value]

    utils.dump_json(OUT_CUM_USE_PATH, cum_use_data)


def dump_to_main_kanji_info(data):
    utils.dump_json(OUT_KANJI_MAIN_PATH, data)


def dump_to_extended_kanji_info(data):
    utils.dump_json(OUT_KANJI_EXTENDED_PATH, data)


def dump_kanji_representative_words():
    """Merge the algorithmic study words with the manual {kanji: word} overrides,
    the manual pins winning — the study-word analog of the kanji_vocab / keywords
    merges, kept out of the algo builder so overrides/japanese_study_words-algo.json
    stays pure algorithm.

    Sources:
      overrides/japanese_study_words-algo.json → {kanji: [word, reading, meaning, tag]}
          the algo output (already includes replaceKanjiStudyWords picks)
      overrides/japanese_study_words.json      → {kanji: word}  manual pins (win)

    Reading/meaning for each manual pin are derived with the SAME resolver the algo
    uses (japanese_study_words_algo.resolve_manual_pin_entries), so the
    override file stays a plain {kanji: word} map. Throws on duplicate words so a
    human can inspect and fix the collision rather than shipping a silent clash.

    In the OUTPUT only, the ✏️ manual-override tag is replaced with the word's real
    frequency badge (frequency_tag) — the -algo file and the algo's logs keep ✏️ so
    which picks were manual stays visible there.
    """
    # Lazy import: the resolver it constructs loads JMdict, so only pay for it here.
    import japanese_study_words_algo as study_words

    merged = utils.get_data_from_file(IN_JAPANESE_STUDY_WORDS_ALGO_PATH)
    pins = utils.get_data_from_file(IN_JAPANESE_STUDY_WORDS_PATH)  # {kanji: word}

    # Derive full entries for pins targeting a shipped kanji (a key in the algo
    # output); pins for unshipped kanji are ignored, matching the algo's own skip.
    pin_words = {k: v.strip() for k, v in pins.items() if k in merged}
    merged.update(study_words.resolve_manual_pin_entries(pin_words))

    # Show a real frequency badge instead of ✏️ in the shipped output (logs keep ✏️).
    for kanji, entry in merged.items():
        if entry is not None and entry[3] == study_words.OVERRIDE_TAG:
            entry[3] = study_words.frequency_tag(kanji, entry[0])

    word_to_kanjis = {}
    for kanji, entry in merged.items():
        if entry is not None:
            word = entry[0]
            word_to_kanjis.setdefault(word, []).append(kanji)
    duplicates = {w: ks for w, ks in word_to_kanjis.items() if len(ks) > 1}
    if duplicates:
        raise ValueError(
            "Duplicate representative study words after merging manual pins "
            "(overrides/japanese_study_words.json) onto the algorithmic output "
            "(overrides/japanese_study_words-algo.json) — each word must map to "
            f"exactly one kanji: {duplicates}"
        )

    # Every shipped study word must carry BOTH a reading and an english gloss. The algo
    # drops its own no-reading/no-meaning picks to None, but a manual pin merged here is
    # not subject to that drop — so a pin whose word resolves nowhere would otherwise
    # ship blank. Fail loudly (add/fix the word in overrides/japanese_study_words.json,
    # or a reading in overrides/vocab_furigana.json).
    no_reading = [(k, e[0]) for k, e in merged.items() if e is not None and not e[1]]
    no_meaning = [(k, e[0]) for k, e in merged.items() if e is not None and not e[2]]
    if no_reading or no_meaning:
        parts = []
        if no_reading:
            parts.append(f"missing reading ({len(no_reading)}): "
                         + ", ".join(f"{k}→{w}" for k, w in no_reading))
        if no_meaning:
            parts.append(f"missing english gloss ({len(no_meaning)}): "
                         + ", ".join(f"{k}→{w}" for k, w in no_meaning))
        raise ValueError(
            "Representative study word(s) with no reading/meaning — every shipped "
            "study word must have both. Fix the pin in overrides/japanese_study_words.json "
            "(or add a reading to overrides/vocab_furigana.json). " + "  ".join(parts)
        )

    # How rich the shipped study words are. Reading/meaning formats come from
    # jmdict_resolver: a ・-joined reading means two readings were kept; a "[1]…[2]…"
    # meaning means those two readings have distinct senses; a " · " means one reading
    # with two senses. (Sample vocab never use these formats — their gloss is a flat
    # JMdict list.)
    shipped = [e for e in merged.values() if e is not None]
    kanji_two_readings = "".join(k for k, e in merged.items() if e is not None and "・" in e[1])
    kanji_block_defs = "".join(k for k, e in merged.items() if e is not None and "[2]" in e[2])
    dot_senses = sum(1 for e in shipped if " · " in e[2])
    print(f"Study words ({len(shipped)}):")
    print(f"  two readings (・, e.g. なか・ちゅう):        {len(kanji_two_readings)}")
    print(f"  two reading-aligned defs ([1]…[2]…):        {len(kanji_block_defs)}")
    print(f"  one reading, two senses ( · ):              {dot_senses}")
    # Concatenated kanji for easy copy-paste (e.g. to spot-check or bulk-edit).
    print(f"  kanji with two readings:\n    {kanji_two_readings}")
    print(f"  kanji with two reading-aligned defs ([1]…[2]…):\n    {kanji_block_defs}")

    utils.dump_json(OUT_KANJI_REPRESENTATIVE_WORDS_PATH, merged)


# *********************************
# Functions to dump word details in particular
# *********************************
def dump_all_vocab_furigana(all_words):
    """Generate furigana for the shipped words into output/vocab_furigana.json.

    Hand-curated overrides/vocab_furigana.json wins; everything else is generated
    on the fly via generate_furigana_algo (furigana map + reading hints + JMdict
    fallback). A word covered by neither — or left as bare [[word]] with kanji —
    aborts the build.
    """
    import generate_furigana_algo as furigana_algo

    furigana_source_overrides = utils.get_data_from_file(
        IN_VOCAB_FURIGANA_OVERRIDES_PATH
    )
    # Generate only for words not already pinned manually.
    to_generate = [w for w in all_words if w not in furigana_source_overrides]
    furigana_source_algo = furigana_algo.build_furigana_for_words(to_generate)

    vocab_furigana = {}
    missing = []
    unreadable = []  # has a furigana entry but it's bare [[word]] (kanji, no reading)

    for word in all_words:
        furigana = furigana_source_overrides.get(word) or furigana_source_algo.get(word)
        if not furigana:
            missing.append(word)
            continue
        vocab_furigana[word] = furigana
        # generate_furigana_algo emits [[word]] (no reading) for words it can't
        # align. That used to be pre-filtered out of selection; now it must fail
        # the build so a truly unreadable word never ships with bare furigana.
        if furigana == [[word]] and any(japanese.is_kanji_char(ch) for ch in word):
            unreadable.append(word)

    if missing or unreadable:
        parts = []
        if missing:
            parts.append(f"no furigana at all ({len(missing)}): {' '.join(missing)}")
        if unreadable:
            parts.append(f"bare [[word]], no reading ({len(unreadable)}): {' '.join(unreadable)}")
        raise Exception(
            "Un-readable sample word(s) — if no reading can be derived, add one to "
            "overrides/vocab_furigana.json. " + "  ".join(parts)
        )

    utils.dump_json(OUT_VOCAB_FURIGANA_PATH, vocab_furigana)


# Suffix-stripping fallback: a handle like 勃発する / 厳粛な is not a JMdict headword,
# but its stem (勃発 / 厳粛) is — so a word JMdict can't gloss directly resolves to the
# stem's gloss. Longest suffixes first so 慄然として strips として before と.
MEANING_STRIP_SUFFIXES = ("として", "する", "な", "と", "だ", "に")


def make_meaning_resolver(*, definition_count=3):
    """Return a `resolve(word) -> meaning` closure over the single JMdict source.

    Every gloss comes from JMdict (input/scriptin-jmdict-eng.json), built the same
    way the sample-vocab algorithm builds glosses. Resolution order:
        overrides/vocab_meaning.json  (manual hatch, empty for now)
        → JMdict gloss for the exact word
        → JMdict gloss for the word's stem after stripping a する/な/… suffix
    The returned function carries the JMdict common flags as `.is_common` for the
    coverage breakdown in dump_all_vocab_meanings.
    """
    overrides: dict[str, str] = utils.get_data_from_file(IN_VOCAB_MEANING_OVERRIDES_PATH)
    jmdict = utils.get_data_from_file(IN_ALL_VOCAB_MEANING_JM_DICT_PATH)
    gloss, is_common = sources.build_jmdict_meaning_index(jmdict, definition_count)

    def resolve(word):
        meaning = overrides.get(word) or gloss.get(word)
        if meaning:
            return meaning
        for suffix in sorted(MEANING_STRIP_SUFFIXES, key=len, reverse=True):
            if word.endswith(suffix) and gloss.get(word[: -len(suffix)]):
                return gloss[word[: -len(suffix)]]
        return None

    resolve.is_common = is_common
    return resolve


def _print_common_breakdown(label, words, is_common):
    """One line: how many of `words` JMdict flags as common vs uncommon/full-only."""
    total = len(words)
    common = sum(1 for w in words if is_common.get(w))
    if not total:
        return
    print(
        f"  {label} ({total}): "
        f"{common} JMdict-common ({common / total:.0%}), "
        f"{total - common} uncommon/full-only ({(total - common) / total:.0%})"
    )


def _word_to_kanji_map():
    """{word: [kanji, ...]} — which kanji each sample word belongs to. Built only to
    make the no-meaning failure below point at the kanji whose sample list to fix."""
    word_to_kanji: dict[str, list[str]] = {}
    for src_path in (IN_KANJI_VOCAB_PATH, IN_VOCAB_ALGO_OVERRIDES_PATH, IN_VOCAB_OVERRIDES_PATH):
        for kanji, words in utils.get_data_from_file(src_path).items():
            for w in words:
                word_to_kanji.setdefault(w, []).append(kanji)
    return word_to_kanji


def dump_all_vocab_meanings(all_words):
    vocab_meanings = {}
    get_meaning = make_meaning_resolver(definition_count=3)

    not_found: list[str] = []
    for word in all_words:
        meaning = get_meaning(word)
        if not meaning:
            not_found.append(word)
        else:
            vocab_meanings[word] = meaning

    # Every shipped sample word must resolve to a meaning. JMdict covers essentially
    # everything; a word with no gloss (even after suffix-stripping) is a data gap to
    # fix — pin it in overrides/vocab_meaning.json — not something to ship blank.
    if not_found:
        word_to_kanji = _word_to_kanji_map()
        detail = "\n".join(f"    {word_to_kanji.get(w, [])}: {w}" for w in not_found)
        kanjis = "".join("".join(word_to_kanji.get(w, [])) for w in not_found)
        raise Exception(
            f"No meaning for {len(not_found)} sample word(s) — add them to "
            f"overrides/vocab_meaning.json (kanji: {kanjis}):\n{detail}"
        )

    # JMdict-common vs uncommon breakdown for the two shipped word sets.
    study_words = [
        e[0] for e in utils.get_data_from_file(OUT_KANJI_REPRESENTATIVE_WORDS_PATH).values()
        if e is not None
    ]
    print("JMdict-common coverage:")
    _print_common_breakdown("sample vocab", all_words, get_meaning.is_common)
    _print_common_breakdown("study words", study_words, get_meaning.is_common)
    utils.dump_json(OUT_VOCAB_MEANING_PATH, vocab_meanings)
