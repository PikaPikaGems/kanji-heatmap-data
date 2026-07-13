"""Keyword sourcing shared by the keyword algorithm and the final build.

`raw_keyword` picks a single best English keyword for a kanji from the same raw
sources `keywords_algo.py` uses (priority j → k → w), and
`base_keyword` falls back to the keyword the build derives from input/merged_kanji.json.

The build uses these to supply keywords for kanji that appear as component parts or
inside sample/study words but are NOT shipped (not in filtered_kanji.json), so those
characters still get a label even though they aren't in output/kanji_main.json.
"""

import re

import kanji_extract
from sources import load_json

_VALID = re.compile(r'^[a-z]+( [a-z]+)*$')


def is_valid_keyword(phrase):
    """Valid: lowercase roman-alphabet word or phrase (letters and spaces only)."""
    return bool(_VALID.match((phrase or '').strip()))


def load_raw_keyword_sources():
    """Load the three raw keyword maps: (j, w, k)."""
    return (
        load_json('raw/kanji-keywords-j.json', {}),
        load_json('raw/kanji-keywords-w.json', {}),
        load_json('raw/kanji-keywords-k.json', {}),
    )


def _validated(values):
    """Strip/lowercase each value and keep only valid keywords, preserving order."""
    out = []
    for v in values:
        v = (str(v) if v is not None else '').strip().lower()
        if is_valid_keyword(v):
            out.append(v)
    return out


def raw_candidates(kanji, keywords_j, keywords_w, keywords_k):
    """Ordered, de-duplicated keyword candidates for `kanji` from the raw sources.

    Order: j → first k → first w → the remaining k/w candidates by length
    (shortest first). This is the candidate priority the keyword algorithm's
    greedy-uniqueness pass consumes; `raw_keyword` returns the first of these.

    keywords_k values are comma-separated strings; keywords_w values are lists.
    """
    j = (keywords_j.get(kanji, '') or '').strip().lower()
    pj = [j] if is_valid_keyword(j) else []

    pk = _validated((keywords_k.get(kanji, '') or '').split(','))
    w_raw = keywords_w.get(kanji, [])
    pw = _validated(w_raw if isinstance(w_raw, list) else [w_raw])

    sorted_rest = sorted(pk[1:] + pw[1:], key=len)
    ordered = pj + pk[:1] + pw[:1] + sorted_rest

    seen = []
    for c in ordered:
        if c not in seen:
            seen.append(c)
    return seen


def raw_keyword(kanji, keywords_j, keywords_w, keywords_k):
    """Best keyword for `kanji` from the raw sources, priority j → k → w, or None."""
    candidates = raw_candidates(kanji, keywords_j, keywords_w, keywords_k)
    return candidates[0] if candidates else None


def base_keyword(kanji, merged_kanji):
    """The keyword the build would derive for `kanji` from input/merged_kanji.json
    (kanji_extract.get_keyword, no overrides), or None when it isn't in the dataset."""
    info = dict(merged_kanji.get(kanji) or {})
    if not info:
        return None
    info['kanji'] = kanji
    return kanji_extract.get_keyword(info, {})
