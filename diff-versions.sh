#!/bin/bash
# Build overrides/japanese_study_words-algo.json under two source combos and diff
# them with src/diff_study_words_versions.py.
#
#   versionA: v3  + kanji-textbook-words      (full)
#   versionB: v3b + kanji-textbook-words-min  (trimmed)
#
# Each combo rebuilds the file in place, so this backs up your current
# overrides/japanese_study_words-algo.json first and restores it at the end —
# the working tree is left untouched. Extra args are forwarded to the diff script
# (e.g. --word-only, --tier-only).
set -e

OUT="overrides/japanese_study_words-algo.json"
A="/tmp/jsw-versionA.json"
B="/tmp/jsw-versionB.json"
BACKUP="$(mktemp)"

cp "$OUT" "$BACKUP"
trap 'cp "$BACKUP" "$OUT"; rm -f "$BACKUP"' EXIT

echo ">>> building versionA (v3 + kanji-textbook-words)" >&2
V3_SUBDIR=v3 TEXTBOOK_SUBDIR=kanji-textbook-words \
    python3 src/build_representative_study_word_algo.py > /dev/null
cp "$OUT" "$A"

echo ">>> building versionB (v3b + kanji-textbook-words-min)" >&2
V3_SUBDIR=v3b TEXTBOOK_SUBDIR=kanji-textbook-words-min \
    python3 src/build_representative_study_word_algo.py > /dev/null
cp "$OUT" "$B"

echo ">>> diffing" >&2
python3 src/diff_study_words_versions.py "$A" "$B" "$@"
