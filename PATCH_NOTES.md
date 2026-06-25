# Roi-Kham ร้อย-คำ — Patch Notes

---

## v0.5 — 2026-06-26

### New Features

#### Local-LLM Word Categorizer (`scraper/categorize_llm.py`)
Categorizes Thai words by **meaning** using a local Ollama model — far more accurate
than the keyword-matching scraper. Runs fully offline, no API key, stdlib only.

- **Model**: default `qwen3.5:2b` (override with `--model`, e.g. `qwen2.5:7b`)
- **Structured output**: constrains the model to a JSON schema over the exact 16 game
  categories, so it can't invent categories
- **Tuned prompt**: few-shot examples steer abstract/legal/grammatical words to *no
  category* (e.g. กฎหมาย, วิ่ง, และ → none), while concrete nouns tag correctly
  (แมว→animal, กล้วย→fruit, เก้าอี้→house_item)
- **Resume-safe**: a new `cat_checked` column marks processed words, so chunked/stopped
  runs pick up where they left off instead of re-querying empty-category words
- **Batched** requests with per-word fallback for reliability
- **Auto-exports** `words.js` at the end (skip with `--no-export`)
- **CLI**: `--word`, `--limit`, `--model`, `--batch`, `--overwrite`, `--no-export`

```
python scraper/categorize_llm.py --word แมว        # test one word
python scraper/categorize_llm.py --limit 5000      # a chunk (repeat to continue)
python scraper/categorize_llm.py                   # all remaining words
```

#### Compound Decomposer (`scraper/decompose_words.py`)
Splits compound Thai words into known sub-words via DP segmentation and inherits the
union of their categories (ประจำวัน → ประ + จำ + วัน). Fills parents once their parts
are categorized. Auto-exports `words.js`.

### Improvements
- **`export_words.js`**: fixed a filter that silently dropped 611 multi-word phrases —
  the prototype now loads **62,098** words (was 61,487)
- **`scraper/scrape_categories.py`**: now processes all DB words by default
  (`--new-only` for uncategorized only) and auto-exports `words.js`
- **`scraper/run_pipeline.bat`**: 3-step pipeline — LLM categorize → decompose → export
  (the web scraper is now optional/legacy; the local LLM supersedes its keyword matching)

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
