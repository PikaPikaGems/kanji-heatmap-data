#!/usr/bin/env python3
"""
Manual one-off helper for hand-filling meanings of obscure words.

Given a full JMdict-simplified JSON file as its single argument, it looks up the
English glosses (up to DEFINITION_COUNT) for the hardcoded WORDS_TO_FIND set —
rare/uncommon words that the automated meaning sources miss — and prints them as
ready-to-paste `"word": "meaning",` lines for overrides/vocab_meaning.json.

Not part of the build pipeline; edit WORDS_TO_FIND and re-run as needed:
  ./src/uncommon_vocab_meaning.py /path/to/jmdict-eng.json
"""

import sys
from pathlib import Path
from typing import Any
import utils
import sources

DEFINITION_COUNT = 3
WORDS_TO_FIND = set(
    [
        "喉飴",
        "鴻業",
        "朱色",
        "怜悧",
        "噂話",
        "稀に見る",
        "手筈",
        "熙春茶",
        "輪廻",
        "洪大",
        "雰囲気美人",
        "楠",
        "松笠",
        "遺憾無く",
        "黎明",
        "頷き合う",
        "麿",
        "貢ぐ",
        "遮蔽物",
        "中洲",
        "石楠花",
        "三絃",
        "鷹匠",
        "神祐",
        "栞",
        "洵に",
        "莞然",
        "綾子",
        "分水嶺",
        "虞犯",
        "熊之実",
        "束脩",
        "坪庭",
        "皐月",
        "臼歯",
        "諒解",
        "花芯",
        "錯綜",
        "蒲焼",
        "萌黎",
        "登龍門",
        "友誼",
        "頰杖",
        "石臼",
        "詮索",
        "禁錮刑",
        "廻る",
        "庄屋",
        "彙報",
        "凜々",
        "一目瞭然",
        "熙々",
        "孝悌",
        "膨脹",
        "頰",
        "亘る",
        "喉頭",
        "庭燎",
        "糾す",
        "晨り鴨",
        "凜然",
        "澪",
        "亮直",
        "鴻毛",
        "菖蒲",
        "祐筆",
        "蝶々",
        "恭しい",
        "附属",
        "山麓",
    ]
)
word_to_id = {}
id_to_info = {}


def build_global_lookups(words: list[dict[str, Any]]):
    for word_info in words:
        if not word_info["kanji"]:
            continue

        matching_words = [
            kanji_info["text"]
            for kanji_info in word_info["kanji"]
            if kanji_info["text"] in WORDS_TO_FIND
        ]
        if not matching_words:
            continue

        id = word_info["id"]
        id_to_info[id] = word_info

        for word in matching_words:
            word_to_id[word] = id


def get_meaning(word: str) -> str:
    info = id_to_info[word_to_id[word]]
    return sources.jmdict_word_definition(info, word, DEFINITION_COUNT) or "undefined"


def find_all_meanings():
    for word in WORDS_TO_FIND:
        meaning = get_meaning(word)
        print(f'"{word}": "{meaning}",')


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: ./src/uncommon_vocab_meaning.py /path/to/dictionary.json")

    dictionary_path = Path(sys.argv[1])
    dictionary = utils.get_data_from_file(dictionary_path)
    build_global_lookups(dictionary.get("words"))
    find_all_meanings()
