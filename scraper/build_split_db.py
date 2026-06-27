#!/usr/bin/env python3
"""
build_split_db.py
─────────────────
Produce a NEW database where every word carries both its WHOLE form and its
SPLIT form. The split is the longest-match decomposition into sub-words that
exist in the database (same DP segmenter used by decompose_words.py).

    ประจำวัน   ->  split = "ประจำ + วัน"
    รถไฟ       ->  split = "รถ + ไฟ"      (if รถ and ไฟ are both in the DB)
    สุนัข       ->  split = "สุนัข"          (no decomposition -> stays whole)

The original words.db is never modified — output goes to a fresh copy.

Run (from project root):
  python scraper/build_split_db.py                       # all words -> Handoff/words_split.db
  python scraper/build_split_db.py --out my.db           # choose output path
  python scraper/build_split_db.py --only-split          # keep ONLY words that decompose
  python scraper/build_split_db.py --sep " + "           # change the join separator

Standard library only.
"""

import sys
import shutil
import sqlite3
import argparse
from pathlib import Path

ROOT    = Path(__file__).parent.parent
DB_PATH = ROOT / "Handoff" / "words.db"
MAX_CHUNK = 40   # mirrors decompose_words.py


def segment_word(word: str, word_set: set) -> list:
    """Longest-match DP split into sub-words that exist in word_set.
    Returns parts (len >= 2) or [] if no full cover. Excludes the word itself."""
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


def main() -> None:
    p = argparse.ArgumentParser(description="Build a words.db copy with a whole+split column")
    p.add_argument("--out", default=str(ROOT / "Handoff" / "words_split.db"),
                   help="output database path")
    p.add_argument("--sep", default=" + ", help="separator between split parts")
    p.add_argument("--only-split", action="store_true",
                   help="keep only words that actually decompose (drop whole-only words)")
    args = p.parse_args()

    if not DB_PATH.exists():
        sys.exit(f"Database not found: {DB_PATH}")

    # Build the vocabulary (exclude punctuation, same as decompose_words.py).
    src = sqlite3.connect(DB_PATH)
    word_set = {r[0] for r in src.execute("SELECT word FROM words WHERE pos <> 'PUNC'")}
    all_words = [r[0] for r in src.execute("SELECT word FROM words")]
    src.close()
    print(f"Loaded {len(all_words):,} words ({len(word_set):,} in vocabulary)")

    # Fresh copy → original untouched.
    shutil.copyfile(DB_PATH, args.out)
    conn = sqlite3.connect(args.out)

    # Add the split column (idempotent).
    cols = {r[1] for r in conn.execute("PRAGMA table_info(words)")}
    if "split" not in cols:
        conn.execute("ALTER TABLE words ADD COLUMN split TEXT DEFAULT ''")

    decomposed = 0
    batch = []
    for word in all_words:
        parts = segment_word(word, word_set)
        if parts:
            split_str = args.sep.join(parts)
            decomposed += 1
        else:
            split_str = word            # whole word, no split found
        batch.append((split_str, word))
        if len(batch) >= 2000:
            conn.executemany("UPDATE words SET split = ? WHERE word = ?", batch)
            batch.clear()
    if batch:
        conn.executemany("UPDATE words SET split = ? WHERE word = ?", batch)

    if args.only_split:
        # Drop rows that did not decompose (split == word).
        conn.execute("DELETE FROM words WHERE split = word")
    conn.commit()

    kept = conn.execute("SELECT COUNT(*) FROM words").fetchone()[0]
    conn.close()

    print(f"Decomposed (split into parts) : {decomposed:,}")
    print(f"Whole only (no split)         : {len(all_words) - decomposed:,}")
    print(f"Rows in new database          : {kept:,}")
    print(f"\nNew database written to: {args.out}")


if __name__ == "__main__":
    main()
