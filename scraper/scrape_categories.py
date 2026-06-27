"""
Roi-Kham Category Scraper
Fills the 'categories', 'is_foreign', 'is_royal' columns in words.db
by querying Thai dictionary sources.

Sources (tried in order until categories found):
  1. Royal Institute Dictionary (ORST) — dictionary.orst.go.th
  2. Longdo Dictionary             — dict.longdo.com
  3. Thai Wiktionary               — th.wiktionary.org

After scraping, automatically re-exports prototype/words.js via export_words.js.
Use --no-export to skip the export step.

Usage:
  python scraper/scrape_categories.py                    # all words (up to --limit)
  python scraper/scrape_categories.py --new-only         # skip words that already have categories
  python scraper/scrape_categories.py --limit 500        # first N words
  python scraper/scrape_categories.py --word สุนัข        # single word test
  python scraper/scrape_categories.py --source longdo    # force specific source
  python scraper/scrape_categories.py --no-export        # skip export_words.js at end

Run from project root:
  cd "C:\\Users\\ASUS\\Documents\\Vault\\Claude Vault\\roi-kham-cardgame"
  pip install -r scraper/requirements.txt
  python scraper/scrape_categories.py --word สุนัข
"""

import asyncio
import aiohttp
import aiosqlite
import argparse
import json
import logging
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote

try:
    from bs4 import BeautifulSoup
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
    RICH = True
except ImportError:
    RICH = False

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT    = Path(__file__).parent.parent
DB_PATH = ROOT / "Handoff" / "words.db"
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# ── Scraping config ─────────────────────────────────────────────────────────────
DELAY_SEC  = 0.30   # seconds between requests per source
CONCUR     = 6      # max parallel requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; RoiKhamCategorizer/1.0; educational research)",
    "Accept-Language": "th-TH,th;q=0.9,en;q=0.8",
}

# ── Category keyword map ────────────────────────────────────────────────────────
# Keys must match the game's category values exactly.
KEYWORD_MAP: dict[str, list[str]] = {
    "animal":     ["สัตว์", "นก", "ปลา", "แมลง", "สัตว์เลี้ยง", "สัตว์ป่า", "สัตวศาสตร์",
                   "zool", "zoology", "สัตววิทยา", "ปักษา", "ปลา", "สัตว์เลื้อยคลาน"],
    "plant":      ["พืช", "ต้นไม้", "ดอกไม้", "หญ้า", "ไม้ยืนต้น", "พืชพรรณ",
                   "bot", "botany", "พฤกษศาสตร์", "พฤกษา", "ไม้ดอก", "ไม้ผล"],
    "food":       ["อาหาร", "กับข้าว", "อาหารคาว", "อาหารหวาน", "ขนม", "กินได้",
                   "cuisine", "dish", "meal", "snack"],
    "drink":      ["เครื่องดื่ม", "น้ำดื่ม", "ชา", "กาแฟ", "น้ำผลไม้", "beverage", "drink"],
    "vehicle":    ["ยานพาหนะ", "รถ", "เรือ", "เครื่องบิน", "พาหนะ", "ยานยนต์",
                   "vehicle", "transport", "conveyance"],
    "house_item": ["เครื่องใช้ในบ้าน", "เฟอร์นิเจอร์", "เครื่องใช้", "ของใช้",
                   "furniture", "household", "utensil", "appliance"],
    "body_part":  ["อวัยวะ", "ร่างกาย", "กายวิภาค", "กาย",
                   "anat", "anatomy", "body part", "organ", "limb"],
    "family":     ["ครอบครัว", "ญาติ", "พ่อแม่", "พี่น้อง",
                   "family", "kinship", "relative", "kin"],
    "color":      ["สี", "สีสัน", "colour", "color", "hue"],
    "shape":      ["รูปร่าง", "รูปทรง", "เรขาคณิต", "รูปแบบ",
                   "shape", "geometry", "figure"],
    "nature":     ["ธรรมชาติ", "ภูมิศาสตร์", "ป่า", "ภูเขา", "แม่น้ำ",
                   "nature", "geography", "terrain", "environment", "landscape"],
    "weather":    ["อากาศ", "สภาพอากาศ", "ฝน", "พายุ", "ลม", "เมฆ",
                   "weather", "climate", "atmospheric"],
    "sport":      ["กีฬา", "การแข่งขัน", "ออกกำลังกาย",
                   "sport", "game", "athletics", "competition"],
    "hobby":      ["งานอดิเรก", "กิจกรรมยามว่าง", "กิจกรรม",
                   "hobby", "pastime", "recreation", "leisure"],
    "fruit":      ["ผลไม้", "ลูกไม้", "fruit"],
    "vegetable":  ["ผัก", "พืชผัก", "ผักสด", "vegetable", "veggie", "legume"],
}

# Words/phrases that indicate foreign loanwords
FOREIGN_MARKERS = [
    "ทับศัพท์", "ภาษาต่างประเทศ", "ยืมมาจาก", "มาจากภาษา",
    "borrowed from", "loanword", "from english", "from french",
    "from chinese", "from japanese", "from malay", "from sanskrit",
    "from pali", "from khmer",
]

# Words/phrases that indicate royal vocabulary
ROYAL_MARKERS = [
    "ราชาศัพท์", "ราชาศัพย์", "คำราชาศัพท์", "[ราชา]",
    "royal vocabulary", "royal word", "royal thai",
]

# ── Logging setup ───────────────────────────────────────────────────────────────
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

console = Console() if RICH else None


# ══════════════════════════════════════════════════════════════════════════════
# PARSING HELPERS
# ══════════════════════════════════════════════════════════════════════════════

# ── Word-boundary matching (thai_tokenizer) ─────────────────────────────────────
# Raw substring matching is unsafe for Thai: short keywords match INSIDE unrelated
# words (e.g. 'สี' inside 'เสียหาย' → false 'color'; 'รถ' inside 'ปรารถนา' →
# false 'vehicle'). We tokenize the scraped definition into real words and match
# Thai keywords only at word boundaries. English keywords keep substring matching
# (they're space-separated, so it's already safe). Falls back to the old substring
# behaviour if thai_tokenizer / PyThaiNLP isn't installed.
_THAI_RE = re.compile(r"[฀-๿]")

try:
    from thai_tokenizer import split as _tok_split
    _tok_split("รถ")              # probe: confirms a backend engine is usable
    _TOKENIZER_OK = True
except Exception:                 # ImportError or EngineNotInstalledError
    _TOKENIZER_OK = False


def _boundary_text(s: str) -> str:
    """Tokenize and rejoin with spaces so keywords can be matched at word
    boundaries: ' word1 word2 word3 ' (wrapped + lowercased)."""
    return " " + " ".join(_tok_split(s)).lower() + " "


# Precompute, per category, which keywords go through the token path (Thai) vs
# the substring path (English). Done once at import, not per word.
_THAI_MATCHERS: dict[str, list[str]] = {}
_SUB_MATCHERS:  dict[str, list[str]] = {}
if _TOKENIZER_OK:
    for _cat, _kws in KEYWORD_MAP.items():
        thai, sub = [], []
        for _kw in _kws:
            if _THAI_RE.search(_kw):
                thai.append(_boundary_text(_kw))
            else:
                sub.append(_kw.lower())
        _THAI_MATCHERS[_cat] = thai
        _SUB_MATCHERS[_cat]  = sub


def extract_categories(text: str) -> tuple[list[str], int, int]:
    """
    Scan text for category keywords.
    Returns: (categories_list, is_foreign, is_royal)
    """
    t = text.lower()
    found = set()

    if _TOKENIZER_OK:
        boundary = _boundary_text(text)
        for cat in KEYWORD_MAP:
            if any(kwp in boundary for kwp in _THAI_MATCHERS[cat]) \
               or any(kw in t for kw in _SUB_MATCHERS[cat]):
                found.add(cat)
    else:
        # Legacy substring matching (tokenizer unavailable).
        for cat, keywords in KEYWORD_MAP.items():
            if any(kw.lower() in t for kw in keywords):
                found.add(cat)

    is_foreign = 1 if any(m in t for m in FOREIGN_MARKERS) else 0
    is_royal   = 1 if any(m in t for m in ROYAL_MARKERS)   else 0

    return sorted(found), is_foreign, is_royal


def parse_orst(html: str) -> str:
    """Extract definition text from ORST dictionary HTML."""
    soup = BeautifulSoup(html, "lxml")
    # ORST puts definitions in <div class="meaning"> or similar
    # Try common selectors
    for sel in [".meaning", ".definition", "#content", ".entry-content", "article"]:
        el = soup.select_one(sel)
        if el:
            return el.get_text(" ", strip=True)
    # Fallback: all paragraph text
    paras = soup.find_all("p")
    return " ".join(p.get_text(" ", strip=True) for p in paras[:10])


def parse_longdo(html: str) -> str:
    """Extract definition text from Longdo dictionary HTML."""
    soup = BeautifulSoup(html, "lxml")
    for sel in [".definition-box", ".result-box", "#result", ".entry", "table"]:
        el = soup.select_one(sel)
        if el:
            return el.get_text(" ", strip=True)
    return soup.get_text(" ", strip=True)[:2000]


def parse_wiktionary_th(html: str) -> str:
    """Extract category and definition text from Thai Wiktionary HTML."""
    soup = BeautifulSoup(html, "lxml")
    # Categories are in <div id="catlinks">
    catlinks = soup.find(id="catlinks")
    cat_text = catlinks.get_text(" ", strip=True) if catlinks else ""
    # Also grab definition content
    content = soup.find(id="mw-content-text")
    def_text = content.get_text(" ", strip=True)[:1500] if content else ""
    return cat_text + " " + def_text


# ══════════════════════════════════════════════════════════════════════════════
# SCRAPERS
# ══════════════════════════════════════════════════════════════════════════════

async def scrape_orst(session: aiohttp.ClientSession, word: str) -> str | None:
    url = f"https://dictionary.orst.go.th/?q={quote(word)}"
    try:
        async with session.get(url, headers=HEADERS,
                               timeout=aiohttp.ClientTimeout(total=12)) as r:
            if r.status != 200:
                return None
            html = await r.text(encoding="utf-8", errors="replace")
            return parse_orst(html)
    except Exception as e:
        log.debug("ORST error for %s: %s", word, e)
        return None


async def scrape_longdo(session: aiohttp.ClientSession, word: str) -> str | None:
    url = f"https://dict.longdo.com/search/{quote(word)}"
    try:
        async with session.get(url, headers=HEADERS,
                               timeout=aiohttp.ClientTimeout(total=12)) as r:
            if r.status != 200:
                return None
            html = await r.text(encoding="utf-8", errors="replace")
            return parse_longdo(html)
    except Exception as e:
        log.debug("Longdo error for %s: %s", word, e)
        return None


async def scrape_wiktionary_th(session: aiohttp.ClientSession, word: str) -> str | None:
    url = f"https://th.wiktionary.org/wiki/{quote(word)}"
    try:
        async with session.get(url, headers=HEADERS,
                               timeout=aiohttp.ClientTimeout(total=12)) as r:
            if r.status != 200:
                return None
            html = await r.text(encoding="utf-8", errors="replace")
            return parse_wiktionary_th(html)
    except Exception as e:
        log.debug("Thai Wiktionary error for %s: %s", word, e)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# MAIN WORKER
# ══════════════════════════════════════════════════════════════════════════════

async def process_word(
    session: aiohttp.ClientSession,
    sem: asyncio.Semaphore,
    word: str,
    source_filter: str | None,
) -> dict:
    """Try each source until categories are found. Returns result dict."""
    async with sem:
        await asyncio.sleep(DELAY_SEC)

    result = {
        "word": word, "categories": "", "is_foreign": 0, "is_royal": 0,
        "source": None, "skipped": False,
    }

    sources = []
    if source_filter == "orst":
        sources = [("orst", scrape_orst)]
    elif source_filter == "longdo":
        sources = [("longdo", scrape_longdo)]
    elif source_filter == "wiktionary":
        sources = [("wiktionary", scrape_wiktionary_th)]
    else:
        sources = [
            ("orst",       scrape_orst),
            ("longdo",     scrape_longdo),
            ("wiktionary", scrape_wiktionary_th),
        ]

    for src_name, scraper in sources:
        text = await scraper(session, word)
        if not text:
            continue
        cats, is_foreign, is_royal = extract_categories(text)
        if cats or is_foreign or is_royal:
            result["categories"] = ",".join(cats)
            result["is_foreign"] = is_foreign
            result["is_royal"]   = is_royal
            result["source"]     = src_name
            break

    return result


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

async def main(args: argparse.Namespace):
    if not DB_PATH.exists():
        log.error("Database not found: %s", DB_PATH)
        sys.exit(1)

    async with aiosqlite.connect(DB_PATH) as db:
        # Verify columns exist (add is_foreign / is_royal if missing)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS words (
                word TEXT PRIMARY KEY,
                syllables INT,
                pos TEXT,
                leading_class TEXT,
                final_class TEXT,
                live_dead TEXT,
                has_sara_a INT DEFAULT 0,
                has_ban_bor INT DEFAULT 0,
                is_foreign INT DEFAULT 0,
                is_royal INT DEFAULT 0,
                categories TEXT DEFAULT ''
            )
        """)
        # Add columns if they don't exist (safe no-op if present)
        for col, typedef in [("is_foreign", "INT DEFAULT 0"),
                              ("is_royal",   "INT DEFAULT 0"),
                              ("categories", "TEXT DEFAULT ''")]:
            try:
                await db.execute(f"ALTER TABLE words ADD COLUMN {col} {typedef}")
                await db.commit()
                log.info("Added column: %s", col)
            except Exception:
                pass  # column already exists

        # Build word list
        if args.word:
            words = [args.word]
        elif args.new_only:
            # Only words that have no categories yet
            cur = await db.execute(
                "SELECT word FROM words "
                "WHERE (categories IS NULL OR categories = '') "
                "AND word NOT LIKE '% %' AND pos <> 'PUNC' "
                "ORDER BY word LIMIT ?", (args.limit,)
            )
            rows = await cur.fetchall()
            words = [r[0] for r in rows]
        else:
            # Default: process all existing words in the database
            cur = await db.execute(
                "SELECT word FROM words WHERE word NOT LIKE '% %' AND pos <> 'PUNC' "
                "ORDER BY word LIMIT ?", (args.limit,)
            )
            rows = await cur.fetchall()
            words = [r[0] for r in rows]

    total = len(words)
    log.info("Words to process: %d", total)

    if total == 0:
        log.info("Nothing to do — all words already categorized.")
        print(json.dumps({"total": 0, "categorized": 0, "is_foreign": 0, "is_royal": 0}))
        return

    sem = asyncio.Semaphore(CONCUR)
    stats = {"total": total, "categorized": 0, "is_foreign": 0, "is_royal": 0, "errors": 0}

    connector = aiohttp.TCPConnector(limit=CONCUR, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            process_word(session, sem, w, args.source)
            for w in words
        ]

        async with aiosqlite.connect(DB_PATH) as db:
            batch: list[dict] = []

            for coro in asyncio.as_completed(tasks):
                result = await coro
                batch.append(result)

                if result["categories"] or result["is_foreign"] or result["is_royal"]:
                    if result["categories"]:
                        stats["categorized"] += 1
                    if result["is_foreign"]:
                        stats["is_foreign"] += 1
                    if result["is_royal"]:
                        stats["is_royal"] += 1
                    log.info("✓ %-20s  cats=%-30s  foreign=%d royal=%d  [%s]",
                             result["word"], result["categories"] or "—",
                             result["is_foreign"], result["is_royal"],
                             result["source"] or "?")

                # Write in batches of 50
                if len(batch) >= 50:
                    await _flush_batch(db, batch)
                    batch.clear()

            if batch:
                await _flush_batch(db, batch)

    summary = {
        "total": stats["total"],
        "categorized": stats["categorized"],
        "is_foreign_flagged": stats["is_foreign"],
        "is_royal_flagged": stats["is_royal"],
        "coverage_pct": round(stats["categorized"] / stats["total"] * 100, 1) if stats["total"] else 0,
    }
    log.info("=== DONE === %s", json.dumps(summary))
    print(json.dumps(summary, ensure_ascii=False))

    if not getattr(args, "no_export", False):
        _run_export()


async def _flush_batch(db: aiosqlite.Connection, batch: list[dict]):
    await db.executemany(
        "UPDATE words SET categories=?, is_foreign=?, is_royal=? WHERE word=?",
        [(r["categories"], r["is_foreign"], r["is_royal"], r["word"]) for r in batch]
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
    parser = argparse.ArgumentParser(description="Roi-Kham category scraper")
    parser.add_argument("--word",      help="Test a single Thai word")
    parser.add_argument("--limit",     type=int, default=1000,
                        help="Max words to process (default 1000)")
    parser.add_argument("--source",    choices=["orst", "longdo", "wiktionary"],
                        help="Force a specific source (default: try all)")
    parser.add_argument("--new-only",  dest="new_only", action="store_true",
                        help="Only scrape words that have no categories yet")
    parser.add_argument("--no-export", dest="no_export", action="store_true",
                        help="Skip running export_words.js at the end")
    args = parser.parse_args()

    asyncio.run(main(args))
