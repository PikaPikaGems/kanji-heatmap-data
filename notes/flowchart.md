# Kanji-heatmap-data build flowcharts

Visual map of how `src/*.py` turns raw sources into the shipped `output/` JSONs.
This is a snapshot of the current pipeline.

Legend:
- 🟩 raw input (hand-authored or third-party, in `raw/` or `input/`)
- 🟦 intermediate override (`overrides/`)
- 🟧 final shipped artifact (`output/`)
- ⬜ script

`input/` is externally maintained and git-ignored; the build only reads from it.

---

## 1. The orchestrated pipeline (`generate.sh`, top to bottom)

The full build is offline and deterministic. Each step writes files the next reads.

```mermaid
flowchart TD
    A[build_filtered_kanji_json.py] --> B[build_representative_study_word_algo.py]
    B --> C[algorithmic_kanji_vocab_overrides.py]
    C --> D[generate_furigana_algo.py]
    D --> E[algorithmic_overrides_keywords.py]
    E --> G[kanji_build_output_jsons.py]
    G --> H[kanji_inspect.py — stats only]

    A -.writes.-> a1[(input/filtered_kanji.json
    input/all_kanjis.json)]
    B -.writes.-> b1[(overrides/japanese_study_words-algo.json)]
    C -.writes.-> c1[(overrides/kanji_vocab-algo.json
    vocab_meaning-algo.json
    vocab_reading-algo.json
    vocab-with-no-furigana.json)]
    D -.writes.-> d1[(overrides/vocab_furigana-algo.json)]
    E -.writes.-> e1[(overrides/keywords-algo.json
    debug/debug-keywords.json)]
    G -.writes.-> g1[(output/kanji_main.json, kanji_extended.json,
    component_keyword.json, extra_kanji_keyword.json, phonetic.json,
    cum_use.json, vocab_meaning.json, vocab_furigana.json,
    kanji_representative_words.json)]
```

`src/fetch_missing_vocab_meanings.py` is a separate MANUAL tool (it makes live network
calls). It is not part of `generate.sh`; see §5.

`output/similar-kanjis.json` is a static artifact: its generator
(`build_similar_kanjis.py`) has been removed from the repo, but the file still ships
in the release tarball (listed in `constants.output_files`).

---

## 2. Full data-dependency graph

```mermaid
flowchart LR
    %% raw inputs
    merged[("🟩 input/merged_kanji.json")]
    remove[("🟩 overrides/kanji_to_remove.json")]
    v3[("🟩 raw/kanji-words/v3/*")]
    textbook[("🟩 raw/kanji-textbook-words/* OR
    raw/kanji-textbook-words-min/* — chosen per script
    by USE_TEXT_BOOK_MIN")]
    jmdict[("🟩 input/scriptin-jmdict-eng.json")]
    furimap[("🟩 input/jmdict-furigana-map.json")]
    aiwords[("🟩 raw/ai-generated/sample-vocab-ai.json")]
    aimean[("🟩 raw/ai-generated/vocab-meanings-ai.json")]
    aistudy[("🟩 raw/ai-generated/japanese-study-words-ai.json")]
    jpdbfreq[("🟩 raw/JPDB_FREQUENCY_*.csv")]
    keywordsraw[("🟩 raw/kanji-keywords-{j,w,k}.json")]
    manual[("🟩 raw/manual-inspections.json")]

    %% scripts
    S1[build_filtered_kanji_json]
    S2[build_representative_study_word_algo]
    S3[algorithmic_kanji_vocab_overrides]
    S4[generate_furigana_algo]
    SK[algorithmic_overrides_keywords]
    S6[kanji_build_output_jsons]

    %% intermediate files — all script-written: input/filtered_kanji.json, the
    %% -algo.json overrides, and the external-dict cache. The hand-written
    %% overrides/*.json (no -algo suffix) that take priority at build time are
    %% authoritative and intentionally omitted from this view (see §3).
    filt[("🟦 input/filtered_kanji.json")]
    jsw[("🟦 japanese_study_words-algo")]
    kv[("🟦 kanji_vocab-algo")]
    vm[("🟦 vocab_meaning-algo")]
    vr[("🟦 vocab_reading-algo")]
    nofuri[("🟦 vocab-with-no-furigana")]
    vf[("🟦 vocab_furigana-algo")]
    kwalgo[("🟦 keywords-algo")]
    ext[("🟦 vocab_meaning-external-dict")]

    %% outputs
    main[("🟧 output/kanji_main")]
    extd[("🟧 output/kanji_extended")]
    repw[("🟧 output/kanji_representative_words")]
    outvf[("🟧 output/vocab_furigana")]
    outvm[("🟧 output/vocab_meaning")]
    compkw[("🟧 output/component_keyword")]

    merged --> S1
    remove --> S1
    jpdbfreq --> S1
    S1 --> filt
    %% S1 also frequency-orders filtered_kanji.json: Google (in merged) → JPDB → Netflix

    filt --> S2
    v3 --> S2
    textbook --> S2
    jmdict --> S2
    aimean --> S2
    aistudy --> S2
    manual --> S2
    furimap --> S2
    S2 --> jsw

    filt --> S3
    v3 --> S3
    textbook --> S3
    jmdict --> S3
    furimap --> S3
    aiwords --> S3
    aimean --> S3
    jsw --> S3
    ext --> S3
    S3 --> kv & vm & vr & nofuri

    nofuri --> S4
    furimap --> S4
    jmdict --> S4
    vr --> S4
    S4 --> vf

    merged --> SK
    keywordsraw --> SK
    filt --> SK
    SK --> kwalgo

    %% final build
    filt --> S6
    merged --> S6
    kv --> S6
    vm --> S6
    vr --> S6
    vf --> S6
    ext --> S6
    aimean --> S6
    jsw --> S6
    kwalgo --> S6
    furimap --> S6
    jmdict --> S6
    S6 --> main & extd & repw & outvf & outvm & compkw
```

---

## 3. Override files: algorithm-generated vs hand-written

Files in `overrides/` come from two sources. Only these are written by scripts — all
have the `-algo` suffix (plus the external-dict cache). Every other `overrides/*` file
is hand-maintained and must not be regenerated.

```mermaid
flowchart TB
    subgraph ALGO["Written by scripts (do NOT hand-edit)"]
      a1["japanese_study_words-algo.json — build_representative_study_word_algo"]
      a2["kanji_vocab-algo.json — algorithmic_kanji_vocab_overrides"]
      a3["vocab_meaning-algo.json — algorithmic_kanji_vocab_overrides"]
      a4["vocab_reading-algo.json — algorithmic_kanji_vocab_overrides"]
      a5["vocab_furigana-algo.json — generate_furigana_algo"]
      a6["keywords-algo.json — algorithmic_overrides_keywords"]
      a7["vocab_meaning-external-dict.json — fetch_missing_vocab_meanings (manual run)"]
    end
    subgraph MANUAL["Hand-written (authoritative overrides)"]
      m1["keywords.json, component_keyword.json, kanji_vocab.json,
      vocab_meaning.json, vocab_furigana.json, kanji_parts.json,
      kanji_to_remove.json, japanese_study_words.json, …"]
    end
```

At build time the final build prefers manual overrides over the `-algo` files.

---

## 4. The two selection algorithms (per-kanji logic)

### `build_representative_study_word_algo.py`
One unique study word per kanji; the word must START with the kanji.

```mermaid
flowchart TD
    K[for each kanji] --> C[collect v3 + textbook candidates
    that START with kanji, all-Japanese, 1-2 kanji
    textbook source: full or -min per USE_TEXT_BOOK_MIN]
    C --> SR{single-kanji word, kanji_count==1,
    tagged 🌱 or ☘️ — or 🌷 if
    INCLUDE_TULIP_IN_PRIORITY=True?}
    SR -- yes --> PICK[pick best among them by word_score — bypasses Rule 1 and 2]
    SR -- no --> SC[score: source tier, then word-type, then length]
    SC --> U{best unused word?}
    U -- yes --> PICK
    U -- no candidates --> FB[relaxed: textbook word
    CONTAINING kanji, shortest first]
    FB --> U2{unused?}
    U2 -- yes --> PICK
    U2 -- no --> AI[last resort: ai-generated study word]
    AI --> PICK
    PICK --> MEAN[resolve meaning:
    entry -> jmdict -> scriptin -> ai]
    MEAN --> MAN[apply manual replaceKanjiStudyWords]
    MAN --> DUP{any word maps to 2 kanji?}
    DUP -- yes --> ERR[raise ValueError]
    DUP -- no --> OUT[(japanese_study_words-algo.json)]
```

### `algorithmic_kanji_vocab_overrides.py`
Up to two SAMPLE words per kanji (kanji can appear anywhere), with reading diversity.

```mermaid
flowchart TD
    K[for each kanji] --> OV{hand-curated override
    in sample-vocab-ai.json?}
    OV -- yes --> RES[use override words] --> EMIT
    OV -- no --> C[collect v3 + textbook + existing + jmdict
    candidates that have a meaning available
    textbook source: full or -min per USE_TEXT_BOOK_MIN]
    C --> S1[first word = best score
    tier, extra-kanji, length, reading, meaning]
    S1 --> S2[second word = best score
    + bonus for DIFFERENT kanji reading
    only if itself high-frequency]
    S2 --> RP{pair redundant?
    one contains other / same kanji set}
    RP -- yes --> ALT[reach down to textbook/📚
    for a different-reading word]
    RP -- no --> EMIT
    ALT --> EMIT[emit 1-2 words]
    EMIT --> W[(kanji_vocab-algo + vocab_meaning-algo
    + vocab_reading-algo + vocab-with-no-furigana)]
```

---

## 5. Word-meaning resolution

A word's English meaning is resolved by one shared function,
`sources.resolve_meaning(word, ...)`, used by the sample-vocab algorithm (override
resolution), the final build, and the manual `fetch_missing` tool. Callers pass
whichever source maps they have; the precedence is fixed in the function:

```mermaid
flowchart LR
    w[word] --> R[sources.resolve_meaning]
    R --> o["common → custom → algo → external → ai → jmdict_full → jsw"]
    o --> m[meaning or None]
```

The final build falls back to the word itself when every source misses.
`fetch_missing_vocab_meanings.py` (manual, network) fills `vocab_meaning-external-dict.json`
for words still missing a meaning via the Jotoba/Jisho APIs.

---

## 6. Where a kanji's keyword comes from

A kanji can need a keyword in three situations, each with its own output file:

```mermaid
flowchart TB
    s["Shipped kanji (in filtered_kanji.json)"] --> m["output/kanji_main.json
    keyword[0] — base (merged_kanji) + keywords-algo + keywords.json"]
    c["Component part, not shipped (e.g. 勺)"] --> ck["output/component_keyword.json
    input/missing_components.json + overrides/component_keyword.json (manual)
    + non-shipped keys from keywords-algo / keywords.json"]
    v["Kanji inside a sample/study word, not shipped (e.g. 癌, 飴)"] --> ek["output/extra_kanji_keyword.json
    auto-sourced via keyword_sources (raw kanji-keywords-{j,k,w} → merged base)"]
```

Kanji that appear only inside vocabulary words but aren't in `merged_kanji.json` at all
(e.g. 癌, 飴, 葱) get a keyword from `extra_kanji_keyword.json` when the raw keyword
files have one; the rest (very rare) are left unlabeled.

