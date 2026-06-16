#!/bin/bash
# Run ./generate.sh for each (textbook, v3) source combination, sending each
# build's output to generate-log-<VERSION_NAME>.txt for side-by-side inspection.
#
# Combos: textbook = full vs -min, v3 = v3 vs v3b.
# NOTE: each run overwrites the override/output files in place, so the working
# tree reflects whichever combo ran LAST. The point of comparison here is the
# logs, which are kept per-combo.
set -e

run_combo() {
    local textbook="$1" v3="$2" name="$3"
    echo ">>> building $name (TEXTBOOK_SUBDIR=$textbook, V3_SUBDIR=$v3)"
    TEXTBOOK_SUBDIR="$textbook" V3_SUBDIR="$v3" \
        GENERATE_LOG="generate-log-$name.txt" ./generate.sh
    echo "<<< done $name -> generate-log-$name.txt"
}

run_combo "kanji-textbook-words"     "v3"  "textbook-v3"
run_combo "kanji-textbook-words"     "v3b" "textbook-v3b"
run_combo "kanji-textbook-words-min" "v3"  "textbook-min-v3"
run_combo "kanji-textbook-words-min" "v3b" "textbook-min-v3b"

echo "All four builds complete."
