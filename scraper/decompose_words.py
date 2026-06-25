"""
Roi-Kham Compound Word Decomposer
Infers categories for Thai compound words by splitting them into known sub-words.

  ประจำวัน  →  ประ + จำ + วัน
  parent inherits the union of categories from all children that have them.

Algorithm: dynamic-programming longest-match segmentation.
  For each target word, try every possible split into sub-strings that exist
  in the word set. If a full cover is found, collect children's categories.
  Only fills words that have no categories yet (use --overwrite to redo all).

Usage (run from project root):
  python scraper/decompose_words.py --word ประจำวัน    # inspect one word
  python scraper/decompose_words.py --limit 5000       # fill uncategorized compounds
  python scraper/decompose_words.py --overwrite        # re-process all compounds
  python scraper/decompose_words.py --no-export        # skip words.js export at end
"""

import aiosqlite
import argparse
import asyncio
import json
import logging
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT    = Path(__file__).parent.parent
DB_PATH = ROOT / "Handoff" / "words.db"
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Longest Thai word in chars we bother matching as a sub-word chunk
MAX_CHUNK = 40

log_file = LOG_DIR / f"{date.today()}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# SEGMENTATION
# ══════════════════════════════════════════════════════════════════════════════

def segment_word(word: str, word_set: set[str]) -> list[str]:
    """
    DP segmentation: find the longest-first split of `word` into
    sub-strings that all exist in word_set.

    Returns a list of parts with len >= 2, or [] if no valid split exists.
    The word itself is excluded from matching (so it won't trivially match itself).
    """
    n = len(word)
    if n < 2:
        return []

    reachable = [False] * (n + 1)
    reachable[0] = True
    # back[i] = candidate sub-words that end at position i
    back: list[list[str]] = [[] for _ in range(n + 1)]

    for i in range(1, n + 1):
        for j in range(max(0, i - MAX_CHUNK), i):
            chunk = word[j:i]
            if reachable[j] and chunk != word and chunk in word_set:
                reachable[i] = True
                back[i].append(chunk)

    if not reachable[n]:
        return []

    # Walk back using longest match at each step
    path: list[str] = []
    pos = n
    while pos > 0:
        if not back[pos]:
            return []  # gap — no valid cover
        piece = max(back[pos], key=len)
        path.append(piece)
        pos -= len(piece)

    path.reverse()
    return path if len(path) >= 2 else []


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

async def main(args: argparse.Namespace):
    if not DB_PATH.exists():
        log.error("Database not found: %s", DB_PATH)
        sys.exit(1)

    # ── Load entire word+category table into memory ───────────────────────────
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT word, COALESCE(categories, '') FROM words WHERE pos <> 'PUNC'"
        )
        all_rows = await cur.fetchall()

    word_set: set[str]       = {r[0] for r in all_rows}
    cat_map:  dict[str, str] = {r[0]: r[1] for r in all_rows}
    log.info("Loaded %d words into memory", len(word_set))

    # ── Select target words ───────────────────────────────────────────────────
    async with aiosqlite.connect(DB_PATH) as db:
        if args.word:
            targets = [args.word]

        elif args.overwrite:
            cur = await db.execute(
                "SELECT word FROM words "
                "WHERE syllables >= 2 AND pos <> 'PUNC' AND word NOT LIKE '% %' "
                "ORDER BY syllables DESC LIMIT ?",
                (args.limit,),
            )
            targets = [r[0] for r in await cur.fetchall()]

        else:
            # Default: only words that have no categories yet
            cur = await db.execute(
                "SELECT word FROM words "
                "WHERE (categories IS NULL OR categories = '') "
                "AND syllables >= 2 AND pos <> 'PUNC' AND word NOT LIKE '% %' "
                "ORDER BY syllables DESC LIMIT ?",
                (args.limit,),
            )
            targets = [r[0] for r in await cur.fetchall()]

        log.info("Targets: %d compound words to decompose", len(targets))

        stats = {
            "total":       len(targets),
            "split":       0,
            "categorized": 0,
            "no_split":    0,
        }
        batch: list[tuple[str, str]] = []   # (cats_str, word)

        for word in targets:
            parts = segment_word(word, word_set)

            # ── No valid split ────────────────────────────────────────────────
            if not parts:
                stats["no_split"] += 1
                if args.word:
                    print(f"  {word}  →  (no valid split found)")
                continue

            stats["split"] += 1

            # ── Inherit categories from children ──────────────────────────────
            inherited: set[str] = set()
            for p in parts:
                for c in cat_map.get(p, "").split(","):
                    if c:
                        inherited.add(c)

            cats_str = ",".join(sorted(inherited))

            if args.word:
                parts_display = " + ".join(
                    f"{p}[{cat_map.get(p)}]" if cat_map.get(p) else p
                    for p in parts
                )
                print(f"\n  Word   : {word}")
                print(f"  Split  : {parts_display}")
                print(f"  Cats   : {cats_str or '(none — children have no categories yet)'}")

            if cats_str:
                stats["categorized"] += 1
                batch.append((cats_str, word))

            # ── Flush every 100 rows ──────────────────────────────────────────
            if len(batch) >= 100:
                await _flush(db, batch, args.overwrite)
                batch.clear()
                log.info("  … split=%d  categorized=%d  no_split=%d",
                         stats["split"], stats["categorized"], stats["no_split"])

        if batch:
            await _flush(db, batch, args.overwrite)

    # ── Summary ───────────────────────────────────────────────────────────────
    summary = {
        "total":               stats["total"],
        "successfully_split":  stats["split"],
        "categories_inferred": stats["categorized"],
        "no_valid_split":      stats["no_split"],
    }
    log.info("=== DONE === %s", json.dumps(summary))
    print(json.dumps(summary, ensure_ascii=False))

    if not args.no_export:
        _run_export()


async def _flush(db: aiosqlite.Connection, batch: list[tuple[str, str]], overwrite: bool):
    if overwrite:
        await db.executemany(
            "UPDATE words SET categories=? WHERE word=?",
            batch,
        )
    else:
        await db.executemany(
            "UPDATE words SET categories=? "
            "WHERE word=? AND (categories IS NULL OR categories = '')",
            batch,
        )
    await db.commit()


def _run_export():
    log.info("Running export_words.js …")
    result = subprocess.run(
        ["node", str(ROOT / "export_words.js")],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    if result.returncode == 0:
        last_line = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "ok"
        log.info("Export OK: %s", last_line)
        print(last_line)
    else:
        log.error("Export FAILED:\n%s", result.stderr)
        print("ERROR: export_words.js failed — see log", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Infer categories for Thai compound words via sub-word decomposition"
    )
    parser.add_argument("--word",      help="Inspect a single Thai word")
    parser.add_argument("--limit",     type=int, default=5000,
                        help="Max words to process (default 5000)")
    parser.add_argument("--overwrite", action="store_true",
                        help="Re-process words that already have categories")
    parser.add_argument("--no-export", dest="no_export", action="store_true",
                        help="Skip running export_words.js at the end")
    args = parser.parse_args()
    asyncio.run(main(args))
