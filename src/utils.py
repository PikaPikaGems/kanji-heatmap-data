import json

INDENT = None
# INDENT = 4
SEPARATORS = (",", ":")
# SEPARATORS = None


def dump_json(file_name, data, indent=INDENT, separators=SEPARATORS):
    with open(file_name, mode="w", encoding="utf-8") as write_file:
        json.dump(
            data, write_file, indent=indent, separators=separators, ensure_ascii=False
        )


def get_data_from_file(file_path):
    result = {}
    with open(file_path, mode="r", encoding="utf-8") as read_file:
        result = json.load(read_file)

    return result


def compress_json(path_in, path_out):
    in_file = get_data_from_file(path_in)
    dump_json(path_out, in_file)


def to_int(str, default_value=None):
    if isinstance(str, (int)):
        return str

    if not str:
        return default_value

    try:
        num = int(str)
        return num
    except:
        return default_value


def is_japanese_only(text):
    """
    "六日",          # True (pure kanji)
    "こんにちは",     # True (pure hiragana)
    "コンニチハ",     # True (pure katakana)
    "東京",          # True (pure kanji)
    "東京こんにちは", # True (kanji + hiragana)
    "東京コンニチハ", # True (kanji + katakana)
    "６日",          # False (has Arabic numeral)
    "東京23区",       # False (has Arabic numerals)
    "東京!",         # False (has punctuation)
    "Japan",         # False (English letters)
    "",             # False (empty string)
    """
    valid_ranges = [
        (0x4E00, 0x9FFF),  # Basic CJK Unified Ideographs
        (0x3400, 0x4DBF),  # CJK Unified Ideographs Extension A
        (0x20000, 0x2A6DF),  # Extension B
        (0x2A700, 0x2B73F),  # Extension C
        (0x2B740, 0x2B81F),  # Extension D
        (0x2B820, 0x2CEAF),  # Extension E
        (0x2CEB0, 0x2EBEF),  # Extension F
        (0x3040, 0x309F),  # Hiragana
        (0x30A0, 0x30FF),  # Katakana
    ]

    if not text:  # Handle empty string
        return False

    for char in text:
        char_code = ord(char)
        is_valid = any(start <= char_code <= end for start, end in valid_ranges)
        if not is_valid:
            return False
    return True
