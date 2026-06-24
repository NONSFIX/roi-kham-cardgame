#!/usr/bin/env python3
"""
build_word_db.py
────────────────
Offline build tool for Roi-Kham word system.
Run once; copy the output file to Assets/StreamingAssets/words.db

Requirements:
    pip install pythainlp[full] nltk

Usage:
    python build_word_db.py
    python build_word_db.py --output path/to/words.db
    python build_word_db.py --royal royal_vocab.txt   (add curated royal vocab list)
"""

import sqlite3
import argparse
import sys
from pathlib import Path

# ── Thai consonant class tables ───────────────────────────────────────────────
MID_CLASS  = set("กจดตบปอ")       # อักษรกลาง (7)
HIGH_CLASS = set("ขฃฉฐถผฝศษสห")  # อักษรสูง (11)
# Low class (อักษรต่ำ) = all other consonants

# Final consonant → แม่ class
FINAL_CLASS_MAP = {
    **{c: "กก"  for c in "กขคฆ"},
    **{c: "กด"  for c in "จชซฌฎฏฐฑฒดตถทธศษส"},
    **{c: "กบ"  for c in "บปพฟภ"},
    "ง": "กง",
    **{c: "กน"  for c in "ญณนรลฬ"},
    "ม": "กม",
    "ย": "เกย",
    "ว": "เกอว",
}

# Semantic category → WordNet synset name fragments
CATEGORY_SYNSET_FRAGMENTS = {
    "animal":         ["animal", "fauna", "creature", "mammal", "bird", "fish",
                       "reptile", "insect", "amphibian"],
    "plant":          ["plant", "flora", "tree", "flower", "shrub", "herb"],
    "food":           ["food", "dish", "meal", "cuisine", "snack", "dessert"],
    "drink":          ["drink", "beverage", "liquid", "juice", "tea", "coffee"],
    "vehicle":        ["vehicle", "conveyance", "transport", "car", "boat", "aircraft"],
    "house_item":     ["furniture", "utensil", "household", "appliance", "tool"],
    "body_part":      ["body_part", "organ", "limb", "extremity", "anatomical"],
    "family":         ["relative", "parent", "sibling", "family", "kin", "ancestor"],
    "color":          ["color", "colour", "hue", "tint", "shade"],
    "shape":          ["shape", "form", "figure", "geometry"],
    "nature":         ["nature", "environment", "landscape", "terrain", "ecology"],
    "weather":        ["weather", "climate", "atmospheric", "precipitation", "storm"],
    "sport":          ["sport", "game", "athletics", "competition", "exercise"],
    "hobby":          ["hobby", "pastime", "recreation", "craft", "leisure"],
    "fruit":          ["fruit"],
    "vegetable":      ["vegetable", "veggie", "legume", "root"],
    # Level 3 (manually curated — PyThaiNLP flags these, others need manual review)
    "synonym_pair":   [],   # คำซ้อน — hard to auto-detect
    "compound":       ["compound_word"],
    "samat":          [],   # คำสมาส — Sanskrit origin compounds
    "transliteration":["transliteration", "loanword", "borrowing"],
    "coined":         [],   # คำบัญญัติ — Royal Academy coined terms
}

# POS tag normalisation (Orchid corpus tags → simple labels)
ORCHID_POS_MAP = {
    "NCMN": "NOUN", "NTTL": "NOUN", "NONM": "NOUN", "NCNM": "NOUN",
    "VACT": "VERB", "VSTA": "VERB", "VMODX": "VERB",
    "ADVN": "ADV",  "ADVI": "ADV",  "ADVP": "ADV",
    "ADJV": "ADJ",  "ATTQ": "ADJ",
    "RPRE": "PREP", "RPST": "PREP",
    "JCRR": "CONJ", "JCMP": "CONJ", "JSBR": "CONJ",
    "PPRS": "PRON", "PDMT": "PRON", "PNTR": "PRON",
    "INTJ": "INTJ",
}

# ── Helper functions ──────────────────────────────────────────────────────────

def get_lead_class(word: str) -> str:
    for ch in word:
        if "\u0E01" <= ch <= "\u0E4E":
            if ch in MID_CLASS:  return "mid"
            if ch in HIGH_CLASS: return "high"
            return "low"
    return ""


def get_final_class(word: str) -> str:
    consonants = [ch for ch in word if "\u0E01" <= ch <= "\u0E2E"]
    if not consonants:
        return "none"
    return FINAL_CLASS_MAP.get(consonants[-1], "none")


def is_live_dead(word: str) -> str:
    """
    คำตาย: final consonant is a stop (กก/กด/กบ class)
    คำเป็น: final is sonorant/semi-vowel or open syllable
    Unknown when we can't determine final consonant.
    """
    stops = set("กขคฆจชซฌฎฏฐฑฒดตถทธศษสบปพฟภ")
    consonants = [ch for ch in word if "\u0E01" <= ch <= "\u0E2E"]
    if not consonants:
        return "unknown"
    return "dead" if consonants[-1] in stops else "live"


def get_categories(word: str, wn) -> str:
    """Resolve semantic categories via PyThaiNLP WordNet hypernym chain."""
    found = set()
    try:
        synsets = wn.synsets(word, lang="tha")
        for syn in synsets:
            for path in syn.hypernym_paths():
                for s in path:
                    name = s.name().split(".")[0].lower()
                    for cat, fragments in CATEGORY_SYNSET_FRAGMENTS.items():
                        if any(f in name for f in fragments):
                            found.add(cat)
    except Exception:
        pass
    return ",".join(sorted(found))


def normalize_pos(orchid_tag: str) -> str:
    return ORCHID_POS_MAP.get(orchid_tag, "")


# ── Main build ────────────────────────────────────────────────────────────────

def build(output_path: str, royal_vocab_path: str | None):
    # Late imports — give clear error if not installed
    try:
        from pythainlp.corpus import words as th_corpus
        from pythainlp.tokenize import syllable_tokenize
        from pythainlp.tag import pos_tag
        from pythainlp.corpus import wordnet as wn
    except ImportError as e:
        print(f"ERROR: {e}\nInstall with:  pip install pythainlp[full]")
        sys.exit(1)

    # Load royal vocab if provided
    royal_vocab: set[str] = set()
    if royal_vocab_path and Path(royal_vocab_path).exists():
        royal_vocab = set(Path(royal_vocab_path).read_text(encoding="utf-8").splitlines())
        print(f"Loaded {len(royal_vocab)} royal vocabulary entries.")

    # Word list from PyThaiNLP
    word_list = list(th_corpus.get_corpus_path("words_th") or [])
    print(f"Processing {len(word_list)} words → {output_path}")

    conn = sqlite3.connect(output_path)
    cur  = conn.cursor()

    cur.executescript("""
        DROP TABLE IF EXISTS words;
        CREATE TABLE words (
            word            TEXT PRIMARY KEY,
            syllable_count  INT,
            pos             TEXT,
            live_dead       TEXT,
            final_class     TEXT,
            lead_class      TEXT,
            is_foreign      INT  DEFAULT 0,
            is_royal        INT  DEFAULT 0,
            has_vissajaniya INT  DEFAULT 0,
            has_bun_brr     INT  DEFAULT 0,
            categories      TEXT DEFAULT ''
        );
    """)

    BATCH_SIZE = 500
    batch      = []
    errors     = 0

    for i, word in enumerate(word_list):
        word = word.strip()
        if not word:
            continue
        try:
            # Syllable count
            syls = len(syllable_tokenize(word))

            # POS — use first tag from Orchid tagger
            pos_raw  = pos_tag([word], corpus="orchid")
            pos_norm = normalize_pos(pos_raw[0][1]) if pos_raw else ""

            # Computed fields
            live_dead   = is_live_dead(word)
            final_cls   = get_final_class(word)
            lead_cls    = get_lead_class(word)
            is_royal    = 1 if word in royal_vocab else 0
            has_viss    = 1 if "ะ" in word else 0
            has_bun     = 1 if (word.startswith("บัน") or word.startswith("บรร")) else 0

            # WordNet categories (slowest step — ~0.05s/word)
            categories  = get_categories(word, wn)

            # IsForeign: mark words that appear in transliteration/loanword category
            is_foreign  = 1 if ("transliteration" in categories or "loanword" in categories) else 0

            batch.append((
                word, syls, pos_norm, live_dead, final_cls, lead_cls,
                is_foreign, is_royal, has_viss, has_bun, categories
            ))

        except Exception as e:
            errors += 1
            continue  # skip problematic words silently

        if len(batch) >= BATCH_SIZE:
            cur.executemany(
                "INSERT OR IGNORE INTO words VALUES (?,?,?,?,?,?,?,?,?,?,?)", batch)
            conn.commit()
            batch.clear()
            pct = (i + 1) / len(word_list) * 100
            print(f"  {i+1}/{len(word_list)}  ({pct:.1f}%)  errors: {errors}", end="\r")

    # Final flush
    if batch:
        cur.executemany(
            "INSERT OR IGNORE INTO words VALUES (?,?,?,?,?,?,?,?,?,?,?)", batch)
        conn.commit()

    # Index for fast primary-key lookup
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_word ON words(word)")
    conn.commit()
    conn.close()

    print(f"\nDone. Errors skipped: {errors}")
    print(f"Output: {Path(output_path).resolve()}")
    print(f"Copy to: Assets/StreamingAssets/words.db")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Roi-Kham words.db")
    parser.add_argument("--output", default="words.db",
                        help="Output SQLite path (default: words.db)")
    parser.add_argument("--royal", default=None,
                        help="Path to royal_vocab.txt (one word per line)")
    args = parser.parse_args()
    build(args.output, args.royal)
