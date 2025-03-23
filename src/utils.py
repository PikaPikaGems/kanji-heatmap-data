import json

INDENT = None
#INDENT = 4
SEPARATORS = (',', ':')
#SEPARATORS = None

def dump_json(file_name, data, indent=INDENT, separators=SEPARATORS):
    with open(file_name, mode="w", encoding="utf-8") as write_file:
        json.dump(data, write_file, indent=indent, separators=separators, ensure_ascii=False)


def get_data_from_file(file_path):
    with open(file_path, mode="r", encoding="utf-8") as read_file:
        return json.load(read_file)
    
    return {}

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
    