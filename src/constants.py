outfile_component_keyword = "component_keyword.json"
outfile_cum_use = "cum_use.json"
outfile_kanji_extended = "kanji_extended.json"
outfile_kanji_main = "kanji_main.json"
outfile_phonetic = "phonetic.json"
outfile_vocab_meaning = "vocab_meaning.json"
outfile_vocab_furigana = "vocab_furigana.json"
outfile_kanji_representative_words = "kanji_representative_words.json"
outfile_similar_kanjis = "similar-kanjis.json"
outfile_extra_kanji_keyword = "extra_kanji_keyword.json"
outfile_kanji_list = "filtered_kanji.json"

# Index of the sample-words list within each output/kanji_extended.json row (that
# file's rows are positional lists). Shared so the build, build_helpers.furigana_stats,
# and missing_vocab all refer to the field by name instead of a bare `9`.
kanji_extended_words_index = 9

dir_raw = "raw"
dir_in = "input"
# Script-written pipeline intermediates (git-ignored). build_filtered_kanji_json.py
# writes filtered_kanji.json / all_kanjis.json here; downstream steps read them.
# Kept out of input/ so input/ stays purely read-only third-party data.
dir_intermediate = "intermediate"
dir_out = "output"
dir_releases = "releases"
dir_overrides = "overrides"
dir_debug = "debug"

archive_file = "kanji-heatmap-data.tar.gz"

output_files = [
    outfile_component_keyword,
    outfile_cum_use,
    outfile_kanji_extended,
    outfile_kanji_main,
    outfile_phonetic,
    outfile_vocab_meaning,
    outfile_vocab_furigana,
    outfile_kanji_representative_words,
    outfile_similar_kanjis,
    outfile_extra_kanji_keyword,
    outfile_kanji_list,
]
