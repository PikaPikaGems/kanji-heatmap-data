#!/usr/bin/env python3

from functools import reduce
import kanji_extract
from kanji_load import KANJI_INFO

KANJI_LIST = KANJI_INFO["KANJI_LIST"]
WORD_DETAILS = KANJI_INFO['WORD_DETAILS']
OWN_KEYWORDS_OVERRIDE = KANJI_INFO['OWN_KEYWORDS_OVERRIDE']
KANJI_DATA = KANJI_INFO['KANJI_DATA']
OWN_PARTS_OVERRIDE = KANJI_INFO['OWN_PARTS_OVERRIDE']

def get_max_strokes(acc, iter):
    kanji = iter[1]
    kanji_info = KANJI_DATA[kanji]
    new_acc = kanji_extract.get_strokes(kanji_info)
    if new_acc is not None:
        new_acc = max(new_acc, acc)
        if new_acc > acc:
            print("{:<2} {:<5}".format(kanji, new_acc))
        return new_acc
    return acc

def generic_get_max(retrieve_data):
    def get_max(acc, iter):
        kanji = iter[1]
        kanji_info = KANJI_DATA[kanji]
        items = retrieve_data(kanji_info) or []
        new_acc = max(len(items), acc)

        if new_acc > acc:
            print("{:<4} {:<2} {:<0}".format(kanji, len(items), str(items)[:]))

        return new_acc

    return get_max

def get_reading_stats(get_readings):
    # number of possible readings
    def get_reading_set(acc, kanji):
        kanji_info = KANJI_DATA[kanji]
        items = get_readings(kanji_info) or []
        acc.update(items)
        return acc
    
    
    one_reading = list(
        filter(
            lambda x: len(get_readings(KANJI_DATA[x]) or []) == 1,
            KANJI_LIST
        )
    )
    
    print("---> number of kanjis with one reading", len(one_reading))
    
    
    all_readings = reduce(get_reading_set, KANJI_LIST, set())
    print("---> All possible readings", len(list(all_readings)))
    
    reading_counts = {}
    for kanji in KANJI_LIST:
        readings = get_readings(KANJI_DATA[kanji]) or []
        for reading in readings:
            reading_counts[reading] = reading_counts.get(reading, 0) + 1
    
    reading_counts_array = [ 
        { 'reading': reading , 'count': count } for reading, count in reading_counts.items()
    ]
    
    unique_reading_count = len(reading_counts_array)
    print("---> unique_readings", unique_reading_count)
    
    multiple_on_count = len(list(filter(lambda x: x['count'] > 1, reading_counts_array)))
    single_on_count = len(list(filter(lambda x: x['count'] <= 1, reading_counts_array)))
    
    print("---> reading with multiple kanjis:", multiple_on_count) 
    print("---> reading with single kanji:", single_on_count) 
    
    def sort_func(item):
        return item['count']
    
    # An array of items { kanji, count, fraction, cum_use } now sorted by frequency, most frequent at the top 
    reading_counts_array.sort(key=sort_func, reverse=True)
    
    
    # Top X readings
    top_x = 10
    # mapping count of reading
    print(f"---- Top {top_x} Readings ---")
    print("{:<10} {:<15}".format('Reading','Count'))
    for item in reading_counts_array[:top_x]:
        print("{:<10} {:<15}".format(item['count'], item['reading']))


iter = [x for x in enumerate(KANJI_LIST)]
max_strokes = reduce(get_max_strokes, iter, 0)
print("---> max strokes count:", max_strokes)
# 29

def get_component_parts(kanji_info):
    return kanji_extract.get_component_parts(kanji_info, OWN_PARTS_OVERRIDE)


max_deps = reduce(generic_get_max(get_component_parts), iter, 0)
print("---> max dependencies count:", max_deps)
# 8

max_on_readings = reduce(generic_get_max(kanji_extract.get_all_on_readings), iter, 0)

print("---> max onyomi count:", max_on_readings)
# 10

max_kun_readings = reduce(generic_get_max(kanji_extract.get_all_kun_readings), iter, 0)
print("---> max kun count:", max_kun_readings)
# 21

max_meaning = reduce(generic_get_max(kanji_extract.get_all_meanings), iter, 0)

print("---> max meaning count:", max_meaning)
# 16

print("---> Number of Words:", len(WORD_DETAILS.keys()))
# ---> word count 4453


# Verify if keyword is unique
keyword_list = [
    kanji_extract.get_keyword(KANJI_DATA[kanji], OWN_KEYWORDS_OVERRIDE) for kanji in KANJI_LIST
]

# KANJI_LIST WORD_DETAILS OWN_KEYWORDS_OVERRIDE KANJI_DATA OWN_PARTS_OVERRIDE
print("---> Number of Kanjis:", len(KANJI_LIST))
# 2427



print("---> Unique Keywords:", len(set(keyword_list)))
# Before the override -> Unique Keywords 2423

no_keys = list(
    filter(
        lambda x: kanji_extract.get_keyword(KANJI_DATA[x], OWN_KEYWORDS_OVERRIDE) is None,
        KANJI_LIST
    )
)

print("---> No keywords:", no_keys)
# Before the overrides -> No keywords: ['呟', '睨', '頷'] 

print("..........")
print("ONYOMI")
print("..........")
get_reading_stats(kanji_extract.get_all_on_readings)

print("..........")
print("KUNYOMI")
print("..........")
get_reading_stats(kanji_extract.get_all_kun_readings)

