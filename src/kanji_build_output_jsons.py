#!/usr/bin/env python3

import kanji_extract
import kanji_load

automated_all_words = kanji_load.load_automated_kanji_vocab()
override_all_words = kanji_load.load_vocab_override()

def get_words(kanji):
    automated_words = automated_all_words.get(kanji, [])
    override_words = override_all_words.get(kanji, [])
    kanji_words = (override_words + automated_words)[:2]
    return kanji_words

# ***********************
# Begin extracting kanji information
# ***********************

NO_NUM_DATA = -1

kanji_main_reformatted = {}
kanji_extended_reformatted = {}
all_words = set(())

kanji_data = kanji_load.load_aggregated_kanji_data()
keyword_overrides = kanji_load.load_keywords_override()
parts_overrides =  kanji_load.load_decomposition_override()

for kanji in kanji_data.keys():

    kanji_info = kanji_data[kanji]

    kanji_main_reformatted[kanji] = [
        kanji_extract.get_keyword(kanji_info, keyword_overrides) or "",
        kanji_extract.get_main_on_reading(kanji_info) or "",
        kanji_extract.get_main_kun_reading(kanji_info) or "",
        kanji_extract.get_jlpt(kanji_info) or NO_NUM_DATA,
        kanji_extract.get_ranks(kanji_info, NO_NUM_DATA),
    ]

    kanji_words = get_words(kanji)
    all_words.update(kanji_words)

    kanji_extended_reformatted[kanji] = [
        kanji_extract.get_component_parts(kanji_info, parts_overrides),
        kanji_extract.get_strokes(kanji_info) or NO_NUM_DATA,
        kanji_extract.get_rtk_index(kanji_info) or NO_NUM_DATA,
        kanji_extract.get_wanikani_lvl(kanji_info) or NO_NUM_DATA,
        kanji_extract.get_jouyou(kanji_info) or NO_NUM_DATA,
        kanji_extract.get_all_meanings(kanji_info) or [],
        kanji_extract.get_all_on_readings(kanji_info) or [],
        kanji_extract.get_all_kun_readings(kanji_info) or [],
        kanji_extract.get_semantic_phonetic(kanji_info) or [],
        kanji_words
    ]

# ***********************
# Dump extracted kanji information
# ***********************
kanji_load.dump_to_main_kanji_info(kanji_main_reformatted)
kanji_load.dump_to_extended_kanji_info(kanji_extended_reformatted)
kanji_load.dump_word_details(all_words)

# ***********************
# Dump other reformatted data
# ***********************
kanji_load.dump_phonetic_components()
kanji_load.dump_cum_use()
kanji_load.dump_part_keyword_with_overrides()

print("Done.")