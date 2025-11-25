#!/usr/bin/env python3

import sys
from pathlib import Path
from typing import Any
import utils


def find_kanji_with_missing_vocab(kanji_extended: dict[str, list[Any]]):
    no_vocab = []
    one_vocab = []
    for kanji, info in kanji_extended.items():
        vocab_list = info[9]
        if not vocab_list:
            no_vocab.append(kanji)
            print(f"{kanji}: none")
            continue
        if len(vocab_list) < 2:
            one_vocab.append(kanji)
            print(f"{kanji}: {vocab_list}")
    print("No vocab:", "".join(no_vocab))
    print("Only one vocab:", "".join(one_vocab))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: ./src/missing_vocab.py /path/to/kanji_extended.json")

    json_path = Path(sys.argv[1])
    kanji_extended = utils.get_data_from_file(json_path)
    find_kanji_with_missing_vocab(kanji_extended)
