"""Diagnostic reporting for kanji_vocab_algo (stdout only — writes no files).

Extracted from kanji_vocab_algo so the selection algorithm reads top-to-bottom
without ~300 lines of terminal-formatting interleaved. Everything here is
read-only over the selection results; kanji_vocab_algo.main calls print_replace_logs
and print_report after it has written overrides/kanji_vocab-algo.json.

Some selection state this needs (the SHIPPED constant, tag priorities, per-kanji
reading lookup) is read through the `kv` alias below; the word→JLPT map is passed
in to print_report as `word_jlpt` (it's built during selection, so it's threaded
explicitly rather than reached for as a global).
"""

import unicodedata
from collections import Counter

from japanese import kanji_count, is_kanji_char, readings_equivalent
from sources import load_textbook_entries
import kanji_vocab_algo as kv


def fmt_tag(tag):
    # ☘️ and ✍️ are VS16 sequences (base char + U+FE0F) that macOS renders NARROWER
    # than single-codepoint emoji, which breaks column alignment on the rows they appear
    # in (every other tag/medal is a single, uniform-width emoji). Remap them to
    # single-codepoint look-alikes (🍀 clover, 📝 memo) so all glyphs share one width.
    return {
        "☘️": "☘️ ",
        "🌶️": "🌶️ ",
        "✏️": "✏️ ",
        kv.TEXTBOOK_TAG: "📖",
        kv.EXISTING_TAG: "📋",
        kv.JMDICT_TAG: "📕",
    }.get(tag, tag)


def display_width(s):
    """Terminal display width: CJK and emoji (incl. VS16 sequences) count as 2 columns."""
    w = 0
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        cp = ord(c)
        nxt = s[i + 1] if i + 1 < n else ''
        if nxt == '️':  # emoji presentation: base + VS16 renders wide (☘️ ✍️)
            w += 2
            i += 2
            continue
        if 0xFE00 <= cp <= 0xFE0F or unicodedata.combining(c):  # stray VS / combining marks
            i += 1
            continue
        eaw = unicodedata.east_asian_width(c)
        if eaw in ('W', 'F') or cp >= 0x1F000:  # wide CJK + emoji plane (🥇🌱 etc.)
            w += 2
        else:
            w += 1
        i += 1
    return w


def pad(s, target_width):
    return s + ' ' * max(0, target_width - display_width(s))


def print_replace_logs(logs):
    """Print aligned table of replacements: rows buffered first so columns can be padded."""
    if not logs:
        return
    def cell(medal, entry, kanji_reading):
        # word, its full reading, and 「the kanji's own reading」 — the diversity signal.
        return f"{medal} {fmt_tag(entry.tag)} 「{kanji_reading or '?'}」 {entry.word} ~ {entry.reading or '?'}"

    rows = []
    for kanji, first, fr, second, sr, best_passed, pr in logs:
        c1 = cell('🥇', first, fr)
        c2 = cell('🥈', second, sr)
        c3 = cell('🙅', best_passed, pr)
        rows.append((kanji, c1, c2, c3))

    w1 = max(display_width(c1) for _, c1, _, _ in rows)
    w2 = max(display_width(c2) for _, _, c2, _ in rows)

    for i, (kanji, c1, c2, c3) in enumerate(rows, 1):
        print(f"{i:03d}. {kanji}  →  {pad(c1, w1 + 3)}{pad(c2, w2 + 3)}{c3}")
    print(f"\n  Replaced ({len(rows)}): {''.join(kanji for kanji, *_ in rows)}")


def _word_reading_from_map(word, furigana_map):
    """Full-word reading from the JMdict furigana map, or None if absent."""
    entry = furigana_map.get(word) or {}
    return next(iter(entry), None)


def _print_reading_diversity_stats(kanji_vocab_result, furigana_map, selected_all, word_gloss):
    """Same-vs-different reading breakdown for the selected pairs (mirrors the
    build-time furigana_stats summary, using the JMdict furigana map directly).

    Skipped kanji (< 2 words or a missing per-kanji furigana segment) are listed
    with tier / word / reading / gloss so gaps are easy to inspect.
    """
    by_kanji = {}
    for w, t, k, r in selected_all:
        by_kanji.setdefault(k, []).append((w, t, r))

    same = rendaku_same = different = skipped = 0
    skipped_rows = []  # (kanji, tag, word, candidate_reading)
    for kanji, words in kanji_vocab_result.items():
        if len(words) < 2:
            skipped += 1
            skipped_rows.extend((kanji, t, w, r) for w, t, r in by_kanji.get(kanji, []))
            continue
        r1 = kv.kanji_reading_in_word(kanji, words[0], '', furigana_map)
        r2 = kv.kanji_reading_in_word(kanji, words[1], '', furigana_map)
        if r1 is None or r2 is None:
            skipped += 1
            skipped_rows.extend((kanji, t, w, r) for w, t, r in by_kanji.get(kanji, []))
            continue
        if r1 == r2:
            same += 1
        elif readings_equivalent(r1, r2):
            rendaku_same += 1
        else:
            different += 1
    total = same + rendaku_same + different
    if total == 0:
        print("\n--- Furigana Reading Stats ---")
        print("  No kanji with 2 sample words and furigana found.")
        return
    equiv_same = same + rendaku_same
    print(f"\n--- Furigana Reading Stats ({total} kanji) ---")
    print(f"  Same reading (exact):          {same:4d} ({same / total * 100:.1f}%)")
    print(f"  Same reading (incl. 連濁/促音): {equiv_same:4d} ({equiv_same / total * 100:.1f}%)  [+{rendaku_same} rendaku/gemination]")
    print(f"  Different reading:             {different:4d} ({different / total * 100:.1f}%)")
    if skipped:
        print(f"  Skipped (< 2 words or missing furigana): {skipped}")
        for k, t, w, cand_r in skipped_rows:
            reading = _word_reading_from_map(w, furigana_map) or cand_r or '?'
            g = word_gloss.get(w, '')
            gloss = f"  {g[:50]}" if g else ''
            print(f"    {k} {fmt_tag(t)} {w} ~ {reading}{gloss}")


def print_report(selected_all, kanji_vocab_result, all_kanji, existing_vocab_words, word_gloss, furigana_map, word_jlpt):
    """Print selection statistics, then detailed word groups (with gloss), then a
    single Copy-paste kanji strings section. Read-only over the selection results —
    it does not affect the written output files."""
    total = len(selected_all)
    unique = len({w for w, *_ in selected_all})
    without_vocab = [k for k in all_kanji if k not in kanji_vocab_result]
    with_one  = sum(1 for v in kanji_vocab_result.values() if len(v) == 1)
    with_two  = sum(1 for v in kanji_vocab_result.values() if len(v) >= 2)

    # label = display-glyph + source + plain-language meaning (the freq-ranks tiers
    # 🌱→🦉 run most-frequent → rarest).
    tier_labels = {
        "🌱": "🌱  freq-ranks BASIC — most frequent (core everyday words)",
        "☘️": "🍀  freq-ranks COMMON — very frequent",
        "🌷": "🌷  freq-ranks FLUENT — frequent / common",
        kv.TEXTBOOK_TAG: "📖  textbook — from raw/kanji-textbook-words-min/",
        "📚": "📚  freq-ranks ADVANCED — less common",
        "🦉": "🦉  freq-ranks UNRANKED — rare",
        "🌶️": "🌶️  freq-ranks NICHE — same tier as 🦉",
        kv.EXISTING_TAG: "📋  existing — current production word (fallback)",
        kv.JMDICT_TAG: "📕  jmdict — pulled from full JMdict (last resort)",
    }

    display_tag = fmt_tag

    tier_counts  = Counter(t for _, t, *_ in selected_all)
    length_counts = Counter(len(w) for w, *_ in selected_all)
    kanji_counts  = Counter(kanji_count(w) for w, *_ in selected_all)
    new_words = sum(1 for w, *_ in selected_all if w not in existing_vocab_words)

    print(f"\n{'─'*40}")
    print(f"  Kanji processed:   {len(all_kanji)}")
    print(f"  With 2 words:      {with_two}")
    print(f"  With 1 word:       {with_one}")
    print(f"  With 0 words:      {len(without_vocab)}")
    print(f"  Total words:       {total}  (kanji→word assignments)")
    print(f"  Unique words:      {unique}  ({total - unique} shared across >1 kanji)")

    _print_reading_diversity_stats(kanji_vocab_result, furigana_map, selected_all, word_gloss)

    print(f"\n  Source / tier breakdown")
    for tag, label in tier_labels.items():
        n = tier_counts.get(tag, 0)
        print(f"    {label}: {n}  ({n/total*100:.1f}%)")

    print(f"\n  Word length")
    for l in sorted(length_counts):
        print(f"    {l} chars: {length_counts[l]}  ({length_counts[l]/total*100:.1f}%)")

    print(f"\n  Kanji per word")
    for k in sorted(kanji_counts):
        print(f"    {k} kanji: {kanji_counts[k]}  ({kanji_counts[k]/total*100:.1f}%)")
    n3 = sum(n for k, n in kanji_counts.items() if k >= 3)
    n4 = sum(n for k, n in kanji_counts.items() if k >= 4)
    print(f"    (3+ kanji picks: {n3};  4+ kanji picks: {n4})")

    # Textbook pools ({word: jlpt} per kanji), shared by the JLPT breakdown
    # (fallback level for words freq-ranks doesn't rank) and the overlap stat.
    tb_pool_cache = {}
    def textbook_pool(kanji):
        if kanji not in tb_pool_cache:
            tb_pool_cache[kanji] = {w: j for w, _r, _e, j in load_textbook_entries(kanji)}
        return tb_pool_cache[kanji]

    # JLPT level from the word's own freq-ranks row (word_jlpt covers every corpus
    # word, so textbook/existing/jmdict-tagged picks get counted too when ranked),
    # falling back to the textbook pool's own jlpt field.
    def jlpt_of(kanji, word):
        jlpt = word_jlpt.get(word)
        return jlpt if jlpt is not None else textbook_pool(kanji).get(word)

    jlpt_counts = Counter(jlpt_of(k, w) for w, _, k, *_ in selected_all)
    print(f"\n  JLPT level (freq-ranks jlpt_level, else the textbook's)")
    for level in (5, 4, 3, 2, 1):
        n = jlpt_counts.get(level, 0)
        print(f"    N{level}: {n}  ({n/total*100:.1f}%)")
    n = jlpt_counts.get(None, 0)
    print(f"    no JLPT tag: {n}  ({n/total*100:.1f}%)")

    # Textbook overlap: 📖-tagged words came from the textbook pool alone; count
    # how many words tagged from another source ALSO sit in their kanji's pool.
    overlap_counts = Counter(
        t for w, t, k, *_ in selected_all
        if t != kv.TEXTBOOK_TAG and w in textbook_pool(k)
    )
    n_overlap = sum(overlap_counts.values())
    print(f"\n  Textbook overlap")
    print(f"    tagged 📖 (textbook was the best source): {tier_counts.get(kv.TEXTBOOK_TAG, 0)}")
    print(f"    tagged from another source but ALSO in the textbook pool: "
          f"{n_overlap}  ({n_overlap/total*100:.1f}%)")
    for t, n in overlap_counts.most_common():
        print(f"      {display_tag(t)} {n}  ({n/total*100:.1f}%)")

    print(f"\n  Not in input/kanji_vocab.json: {new_words}/{total}  ({new_words/total*100:.1f}%)")
    print(f"{'─'*40}")

    def sort_key(item):
        w, t, *_ = item
        return (kv.TAG_PRIORITY.get(t, kv.DEFAULT_TAG_PRIORITY), len(w), w)

    def kanji_str(items):
        return ''.join(k for _, _, k, *_ in sorted(items, key=sort_key))

    def print_word_group(title, items):
        """Per-row detail with english gloss. Copy-paste kanji strings go in the
        bottom section so all inspectable sequences sit together."""
        if not items:
            return
        items = sorted(items, key=sort_key)
        print(f"\n  {title} ({len(items)}):")
        for w, t, k, *_ in items:
            g = word_gloss.get(w, '')
            gloss = f"  {g[:50]}" if g else ''
            print(f"    {k} {display_tag(t)} {w}{gloss}")

    def print_nonshipped_group(items):
        # Picks whose word drags in a kanji we don't ship: target kanji, the
        # unshipped kanji(s), source tag, word, gloss — so a bad pull-in can be
        # spotted and pinned. Tolerated by design (see has_nonshipped_kanji), but
        # worth eyeballing for proper nouns that slipped through (嵯峨野線, 珊瑚海).
        if not items:
            return
        items = sorted(items, key=sort_key)
        print(f"\n  Non-shipped-kanji words ({len(items)}):")
        for w, t, k, *_ in items:
            unshipped = ''.join(c for c in w if is_kanji_char(c) and c not in kv.SHIPPED)
            g = word_gloss.get(w, '')
            print(f"    {k} [{unshipped}] {display_tag(t)} {w}  {g[:50]}")

    one_word_kanji = {k for k, v in kanji_vocab_result.items() if len(v) == 1}
    one_word_items = [i for i in selected_all if i[2] in one_word_kanji]
    advanced_items = [i for i in selected_all if i[1] == '📚']
    unranked_items = [i for i in selected_all if i[1] == '🦉']
    three_kanji_items = [i for i in selected_all if kanji_count(i[0]) == 3]
    four_plus_items = [i for i in selected_all if kanji_count(i[0]) >= 4]
    five_char_items = [i for i in selected_all if len(i[0]) == 5]
    nonshipped_items = [i for i in selected_all if kv.has_nonshipped_kanji(i[0])]
    four_kanji_items = [i for i in selected_all if kanji_count(i[0]) == 4]
    five_kanji_items = [i for i in selected_all if kanji_count(i[0]) == 5]
    niche_items = [i for i in selected_all if i[1] == '🌶️']
    existing_items = [i for i in selected_all if i[1] == kv.EXISTING_TAG]
    jmdict_items = [i for i in selected_all if i[1] == kv.JMDICT_TAG]

    # Detailed word lists (with gloss) — no trailing kanji strings here.
    print_word_group("With 1 word", one_word_items)
    print_word_group("🦉  UNRANKED words", unranked_items)
    print_word_group("4+ kanji words", four_plus_items)
    print_word_group("5-char words", five_char_items)
    print_nonshipped_group(nonshipped_items)

    # All copy-pasteable kanji sequences in one place (assignment targets, ordered
    # by sort_key so the string matches the detailed groups above when present).
    print(f"\n  Copy-paste kanji strings")
    copy_groups = [
        ("With 1 word", one_word_items),
        ("With 0 words", None),  # handled specially below
        ("📚  ADVANCED", advanced_items),
        ("🦉  UNRANKED", unranked_items),
        ("3-kanji words", three_kanji_items),
        ("4-kanji words", four_kanji_items),
        ("5-kanji words", five_kanji_items),
        ("5-char words", five_char_items),
        ("Non-shipped-kanji", nonshipped_items),
        ("🌶️  NICHE", niche_items),
        ("📋  existing", existing_items),
        ("📕  jmdict", jmdict_items),
    ]
    for title, items in copy_groups:
        if title == "With 0 words":
            if without_vocab:
                print(f"    {title} ({len(without_vocab)}): {''.join(sorted(without_vocab))}")
            continue
        if not items:
            continue
        print(f"    {title} ({len(items)}): {kanji_str(items)}")
