#!/bin/bash
set -e

# Send all output (stdout + stderr) to a log file instead of the terminal.
# To also watch it live, swap the line below for: exec > >(tee generate-log.txt) 2>&1
exec > generate-log.txt 2>&1

# Run a build step inside a clearly delimited banner so each script's output is
# easy to locate in generate-log.txt (START header before it, END footer after).
run() {
    echo ""
    echo "------------------------------------------------------------------"
    echo ">>> START  $*"
    echo "------------------------------------------------------------------"
    "$@"
    echo "------------------------------------------------------------------"
    echo "<<< END    $*"
    echo "------------------------------------------------------------------"
}

run python3 src/build_filtered_kanji_json.py
run python3 src/build_representative_study_word_algo.py
run python3 src/algorithmic_kanji_vocab_overrides.py
run python3 src/generate_furigana_algo.py
run python3 src/algorithmic_overrides_keywords.py
run python3 src/build_similar_kanjis.py
run python3 src/kanji_build_output_jsons.py

cp ./input/filtered_kanji.json ./output/filtered_kanji.json

run ./src/kanji_inspect.py

# NOTE: src/fetch_missing_vocab_meanings.py is intentionally NOT run here. It makes
# live network calls (Jotoba/Jisho) to fill overrides/vocab_meaning-external-dict.json,
# which would make this build non-deterministic. That cache is committed; run the
# script by hand only when new words need external meanings.
