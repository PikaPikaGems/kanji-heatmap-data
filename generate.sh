#!/bin/bash
set -e

mkdir -p logs

# Send all output (stdout + stderr) to a log file instead of the terminal.
# Log file defaults to logs/generate-log.txt; override with the GENERATE_LOG env var
# (e.g. batch comparison runs that build several source combos).
# To also watch it live, swap the line below for: exec > >(tee "$LOG_FILE") 2>&1
LOG_FILE="${GENERATE_LOG:-logs/generate-log.txt}"
exec > "$LOG_FILE" 2>&1

# Run a build step inside a clearly delimited banner so each script's output is
# easy to locate in the generate log (START header before it, END footer after).
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

# Like run(), but the step's own (verbose) output goes to a dedicated log file so
# the main generate log stays short — only the START/END banner and a pointer to the
# per-step log remain in the main log.
run_to() {
    local step_log="$1"; shift
    echo ""
    echo "------------------------------------------------------------------"
    echo ">>> START  $*   (output → $step_log)"
    echo "------------------------------------------------------------------"
    "$@" > "$step_log" 2>&1
    echo "<<< END    $*   (see $step_log)"
    echo "------------------------------------------------------------------"
}

run python3 src/build_filtered_kanji_json.py
run_to logs/study-words-algo-log.txt python3 src/japanese_study_words_algo.py
run_to logs/sample-vocabs-algo.txt python3 src/kanji_vocab_algo.py
run python3 src/keywords_algo.py
run python3 src/build_similar_kanji.py
run python3 src/kanji_build_output_jsons.py

cp ./input/filtered_kanji.json ./output/filtered_kanji.json

run ./src/kanji_inspect.py
