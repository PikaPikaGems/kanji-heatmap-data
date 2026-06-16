# Compares input/kanji_vocab.json against overrides/kanji_vocab-algo.json and reports
# how many kanji/words were changed, listing each substitution (old word -> new word).

from sources import load_json

original = load_json("input/kanji_vocab.json", {})
overrides = load_json("overrides/kanji_vocab-algo.json", {})

affected_kanji = 0
affected_words = 0
changes = []

for kanji, override_words in overrides.items():
    orig_words = original.get(kanji, [])
    orig_set = set(orig_words)
    override_set = set(override_words)

    removed = orig_set - override_set
    added = override_set - orig_set

    if not removed and not added:
        continue

    affected_kanji += 1
    affected_words += len(removed)

    for old, new in zip(removed, added):
        changes.append((kanji, old, new))

for i, (kanji, old, new) in enumerate(changes, 1):
    print(f"{i}. {kanji} {old} -> {new}")

print()
print(f"Affected kanji: {affected_kanji}")
print(f"Affected words: {affected_words}")
