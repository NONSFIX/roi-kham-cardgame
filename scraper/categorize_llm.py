"""
Roi-Kham Local-LLM Word Categorizer
Fills the 'categories' column in words.db using a local Ollama model.

Talks to the local Ollama HTTP API (http://localhost:11434) — no cloud, no API key.
Default model: qwen3.5:2b  (override with --model). No extra pip deps (stdlib only).

Usage (run from project root):
  python scraper/categorize_llm.py --word แมว              # test one word
  python scraper/categorize_llm.py --limit 50 --no-export  # small sample run
  python scraper/categorize_llm.py                         # all uncategorized words
  python scraper/categorize_llm.py --overwrite             # re-do every word
  python scraper/categorize_llm.py --model qwen2.5:7b      # use a different model

After a run it re-exports prototype/words.js (unless --no-export).
Safe to stop and resume — it only fills words that are still empty (unless --overwrite).
"""

import argparse
import json
import logging
import re
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

# Force UTF-8 on Windows consoles (cp1252 can't encode Thai)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT     = Path(__file__).parent.parent
DB_PATH  = ROOT / "Handoff" / "words.db"
LOG_DIR  = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

OLLAMA_URL = "http://localhost:11434"

# ── The 16 game categories (value -> Thai gloss). MUST match prototype/index.html ──
CATEGORIES: dict[str, str] = {
    "animal":     "สัตว์",
    "plant":      "พืช ต้นไม้",
    "food":       "อาหารคาว/ของกิน",
    "drink":      "เครื่องดื่ม",
    "fruit":      "ผลไม้",
    "vegetable":  "ผัก",
    "vehicle":    "ยานพาหนะ",
    "house_item": "ของใช้ในบ้าน เครื่องเรือน",
    "body_part":  "อวัยวะ ส่วนของร่างกาย",
    "family":     "เครือญาติ สมาชิกครอบครัว",
    "color":      "สี",
    "shape":      "รูปร่าง รูปทรง",
    "nature":     "ธรรมชาติ ภูมิประเทศ",
    "weather":    "สภาพอากาศ ลมฟ้าอากาศ",
    "sport":      "กีฬา",
    "hobby":      "งานอดิเรก กิจกรรมยามว่าง",
}
ALLOWED = set(CATEGORIES)

# JSON schema constraining the model's structured output.
# Categories only — foreign/royal flagging proved too noisy on small models and is
# left to rule-based detection / the scraper.
ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "word":       {"type": "string"},
        "categories": {"type": "array", "items": {"type": "string", "enum": sorted(ALLOWED)}},
    },
    "required": ["word", "categories"],
}
BATCH_SCHEMA = {"type": "array", "items": ITEM_SCHEMA}

# ── Logging ───────────────────────────────────────────────────────────────────
log_file = LOG_DIR / f"{date.today()}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(log_file, encoding="utf-8"),
              logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# OLLAMA
# ══════════════════════════════════════════════════════════════════════════════

def _post(path: str, payload: dict, timeout: int = 120) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL + path, data=data,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def health_check(model: str) -> None:
    try:
        with urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=5) as r:
            tags = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        log.error("Cannot reach Ollama at %s (%s).", OLLAMA_URL, e)
        log.error("Start it with:  ollama serve")
        sys.exit(1)

    names = {m["name"] for m in tags.get("models", [])}
    # match with or without :latest tag
    if model not in names and f"{model}:latest" not in names and \
       not any(n.split(":")[0] == model.split(":")[0] for n in names):
        log.error("Model '%s' not found in Ollama. Available: %s", model, ", ".join(sorted(names)) or "(none)")
        log.error("Pull it with:  ollama pull %s", model)
        sys.exit(1)
    log.info("Ollama OK — using model '%s'", model)


SYSTEM_PROMPT = (
    "You are a Thai lexicographer. For each Thai word, decide which of a fixed set of "
    "concrete semantic categories it belongs to.\n"
    "CRITICAL: MOST Thai words fit NONE of the categories — return an empty list for them. "
    "Only assign a category when the word itself NAMES a concrete member of that category "
    "(a physical thing, creature, colour, body part, etc.).\n"
    "Return an EMPTY list for abstract, grammatical, legal, administrative, action, or "
    "quality words — e.g. กฎหมาย (law), การเมือง (politics), ความรัก (love), วิ่ง (to run), "
    "และ (and), abbreviations like ก.ล.ต. — none of these get a category.\n"
    "Do NOT assign a category just because a word is topically related; it must literally "
    "denote a member. กฎจราจร (traffic law) is NOT a vehicle.\n"
    "Return strictly valid JSON matching the schema; no explanations."
)

# Few-shot examples steer the model toward 'empty for abstract' and exact-denotation tagging.
FEWSHOT = (
    "Examples:\n"
    '  แมว -> ["animal"]      รถยนต์ -> ["vehicle"]    กล้วย -> ["fruit"]\n'
    '  แดง -> ["color"]       พ่อ -> ["family"]        เก้าอี้ -> ["house_item"]\n'
    '  กฎหมาย -> []           กฎจราจร -> []            การเมือง -> []\n'
    '  วิ่ง -> []             และ -> []               ก.ล.ต. -> []\n'
)


def _build_prompt(words: list[str]) -> str:
    cat_lines = "\n".join(f"  - {k}: {v}" for k, v in CATEGORIES.items())
    word_lines = "\n".join(f"  {i+1}. {w}" for i, w in enumerate(words))
    return (
        f"Categories (value: meaning):\n{cat_lines}\n\n"
        f"{FEWSHOT}\n"
        f"Classify these {len(words)} Thai words. Return a JSON array with one object per "
        f"word, each {{word, categories[]}}, preserving the exact word spelling. "
        f"Remember: when unsure, return an empty categories list.\n\nWords:\n{word_lines}"
    )


def _strip_think(s: str) -> str:
    return re.sub(r"<think>.*?</think>", "", s, flags=re.DOTALL).strip()


def query_batch(model: str, words: list[str]) -> dict[str, set]:
    """Return {word: set(categories)} for words the model answered."""
    payload = {
        "model": model,
        "prompt": _build_prompt(words),
        "system": SYSTEM_PROMPT,
        "stream": False,
        "think": False,                 # qwen3 is a thinking model — turn it off
        "format": BATCH_SCHEMA,
        "options": {"temperature": 0},
    }
    try:
        resp = _post("/api/generate", payload)
    except Exception as e:
        log.warning("Ollama request failed for batch of %d: %s", len(words), e)
        return {}

    raw = _strip_think(resp.get("response", ""))
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("Bad JSON from model; will retry per-word. Snippet: %s", raw[:120])
        return {}

    out: dict[str, set] = {}
    wanted = set(words)
    for it in items if isinstance(items, list) else []:
        w = (it.get("word") or "").strip()
        if w not in wanted:
            continue
        out[w] = {c for c in it.get("categories", []) if c in ALLOWED}
    return out


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def ensure_schema(con: sqlite3.Connection) -> None:
    """Add the cat_checked column if missing (marks words the LLM has processed,
    so empty-category results aren't re-queried on every resumed run)."""
    cols = {r[1] for r in con.execute("PRAGMA table_info(words)").fetchall()}
    if "cat_checked" not in cols:
        con.execute("ALTER TABLE words ADD COLUMN cat_checked INT DEFAULT 0")
        con.commit()
        log.info("Added column: cat_checked")


def select_words(con: sqlite3.Connection, args) -> list[str]:
    if args.word:
        return [args.word]
    if args.overwrite:
        q = ("SELECT word FROM words WHERE pos <> 'PUNC' AND word <> '' "
             "ORDER BY word LIMIT ?")
    else:
        q = ("SELECT word FROM words "
             "WHERE (cat_checked IS NULL OR cat_checked = 0) "
             "AND pos <> 'PUNC' AND word <> '' ORDER BY word LIMIT ?")
    return [r[0] for r in con.execute(q, (args.limit,)).fetchall()]


def main(args):
    if not DB_PATH.exists():
        log.error("Database not found: %s", DB_PATH)
        sys.exit(1)
    health_check(args.model)

    con = sqlite3.connect(DB_PATH)
    ensure_schema(con)
    words = select_words(con, args)
    total = len(words)
    log.info("Words to categorize: %d  (model=%s, batch=%d)", total, args.model, args.batch)
    if total == 0:
        print(json.dumps({"total": 0}))
        return

    stats = {"total": total, "categorized": 0}
    writes: list[tuple] = []
    t0 = time.time()

    def flush():
        if not writes:
            return
        if args.overwrite:
            con.executemany(
                "UPDATE words SET categories=?, cat_checked=1 WHERE word=?", writes)
        else:
            con.executemany(
                "UPDATE words SET categories=?, cat_checked=1 "
                "WHERE word=? AND (cat_checked IS NULL OR cat_checked=0)", writes)
        con.commit()
        writes.clear()

    for start in range(0, total, args.batch):
        chunk = words[start:start + args.batch]
        results = query_batch(args.model, chunk)

        # Per-word fallback for any word the batch didn't answer
        missing = [w for w in chunk if w not in results]
        if missing and not args.word:
            for w in missing:
                results.update(query_batch(args.model, [w]))

        for w in chunk:
            r = results.get(w)
            if r is None:
                continue
            cats_str = ",".join(sorted(r))
            writes.append((cats_str, w))
            if cats_str:
                stats["categorized"] += 1
                log.info("  %-22s -> %s", w, cats_str)

        if len(writes) >= 50:
            flush()

        done = min(start + args.batch, total)
        rate = done / max(time.time() - t0, 0.001)
        eta  = (total - done) / max(rate, 0.001)
        log.info("[%d/%d] %.1f words/s  cat=%d  eta=%.0fs",
                 done, total, rate, stats["categorized"], eta)

    flush()
    con.close()

    summary = {
        "total": stats["total"],
        "categorized": stats["categorized"],
        "coverage_pct": round(stats["categorized"] / stats["total"] * 100, 1),
        "seconds": round(time.time() - t0, 1),
    }
    log.info("=== DONE === %s", json.dumps(summary))
    print(json.dumps(summary, ensure_ascii=False))

    if not args.no_export:
        _run_export()


def _run_export():
    log.info("Running export_words.js …")
    result = subprocess.run(["node", str(ROOT / "export_words.js")],
                            capture_output=True, text=True, cwd=str(ROOT))
    if result.returncode == 0:
        line = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "ok"
        log.info("Export OK: %s", line)
        print(line)
    else:
        log.error("Export FAILED:\n%s", result.stderr)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Roi-Kham local-LLM word categorizer")
    p.add_argument("--word",      help="Test a single Thai word")
    p.add_argument("--limit",     type=int, default=2000, help="Max words (default 2000)")
    p.add_argument("--model",     default="qwen3.5:2b", help="Ollama model (default qwen3.5:2b)")
    p.add_argument("--batch",     type=int, default=10, help="Words per request (default 10)")
    p.add_argument("--overwrite", action="store_true", help="Re-categorize every word")
    p.add_argument("--no-export", dest="no_export", action="store_true",
                   help="Skip export_words.js at the end")
    args = p.parse_args()
    main(args)
