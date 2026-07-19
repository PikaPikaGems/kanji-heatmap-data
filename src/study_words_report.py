"""Diagnostic reporting for japanese_study_words_algo (stdout only — writes no files).

Extracted from japanese_study_words_algo so the selection algorithm reads
top-to-bottom without ~250 lines of terminal-formatting interleaved. Everything
here is read-only over `result`; japanese_study_words_algo.main calls print_report
after it has written overrides/japanese_study_words-algo.json.

Constants and helpers this needs (the tag values, the freq-row reader, the TSV
column names) still live on japanese_study_words_algo and are read through the
`sw` alias below — by the time main() imports this module those are defined.
"""

from collections import Counter, defaultdict

from japanese import kanji_count
from jmdict_resolver import classify_pos
from sources import load_textbook_entries, parse_rank
import japanese_study_words_algo as sw


def print_report(result, all_kanji, resolver):
    """Print selection statistics: tier/length/kanji-count/POS/JLPT breakdowns,
    textbook overlap, plus anomaly lists (no-word, no-meaning,
    not-starting-with-kanji, overlaps). Read-only over `result` — it does not
    affect the written output file."""
    selected_flat = [v for v in result.values() if v is not None]
    total = len(selected_flat)
    with_word = sum(1 for v in result.values() if v is not None)
    without   = sum(1 for v in result.values() if v is None)

    words         = [e[0] for e in selected_flat]
    tags          = [e[3] for e in selected_flat]
    length_counts = Counter(len(w) for w in words)
    kc_counts     = Counter(kanji_count(w) for w in words)
    tag_counts    = Counter(tags)

    # Per-tag and per-length groups: (kanji, entry) pairs preserving result order
    tag_groups    = {}
    length_groups = {}
    for k, v in result.items():
        if v is None:
            continue
        tag_groups.setdefault(v[3], []).append((k, v))
        length_groups.setdefault(len(v[0]), []).append((k, v))

    def kanji_compact(pairs):
        return ''.join(k for k, _ in pairs)

    display_tag_priority = {
        sw.OVERRIDE_TAG: 0, "🌱": 1, "☘️": 2, "🌷": 3,
        sw.OUTPUT_TEXTBOOK_TAG: 4, "📚": 5, "🦉": 7, "🌶️": 7
    }
    unknown_tag_priority = 6

    def print_entries(pairs):
        for k, v in sorted(pairs, key=lambda x: display_tag_priority.get(x[1][3], unknown_tag_priority)):
            print(f"{v[3]} {k} → {v[0]} ~ {v[1]} {v[2]}")

    tag_labels = {
        sw.OVERRIDE_TAG: "✏️  manual",
        "🌱": "🌱  BASIC",
        "☘️": "☘️  COMMON",
        "🌷": "🌷  FLUENT",
        sw.OUTPUT_TEXTBOOK_TAG: "📖  textbook",
        "📚": "📚  ADVANCED",
        "🦉": "🦉  UNRANKED",
        "🌶️": "🌶️  NICHE",
    }

    print(f"\n{'─'*44}")
    print(f"  Kanji processed:   {len(all_kanji)}")
    no_meaning = sum(1 for v in result.values() if v is not None and not v[2])
    no_reading = sum(1 for v in result.values() if v is not None and not v[1])

    print(f"  With word:         {with_word}")
    print(f"  Without word:      {without}")
    print(f"  No meaning:        {no_meaning}")
    print(f"  No reading:        {no_reading}")

    known_tags = set(tag_labels.keys())
    unknown_pairs = [(k, v) for k, v in result.items()
                     if v is not None and v[3] not in known_tags]
    n_unknown = len(unknown_pairs)

    print(f"\n  Tag / source breakdown")
    for tag, label in tag_labels.items():
        n = tag_counts.get(tag, 0)
        pct = n / total * 100 if total else 0
        pairs = tag_groups.get(tag, [])
        if tag == "🦉" or tag == "🌶️":
            print(f"    {label}: {n}  ({pct:.1f}%)  {kanji_compact(pairs)}")
            print_entries(pairs)
        else:
            print(f"    {label}: {n}  ({pct:.1f}%)")
        if tag == "📚":
            pct_u = n_unknown / total * 100 if total else 0
            print(f"    🤔  unknown: {n_unknown}  ({pct_u:.1f}%)  {kanji_compact(unknown_pairs)}")
            print_entries(unknown_pairs)

    print(f"\n  Word length")
    for length in sorted(length_counts):
        n = length_counts[length]
        pct = n / total * 100 if total else 0
        if length >= 4:
            pairs = length_groups.get(length, [])
            print(f"    {length} chars: {n}  ({pct:.1f}%)  {kanji_compact(pairs)}")
            print_entries(pairs)
        else:
            print(f"    {length} chars: {n}  ({pct:.1f}%)")

    kc_groups = {}
    for k, v in result.items():
        if v is None:
            continue
        kc_groups.setdefault(kanji_count(v[0]), []).append((k, v))

    print(f"\n  Kanji per word")
    for kc in sorted(kc_counts):
        n = kc_counts[kc]
        pct = n / total * 100 if total else 0
        if kc >= 3:
            pairs = kc_groups.get(kc, [])
            print(f"    {kc} kanji: {n}  ({pct:.1f}%)  {kanji_compact(pairs)}")
            print_entries(pairs)
        else:
            print(f"    {kc} kanji: {n}  ({pct:.1f}%)")

    def stat_line(label, n, indent="    ", members=None):
        pct = f"  ({n/total*100:.1f}%)" if total else ""
        # members: (kanji, word) pairs, printed inline so small outlier buckets
        # are inspectable straight from the log.
        listing = "  " + " ".join(f"{k}→{w}" for k, w in members) if members else ""
        print(f"{indent}{label}: {n}{pct}{listing}")

    # POS buckets over the study word's best JMdict reading (a word with both
    # verb and noun senses counts as a verb — see classify_pos). The "no POS tags"
    # bucket is words with no partOfSpeech tags on the standard resolve path: these
    # ship fine via the rare-writing fallback (resolve_fallback gives a reading +
    # meaning but no POS), so it is NOT the same as "no JMdict entry" (those are
    # dropped above). The bucket key stays a fixed string; only the label differs.
    def pos_bucket(word):
        tags = resolver.pos_profile(word)
        return classify_pos(tags) if tags else "no POS tags"

    pos_groups = {}
    for k, v in result.items():
        if v is not None:
            pos_groups.setdefault(pos_bucket(v[0]), []).append((k, v[0]))
    pos_counts = {bucket: len(pairs) for bucket, pairs in pos_groups.items()}
    adj_all = sum(pos_counts.get(b, 0)
                  for b in ("i-adjective", "na-adjective", "adjective (other)"))

    def takes_suru(word):
        # A word that can take する ("vs", "vs-i", "vs-s", "vs-c"). Most such words
        # are nouns/na-adjectives that verbalise (勉強 → 勉強する); a handful spell
        # する in the word itself (察する).
        return any(p.startswith("vs") for p in resolver.pos_profile(word))

    # Split the verb bucket into words that ARE a plain verb vs words that only
    # become verbs by attaching する. classify_pos already counts 察する (vs-s) as
    # a verb, so the verb bucket contains both kinds.
    verb_pairs = pos_groups.get("verb", [])
    verb_suru = sum(1 for _k, w in verb_pairs if takes_suru(w))
    verb_plain = len(verb_pairs) - verb_suru

    # Every する-capable word across ALL buckets (勉強 sits in noun, 察する in verb),
    # and how many literally contain する in the writing (察する) vs attach it (勉強).
    suru_all = sum(1 for w in words if takes_suru(w))
    suru_literal = sum(1 for w in words if takes_suru(w) and "する" in w)

    print(f"\n  Word class (JMdict POS)")
    stat_line("verb", pos_counts.get("verb", 0))
    stat_line("plain verbs (書く, 語る)", verb_plain, indent="      ")
    stat_line("する verbs (verbalise with する: 察する, 愛する)", verb_suru, indent="      ")
    stat_line("adjective (all)", adj_all)
    stat_line("i-adjective", pos_counts.get("i-adjective", 0), indent="      ")
    stat_line("na-adjective", pos_counts.get("na-adjective", 0), indent="      ")
    stat_line("other adjective", pos_counts.get("adjective (other)", 0),
              indent="      ", members=pos_groups.get("adjective (other)"))
    stat_line("noun", pos_counts.get("noun", 0))
    stat_line("other (adverbs, numerals, expressions…)", pos_counts.get("other", 0))
    stat_line("no POS tags (rare-writing, resolves via fallback — ships fine)",
              pos_counts.get("no POS tags", 0), members=pos_groups.get("no POS tags"))
    # Cross-cutting tally (overlaps the buckets above; does not add to 100%).
    stat_line("する-capable overall (any bucket: 勉強→勉強する, 察する)", suru_all)
    print(f"        of which spell する in the word itself (察する): {suru_literal}; "
          f"the rest attach it (勉強 → 勉強する): {suru_all - suru_literal}")

    # Textbook pools ({word: jlpt} per kanji), shared by the JLPT breakdown
    # (fallback level for words freq-ranks doesn't rank) and the overlap stat.
    tb_pool_cache = {}
    def textbook_pool(kanji):
        if kanji not in tb_pool_cache:
            tb_pool_cache[kanji] = {w: j for w, _r, _e, j in load_textbook_entries(kanji)}
        return tb_pool_cache[kanji]

    # JLPT level from the freq-ranks row of the word itself (TSVs are keyed by
    # the word's first character, so the lookup works for ✏️/📖 picks too),
    # falling back to the textbook pool's own jlpt field.
    rows_cache = {}
    def jlpt_of(kanji, word):
        first = word[0]
        if first not in rows_cache:
            rows_cache[first] = sw.read_freq_rows(first)
        for row in rows_cache[first]:
            if row.get(sw.COL_WORD) == word:
                jlpt = parse_rank(row.get(sw.COL_JLPT))
                if jlpt is not None:
                    return jlpt
        return textbook_pool(kanji).get(word)

    jlpt_counts = Counter(
        jlpt_of(k, v[0]) for k, v in result.items() if v is not None
    )
    print(f"\n  JLPT level (freq-ranks jlpt_level, else the textbook's)")
    for level in (5, 4, 3, 2, 1):
        stat_line(f"N{level}", jlpt_counts.get(level, 0))
    stat_line("no JLPT tag", jlpt_counts.get(None, 0))

    # Textbook overlap: 📖-tagged words came from the textbook pool alone; count
    # how many words tagged from freq-ranks ALSO sit in their kanji's textbook pool.
    overlap_counts = Counter(
        v[3] for k, v in result.items()
        if v is not None and v[3] != sw.OUTPUT_TEXTBOOK_TAG and v[0] in textbook_pool(k)
    )
    n_overlap = sum(overlap_counts.values())
    print(f"\n  Textbook overlap")
    stat_line("tagged 📖 (textbook was the only/best source)",
              tag_counts.get(sw.OUTPUT_TEXTBOOK_TAG, 0))
    stat_line("tagged from another source but ALSO in the textbook pool", n_overlap)
    for tag, n in overlap_counts.most_common():
        stat_line(f"{tag}", n, indent="      ")

    print(f"{'─'*44}")

    if without:
        no_vocab = [k for k, v in result.items() if v is None]
        print(f"\nNo-word kanji ({without}): {''.join(no_vocab)}")

    print(f"")
    no_meaning = [k for k, v in result.items() if v is not None and not v[2]]
    print(f"No meaning kanji ({len(no_meaning)}): {''.join(no_meaning)}")

    for k, v in result.items():
        if v is not None and not v[2]:
            print(k, v)

    starts_with = [(k, v) for k, v in result.items() if v is not None and v[0].startswith(k)]
    not_starts_with = [(k, v) for k, v in result.items() if v is not None and not v[0].startswith(k)]
    print(f"\n  Words starting with kanji:     {len(starts_with)}")
    print(f"  Words NOT starting with kanji: {len(not_starts_with)}")

    if not_starts_with:
        print(f"\nKanji whose study word does NOT start with it ({len(not_starts_with)}):")
        print(f"  {''.join(k for k, _ in not_starts_with)}")
        print_entries(not_starts_with)

    # --- Overlap check ---
    word_to_kanjis = defaultdict(list)
    for k, v in result.items():
        if v:
            word_to_kanjis[v[0]].append(k)
    overlapping = {w: ks for w, ks in word_to_kanjis.items() if len(ks) > 1}
    print(f"\n  Overlapping study words: {len(overlapping)}")
    for w, ks in overlapping.items():
        print(f"    {w}: {''.join(ks)}")
