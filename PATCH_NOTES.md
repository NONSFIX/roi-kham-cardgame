# Roi-Kham ร้อย-คำ — Patch Notes

---

## v0.4 — 2026-06-25

### New Features

#### 4-Tab Interface (`prototype/index.html`)
The prototype now has a full tab navigation system in the header replacing the original single-page layout.

**Card Setup tab** *(new default view)*
- Word input with Thai dictionary lookup (ค้น button / Enter key)
- Categories section — all 16 semantic category pills in a dedicated card
- Special Flags section — วิสรรชนีย์, บัน/บรร, คำต่างประเทศ, ราชาศัพท์
- Bonus Card section — level selector (L0–L3) and Condition A/B dropdowns, separated from scoring
- **Calculate Score →** button transfers all selections to the Score Calculator tab and auto-calculates

**Manual Category tab** *(new)*
- Paste any Thai dictionary definition text (from ORST, Longdo, or any source)
- **วิเคราะห์ →** button scans for Thai category keywords and auto-checks matching pills
- Shows which keywords triggered each match
- **Apply to Card Setup →** transfers selections back to Card Setup tab

**Database tab** *(new)*
- Searchable, filterable table of all 62,099 Thai words
- Filter by: word text, POS (Noun/Verb/Adj etc.), Live/Dead, semantic Category
- 50 words per page with ← → pagination
- Category tags displayed as badges per word
- **→** button on each row loads that word directly into Card Setup
- Lazy-loads on first open (no performance impact on other tabs)

**Score Calculator tab**
- Existing scoring layout unchanged
- Now receives pre-filled data from Card Setup via Calculate Score →

#### Category Scraper (`scraper/`)
Automated pipeline to fill empty `categories`, `is_foreign`, and `is_royal` columns in `words.db` by querying Thai dictionary sources.

- **Sources** (tried in order): Royal Institute Dictionary (dict.orst.go.th) → Longdo Dictionary (dict.longdo.com) → Thai Wiktionary (th.wiktionary.org)
- **CLI**: `python scraper/scrape_categories.py --word สุนัข` / `--limit 500` / `--source orst`
- **Logging**: writes daily log to `scraper/logs/YYYY-MM-DD.log`
- **`run_pipeline.bat`**: Windows one-click batch file — runs scraper then re-exports `words.js`
- **`n8n-workflow.json`**: importable n8n workflow for nightly scheduled automation (2am cron)
- **`requirements.txt`**: `aiohttp`, `aiosqlite`, `beautifulsoup4`, `lxml`, `rich`

### Improvements

- **`export_words.js`**: now includes `categories` at array index `[7]` in the exported `words.js`
- **Word lookup** (`lookupWord()`): auto-checks the correct category pills when a word is found in the database with existing categories; shows green "✓ หมวด: …" note or a hint to use Manual Category tab if empty
- **`.gitignore`**: added Python artifacts (`__pycache__/`, `*.pyc`), virtual environments, and `scraper/logs/`
- **Empty directories** (`assets/`, `design/`, `rules/`): tracked with `.gitkeep` placeholder files

### Database Status
| | Count |
|---|---|
| Total words | 62,099 |
| With categories | ~205 (0.3%) — to be filled by scraper |
| Foreign flagged | 24 |
| Royal flagged | 2 |

---

## v0.3 — Initial Release

- Word scoring prototype (`prototype/index.html`)
- 61,487 Thai words loaded from `words.db` via `export_words.js`
- Syllable, consonant tier, T5 triple bonus, and bonus card scoring
- 28 bonus conditions across 4 levels (L0 Semantic → L3 Complex)
- Unity C# handoff package (`Handoff/`) with full game design document
- SQLite word database with linguistic properties (POS, live/dead, consonant class, etc.)
