#!/usr/bin/env python3
"""
Inspect overrides/kanji_to_remove.json: for each removed kanji, show its frequency
ranks (JPDB, Jiten, Google, Netflix) and whether it appears in KKLC and WaniKani,
to decide which (if any) are worth bringing back.

A kanji is a bring-back CANDIDATE if it is ranked within 1–2000 in at least one of
the four frequency sources. The last two columns help judge whether it would even
get a decent study word:
  start = best v3 tag of a word that STARTS with the kanji (current rule)
  has   = best v3 tag of any word CONTAINING the kanji (the relaxed rule)

Run from the project root: python3 src/inspect_removed_kanji.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import japanese
import kanji_load
from sources import load_json, load_v3_entries

TOP = 2000  # "common" threshold
TAG_ORDER = {"🌱": 0, "☘️": 1, "🌷": 2, "📚": 4, "🦉": 5}


def best_v3_tag(kanji, starts_with):
    """Best (most frequent) v3 tag among words that start with / contain `kanji`,
    restricted to 1–2 kanji all-Japanese words; '-' if none."""
    best = None
    for w, r, t, e in load_v3_entries(kanji):
        if not japanese.is_all_japanese(w) or not (1 <= japanese.kanji_count(w) <= 2):
            continue
        if starts_with and not w.startswith(kanji):
            continue
        if not starts_with and kanji not in w:
            continue
        if best is None or TAG_ORDER.get(t, 9) < TAG_ORDER.get(best, 9):
            best = t
    return best or "-"


def main():
    removed = load_json("overrides/kanji_to_remove.json", {}).get("data", [])
    merged = load_json("input/merged_kanji.json", {})
    jpdb = kanji_load.load_jpdb_frequency()
    jiten = kanji_load.load_jiten_frequency()
    kklc = kanji_load.load_kklc_order()

    def google(k):
        return _to_int(merged.get(k, {}).get("frequency", {}).get("ultimate", {}).get("google"))

    def netflix(k):
        return _to_int(merged.get(k, {}).get("frequency", {}).get("ohTalkWhoNetflix", {}).get("rank1224"))

    def jpdb_rank(k):
        r = jpdb.get(k)
        return r if r and r != 50_000 else None

    def wk(k):
        return merged.get(k, {}).get("waniKani", {}).get("level")

    rows = []
    for k in removed:
        ranks = {
            "jpdb": jpdb_rank(k),
            "jiten": jiten.get(k),
            "google": google(k),
            "netflix": netflix(k),
        }
        present = [r for r in ranks.values() if r]
        best = min(present) if present else None
        rows.append({
            "k": k, "ranks": ranks, "best": best,
            "kklc": k in kklc, "wk": wk(k),
            "start": best_v3_tag(k, True), "has": best_v3_tag(k, False),
        })

    def fmt(r):
        return None if r is None else (r if r <= 9999 else ">9999")

    def line(row):
        rk = row["ranks"]
        cells = "  ".join(f"{name}={fmt(rk[name]) if rk[name] else '–':>5}"
                           for name in ("jpdb", "jiten", "google", "netflix"))
        kklc = "KKLC" if row["kklc"] else "    "
        wk = f"WK{row['wk']:<2}" if row["wk"] else "    "
        return (f"  {row['k']}  {cells}  {kklc} {wk}  "
                f"start:{row['start']} has:{row['has']}")

    candidates = sorted((r for r in rows if r["best"] and r["best"] <= TOP),
                        key=lambda r: r["best"])
    notable = sorted((r for r in rows if not (r["best"] and r["best"] <= TOP)
                      and (r["kklc"] or r["wk"])),
                     key=lambda r: (r["best"] or 10**9))
    rest = [r for r in rows if r not in candidates and r not in notable]

    print(f"Removed kanji: {len(removed)}\n")
    print(f"=== IN TOP {TOP} of ≥1 frequency source — BRING-BACK CANDIDATES ({len(candidates)}) ===")
    for r in candidates:
        print(line(r))
    print(f"\n=== NOT top-{TOP}, but in KKLC or WaniKani ({len(notable)}) ===")
    for r in notable:
        print(line(r))
    print(f"\n=== Neither common nor in KKLC/WK — genuinely rare ({len(rest)}) ===")
    print("  " + "".join(r["k"] for r in rest))

    # Summary
    in_kklc = sum(1 for r in rows if r["kklc"])
    in_wk = sum(1 for r in rows if r["wk"])
    good_word = sum(1 for r in candidates if r["has"] in ("🌱", "☘️"))
    print("\n-------- summary --------")
    print(f"top-{TOP} in ≥1 source : {len(candidates)}")
    print(f"in KKLC               : {in_kklc}")
    print(f"in WaniKani           : {in_wk}")
    print(f"candidates that also have a 🌱/☘️ word (good study word under relaxed rule): {good_word}")


def _to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    main()
