# Kanji-heatmap-data build flowcharts

Visual map of how `src/*.py` turns raw sources into the shipped `output/` JSONs.
This is a snapshot of the current pipeline.

Legend:
- 🟩 raw input (hand-authored or third-party, in `raw/` or `input/`)
- 🟦 intermediate override (`overrides/`)
- 🟧 final shipped artifact (`output/`)
- ⬜ script

`input/` is externally maintained and git-ignored; the build only reads from it.

Each `*_algo.py` generator is named after the `-algo.json` file it writes
(`kanji_vocab_algo.py` → `kanji_vocab-algo.json`) and is **pure**: it never reads
its hand-written override counterpart. Those manual overrides are merged on top at
build time by `kanji_build_output_jsons.py` (see §3, §4).

---

## 1. The orchestrated pipeline (`generate.sh`, top to bottom)

The full build is offline and deterministic. Each step writes files the next reads.

```mermaid
flowchart TD
    A[build_filtered_kanji_json.py] --> B[japanese_study_words_algo.py]
    B --> C[kanji_vocab_algo.py]
    C --> D[generate_furigana_algo.py]
    D --> E[keywords_algo.py]
    E --> F[build_similar_kanji.py]
    F --> G[kanji_build_output_jsons.py]
    G --> H[kanji_inspect.py — stats only]

    A -.writes.-> a1[(input/filtered_kanji.json
    input/all_kanjis.json)]
    B -.writes.-> b1[(overrides/japanese_study_words-algo.json)]
    C -.writes.-> c1[(overrides/kanji_vocab-algo.json
    vocab_reading-algo.json)]
    D -.writes.-> d1[(overrides/vocab_furigana-algo.json)]
    E -.writes.-> e1[(overrides/keywords-algo.json
    debug/debug-keywords.json)]
    F -.writes.-> f1[(output/similar-kanjis.json)]
    G -.writes.-> g1[(output/kanji_main.json, kanji_extended.json,
    component_keyword.json, extra_kanji_keyword.json, phonetic.json,
    cum_use.json, vocab_meaning.json, vocab_furigana.json,
    kanji_representative_words.json)]
```

`generate_furigana_algo.py` is the ONLY step that generates furigana. It computes the
shipped word set itself (same `get_words` logic as the final build) and covers EVERY
shipped word — like all `-algo` files it is complete and never consults the manual
overrides. The final build then just merges the two layers (hand-written
`overrides/vocab_furigana.json` wins) and aborts if a word is in neither.

`kanji_build_output_jsons.py` is the single hard gate. It raises loudly on:
- a shipped sample word with no resolvable meaning (`dump_all_vocab_meanings`) or no
  reading (`dump_all_vocab_furigana`);
- two kanji sharing a keyword (`assert_unique_keywords`);
- two kanji sharing a representative study word, or a study word missing its
  reading/gloss (`dump_kanji_representative_words`).

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
    readingOrder/meanings corrections for jmdict_resolver
    + replaceKanjiStudyWords ✏️ study-word pins")]
    furimap[("🟩 input/jmdict-furigana-map.json")]
    jpdbfreq[("🟩 raw/JPDB_FREQUENCY_*.csv")]
    keywordsraw[("🟩 raw/kanji-keywords-{j,w,k}.json")]

    %% hand-written manual overrides that merge at BUILD time (kanji_vocab / study-word
    %% analog of the -algo files) — shown here because they feed S6, not the algos.
    kvman[("🟩 overrides/kanji_vocab.json — manual sample-word pins")]
    jswman[("🟩 overrides/japanese_study_words.json — manual {kanji:word} pins")]

    %% scripts
    S1[build_filtered_kanji_json]
    S2[japanese_study_words_algo]
    S3[kanji_vocab_algo]
    S4[generate_furigana_algo]
    SK[keywords_algo]
    S6[kanji_build_output_jsons]

    %% intermediate files — all script-written: input/filtered_kanji.json and the
    %% -algo.json overrides. The hand-written overrides/*.json (no -algo suffix) that
    %% take priority at build time are authoritative; the two that matter to the algos'
    %% outputs (kanji_vocab, japanese_study_words) are drawn above.
    filt[("🟦 input/filtered_kanji.json")]
    jsw[("🟦 japanese_study_words-algo")]
    kv[("🟦 kanji_vocab-algo")]
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
    furimap --> S2
    S2 --> jsw

    filt --> S3
    freqranks --> S3
    textbook --> S3
    jmdict --> S3
    furimap --> S3
    S3 --> kv & vr

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
    kvman --> S6
    vr --> S6
    vf --> S6
    jsw --> S6
    jswman --> S6
    kwalgo --> S6
    jmdict --> S6
    S6 --> main & extd & repw & outvf & outvm & compkw
```

Note: unlike the earlier design, the study-word algo (S2) no longer reads
`overrides/japanese_study_words.json` — that manual pin file is merged at build time by
S6 (`kanji_load.dump_kanji_representative_words`), the same pattern as
`overrides/kanji_vocab.json` for sample words. `overrides/resolver_hints.json`'s
`replaceKanjiStudyWords` pins are the exception: they still live inside S2 (a resolver
hint, not the `-algo` counterpart).

---

## 3. Override files: algorithm-generated vs hand-written

Files in `overrides/` come from two sources. Only these are written by scripts — all
have the `-algo` suffix. Every other `overrides/*` file is hand-maintained and must
not be regenerated.

```mermaid
flowchart TB
    subgraph ALGO["Written by scripts (do NOT hand-edit)"]
      a1["japanese_study_words-algo.json — japanese_study_words_algo"]
      a2["kanji_vocab-algo.json — kanji_vocab_algo"]
      a4["vocab_reading-algo.json — kanji_vocab_algo"]
      a5["vocab_furigana-algo.json — generate_furigana_algo"]
      a6["keywords-algo.json — keywords_algo"]
    end
    subgraph MANUAL["Hand-written (authoritative overrides)"]
      m1["keywords.json, component_keyword.json, kanji_vocab.json,
      vocab_meaning.json, vocab_furigana.json, kanji_parts.json,
      kanji_to_remove.json, japanese_study_words.json, …"]
    end
```

At build time the final build prefers manual overrides over the `-algo` files. Each
`*_algo.py` generator is pure — it never reads its manual counterpart, so the merge
(and its collision/completeness checks) all live in `kanji_build_output_jsons.py`.

---

## 4. The two selection algorithms (per-kanji logic)

### `japanese_study_words_algo.py`
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
    RES --> MAN[apply replaceKanjiStudyWords ✏️ pins
    from overrides/resolver_hints.json
    lenient resolve — the human picked the writing]
    MAN --> DUP{a replaceKanjiStudyWords pin
    collides with another kanji's word?}
    DUP -- yes --> ERR[raise ValueError]
    DUP -- no --> DROP[drop non-words logged then removed:
    no JMdict entry / empty meaning / affix-only
    妃 卿 哉 → that kanji ships no study word]
    DROP --> OUT[(overrides/japanese_study_words-algo.json
    ✏️ tag kept for pins)]
```

Then the manual `{kanji: word}` pins in `overrides/japanese_study_words.json` are merged
onto that `-algo` output at BUILD time (`kanji_load.dump_kanji_representative_words`,
called by `kanji_build_output_jsons.py`):

```mermaid
flowchart TD
    A[(japanese_study_words-algo.json
    — includes replaceKanjiStudyWords picks)] --> M[merge manual pins:
    overrides/japanese_study_words.json {kanji:word} WINS]
    P[(overrides/japanese_study_words.json)] --> M
    M --> DER[derive each pin's reading + meaning via
    japanese_study_words_algo.resolve_manual_pin_entries
    same resolver the algo uses]
    DER --> DUP{two kanji share a word?}
    DUP -- yes --> ERR1[raise ValueError]
    DUP -- no --> MISS{any shipped word missing
    reading or english gloss?}
    MISS -- yes --> ERR2[raise ValueError]
    MISS -- no --> BADGE[replace ✏️ with the word's REAL
    frequency badge frequency_tag — logs/-algo keep ✏️]
    BADGE --> OUT[(output/kanji_representative_words.json)]
```

### `kanji_vocab_algo.py`
Up to two SAMPLE words per kanji (kanji can appear anywhere), with reading diversity.

```mermaid
flowchart TD
    K[for each kanji] --> C[collect candidates: freq-ranks contains-anywhere
    index over ALL raw/freq-ranks/*.tsv + textbook-min
    + existing input/kanji_vocab.json + full-JMdict fallback.
    reject phrase bridges 診て貰う, resolver.is_phrase_fragment,
    and JMdict exp + が/を/に + kana-verb phrases 音がする / 恋をする / ご覧になる;
    2-5 chars, ≥1 kanji. missing meaning/reading only costs score]
    C --> DEDUP[dedupe per word: keep best score across sources
    textbook word also in corpus keeps the better tier]
    DEDUP --> S1["first word = best word_score (lower wins):
    proper-noun demotion → effective_tier → extra-kanji → length band → shipped → len
    effective_tier = tag priority + kanji-count surcharge
    1–2:+0, 3:+1, 4–5:+5 — so ☘️ 2-kanji beats 🌱 3-kanji"]
    S1 --> S2[second word = best second_score
    + bonus for a DIFFERENT kanji reading when the candidate is
    high-freq 🌱☘️🌷 OR JLPT N5–N2.
    prefer a primary freq-ranks/textbook candidate]
    S2 --> RP{pair redundant?
    one contains other / same kanji set}
    RP -- yes --> ALT[reach down to textbook/📚 for a
    different-reading, non-proper-noun word]
    RP -- no --> EMIT
    ALT --> EMIT[emit 1-2 words]
    EMIT --> W[(kanji_vocab-algo + vocab_reading-algo
    — English glosses are no longer emitted here; the
    final build resolves them straight from JMdict)]
    EMIT --> STATS[report also prints Furigana Reading Stats
    same vs different reading for the selected pairs]
```

Hand-curated sample picks in `overrides/kanji_vocab.json` win at BUILD time
(`build_helpers.get_words`: manual → `kanji_vocab-algo` → `input/kanji_vocab.json`),
not inside the algo.

Readings/meanings for the STUDY words come from `src/jmdict_resolver.py` (JMdict only —
pool reading/meaning fields never reach the output). Per-word hand corrections for the
resolver (leading reading, replacement meaning) and the `replaceKanjiStudyWords` ✏️
study-word pins live in `overrides/resolver_hints.json`, not in code.

---

## 5. Word-meaning resolution

Every English gloss comes from **one source: JMdict** (`input/scriptin-jmdict-eng.json`).
`kanji_load.make_meaning_resolver` builds a `{form: gloss}` index once
(`sources.build_jmdict_meaning_index`, the same appliesToKanji-aware gloss the
sample-vocab algo uses) and returns a `resolve(word)` closure:

```mermaid
flowchart LR
    jm[("🟩 input/scriptin-jmdict-eng.json")] --> IDX[sources.build_jmdict_meaning_index
    pass 1: common forms only — a common writing wins its own gloss
    pass 2: fill the rest — so 万歳→banzai, not the rarer 万年 sense]
    IDX --> R[resolve word]
    ov[("🟩 overrides/vocab_meaning.json — manual hatch, empty")] --> R
    R --> o["overrides → JMdict gloss → JMdict gloss of the
    する/な-stripped stem (勃発する → 勃発)"]
    o --> m[meaning or None]
```

Two passes because the index is keyed by surface writing, and a writing can be shared
by several JMdict entries: pass 1 lets a form that is itself common claim its common
gloss before any rarer homograph, regardless of file order.

The final build is the single hard gate: `dump_all_vocab_meanings` RAISES if any
shipped word resolves to no meaning (add it to `overrides/vocab_meaning.json`), and
`dump_all_vocab_furigana` RAISES if any has no reading (bare `[[word]]`; add it to
`overrides/vocab_furigana.json`). Because of this, the sample-vocab algorithm does
NOT pre-filter candidates by meaning/reading availability — a missing one only
costs score, so eligibility can never drift from what the build actually resolves.

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
files have one; the rest (very rare) are left unlabeled. Two kanji must never share a
keyword — `assert_unique_keywords` fails the build if they do.

---

## 7. Similar-kanji neighbors (`build_similar_kanji.py`)

`output/similar-kanjis.json` is generated (not static): for each shipped kanji, its
most-similar shipped kanji, most-similar first (max 10). Jouyou kanji get a merged
stroke-edit-distance + radical-overlap list (reciprocal-rank fusion over
`raw/similarity/*.csv`); non-jouyou kanji fall back to a component-overlap measure.
