# Kanji-heatmap-data build flowcharts

Visual map of how `src/*.py` turns raw sources into the shipped `output/` JSONs.
This is a snapshot of the current pipeline.

Legend:
- 🟩 raw input (hand-authored or third-party, in `raw/` or `input/`)
- 🟦 intermediate override (`overrides/`)
- 🟧 final shipped artifact (`output/`)
- ⬜ script

`input/` is externally maintained and git-ignored; the build only reads from it.
Script-written pipeline artifacts go in the separate git-ignored `intermediate/`
directory instead: `build_filtered_kanji_json.py` (the first pipeline step) writes
`intermediate/filtered_kanji.json` (the canonical "which kanji ship" list every
later step reads) and `intermediate/all_kanjis.json` there. (Nothing in this repo
reads `all_kanjis.json` — it is emitted for downstream/frontend consumers.)

Each committed `*_algo.py` generator is named after the `-algo.json` file it writes
(`kanji_vocab_algo.py` → `kanji_vocab-algo.json`). `japanese_study_words_algo.py`
and `kanji_vocab_algo.py` are **pure**: they never read their hand-written override
counterpart, so those manual overrides are merged on top at build time by
`kanji_build_output_jsons.py` (see §3, §4). `keywords_algo.py` is the **exception**:
it reads `overrides/keywords.json` both to reserve those keywords (so no other kanji
is assigned one) AND to copy the manual value straight into its own `keywords-algo.json`
output — so ~26 of the committed algo entries are actually manual values. The build's
`load_keywords_override` merges `keywords.json` over the algo layer again regardless,
so shipped output is unaffected, but the `-algo` file is not purely algorithmic.
Furigana and meanings are generated on the fly in the final build (no intermediate
cache files) — only hand pins in `overrides/vocab_furigana.json` /
`overrides/vocab_meaning.json` win over the generated layer.

---

## 1. The orchestrated pipeline (`generate.sh`, top to bottom)

The full build is offline and deterministic. Each step writes files the next reads.

```mermaid
flowchart TD
    A[build_filtered_kanji_json.py] --> B[japanese_study_words_algo.py]
    B --> C[kanji_vocab_algo.py]
    C --> E[keywords_algo.py]
    E --> F[build_similar_kanji.py]
    F --> G[kanji_build_output_jsons.py]
    G --> H[kanji_inspect.py — stats only]

    A -.writes.-> a1[(intermediate/filtered_kanji.json
    intermediate/all_kanjis.json)]
    B -.writes.-> b1[(overrides/japanese_study_words-algo.json)]
    C -.writes.-> c1[(overrides/kanji_vocab-algo.json)]
    E -.writes.-> e1[(overrides/keywords-algo.json
    debug/debug-keywords.json)]
    F -.writes.-> f1[(output/similar-kanjis.json)]
    G -.writes.-> g1[(output/kanji_main.json, kanji_extended.json,
    component_keyword.json, extra_kanji_keyword.json, phonetic.json,
    cum_use.json, vocab_meaning.json, vocab_furigana.json,
    kanji_representative_words.json)]
```

After G, `generate.sh` copies `intermediate/filtered_kanji.json` to
`output/filtered_kanji.json` (a shipped release file — see `constants.output_files`);
it is not written by any script.

Furigana is generated inside the final build (`dump_all_vocab_furigana` →
`generate_furigana_algo.build_furigana_for_words`): furigana map + reading hints
(freq-ranks / JMdict) + alignment fallback. Hand-written
`overrides/vocab_furigana.json` wins; the build aborts if a word is still bare
`[[word]]` or missing. Meanings follow the same pattern (JMdict on the fly +
`overrides/vocab_meaning.json`).

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
    vfman[("🟩 overrides/vocab_furigana.json — manual furigana pins")]

    %% hand-written manual overrides that merge at BUILD time (kanji_vocab / study-word
    %% analog of the -algo files) — shown here because they feed S6, not the algos.
    kvman[("🟩 overrides/kanji_vocab.json — manual sample-word pins")]
    jswman[("🟩 overrides/japanese_study_words.json — manual {kanji:word} pins")]
    kvexist[("🟩 input/kanji_vocab.json — existing production
    sample words (fallback pool)")]
    kwman[("🟩 overrides/keywords.json — manual keyword pins")]

    %% scripts
    S1[build_filtered_kanji_json]
    S2[japanese_study_words_algo]
    S3[kanji_vocab_algo]
    SK[keywords_algo]
    S6[kanji_build_output_jsons]

    %% intermediate files — script-written: intermediate/filtered_kanji.json and the
    %% committed -algo.json overrides. Furigana/meanings are generated inside S6.
    filt[("🟦 intermediate/filtered_kanji.json")]
    jsw[("🟦 japanese_study_words-algo")]
    kv[("🟦 kanji_vocab-algo")]
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
    hints --> S3
    kvexist --> S3
    S3 --> kv

    merged --> SK
    keywordsraw --> SK
    filt --> SK
    kwman --> SK
    SK --> kwalgo

    %% final build — generates furigana/meanings on the fly
    filt --> S6
    merged --> S6
    kv --> S6
    kvman --> S6
    kvexist --> S6
    vfman --> S6
    furimap --> S6
    freqranks --> S6
    jsw --> S6
    jswman --> S6
    kwalgo --> S6
    kwman --> S6
    keywordsraw --> S6
    hints --> S6
    jmdict --> S6
    S6 --> main & extd & repw & outvf & outvm & compkw
```

For readability, S6's many auxiliary single-purpose inputs are NOT drawn above:
`input/missing_components.json`, `input/phonetic_components.json`,
`input/cum_use.json`, `raw/JITEN_FREQUENCY.csv`, `raw/JPDB_FREQUENCY_*.csv`,
`raw/KKLC-ORDER.txt`, `raw/order.csv`, `overrides/kanji_parts.json`,
`overrides/component_keyword.json`, and `overrides/vocab_meaning.json`. The graph
above shows the word / keyword / furigana / meaning flow; those feed straight into
the reformatted kanji fields (strokes, frequency ranks, decomposition, etc.).

Note: unlike the earlier design, the study-word algo (S2) no longer reads
`overrides/japanese_study_words.json` — that manual pin file is merged at build time by
S6 (`kanji_load.dump_kanji_representative_words`), the same pattern as
`overrides/kanji_vocab.json` for sample words. `overrides/resolver_hints.json`'s
`replaceKanjiStudyWords` pins are the exception: they still live inside S2 (a resolver
hint, not the `-algo` counterpart).

---

## 3. Override files: algorithm-generated vs hand-written

Files in `overrides/` come from two sources. Only these are written by scripts and
committed — all have the `-algo` suffix. Every other `overrides/*` file is
hand-maintained and must not be regenerated. Furigana and meanings have no `-algo`
cache; they are generated inside the final build.

```mermaid
flowchart TB
    subgraph ALGO["Written by scripts & committed (do NOT hand-edit)"]
      a1["japanese_study_words-algo.json — japanese_study_words_algo"]
      a2["kanji_vocab-algo.json — kanji_vocab_algo"]
      a6["keywords-algo.json — keywords_algo"]
    end
    subgraph MANUAL["Hand-written (authoritative overrides)"]
      m1["keywords.json, component_keyword.json, kanji_vocab.json,
      vocab_meaning.json, vocab_furigana.json, kanji_parts.json,
      kanji_to_remove.json, japanese_study_words.json, …"]
    end
```

At build time the final build prefers manual overrides over the algo layers. The
`japanese_study_words_algo` and `kanji_vocab_algo` generators are pure — they never
read their manual counterpart, so the merge (and its collision/completeness checks)
all live in `kanji_build_output_jsons.py`. `keywords_algo` is the exception: it reads
`overrides/keywords.json` to reserve those keywords AND copies each manual value into
its own `keywords-algo.json` (so the committed algo file embeds ~26 manual values).
The build merges `keywords.json` on top again, so shipped output is unaffected.

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
    EMIT --> W[(kanji_vocab-algo
    — English glosses / furigana are no longer emitted here;
    the final build resolves them on the fly)]
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
    suffix-stripped stem (longest first: として/する/な/と/だ/に,
    e.g. 勃発する → 勃発, 慄然として → 慄然)"]
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
most-similar shipped kanji, most-similar first (at most 10; lists may be shorter).
Kanji covered by `raw/similarity/dkanjistat.json` use Kanjistat optimal-transport
distance, gated by a distance ceiling and stroke-count delta; the rest fall back
to the kanjidict phonetic / radical+IDS heuristic.
