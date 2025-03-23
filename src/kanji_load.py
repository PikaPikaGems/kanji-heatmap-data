import utils
import os

IN_DIR = "input"
OUT_DIR = "output"
OVERRIDES_DIR = "overrides"

IN_MERGED_KANJI_FILE_PATH = os.path.join(IN_DIR, "merged_kanji.json")

IN_KEYWORD_OVERRIDES_FILE_PATH = os.path.join(OVERRIDES_DIR, "keywords.json")
IN_KANJI_PARTS_OVERRIDES_FILE_PATH = os.path.join(OVERRIDES_DIR, "kanji_parts.json")

IN_KANJI_VOCAB_FILE_PATH = os.path.join(IN_DIR, "kanji_vocab.json")
IN_VOCAB_FURIGANA_FILE_PATH = os.path.join(IN_DIR, "vocab_furigana.json")
IN_VOCAB_MEANING_FILE_PATH = os.path.join(IN_DIR, "vocab_meaning.json")
IN_MISSING_COMPONENTS_FILE_PATH = os.path.join(IN_DIR, "missing_components.json")
IN_PHONETIC_COMPONENTS_FILE_PATH = os.path.join(IN_DIR, "phonetic_components.json")
IN_CUM_USE_FILE_PATH = os.path.join(IN_DIR, "cum_use.json")

OUT_KANJI_MAIN_FILE_PATH = os.path.join(OUT_DIR, "kanji_main.json")
OUT_KANJI_EXTENDED_FILE_PATH = os.path.join(OUT_DIR, "kanji_extended.json")
OUT_PART_KEYWORD_FILE_PATH = os.path.join(OUT_DIR, "component_keyword.json")
OUT_PHONETIC_FILE_PATH = os.path.join(OUT_DIR, "phonetic.json")
OUT_VOCAB_FILE_PATH = os.path.join(OUT_DIR, "vocabulary.json")
OUT_CUM_USE_FILE_PATH = os.path.join(OUT_DIR, "cum_use.json")

# *********************************
# LOAD FROM JSON FILES
# *********************************

KANJI_DATA = utils.get_data_from_file(IN_MERGED_KANJI_FILE_PATH) 
KANJI_LIST = KANJI_DATA.keys()

# We just put the kanji as part of the value of the dictionary sfor quick access
for kanji in KANJI_LIST: 
    KANJI_DATA[kanji]['kanji'] = kanji

OWN_KEYWORDS_OVERRIDE = utils.get_data_from_file(IN_KEYWORD_OVERRIDES_FILE_PATH)
OWN_PARTS_OVERRIDE = utils.get_data_from_file(IN_KANJI_PARTS_OVERRIDES_FILE_PATH)

# merge missing components from own keyword list
MISSING_COMPONENTS = utils.get_data_from_file(IN_MISSING_COMPONENTS_FILE_PATH)

for part, keyword in OWN_KEYWORDS_OVERRIDE.items():
    if KANJI_DATA.get(part, None):
        continue

    MISSING_COMPONENTS[part] = keyword

# LOAD vocabulary details from json
KANJI_WORDS = utils.get_data_from_file(IN_KANJI_VOCAB_FILE_PATH)
VOCAB_FURIGANA = utils.get_data_from_file(IN_VOCAB_FURIGANA_FILE_PATH)
VOCAB_MEANING = utils.get_data_from_file(IN_VOCAB_MEANING_FILE_PATH)
WORD_DETAILS = {}

for kanji, words in KANJI_WORDS.items():
    for word in words:
        WORD_DETAILS[word] = [VOCAB_MEANING.get(word, ""), VOCAB_FURIGANA.get(word, [])]

# *********************************
# Functions to dump created dictionaries to json
# *********************************

def dump_created_info_lookups():
    utils.compress_json(
        IN_PHONETIC_COMPONENTS_FILE_PATH,
        OUT_PHONETIC_FILE_PATH
    )

    utils.dump_json(OUT_VOCAB_FILE_PATH, WORD_DETAILS)
    utils.dump_json(OUT_PART_KEYWORD_FILE_PATH, MISSING_COMPONENTS)

    # Compress cumulative use data
    def convert_cum_use_point(point):
        [x, y] = point 
        return [x, round(float(y), 2)]

    cum_use_data = utils.get_data_from_file(IN_CUM_USE_FILE_PATH) 

    for key, value in cum_use_data.items():
        cum_use_data[key] = [convert_cum_use_point(point) for point in value]

    utils.dump_json(OUT_CUM_USE_FILE_PATH, cum_use_data)


def dump_to_main_kanji_info(info):
    utils.dump_json(OUT_KANJI_MAIN_FILE_PATH , info)

def dump_to_extended_kanji_info(info):
    utils.dump_json(OUT_KANJI_EXTENDED_FILE_PATH , info)

# *********************************
# This is what the user should import
# *********************************
KANJI_INFO = {
    "KANJI_DATA": KANJI_DATA,
    "KANJI_LIST": KANJI_LIST,
    "OWN_KEYWORDS_OVERRIDE": OWN_KEYWORDS_OVERRIDE,
    "OWN_PARTS_OVERRIDE": OWN_PARTS_OVERRIDE,
    "MISSING_COMPONENTS": MISSING_COMPONENTS,
    "KANJI_WORDS": KANJI_WORDS,
    "WORD_DETAILS": WORD_DETAILS,
}

