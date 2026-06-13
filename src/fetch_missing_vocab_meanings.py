#!/usr/bin/env python3
"""
Fills in missing meanings for algo-selected vocab words.

MANUAL TOOL — not part of generate.sh. It makes live network calls (Jotoba/Jisho),
so it is kept out of the deterministic build. Its output
(overrides/vocab_meaning-external-dict.json) is committed and consumed by the build;
run this by hand only when new words need external meanings.

Resolution order for each missing word:
  1. japanese_study_words-algo.json        (in-memory, no network)
  2. raw/ai-generated/vocab-meanings-ai.json  (in-memory, no network)
  3. Jotoba API  (POST /api/search/words)
  4. Jisho API   (GET  /api/v1/search/words?keyword="word")

Saves results to overrides/vocab_meaning-external-dict.json.
Run from project root: python3 src/fetch_missing_vocab_meanings.py
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request

from sources import resolve_path, load_json, ai_meaning_map, jsw_meaning_map

DEFINITION_COUNT = 3
OUT_PATH = "overrides/vocab_meaning-external-dict.json"
JMDICT_CACHE_PATH = "input/jmdict-vocab-meaning.json"

def save(path, data):
    with open(resolve_path(path), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# ── API helpers ────────────────────────────────────────────────────────────────

def _http_get(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def _http_post(url, payload, timeout=10):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def lookup_jotoba(word):
    try:
        body = _http_post(
            "https://jotoba.de/api/search/words",
            {"query": word, "language": "English", "no_english": False},
        )
        for entry in body.get("words") or []:
            reading_info = entry.get("reading", {})
            entry_word = reading_info.get("kanji") or reading_info.get("kana", "")
            if entry_word != word:
                continue
            for sense in entry.get("senses") or []:
                glosses = sense.get("glosses") or []
                if glosses:
                    return ", ".join(glosses[:DEFINITION_COUNT])
    except Exception:
        pass
    return None


def lookup_jisho(word):
    try:
        url = "https://jisho.org/api/v1/search/words?keyword=" + urllib.parse.quote(
            f'"{word}"'
        )
        body = _http_get(url)
        for entry in body.get("data") or []:
            japanese = entry.get("japanese") or []
            if not any(j.get("word") == word for j in japanese):
                continue
            for sense in entry.get("senses") or []:
                defs = sense.get("english_definitions") or []
                if defs:
                    return ", ".join(defs[:DEFINITION_COUNT])
    except Exception:
        pass
    return None


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    kanji_vocab_algo = load_json("overrides/kanji_vocab-algo.json")
    vocab_meaning_algo = load_json("overrides/vocab_meaning-algo.json")
    existing_meanings = load_json("input/vocab_meaning.json")
    jmdict_cache = load_json(JMDICT_CACHE_PATH)
    external_dict = load_json(OUT_PATH)
    jsw_algo = load_json("overrides/japanese_study_words-algo.json")
    ai_meanings_raw = load_json("raw/ai-generated/vocab-meanings-ai.json")

    jsw_word_meanings = jsw_meaning_map(jsw_algo)
    ai_meanings = ai_meaning_map(ai_meanings_raw)

    algo_words = {w for words in kanji_vocab_algo.values() for w in words}
    missing = [
        w for w in sorted(algo_words)
        if w not in vocab_meaning_algo
        and w not in existing_meanings
        and w not in jmdict_cache
        and w not in external_dict
        and w not in ai_meanings
    ]

    print(f"Words missing meaning: {len(missing)}")

    found_jsw = found_jotoba = found_jisho = still_missing = 0
    processed = 0
    SAVE_INTERVAL = 20

    for word in missing:
        # 1. japanese_study_words-algo
        if word in jsw_word_meanings:
            external_dict[word] = jsw_word_meanings[word]
            print(f"[jsw]    {word}: {jsw_word_meanings[word]}")
            found_jsw += 1
        else:
            time.sleep(0.3)

            # 2. Jotoba
            meaning = lookup_jotoba(word)
            if meaning:
                external_dict[word] = meaning
                print(f"[jotoba] {word}: {meaning}")
                found_jotoba += 1
            else:
                # 3. Jisho
                meaning = lookup_jisho(word)
                if meaning:
                    external_dict[word] = meaning
                    print(f"[jisho]  {word}: {meaning}")
                    found_jisho += 1
                else:
                    print(f"[none]   {word}")
                    still_missing += 1

        processed += 1
        if processed % SAVE_INTERVAL == 0:
            save(OUT_PATH, external_dict)
            print(f"  [saved {processed}/{len(missing)}]")

    save(OUT_PATH, external_dict)

    print()
    print(f"Results:")
    print(f"  jsw_algo: {found_jsw}")
    print(f"  Jotoba:   {found_jotoba}")
    print(f"  Jisho:    {found_jisho}")
    print(f"  Missing:  {still_missing}")
    print(f"Saved to {OUT_PATH}")


if __name__ == "__main__":
    main()
