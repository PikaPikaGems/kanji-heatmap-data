import utils
import os
import constants as const

IN_MERGED_KANJI_PATH = os.path.join(const.dir_in, "merged_kanji.json")
IN_KANJI_VOCAB_PATH = os.path.join(const.dir_in, "kanji_vocab.json")
IN_VOCAB_FUGIGANA_PATH = os.path.join(const.dir_in, "vocab_furigana.json")
IN_VOCAB_MEANING_PATH = os.path.join(const.dir_in, "vocab_meaning.json")
IN_MISSING_COMPONENTS_PATH = os.path.join(const.dir_in, "missing_components.json")
IN_PHONETIC_COMPONENTS_PATH = os.path.join(const.dir_in, "phonetic_components.json")
IN_CUM_USE_PATH = os.path.join(const.dir_in, "cum_use.json")

IN_ALL_VOCAB_FURIGANA_PATH = os.path.join(const.dir_in, "jmdict-furigana-map.json")
IN_ALL_VOCAB_MEANING_JM_DICT_PATH = os.path.join(
    const.dir_in, "scriptin-jmdict-eng.json"
)
MID_ALL_VOCAB_MEANING_PATH = os.path.join(const.dir_in, "jmdict-vocab-meaning.json")

IN_KEYWORD_OVERRIDES_PATH = os.path.join(const.dir_overrides, "keywords.json")
IN_KANJI_PARTS_OVERRIDES_PATH = os.path.join(const.dir_overrides, "kanji_parts.json")
IN_VOCAB_OVERRIDES_PATH = os.path.join(const.dir_overrides, "kanji_vocab.json")
IN_VOCAB_FURIGANA_OVERRIDES_PATH = os.path.join(
    const.dir_overrides, "vocab_furigana.json"
)

OUT_KANJI_MAIN_PATH = os.path.join(const.dir_out, const.outfile_kanji_main)
OUT_KANJI_EXTENDED_PATH = os.path.join(const.dir_out, const.outfile_kanji_extended)
OUT_PART_KEYWORD_PATH = os.path.join(const.dir_out, const.outfile_component_keyword)
OUT_PHONETIC_PATH = os.path.join(const.dir_out, const.outfile_phonetic)

OUT_VOCAB_MEANING_PATH = os.path.join(const.dir_out, const.outfile_vocab_meaning)
OUT_VOCAB_FURIGANA_PATH = os.path.join(const.dir_out, const.outfile_vocab_furigana)

OUT_CUM_USE_PATH = os.path.join(const.dir_out, const.outfile_cum_use)


# *********************************
# { word: meaning }
# *********************************
def build_vocab_meaning_map(items, common_only=True, definition_count=3):
    words = items["words"]

    result = {}

    for item in words:
        # Check if there's at least one common kanji element
        all_kanji_words = [k for k in item.get("kanji", [])]
        if common_only:
            all_kanji_words = [
                k for k in item.get("kanji", []) if k.get("common", False)
            ]
        if not all_kanji_words:
            continue

        # Get the first common kanji text as the word, preferably only japanese characters
        word = next(
            (x["text"] for x in all_kanji_words if utils.is_japanese_only(x["text"])),
            all_kanji_words[0]["text"],
        )

        # Process senses to get the definition
        definition_parts = []

        for sense in item.get("sense", []):
            applies_to_kanji = sense.get("appliesToKanji", [])
            # Check if applies to all kanji or specifically to our word
            if "*" in applies_to_kanji or word in applies_to_kanji:
                for gloss in sense.get("gloss", []):
                    if gloss.get("lang") == "eng":
                        definition_parts.append(gloss["text"])

        if definition_parts:
            definition = ", ".join(definition_parts[:definition_count])
            result[word] = definition

    return result


def create_or_retrieve_vocab_meaning_map(
    refresh=False, common_only=True, definition_count=3
):

    meanings = None

    if not refresh:
        try:
            meanings = utils.get_data_from_file(MID_ALL_VOCAB_MEANING_PATH)
            return meanings
        except:
            print(f"Failed read file {MID_ALL_VOCAB_MEANING_PATH}.")
            print(f"Will rebuild dictionary instead...")

    items = utils.get_data_from_file(IN_ALL_VOCAB_MEANING_JM_DICT_PATH)
    meanings = build_vocab_meaning_map(items, common_only, definition_count)
    utils.dump_json(MID_ALL_VOCAB_MEANING_PATH, meanings)
    return meanings


# *********************************
# Functions to load json files
# *********************************
def load_keywords_override():
    return utils.get_data_from_file(IN_KEYWORD_OVERRIDES_PATH)


def load_decomposition_override():
    return utils.get_data_from_file(IN_KANJI_PARTS_OVERRIDES_PATH)


def load_vocab_override():
    return utils.get_data_from_file(IN_VOCAB_OVERRIDES_PATH)


def load_aggregated_kanji_data():
    kanji_data = utils.get_data_from_file(IN_MERGED_KANJI_PATH)
    # We just put the kanji as part of the value of the dictionary sfor quick access
    for kanji in kanji_data.keys():
        kanji_data[kanji]["kanji"] = kanji

    return kanji_data


def load_automated_kanji_vocab():
    return utils.get_data_from_file(IN_KANJI_VOCAB_PATH)


# *********************************
# Functions to dump created dictionaries to json
# *********************************


def dump_phonetic_components():
    utils.compress_json(IN_PHONETIC_COMPONENTS_PATH, OUT_PHONETIC_PATH)


def dump_part_keyword_with_overrides():
    additional_keywords = utils.get_data_from_file(IN_MISSING_COMPONENTS_PATH)
    own_keywords_override = load_keywords_override()
    kanji_data = load_aggregated_kanji_data()

    for part, keyword in own_keywords_override.items():
        if kanji_data.get(part, None):
            continue

        additional_keywords[part] = keyword

    utils.dump_json(OUT_PART_KEYWORD_PATH, additional_keywords)


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


# *********************************
# Functions to dump word details in particular
# *********************************
def dump_all_vocab_furigana(all_words):

    furigana_source = utils.get_data_from_file(IN_ALL_VOCAB_FURIGANA_PATH)
    furigana_source_custom = utils.get_data_from_file(IN_VOCAB_FUGIGANA_PATH)
    furigana_source_overrides = utils.get_data_from_file(
        IN_VOCAB_FURIGANA_OVERRIDES_PATH
    )

    vocab_furigana = {}

    count_not_in_default_furigana_src = 0

    for word in all_words:

        furigana = furigana_source_overrides.get(
            word, furigana_source_custom.get(word, None)
        )

        if not furigana:
            count_not_in_default_furigana_src += 1
            furigana_deep = furigana_source.get(word, None)
            if not furigana_deep:
                raise Exception("Decomposition Not Found", word)
            furigana_keys = [x for x in furigana_deep.keys()]

            if not furigana_keys:
                raise Exception("Decomposition Not Found", word)

            # get the first pronounciation available
            key = furigana_keys[0]
            furigana = furigana_deep[key]

        vocab_furigana[word] = furigana
    print("total of not in default furigana_source:", count_not_in_default_furigana_src)

    utils.dump_json(OUT_VOCAB_FURIGANA_PATH, vocab_furigana)


def dump_all_vocab_meanings(all_words):
    vocab_meanings = {}
    meaning_source_common = create_or_retrieve_vocab_meaning_map(
        refresh=True, common_only=True, definition_count=3
    )
    meaning_source_custom = utils.get_data_from_file(IN_VOCAB_MEANING_PATH)

    count_common_source_only = 0
    count_custom_source_only = 0
    for word in all_words:
        meaning1 = meaning_source_common.get(word, None)
        meaning2 = meaning_source_custom.get(word, None)

        if meaning1 and not meaning2:
            count_common_source_only += 1

        if meaning2 and not meaning1:
            count_custom_source_only += 1

        meaning = meaning1 or meaning2
        if not meaning:
            raise Exception("Word meaning Not Found", word)

        vocab_meanings[word] = meaning

    print("in common meaning source only:", count_common_source_only)
    print("in custom meaning source only:", count_custom_source_only)
    utils.dump_json(OUT_VOCAB_MEANING_PATH, vocab_meanings)
