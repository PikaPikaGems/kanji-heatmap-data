import utils

def get_all_generic(all_, all_source_keys):

    def dig_main(source_key):
        main = all_.get(source_key, {}).get('main', None)
        if main is None:
            return None

        return main.strip().lower()
    
    def dig_others(source_key):
        raw_others = all_.get(source_key, {}).get('others', [])
        return [word.strip().lower() for word in raw_others]
    
    item_set = set(())
    for source_key in all_source_keys:
        main = dig_main(source_key)
        
        if main is not None:
            item_set.update([main])
        others = dig_others(source_key)

        item_set.update(others)
    
    item_set.discard('')

    item_list = list(item_set)

    if len(item_list) == 0:
        return None
    return item_list

def get_component_parts(kanji_info, overrides = {}):

    deps = kanji_info.get('componentDependencies', {}).get('topoKanji', [])
    return overrides.get(kanji_info['kanji'], None) or deps

def get_keyword(kanji_info, overrides):
    all_ = kanji_info.get('meanings', {})
    def dig(source_key):
        return all_.get(source_key, {}).get('main', None)

    keyword = dig('kanjiKeys') \
        or dig('rtk5100') \
        or dig('davidluzgouveiaJlpt') \
        or dig('shirabeJishou') \
        or dig('waniKani')
    
    override = overrides.get(kanji_info["kanji"], None)
    if override:
        keyword = override

    if keyword is None:
        print("No keyword:", kanji_info["kanji"])
        return None

    return keyword.strip().lower()

def get_all_meanings(kanji_info):
    all_source_keys = [
        'kanjiKeys',
        'rtk5100',
        'davidluzgouveiaJlpt',
        'shirabeJishou',
        'waniKani'
    ]
    all_ = kanji_info.get('meanings', {})
    return get_all_generic(all_, all_source_keys)

def get_main_on_reading(kanji_info):
    all_ = kanji_info.get('readings', {}).get('onyomi', {})
    def dig(source_key):
        return (all_.get(source_key, {}) or {}).get('main', None)

    return dig('davidluzgouveiaJlpt') or dig('waniKani') or dig('kanjiApi')

def get_all_on_readings(kanji_info):
    all_source_keys = [
        'davidluzgouveiaJlpt',
        'waniKani',
        'kanjiApi'
    ]
    all_ = kanji_info.get('readings', {}).get('onyomi', {})
    return get_all_generic(all_, all_source_keys)

def get_main_kun_reading(kanji_info):
    all_ = kanji_info.get('readings', {}).get('kunyomi', {})  
    def dig(source_key):
        return (all_.get(source_key, {}) or {}).get('main', None)

    return dig('davidluzgouveiaJlpt') or dig('waniKani')or dig('kanjiApi')

def get_all_kun_readings(kanji_info):
    all_source_keys = [
        'davidluzgouveiaJlpt',
        'waniKani',
        'kanjiApi'
    ]
    all_ = kanji_info.get('readings', {}).get('kunyomi', {})
    return get_all_generic(all_, all_source_keys)

def get_jlpt(kanji_info):
    all_ = kanji_info.get('jlpt', {})
    def dig(source_key):
        return all_.get(source_key, None)
    
    a = dig('shirabeJishou') 
    b = dig('kanjiSchool')
    c = dig('davidluzgouveiaJlpt')
    r = a or b or c
    # 416 Kanji do not match

    return r

def get_jouyou(kanji_info):
    all_ = kanji_info.get('jouyouGrade', {})
    def dig(source_key):
        return all_.get(source_key, None)

    # KanjiSchool is more accurate
    # see: https://github.com/PikaPikaGems/kanji-data/issues/5
    a = dig('kanjiSchool')
    b = dig('davidluzgouveiaJlpt')
    c = dig('kanjiApi')
    r = a or b or c

    # For the inconsistent Jouyou Grade between kanjiSchool and davidluzgouveiaJlpt 
    # (found 56 discrepancies), kanjiSchool is more accurate when verified against
    #  https://en.wikipedia.org/wiki/List_of_jōyō_kanji. 
    # Note that grades are from 1-6 for elementary school,
    # then kanjiSchool uses 9 while davidluzgouveiaJlpt uses 8 for secondary school.
    # When comparing kanjiSchool and scriptin kanjidic2-en-3.6.1.json, 
    # there are 55 kanji where kanjiSchool is 0 but kanjidic2 is 9:
    # kanjidic2 is from https://github.com/scriptin/jmdict-simplified

    if a == 9 and b == 8:
        return 9
    
    if a == 0 and b == 8:
        return 9
    
    if r == 8:
        return 9 

    # Previously before new logic:: 1437 Kanji do not match
    # With the new logic 56 kanji do not match

    return r

def get_strokes(kanji_info):
    all_ = kanji_info.get('strokes', {})
    def dig(source_key):
        return all_.get(source_key, None)

    a = dig('kanjiSchool')
    b = dig('davidluzgouveiaJlpt')
    c = dig('kanjiApi')
    # d = dig('topoKanji')
    r = a or b or c

    # There are 48 discrepancies in stroke count between topoKanji vs kanjiSchool 
    # or davidluzgouveiaJlpt (latter two have the same count). 
    # By manually verifying the stroke count with the help of https://jisho.org,
    # topoKanji has been found to be consistently incorrect. 
    # see: https://github.com/PikaPikaGems/kanji-data/issues/5

    # Found incorrect stroke count for davidluzgouveiaJlpt which indicates 稽 has stroke count of 16 when it should only have 15.
    #  Discovered when comparing it against scriptin's kanjidic2-en-3.6.1.json.
    # See also https://github.com/PikaPikaGems/kanji-data/issues/8

    if kanji_info["kanji"] == "稽":
        return 15
    
    # previous logic: 96 Kanji do not match
    # Now: Everything matches
    return r

def get_rtk_index(kanji_info):
    all_ = kanji_info.get('rtkIndex', {})
    def dig(source_key):
        return all_.get(source_key, None)
    
    return utils.to_int(dig('rtk5100'))

def get_wanikani_lvl(kanji_info):
    return kanji_info.get('waniKani', {}).get('level', None)


def get_semantic_phonetic(kanji_info):
    phonetic = kanji_info.get("semanticPhonetic", {}).get('moeUsagi', None)
    return phonetic


def get_ranks(kanji_info, NUMBER_DATA_NOT_FOUND_VAL):
    all_ = kanji_info.get('frequency', {})
    def dig_1224(source_key):
        rank = all_.get(source_key, {}).get('rank1224', None)
        return utils.to_int(rank)

    all_scriptin = all_.get('scriptin', {}).get('mostRecent', {})
    def dig_scriptin(source_key, rank_type_key = 'charRank1224'):
        rank = all_scriptin.get(source_key, {}).get(rank_type_key, None)
        return utils.to_int(rank)

    all_ultimate = all_.get('ultimate', {})
    def dig_ultimate(source_key):
        rank = all_ultimate.get(source_key, None)
        return utils.to_int(rank)

    rank_aozora_char = dig_scriptin('aozora') or NUMBER_DATA_NOT_FOUND_VAL
    rank_aozora_doc = dig_scriptin('aozora', 'docRank1224') or NUMBER_DATA_NOT_FOUND_VAL
    rank_wikipedia_char = dig_scriptin('wikipedia') or NUMBER_DATA_NOT_FOUND_VAL
    rank_wikipedia_doc = dig_scriptin('wikipedia', 'docRank1224') or NUMBER_DATA_NOT_FOUND_VAL
    rank_online_news_char = dig_scriptin('news') or NUMBER_DATA_NOT_FOUND_VAL
    rank_online_news_doc = dig_scriptin('news', 'docRank1224') or NUMBER_DATA_NOT_FOUND_VAL

    rank_twitter_raw = all_.get('scriptin', {}).get('year2015', {}).get("twitter", {}).get("rank1224", None)
    rank_twitter = utils.to_int(rank_twitter_raw) or NUMBER_DATA_NOT_FOUND_VAL

    rank_netflix = dig_1224('ohTalkWhoNetflix') or NUMBER_DATA_NOT_FOUND_VAL
    rank_novels_5100 = dig_1224('rtk5100') or NUMBER_DATA_NOT_FOUND_VAL
    rank_drama_subtitles = dig_1224('chriskempsonSubtitles') or NUMBER_DATA_NOT_FOUND_VAL

    rank_google = dig_ultimate("google") or NUMBER_DATA_NOT_FOUND_VAL
    rank_kuf = dig_ultimate("kuf") or NUMBER_DATA_NOT_FOUND_VAL
    rank_mcd = dig_ultimate("mcd") or NUMBER_DATA_NOT_FOUND_VAL
    rank_bunka = dig_ultimate("bunka") or NUMBER_DATA_NOT_FOUND_VAL
    rank_kd = dig_ultimate("kd") or NUMBER_DATA_NOT_FOUND_VAL
    rank_wkfr = dig_ultimate("wkfr") or NUMBER_DATA_NOT_FOUND_VAL

    rank_jisho = dig_ultimate("jisho") or NUMBER_DATA_NOT_FOUND_VAL

    # rank_newspapers_1 = all_.get('davidluzgouveiaJlpt', None) or None
    # rank_newspapers_2 = all_.get('kanjiSchool', None) or None
    # a = rank_jisho
    # b = rank_newspapers_1
    # c = rank_newspapers_2 
    # r = a or b or c
    # only 6 kanji do not match
    # 1 飛 r: 619 580 580
    # 2 弁 r: 2077 619 619
    # 3 裁 r: 269 297 297
    # 4 逮 r: 1423 766 766
    # 5 殊 r: 1352 1361 1361
    # 6 緻 r: 2500 2460 None

    freqs = [
        rank_netflix,
        rank_twitter,
        
        rank_google,
        rank_wkfr,

        rank_wikipedia_char,
        rank_wikipedia_doc,
    
        rank_aozora_char,
        rank_aozora_doc,
        
        rank_online_news_char,
        rank_online_news_doc,
        
        rank_novels_5100,
        rank_drama_subtitles,
        
        rank_kuf,
        rank_mcd,
        rank_bunka,

        rank_kd,
        rank_jisho,
    ]

    has_ranks = list(filter(lambda x: x != -1, freqs))

    if len(has_ranks) == 0:
        # only 々 has no rank
        print("no_rank", kanji_info["kanji"], has_ranks)

    return freqs 
