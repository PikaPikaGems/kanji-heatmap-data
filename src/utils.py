import json

from sources import resolve_path

INDENT = None
# INDENT = 4
SEPARATORS = (",", ":")
# SEPARATORS = None


def dump_json(file_name, data, indent=INDENT, separators=SEPARATORS):
    # Paths are resolved relative to the project root so callers work from any cwd;
    # absolute paths (e.g. a CLI argument) pass through resolve_path unchanged.
    with open(resolve_path(file_name), mode="w", encoding="utf-8") as write_file:
        json.dump(
            data, write_file, indent=indent, separators=separators, ensure_ascii=False
        )


def get_data_from_file(file_path):
    result = {}
    with open(resolve_path(file_path), mode="r", encoding="utf-8") as read_file:
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
    except (ValueError, TypeError):
        return default_value


