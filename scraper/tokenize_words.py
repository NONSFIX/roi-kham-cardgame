#!/usr/bin/env python3
"""
tokenize_words.py
─────────────────
Wires the `thai_tokenizer` library (PyThaiNLP backend) into the Roi-Kham word
pipeline as a stronger compound-word segmenter.

Why: decompose_words.py splits a compound only into sub-words that already
exist in words.db. PyThaiNLP ships a ~60k-word dictionary, so it can segment
compounds the in-DB method misses — and any resulting part that *is* in the DB
still lets the parent inherit that part's categories.

This script is READ-ONLY by default: it loads words.db, compares the existing
DP segmenter against the PyThaiNLP tokenizer, and reports the coverage gain.
Pass --apply OUT.db to bake the newly-inferred categories into a COPY of the
database (the original is never touched).

Run (from project root):
  python scraper/tokenize_words.py --word ประจำวัน          # inspect one word
  python scraper/tokenize_words.py --limit 5000             # compare on a sample
  python scraper/tokenize_words.py --limit 5000 --apply Handoff/words_tok.db
  python scraper/tokenize_words.py --engine longest

Only the standard library + thai_tokenizer are needed (no aiosqlite / node).
"""

import sys
import json
import shutil
import sqlite3
import argparse
from pathlib import Path

try:
    from thai_tokenizer import split as tok_split, EngineNotInstalledError
except ImportError:
    sys.exit(
        "thai_tokenizer is not importable. Install it first:\n"
        "  pip install -e ../thai-tokenizer    (adjust path)\n"
        "  # or: pip install pythainlp  and put thai-tokenizer on PYTHONPATH"
    )

ROOT    = Path(__file__).parent.parent
DB_PATH = ROOT / "Handoff" / "words.db"
MAX_CHUNK = 40   # mirrors decompose_words.py


# ── DP segmenter copied from decompose_words.py (DB-vocabulary only) ──────────

def segment_word(word: str, word_set: set) -> list:
    """Longest-match DP split of `word` into sub-words that exist in word_set.
    Returns parts (len >= 2) or [] if no full cover exists. Excludes the word
    itself so it can't trivially match itself."""
    n = len(word)
    if n < 2:
        return []
    reachable = [False] * (n + 1)
    reachable[0] = True
    back = [[] for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(max(0, i - MAX_CHUNK), i):
            chunk = word[j:i]
            if reachable[j] and chunk != word and chunk in word_set:
                reachable[i] = True
                back[i].append(chunk)
    if not reachable[n]:
        return []
    path = []
    pos = n
    while pos > 0:
        if not back[pos]:
            return []
        piece = max(back[pos], key=len)
        path.append(piece)
        pos -= len(piece)
    path.reverse()
    return path if len(path) >= 2 else []


# ── Category inheritance ──────────────────────────────────────────────────────

def inherit_cats(parts: list, cat_map: dict) -> str:
    """Union of categories from any parts that have them (sorted, comma-joined)."""
    cats = set()
    for p in parts:
        for c in cat_map.get(p, "").split(","):
            if c:
                cats.add(c)
    return ",".join(sorted(cats))


def load_db(db_path: Path):
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT word, COALESCE(categories,'') FROM words WHERE pos <> 'PUNC'"
    ).fetchall()
    conn.close()
    word_set = {r[0] for r in rows}
    cat_map  = {r[0]: r[1] for r in rows}
    return word_set, cat_map


def select_targets(db_path: Path, limit: int) -> list:
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT word FROM words "
        "WHERE (categories IS NULL OR categories = '') "
        "AND syllables >= 2 AND pos <> 'PUNC' AND word NOT LIKE '% %' "
        "ORDER BY syllables DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


# ── Modes ─────────────────────────────────────────────────────────────────────

def inspect_one(word: str, word_set: set, cat_map: dict, engine: str) -> None:
    dp = segment_word(word, word_set)
    tok = [p for p in tok_split(word, engine=engine) if len(p) >= 2]
    print(f"\n  Word        : {word}")
    print(f"  DP split    : {' + '.join(dp) if dp else '(no DB-only cover)'}")
    print(f"  Tokenizer   : {' + '.join(tok) if tok else '(none)'}")
    dp_cats  = inherit_cats(dp, cat_map)
    tok_cats = inherit_cats(tok, cat_map)
    print(f"  DP cats     : {dp_cats or '(none)'}")
    print(f"  Tok cats    : {tok_cats or '(none)'}")
    in_db = [p for p in tok if p in word_set]
    print(f"  Tok parts in DB : {' + '.join(in_db) if in_db else '(none)'}")


def compare(targets: list, word_set: set, cat_map: dict, engine: str):
    stats = {
        "total": len(targets),
        "dp_split": 0, "dp_categorized": 0,
        "tok_split": 0, "tok_categorized": 0,
        "tok_only_split": 0,        # tokenizer split where DP failed
        "tok_only_categorized": 0,  # ...and it yielded categories
    }
    inferred = {}   # word -> cats_str  (from tokenizer, where DP gave nothing)
    examples = []

    for word in targets:
        dp  = segment_word(word, word_set)
        tok = [p for p in tok_split(word, engine=engine) if len(p) >= 2]
        dp_cats  = inherit_cats(dp, cat_map) if dp else ""
        tok_cats = inherit_cats(tok, cat_map) if len(tok) >= 2 else ""

        if dp:
            stats["dp_split"] += 1
            if dp_cats:
                stats["dp_categorized"] += 1
        if len(tok) >= 2:
            stats["tok_split"] += 1
            if tok_cats:
                stats["tok_categorized"] += 1

        # Gain: tokenizer found a multi-part split where DP found no cover.
        if not dp and len(tok) >= 2:
            stats["tok_only_split"] += 1
            if tok_cats:
                stats["tok_only_categorized"] += 1
                inferred[word] = tok_cats
                if len(examples) < 12:
                    examples.append((word, tok, tok_cats))

    return stats, inferred, examples


def apply_to_copy(src: Path, out: str, inferred: dict) -> int:
    shutil.copyfile(src, out)
    conn = sqlite3.connect(out)
    written = 0
    for word, cats in inferred.items():
        cur = conn.execute(
            "UPDATE words SET categories = ? "
            "WHERE word = ? AND (categories IS NULL OR categories = '')",
            (cats, word),
        )
        written += cur.rowcount
    conn.commit()
    conn.close()
    return written


def main() -> None:
    p = argparse.ArgumentParser(description="Tokenize/segment Roi-Kham compounds with PyThaiNLP")
    p.add_argument("--word",   help="Inspect a single Thai word and exit")
    p.add_argument("--limit",  type=int, default=5000, help="How many target compounds to compare")
    p.add_argument("--engine", default="newmm", help="thai_tokenizer engine (newmm|longest|...)")
    p.add_argument("--apply",  metavar="OUT.db",
                   help="Write tokenizer-inferred categories into a COPY of words.db")
    p.add_argument("--out",    metavar="report.json", help="Write full comparison stats to JSON")
    args = p.parse_args()

    if not DB_PATH.exists():
        sys.exit(f"Database not found: {DB_PATH}")

    word_set, cat_map = load_db(DB_PATH)
    print(f"Loaded {len(word_set):,} words from {DB_PATH}")

    try:
        if args.word:
            inspect_one(args.word, word_set, cat_map, args.engine)
            return

        targets = select_targets(DB_PATH, args.limit)
        print(f"Comparing on {len(targets):,} uncategorized compounds (engine={args.engine})...\n")
        stats, inferred, examples = compare(targets, word_set, cat_map, args.engine)
    except EngineNotInstalledError as e:
        sys.exit(str(e))

    print("Coverage (of the sampled compounds):")
    print(f"  DP segmenter   — split: {stats['dp_split']:>6,}   categorized: {stats['dp_categorized']:>6,}")
    print(f"  PyThaiNLP tok  — split: {stats['tok_split']:>6,}   categorized: {stats['tok_categorized']:>6,}")
    print(f"  {'─' * 56}")
    print(f"  NEW from tokenizer (DP found nothing):")
    print(f"     extra splits      : {stats['tok_only_split']:>6,}")
    print(f"     extra categorized : {stats['tok_only_categorized']:>6,}")

    if examples:
        print("\n  Examples the tokenizer newly decomposed + categorized:")
        for word, parts, cats in examples:
            print(f"     {word}  →  {' + '.join(parts)}   [{cats}]")

    if args.apply:
        written = apply_to_copy(DB_PATH, args.apply, inferred)
        print(f"\nWrote {written:,} inferred categories into {args.apply} (copy; original untouched).")

    if args.out:
        Path(args.out).write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Stats written to {args.out}")


if __name__ == "__main__":
    main()
