#!/usr/bin/env python3

import kanji_extract
import kanji_load
import os
import constants as const
import utils
import japanese
from build_helpers import get_words, furigana_stats
from keyword_sources import load_raw_keyword_sources, raw_keyword, base_keyword

NO_NUM_DATA = -1


def word_kanji_keywords(kanji_extended, representative_words, shipped):
    """Keywords for non-shipped kanji that appear INSIDE sample / study words (not as
    component parts — those are handled by component_keyword). Sourced from the raw
    keyword files, falling back to the merged_kanji base keyword. Lets the frontend
    label such characters even though they have no output/kanji_main.json entry.
    Kanji with no keyword in any source are omitted. Written to output/extra_kanji_keyword.json."""
    referenced = set()
    for info in kanji_extended.values():
        for word in info[9]:        # sample words
            referenced.update(ch for ch in word if japanese.is_kanji_char(ch))
    for entry in representative_words.values():  # study words
        if entry:
            referenced.update(ch for ch in entry[0] if japanese.is_kanji_char(ch))

    kj, kw, kk = load_raw_keyword_sources()
    merged = kanji_load.load_aggregated_kanji_data()
    result = {}
    for kanji in sorted(referenced):  # sorted so the output's key order is stable
        if kanji in shipped:
            continue
        keyword = raw_keyword(kanji, kj, kw, kk) or base_keyword(kanji, merged)
        if keyword:
            result[kanji] = keyword
    return result


def assert_unique_keywords(kanji_main):
    """Every kanji's keyword (kanji_main[kanji][0]) must be unique — two kanji sharing
    a keyword makes them indistinguishable in the UI. The keyword algo reserves names
    to avoid collisions, but a manual overrides/keywords.json entry can reintroduce one,
    so fail loudly here (fix the clash in overrides/keywords.json). Empty keywords are
    ignored (a separate concern)."""
    keyword_to_kanjis = {}
    for kanji, info in kanji_main.items():
        keyword = info[0]
        if keyword:
            keyword_to_kanjis.setdefault(keyword, []).append(kanji)
    duplicates = {kw: ks for kw, ks in keyword_to_kanjis.items() if len(ks) > 1}
    if duplicates:
        raise ValueError(
            "Duplicate kanji keywords — each keyword must map to exactly one kanji "
            "(fix the clash in overrides/keywords.json): "
            + ", ".join(f"{kw!r} → {''.join(ks)}" for kw, ks in duplicates.items())
        )


def main():
    automated_all_words = kanji_load.load_automated_kanji_vocab()
    override_all_algo_words = kanji_load.load_vocab_algo_override()
    override_all_words = kanji_load.load_vocab_override()

    # ***********************
    # Begin extracting kanji information
    # ***********************
    kanji_main_reformatted = {}
    kanji_extended_reformatted = {}
    all_words = set(())

    kanji_data = kanji_load.load_filtered_kanji_data()
    keyword_overrides = kanji_load.load_keywords_override()
    parts_overrides = kanji_load.load_decomposition_override()
    jiten_frequency = kanji_load.load_jiten_frequency()
    jpdb_frequency = kanji_load.load_jpdb_frequency()
    kklc_order = kanji_load.load_kklc_order()

    for kanji in kanji_data.keys():

        kanji_info = kanji_data[kanji]

        kanji_main_reformatted[kanji] = [
            kanji_extract.get_keyword(kanji_info, keyword_overrides) or "",
            kanji_extract.get_main_on_reading(kanji_info) or "",
            kanji_extract.get_main_kun_reading(kanji_info) or "",
            kanji_extract.get_jlpt(kanji_info) or NO_NUM_DATA,
            kanji_extract.get_ranks(kanji_info, NO_NUM_DATA, jiten_frequency, jpdb_frequency),
        ]

        kanji_words = get_words(kanji, override_all_words, override_all_algo_words, automated_all_words)
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
            kanji_words,
            kanji_extract.get_kklc_index(kanji_info, kklc_order, NO_NUM_DATA),
        ]

    # ***********************
    # Dump extracted information
    # ***********************
    # Loud gates before shipping: keyword uniqueness here; study-word uniqueness and
    # reading/gloss completeness inside dump_kanji_representative_words below.
    assert_unique_keywords(kanji_main_reformatted)
    kanji_load.dump_to_main_kanji_info(kanji_main_reformatted)
    kanji_load.dump_to_extended_kanji_info(kanji_extended_reformatted)
    kanji_load.dump_kanji_representative_words()

    # Sort for a deterministic, stable key order in the output JSONs (all_words is a
    # set, whose per-run iteration order would otherwise reshuffle the file each build).
    all_words = sorted(all_words)
    print("All sample words count:", len(all_words))

    kanji_load.dump_all_vocab_furigana(all_words)
    kanji_load.dump_all_vocab_meanings(all_words)

    vocab_furigana = utils.get_data_from_file(os.path.join(const.dir_out, const.outfile_vocab_furigana))
    furigana_stats(kanji_extended_reformatted, kanji_data, vocab_furigana)

    # ***********************
    # Dump other reformatted data
    # ***********************
    kanji_load.dump_phonetic_components()
    kanji_load.dump_cum_use()

    kanji_load.dump_part_keyword_with_overrides(kanji_data)

    representative_words = utils.get_data_from_file(
        os.path.join(const.dir_out, const.outfile_kanji_representative_words)
    )
    extra_keywords = word_kanji_keywords(
        kanji_extended_reformatted, representative_words, set(kanji_data)
    )
    kanji_load.dump_extra_kanji_keywords(extra_keywords)

    print("Done.")


if __name__ == "__main__":
    main()
