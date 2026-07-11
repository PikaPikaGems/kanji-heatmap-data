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
    vocab_reading-algo.json)]
    D -.writes.-> d1[(overrides/vocab_furigana-algo.json)]
    E -.writes.-> e1[(overrides/keywords-algo.json
    debug/debug-keywords.json)]
    G -.writes.-> g1[(output/kanji_main.json, kanji_extended.json,
    component_keyword.json, extra_kanji_keyword.json, phonetic.json,
    cum_use.json, vocab_meaning.json, vocab_furigana.json,
    kanji_representative_words.json)]
```

`output/similar-kanjis.json` is a static artifact: its generator
(`build_similar_kanjis.py`) has been removed from the repo, but the file still ships
in the release tarball (listed in `constants.output_files`).

`generate_furigana_algo.py` is the ONLY step that generates furigana. It computes the
shipped word set itself (same `get_words` logic as the final build) and covers EVERY
shipped word — like all `-algo` files it is complete and never consults the manual
overrides. The final build then just merges the two layers (hand-written
`overrides/vocab_furigana.json` wins) and aborts if a word is in neither.

---

## 2. Full data-dependency graph

```mermaid
flowchart LR
    %% raw inputs
    merged[("🟩 input/merged_kanji.json")]
    remove[("🟩 overrides/kanji_to_remove.json")]
    freqranks[("🟩 raw/freq-ranks/*.tsv — per-corpus frequency
    ranks + tier + JLPT; the word pool for BOTH
    selection algorithms")]
    textbook[("🟩 raw/kanji-textbook-words-min/*
    (TEXTBOOK_SUBDIR env var; default -min)")]
    jmdict[("🟩 input/scriptin-jmdict-eng.json")]
    hints[("🟩 overrides/resolver_hints.json — hand-edited
    readingOrder/meanings corrections for jmdict_resolver")]
    furimap[("🟩 input/jmdict-furigana-map.json")]
    jpdbfreq[("🟩 raw/JPDB_FREQUENCY_*.csv")]
    keywordsraw[("🟩 raw/kanji-keywords-{j,w,k}.json")]
    manual[("🟩 raw/manual-inspections.json —
    incl. replaceKanjiStudyWords pins")]

    %% scripts
    S1[build_filtered_kanji_json]
    S2[build_representative_study_word_algo]
    S3[algorithmic_kanji_vocab_overrides]
    S4[generate_furigana_algo]
    SK[algorithmic_overrides_keywords]
    S6[kanji_build_output_jsons]

    %% intermediate files — all script-written: input/filtered_kanji.json and the
    %% -algo.json overrides. The hand-written
    %% overrides/*.json (no -algo suffix) that take priority at build time are
    %% authoritative and intentionally omitted from this view (see §3).
    filt[("🟦 input/filtered_kanji.json")]
    jsw[("🟦 japanese_study_words-algo")]
    kv[("🟦 kanji_vocab-algo")]
    vm[("🟦 vocab_meaning-algo")]
    vr[("🟦 vocab_reading-algo")]
    vf[("🟦 vocab_furigana-algo")]
    kwalgo[("🟦 keywords-algo")]

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
    freqranks --> S2
    textbook --> S2
    jmdict --> S2
    hints --> S2
    manual --> S2
    furimap --> S2
    S2 --> jsw

    filt --> S3
    freqranks --> S3
    textbook --> S3
    jmdict --> S3
    hints --> S3
    furimap --> S3
    jsw --> S3
    S3 --> kv & vm & vr

    filt --> S4
    kv --> S4
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
    jsw --> S6
    kwalgo --> S6
    jmdict --> S6
    S6 --> main & extd & repw & outvf & outvm & compkw
```

---

## 3. Override files: algorithm-generated vs hand-written

Files in `overrides/` come from two sources. Only these are written by scripts — all
have the `-algo` suffix. Every other `overrides/*` file is hand-maintained and must
not be regenerated.

```mermaid
flowchart TB
    subgraph ALGO["Written by scripts (do NOT hand-edit)"]
      a1["japanese_study_words-algo.json — build_representative_study_word_algo"]
      a2["kanji_vocab-algo.json — algorithmic_kanji_vocab_overrides"]
      a3["vocab_meaning-algo.json — algorithmic_kanji_vocab_overrides"]
      a4["vocab_reading-algo.json — algorithmic_kanji_vocab_overrides"]
      a5["vocab_furigana-algo.json — generate_furigana_algo"]
      a6["keywords-algo.json — algorithmic_overrides_keywords"]
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
One unique study word per kanji; the word must START with the kanji
(textbook words merely CONTAINING it ride along with a stage penalty).

```mermaid
flowchart TD
    K[for each kanji] --> C[collect candidates: freq-ranks kanji.tsv
    + textbook-min + the bare kanji itself when JMdict
    says it is a standalone word
    all-Japanese, 1-2 kanji, unused]
    C --> F[reject phrase fragments — resolver.is_phrase_fragment:
    この人, 常に, 今も, 事になる]
    F --> SC["score tuple (lower wins): validity → stage →
    band → JLPT → class verb&lt;adj&lt;other → word-type → shipped → freq → len"]
    SC --> SR{any single-kanji candidate in a
    top band BASIC/COMMON that resolves standalone?}
    SR -- "yes — special rule" --> BT{bare kanji ties the best
    through band/JLPT/class?}
    BT -- yes --> PICKBARE[pick the bare kanji: 一, 常, 誰]
    BT -- no --> PICKONE[pick best single-kanji word: 高い, 語る]
    SR -- no --> PICK[pick best-scored word]
    PICK --> STRIP[strip trailing する/な from
    2-kanji stems: 真摯な → 真摯]
    PICKBARE --> RES
    PICKONE --> RES
    STRIP --> RES[reading + meaning from jmdict_resolver ONLY:
    up to 2 readings ・-joined, sense blocks;
    resolve_fallback for rare writings — ⚠️ often-kana marker;
    pool r/e fields never reach the output]
    RES --> MAN[apply manual replaceKanjiStudyWords ✏️
    lenient resolve — the human picked the writing]
    MAN --> DUP{any word maps to 2 kanji?}
    DUP -- yes --> ERR[raise ValueError]
    DUP -- no --> OUT[(japanese_study_words-algo.json)]
```

### `algorithmic_kanji_vocab_overrides.py`
Up to two SAMPLE words per kanji (kanji can appear anywhere), with reading diversity.

```mermaid
flowchart TD
    K[for each kanji] --> C[collect candidates: freq-ranks contains-anywhere
    index over ALL raw/freq-ranks/*.tsv + textbook-min
    + existing + jmdict fallbacks — must have a meaning
    available and a dictionary reading; phrase fragments
    rejected via resolver.is_phrase_fragment]
    C --> S1[first word = best score
    proper-noun demotion, then tier, extra-kanji, length, reading, meaning
    hand-curated picks live in overrides/kanji_vocab.json, applied at BUILD time]
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
    + vocab_reading-algo)]
```

Readings and meanings for the STUDY words come from `src/jmdict_resolver.py`
(JMdict only — pool reading/meaning fields never reach the output). Per-word
hand corrections for the resolver (leading reading, replacement meaning) live in
`overrides/resolver_hints.json`, not in code.

---

## 5. Word-meaning resolution

A word's English meaning is resolved by one shared function,
`sources.resolve_meaning(word, ...)`, used by the sample-vocab algorithm and the
final build. Callers pass whichever source maps they have; the precedence is fixed
in the function:

```mermaid
flowchart LR
    w[word] --> R[sources.resolve_meaning]
    R --> o["common → custom → algo → jmdict_full → jsw"]
    o --> m[meaning or None]
```

The final build falls back to the word itself when every source misses, and prints
each such word in a "Word meaning Not Found" report — hand-add those to
`overrides/vocab_meaning.json`.

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

