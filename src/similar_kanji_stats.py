#!/usr/bin/env python3
"""
Prints counts for output/similar-kanjis.json, mainly about the unshipped
kanji in it (kanji we don't ship that build_similar_kanji.py adds because
they look almost the same as a shipped one):

  - how many shipped kanji have at least one unshipped lookalike
  - how many unshipped lookalike entries there are, and how many distinct
    unshipped kanji
  - where in the lists they land (they're ranked by the same score as the
    shipped kanji)

Run from the project root, after the build:
python3 src/similar_kanji_stats.py
"""

from collections import Counter

import sources

SIMILAR_PATH = "output/similar-kanjis.json"
FILTERED_KANJI_PATH = "intermediate/filtered_kanji.json"


def main():
    similar = sources.load_json(SIMILAR_PATH)
    shipped = set(sources.load_json(FILTERED_KANJI_PATH))

    entries = [(kanji, other, i + 1) for kanji, others in similar.items() for i, other in enumerate(others)]
    unshipped = [(kanji, other, pos) for kanji, other, pos in entries if other not in shipped]
    with_unshipped = {kanji for kanji, _, _ in unshipped}
    distinct = Counter(other for _, other, _ in unshipped)
    lengths = Counter(len(others) for others in similar.values())

    print(f"Shipped kanji:                              {len(similar)}")
    print(f"Similar entries:                            {len(entries)}")
    print(f"List lengths:                               "
          + ", ".join(f"{n} kanji have {length}" for length, n in sorted(lengths.items())))
    print()
    print(f"Kanji with at least one unshipped lookalike: {len(with_unshipped)}")
    print(f"Unshipped lookalike entries:                 {len(unshipped)}")
    print(f"Distinct unshipped kanji:                    {len(distinct)}")
    print()
    print("Unshipped lookalikes per kanji:")
    per_kanji = Counter(Counter(kanji for kanji, _, _ in unshipped).values())
    for count, n in sorted(per_kanji.items()):
        print(f"  {count}: {n} kanji")
    print()
    print("Position of unshipped lookalikes in their list (1 = most similar):")
    positions = Counter(pos for _, _, pos in unshipped)
    for pos, n in sorted(positions.items()):
        print(f"  {pos:>2}: {n}")
    print()
    print("Unshipped kanji listed for more than one kanji:")
    shared = [(other, n) for other, n in distinct.most_common() if n > 1]
    print("  " + "  ".join(f"{other}×{n}" for other, n in shared) if shared else "  none")


if __name__ == "__main__":
    main()
