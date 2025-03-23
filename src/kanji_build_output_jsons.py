#!/usr/bin/env python3

import kanji_extract
import kanji_load

NUMBER_DATA_NOT_FOUND_VAL = -1

kanji_main_reformatted = {}
kanji_extended_reformatted = {}
for kanji in kanji_load.KANJI_INFO["KANJI_LIST"]:

    kanji_info = kanji_load.KANJI_INFO["KANJI_DATA"][kanji]
    
    kanji_main_reformatted[kanji] = [
        kanji_extract.get_keyword(kanji_info, kanji_load.KANJI_INFO["OWN_KEYWORDS_OVERRIDE"]) or "",
        kanji_extract.get_main_on_reading(kanji_info) or "",
        kanji_extract.get_main_kun_reading(kanji_info) or "",
        kanji_extract.get_jlpt(kanji_info) or NUMBER_DATA_NOT_FOUND_VAL,
        kanji_extract.get_ranks(kanji_info, NUMBER_DATA_NOT_FOUND_VAL),
    ]

    kanji_extended_reformatted[kanji] = [
        kanji_extract.get_component_parts(kanji_info, kanji_load.KANJI_INFO["OWN_PARTS_OVERRIDE"]) or [],
        kanji_extract.get_strokes(kanji_info) or NUMBER_DATA_NOT_FOUND_VAL,
        kanji_extract.get_rtk_index(kanji_info) or NUMBER_DATA_NOT_FOUND_VAL,
        kanji_extract.get_wanikani_lvl(kanji_info) or NUMBER_DATA_NOT_FOUND_VAL,
        kanji_extract.get_jouyou(kanji_info) or NUMBER_DATA_NOT_FOUND_VAL,
        kanji_extract.get_all_meanings(kanji_info) or [],
        kanji_extract.get_all_on_readings(kanji_info) or [],
        kanji_extract.get_all_kun_readings(kanji_info) or [],
        kanji_extract.get_semantic_phonetic(kanji_info) or [],
        kanji_load.KANJI_INFO["KANJI_WORDS"].get(kanji, [])
    ]

kanji_load.dump_to_main_kanji_info(kanji_main_reformatted)
kanji_load.dump_to_extended_kanji_info(kanji_extended_reformatted)
kanji_load.dump_created_info_lookups()

print("Done.")