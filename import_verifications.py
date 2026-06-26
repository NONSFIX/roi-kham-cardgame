#!/usr/bin/env python3
"""
import_verifications.py
───────────────────────
Reads verifications.json exported from prototype/verify.html
and updates Handoff/words.db with human verification votes.

Supported fields: pos, final_class, live_dead, leading_class, categories

Adds columns to 'words' table if missing:
  pos_verified        INTEGER  pos_correction        TEXT
  final_verified      INTEGER  final_correction      TEXT
  livedead_verified   INTEGER  livedead_correction   TEXT
  lead_verified       INTEGER  lead_correction       TEXT
  cats_verified       INTEGER  cats_correction       TEXT  (comma-separated)

Usage:
  python import_verifications.py
  python import_verifications.py --db Handoff/words.db --json verifications.json
  python import_verifications.py --dry-run
"""

import sqlite3
import json
import argparse
from pathlib import Path

# (column_name, sql_definition, field_key)
FIELD_COLUMNS = [
    ("pos",          "pos_verified",      "INTEGER DEFAULT 0", "pos_correction",      "TEXT DEFAULT ''"),
    ("final_class",  "final_verified",    "INTEGER DEFAULT 0", "final_correction",    "TEXT DEFAULT ''"),
    ("live_dead",    "livedead_verified", "INTEGER DEFAULT 0", "livedead_correction", "TEXT DEFAULT ''"),
    ("leading_class","lead_verified",     "INTEGER DEFAULT 0", "lead_correction",     "TEXT DEFAULT ''"),
    ("categories",   "cats_verified",     "INTEGER DEFAULT 0", "cats_correction",     "TEXT DEFAULT ''"),
]

VALID_VOTES  = {"correct", "wrong"}
VALID_FIELDS = {row[0] for row in FIELD_COLUMNS}

# Map field key → (verified_col, correction_col)
FIELD_MAP = { row[0]: (row[1], row[3]) for row in FIELD_COLUMNS }


def ensure_columns(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(words)")}
    added = []
    for field, ver_col, ver_def, cor_col, cor_def in FIELD_COLUMNS:
        for col, defn in [(ver_col, ver_def), (cor_col, cor_def)]:
            if col not in existing:
                conn.execute(f"ALTER TABLE words ADD COLUMN {col} {defn}")
                added.append(col)
    if added:
        conn.commit()
        print(f"  Added columns: {', '.join(added)}")
    else:
        print("  All verification columns already present.")


def load_records(json_path: str) -> list:
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


def run_import(db_path: str, json_path: str, dry_run: bool = False) -> None:
    if not Path(db_path).exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    if not Path(json_path).exists():
        raise FileNotFoundError(f"JSON not found: {json_path}")

    records = load_records(json_path)
    print(f"Loaded {len(records):,} records from {json_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    ensure_columns(conn)

    stats = {f: {"correct": 0, "wrong": 0} for f in VALID_FIELDS}
    stats["skipped"]   = 0
    stats["not_found"] = 0
    stats["invalid"]   = 0

    for rec in records:
        word       = rec.get("word")
        field      = rec.get("field")
        vote       = rec.get("vote")
        correction = rec.get("correction")

        if not word or field not in VALID_FIELDS:
            stats["invalid"] += 1
            continue

        if vote not in VALID_VOTES:
            stats["skipped"] += 1
            continue

        exists = conn.execute("SELECT 1 FROM words WHERE word = ?", (word,)).fetchone()
        if not exists:
            stats["not_found"] += 1
            continue

        ver_col, cor_col = FIELD_MAP[field]

        if dry_run:
            stats[field][vote] += 1
            continue

        if vote == "correct":
            conn.execute(
                f"UPDATE words SET {ver_col} = {ver_col} + 1 WHERE word = ?",
                (word,)
            )
            stats[field]["correct"] += 1

        elif vote == "wrong" and correction is not None:
            # correction can be a string or list (categories multi-select)
            if isinstance(correction, list):
                correction = ",".join(sorted(correction))
            conn.execute(
                f"UPDATE words SET {cor_col} = ? WHERE word = ?",
                (str(correction), word)
            )
            stats[field]["wrong"] += 1

    if not dry_run:
        conn.commit()
    conn.close()

    tag = "[DRY RUN] " if dry_run else ""
    print(f"\n{tag}Results:")

    field_labels = {
        "pos":           "ชนิดคำ (POS)       ",
        "final_class":   "มาตราตัวสะกด        ",
        "live_dead":     "เสียงคำ (Live/Dead) ",
        "leading_class": "อักษร 3 หมู่        ",
        "categories":    "หมวดหมู่คำ (Semantic)",
    }
    total_written = 0
    for field, label in field_labels.items():
        c = stats[field]["correct"]
        w = stats[field]["wrong"]
        total_written += c + w
        print(f"  {label}  ✓ confirmed: {c:>6,}  ✗ corrected: {w:>6,}")

    print(f"  {'─' * 52}")
    print(f"  Skipped (no vote)          : {stats['skipped']:>6,}")
    print(f"  Words not in database      : {stats['not_found']:>6,}")
    print(f"  Invalid records            : {stats['invalid']:>6,}")
    if not dry_run:
        print(f"\n  {total_written:,} records written to {db_path}")


def main() -> None:
    p = argparse.ArgumentParser(description="Import verifications.json into words.db")
    p.add_argument("--db",      default="Handoff/words.db",   help="Path to words.db")
    p.add_argument("--json",    default="verifications.json", help="Path to verifications.json")
    p.add_argument("--dry-run", action="store_true",          help="Validate without writing to DB")
    args = p.parse_args()
    run_import(args.db, args.json, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
