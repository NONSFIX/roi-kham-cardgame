# Roi-Kham (ร้อย-คำ)

Thai-language educational card game where players build words from consonant cards and convert word power into combat damage.

## Play the Prototype

Open `prototype/index.html` directly in any browser — no server needed.

**Features:**
- Type a Thai word → auto-lookup from 61,487-word database
- Word properties populate automatically (POS, syllables, live/dead, initial/final class)
- Score calculated instantly:
  - **Syllable Score** — syllable count × 1
  - **Consonant Value** — sum of tier values for each consonant in the word (T1=1 … T5=5)
  - **Triple Bonus** — +5 if 2 consonants from the same T5 card appear; +15 if all 3
  - **Bonus Card** — +1/2/4/6 (L0–L3) if the chosen condition is met
- 28 bonus conditions across 4 levels (semantic, grammatical, structural)

## Consonant Tiers

| Tier | Consonants | Points |
|------|-----------|--------|
| T1 | ก น ร อ | +1 each |
| T2 | ม ง ว ย | +2 each |
| T3 | ด ต ส ล ห ค | +3 each |
| T4 | ข ป บ จ พ ท | +4 each |
| T5 | 8 triple cards (rare) | +5 each |

**T5 Triple Cards** (2/3 = +5 bonus · 3/3 = +15 bonus):
`ผถณ` · `ศธษ` · `ญภซ` · `ฉฐฟ` · `ฝฏฎ` · `ฒฮฑ` · `ฆฬฌ` · `ฃฅฤ`

## Score Formula

```
Word Power = SyllableScore + ConsonantValue + TripleBonus + BonusCardValue
```

## Word Database

`prototype/words.js` is pre-built and ready to use. To regenerate it from `Handoff/words.db`:

```bash
node export_words.js   # requires Node.js 22+
```

Source: 62,099 Thai words from PyThaiNLP, with syllable count, POS (Orchid tagset), live/dead, initial/final consonant class.

## Project Structure

```
roi-kham-cardgame/
├── prototype/
│   ├── index.html        # web prototype (open directly in browser)
│   └── words.js          # pre-built word database for browser
├── Handoff/
│   ├── Roi-Kham_Unity_Handoff.md   # full game design document
│   ├── words.db                     # SQLite source database
│   └── *.cs                         # Unity C# reference implementation
├── export_words.js       # regenerate words.js from words.db
└── README.md
```

## Game Design

See [`Handoff/Roi-Kham_Unity_Handoff.md`](Handoff/Roi-Kham_Unity_Handoff.md) for the full design document including:
- Hero & Demon stats
- All 28 bonus condition types
- Build order and card distribution
- Combat and scoring rules
