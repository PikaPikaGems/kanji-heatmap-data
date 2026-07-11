#!/bin/bash
set -e

# Send all output (stdout + stderr) to a log file instead of the terminal.
# Log file defaults to generate-log.txt; override with the GENERATE_LOG env var
# (e.g. batch comparison runs that build several source combos).
# To also watch it live, swap the line below for: exec > >(tee "$LOG_FILE") 2>&1
LOG_FILE="${GENERATE_LOG:-generate-log.txt}"
exec > "$LOG_FILE" 2>&1

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
run python3 src/kanji_build_output_jsons.py

cp ./input/filtered_kanji.json ./output/filtered_kanji.json

run ./src/kanji_inspect.py
