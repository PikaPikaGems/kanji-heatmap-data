#!/usr/bin/env python3

import kanji_extract
import kanji_load

NO_NUM_DATA = -1

kanji_main_reformatted = {}
kanji_extended_reformatted = {}
all_words = set(())

def get_words(kanji):
    original_words = kanji_load.KANJI_INFO["KANJI_WORDS"].get(kanji, [])
    override_words = kanji_load.KANJI_INFO["OWN_VOCAB_OVERRIDE"].get(kanji, [])
    kanji_words = (override_words + original_words)[:2]
    return kanji_words

for kanji in kanji_load.KANJI_INFO["KANJI_DATA"].keys():

    kanji_info = kanji_load.KANJI_INFO["KANJI_DATA"][kanji]

    keyword_overrides = kanji_load.KANJI_INFO["OWN_KEYWORDS_OVERRIDE"]
    kanji_main_reformatted[kanji] = [
        kanji_extract.get_keyword(kanji_info, keyword_overrides) or "",
        kanji_extract.get_main_on_reading(kanji_info) or "",
        kanji_extract.get_main_kun_reading(kanji_info) or "",
        kanji_extract.get_jlpt(kanji_info) or NO_NUM_DATA,
        kanji_extract.get_ranks(kanji_info, NO_NUM_DATA),
    ]

    kanji_words = get_words(kanji)
    all_words.update(kanji_words)

    parts_overrides =  kanji_load.KANJI_INFO["OWN_PARTS_OVERRIDE"]
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

kanji_load.dump_to_main_kanji_info(kanji_main_reformatted)
kanji_load.dump_to_extended_kanji_info(kanji_extended_reformatted)
kanji_load.dump_word_details(all_words)
kanji_load.dump_phonetic_components()
kanji_load.dump_cum_use()
kanji_load.dump_part_keyword_with_overrides()

print("Done.")