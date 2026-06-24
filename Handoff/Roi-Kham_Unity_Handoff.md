# Roi-Kham (ร้อย-คำ) — Unity Implementation Handoff
> **For:** Claude Code  
> **GDD Version:** v1.4 (authoritative)  
> **Status:** Word System complete · Remaining 17 modules unbuilt  
> **Namespace:** `RoiKham`

---

## 1. What This Game Is

A Thai-language educational card game digitized in Unity. Players form real Thai words from consonant cards and convert the word's score into combat damage against 5 demon types. The game has three modes: 1v1 PvP, PvE Solo, and PvE Co-op (2P / 3P).

**Core loop per turn:**  
Draw consonants → flip bonus card → build Thai word → calculate Word Power → attack/heal/use skills → end turn (return vowels, refill shared stack, tick cooldowns)

**Win condition PvE:** Banish enough demons (6 / 24 / 36 / 48 depending on difficulty) before any player hits 0 HP.

---

## 2. Tech Stack

| Layer | Choice |
|---|---|
| Engine | Unity (C#, ScriptableObjects, MonoBehaviour architecture) |
| Database | SQLite via **sqlite-net-pcl** package |
| Thai word data | PyThaiNLP (Python, offline build tool only — not in Unity) |
| Thai font | **Noto Sans Thai** or **TH Sarabun New** via TextMeshPro font atlas |
| Testing | NUnit (Unity Test Runner, EditMode) |
| Target platforms | Windows, macOS, Android, iOS |

---

## 3. Architecture — 4-Layer Modular System

**Dependency direction: Game Loop → Systems → Core Logic → Data**  
Upper layers depend on lower. Lower layers never import upper.  
Every module is independently testable before integration.

```
Game Loop Layer
  TurnManager · DemonAIManager · PvEManager · GameStateManager · CoopManager

Systems Layer
  DeckManager · SharedStackManager · DemonDeckManager · HandManager
  BonusCardManager · SkillSystem · CombatSystem
  StatusEffectSystem · DemonAbilitySystem

Core Logic Layer  ← BUILT ✓
  WordPowerCalculator (WordScoreService) · SyllableScorer
  TypeAdvantageCalc · WordValidator · TripleCardBonusCalc
  BonusConditionChecker · ConsonantValueResolver

Data Layer (ScriptableObjects)
  ConsonantCardData · VowelCardData · MarkCardData
  BonusCardData · CharacterClassData · DemonData
```

**Rule:** Runtime mutable state (cooldowns, HP, escalation counters, stealth flags) NEVER lives in ScriptableObjects. ScriptableObjects are read-only definitions. All runtime state lives in separate MonoBehaviour or plain-C# runtime objects that hold a reference to the ScriptableObject template.

---

## 4. What Is Already Built — Word System (Core Logic Layer)

All files live under `Assets/Scripts/WordSystem/` in Unity.

### File Structure

```
WordSystem/
├── build_word_db.py              ← Python offline tool, run once
│
├── Data/
│   ├── BonusConditionType.cs     ← enum, 28 conditions from GDD
│   ├── WordEntry.cs              ← SQLite row model
│   └── Models.cs                 ← ConsonantUsage · BonusCardInfo · WordScoreResult
│
├── Database/
│   ├── IWordDatabase.cs          ← interface (real / mock swap)
│   └── WordDatabase.cs           ← SQLite impl + MockWordDatabase for NUnit
│
└── Logic/
    ├── ConsonantValueResolver.cs  ← tier values, triple-card bonus
    ├── BonusConditionChecker.cs   ← all 28 condition checks
    ├── WordScoreService.cs        ← main Calculate() orchestrator
    └── WordSystemTests.cs         ← NUnit tests (EditMode, no Unity runtime)
```

### How to Use

```csharp
// Bootstrap (once at startup)
var db      = WordDatabase.LoadFromStreamingAssets();
var scoring = new WordScoreService(db);

// Each turn
var usages = new[] {
    new ConsonantUsage(2, 'ม'),   // Tier 2
    new ConsonantUsage(2, 'ง'),
    new ConsonantUsage(1, 'ก'),   // Tier 1
    new ConsonantUsage(1, 'ร'),
};
var bonus  = new BonusCardInfo(0, BonusConditionType.Animal, BonusConditionType.Plant);
var result = scoring.Calculate("มังกร", usages, bonus);

result.IsValid          // true/false (dictionary check)
result.TotalWordPower   // 8 (syl:2 + con:6 + bonus:0)
result.AnyBonusMet      // false (dragon not in our animal corpus yet)
result.Breakdown        // "Syllable(2) + Consonant(6) + Triple(0) + Bonus(0) = 8"
```

### Database Setup

1. Run `python build_word_db.py` (requires `pip install pythainlp[full]`)
2. Copy output `words.db` → `Assets/StreamingAssets/words.db`
3. Android auto-copies to `persistentDataPath` on first launch (handled in `WordDatabase.cs`)

### words.db Schema

```sql
CREATE TABLE words (
    word            TEXT PRIMARY KEY,
    syllable_count  INT,
    pos             TEXT,   -- NOUN | VERB | ADJ | ADV | PRON | INTJ | PREP | CONJ
    live_dead       TEXT,   -- live | dead | unknown
    final_class     TEXT,   -- กก | กด | กบ | กง | กน | กม | เกย | เกอว | none
    lead_class      TEXT,   -- mid | high | low
    is_foreign      INT,    -- 0 | 1
    is_royal        INT,    -- 0 | 1  (from royal_vocab.txt, manually curated)
    has_vissajaniya INT,    -- 0 | 1
    has_bun_brr     INT,    -- 0 | 1
    categories      TEXT    -- comma-separated: animal,food,plant...
);
```

### Bonus Condition Coverage

| Condition | Auto-resolved by | Accuracy |
|---|---|---|
| อักษรกลาง/สูง/ต่ำ | C# lookup table | 100% |
| แม่กก/กด/กบ/กง/กน/กม/เกย/เกอว | DB `final_class` | ~95% |
| คำเป็น / คำตาย | DB `live_dead` | ~90% |
| ประวิสรรชนีย์ / บัน/บรร | DB flags | 100% |
| คำซ้ำ (ๆ) | `rawWord.Contains('ๆ')` | 100% |
| คำนาม/กริยา/วิเศษณ์/สรรพนาม | DB `pos` (PyThaiNLP Orchid) | ~85% |
| สัตว์/พืช/อาหาร/อวัยวะ etc. | DB `categories` (WordNet) | ~70% |
| ราชาศัพท์ | `royal_vocab.txt` (manual) | depends on file |
| คำสมาส / คำประสม | honor system (returns false) | manual |
| คำทับศัพท์ / คำบัญญัติ | honor system (returns false) | manual |

---

## 5. What Needs to Be Built — Remaining Modules

### Priority 1 — Data Layer (ScriptableObjects)

These are needed before any Systems or Game Loop can run.

**`ConsonantCardData.cs`**
```
Fields: char[] Consonants (1-3), int Tier (1-5)
Computed: int ValuePerConsonant => Tier
Special: Tier 5 cards have 3 consonants and trigger triple bonus
```

**`BonusCardData.cs`**
```
Fields: int Level (0-3), BonusConditionType ConditionA, BonusConditionType ConditionB
Computed: int BonusValue => Level switch { 0→1, 1→2, 2→4, 3→6 }
Count: 20 cards total (8 L0, 4 L1, 5 L2, 3 L3)
```

**`CharacterClassData.cs`**
```
Fields: string className, int maxHP, int armor, int handSize
       AttackType attackType (enum: Melee/Ranged/Magic)
       SkillDefinition passive, active1, active2, ultimate
```

**`DemonData.cs`**
```
Fields: string demonName, int tier, int maxHP, int armor, int baseDamage
       AttackType attackType, DemonBehaviorType behaviorType
       Any ability-specific parameters (see demon specs below)
```

**`SkillDefinition.cs`** (struct or nested class)
```
Fields: string skillName, SkillType type (Passive/Active/Ultimate)
       int hpCost, int cooldown, string effectTag
```

---

### Priority 2 — Core Logic (no Unity dependency)

**`TypeAdvantageCalc.cs`**
```csharp
// Triangle: Melee → Ranged → Magic → Melee
// Returns: +1, 0, or -1
public static int Calculate(AttackType attacker, AttackType defender)
```

**`WordValidator.cs`**
```csharp
// Challenge system (GDD §4.6)
// Word wrong: attacker takes WordPower / 2 (rounded up)  
// Word right:  challenger takes 1 damage
// Uses IWordDatabase.IsValid() — already available
```

---

### Priority 3 — Systems Layer

**`DeckManager.cs`**
- Holds the 86-card consonant deck at runtime
- Methods: `DrawToFill(handSize)`, `Discard(cards)`, `Shuffle()`
- Deck exhaustion: graceful (no draw if empty, don't crash)

**`SharedStackManager.cs`**
- The vowels/marks pool (always available, returned each turn)
- The consonant shared stack (consumed, replaced 1:1 after use)
- Growth schedule: size starts at 4, +1 at player turns 3, 5, 7, 9 (global turn counter)
- **OPEN QUESTION:** Is the turn counter per-player or total across all players? Not resolved in GDD. Recommend: total turn count (simpler)
- `RefillUsedSlots(count)` — draws from main deck to refill
- `GrowIfScheduled(currentTurn)` — checks growth schedule

**`HandManager.cs`**
- Per-player hand: `List<ConsonantCardData>` at runtime
- `DrawToFull()` calls DeckManager
- Tracks cards in hand vs cards used this turn

**`BonusCardManager.cs`**
- Separate 20-card bonus deck
- `FlipForTurn()` → returns BonusCardInfo for WordScoreService
- Shuffles when exhausted

**`SkillSystem.cs`**
- Per-character runtime state: `int[] cooldowns`, `bool skillUsedThisTurn`
- `TryUseActive(hero, skillIndex, currentHP)` → checks cooldown + HP cost → returns bool
- `TickCooldowns(hero)` → called at end of turn, reduces all by 1
- KHAM MAK modifier: injected from `DemonAbilitySystem` as a runtime HP cost delta

**`CombatSystem.cs`**
- `ResolvePlayerAttack(attacker, target, wordPower, skillBonuses)` → applies type advantage → armor → returns final damage
- `ResolvePlayerHeal(hero, wordPower)` → adds HP, caps at maxHP
- `ResolveReflect(damage, isAlreadyReflected)` → returns 0 if `isAlreadyReflected == true`
- **The `isReflected` flag must be passed through all damage events to prevent reflect chains**

**`StatusEffectSystem.cs`**
- Archer stealth: `bool isStealthed`, breaks on own attack or Active use (NOT on AoE damage, NOT on Ultimate)
- Guardian passive flag: `bool builtWordLastTurn` — set at end of Step 3, read in next damage calculation
- Guardian Ultimate temp armor: `int tempArmor`, `int tempArmorTurnsRemaining` — decremented each turn
- Archer death mark: `DemonData markedTarget`, `int marksRemaining` — +3 to all damage against target; Archer takes 6 HP if target survives
- KHAM ANG skip: `bool nextTurnSkipped`, `string affectedPlayerId`
- Absorption state: `DemonData absorbedKrasip` on each Tier1+ demon (null when none)

**`DemonAbilitySystem.cs`**
- KHAM MAK: tracks `int khamMakTurnsSurvived` per instance; computes HP cost modifier (+2 base, +1 every 2 turns, cap +5)
  - **Design ambiguity:** GDD text says "+2 พลังคำ" (Word Power cost) but the table shows HP costs. The table is authoritative — implement as HP cost increase
- KHAM ANG: `bool activeUsed` (one-time per combat), fires after target player survives 3+ player turns
- KHAM FONG: reflect on hit (2 damage, no chain), card discard if attacker hand >= 6
- TAMRA-PINA Devour: called when any demon is banished — heals by full HP of banished demon, +2 damage stack (cap +8 total). HP overheal allowed, no cap
- Absorption priority: when KRASIP passive triggers, find Tier1+ with highest HP (earliest entry as tiebreak)

**`DemonDeckManager.cs`**
- 15-card demon deck
- Start: put 3 KRASIP directly on field (not from deck)
- When demon banished: draw 1 immediately (1:1 replacement)
- Deck exhausted: reshuffle Demon Grave into new deck
- Tracks `int killCount` for win condition

---

### Priority 4 — Game Loop Layer

**`GameStateManager.cs`** — top-level state machine
```
States: Setup → PlayerTurn → DemonTurn → Victory → Defeat
```

**`TurnManager.cs`** — executes the 6-step turn sequence
```
Step 1: Draw consonants to full hand
Step 2: Flip bonus card
Step 3: Player declares word + optional challenge resolves
Step 4: WordScoreService.Calculate()
Step 5: Player allocates word power (attack/heal) + optional skill use
Step 6: End-of-turn cleanup (return vowels/marks, refill shared stack, grow if scheduled, tick cooldowns)
```

**`DemonAIManager.cs`** — targeting logic per demon type
```
KRASIP:      target player who attacked any demon last turn → else random
KHAM MAK:    target player with most cards in hand → tiebreak HP highest
KHAM FONG:   target player who attacked any demon last turn → tiebreak HP highest
KHAM ANG:    target player who used Active/Ultimate last turn → tiebreak HP highest
TAMRA-PINA:  always target player with highest HP (+3 bonus per Erasure Protocol)

Active priority (only 1 demon per round): highest HP wins, tiebreak higher Tier
Passives: always on, all demons simultaneously
```

**`PvEManager.cs`** — wave management and win/lose
```
Kill count thresholds: Short=6, Standard=24 (3P: 36), Hardcore=48
Wave: start with 3 KRASIP on field; 1:1 replacement on each banishment
Lose condition: all players at 0 HP simultaneously
```

**`CoopManager.cs`** — multi-player coordination
```
Turn order: fixed, decided before game start
HP transfer revive: donor must retain ≥1 HP after transfer
3P scaling: demon HP ×1.5 (round up), +2 KRASIP in deck, Standard kill=36
Word power transfer: declared in Step 5, applied to receiver's NEXT turn
```

---

## 6. Key Game Numbers — Quick Reference

### Hero Stats

| Class | HP | Armor | Hand | Attack Type |
|---|---|---|---|---|
| Warrior | 42 | 1 | 4 | Melee |
| Guardian | 40 | 0 | 5 | Ranged |
| Archer | 36 | 1 | 4 | Ranged |

### Hero Skills

**Warrior:**
- Passive — เพิ่มพลังกาย: word uses 2+ consonants → +1 attack damage (auto, no cost)
- Active 1 — ดับเครื่องชน: 3 HP → +5 attack; damage ignores armor; CD 2
- Active 2 — สวนกลับ: 2 HP → next incoming attack: reflect 75% back (floor); reflected damage cannot chain-reflect; CD 2
- Ultimate — ดาบพิพากษา: 8 HP → +12 attack; pierces armor (ignores armor + passive); CD 6

**Guardian:**
- Passive — โล่เวทมนตร์: reduce incoming damage by 2 — **only if Guardian successfully built a word last turn**; base armor = 0
- Active 1 — ป้อมปราการเวทย์: 4 HP → block next incoming attack up to 8 damage (calculated before Passive); CD 2
- Active 2 — เสริมเวทย์: 3 HP → draw +2 consonants + take 1 from shared stack; CD 2
- Ultimate — ปณิธานแห่งโล่: 6 HP → +5 armor for 3 turns; CD 6

**Archer:**
- Passive — พรางตัว: if not attacked last turn → auto-stealth. Stealth: untargetable by direct attacks, -1 damage from AoE/abilities, first attack from stealth +2. Stealth persists until player attacks or uses Active (NOT broken by Ultimate)
- Active 1 — ฟันหลัง: 2 HP → +4 attack (or +6 if stealthed); breaks stealth; CD 2
- Active 2 — กลายร่าง: 3 HP → force-enter stealth; next attack from this stealth pierces armor; CD 2
- Ultimate — ตรามรณะ: 5 HP → mark 1 enemy for 3 turns; all attacks to marked target +3; if target survives 3 turns → Archer takes 6 HP; does NOT break stealth; CD 6

### Demon Stats

| Tier | Name | HP | Armor | DMG | Type |
|---|---|---|---|---|---|
| 0 | KRASIP (กระซิบ) | 6 | 0 | 2 | Melee |
| 1 | KHAM MAK (คำมาก) | 14 | 0 | 2 | Magic |
| 1 | KHAM FONG (คำฟ้อง) | 12 | 0 | 3 | Melee |
| 1 | KHAM ANG (คำอ้าง) | 14 | 0 | 2 | Ranged |
| 2 | TAMRA-PINA (ตำราพินา) | 20 | 1 | 3→11 | Magic |

### Demon Deck Composition (15 cards)

| Card | Count |
|---|---|
| KRASIP | 8 |
| KHAM MAK | 2 |
| KHAM FONG | 2 |
| KHAM ANG | 2 |
| TAMRA-PINA | 1 |

Note: Game starts with 3 KRASIP placed on field directly (not from deck).

### Type Advantage

| Attacker | Defender | Result |
|---|---|---|
| Melee | Ranged | +1 |
| Ranged | Magic | +1 |
| Magic | Melee | +1 |
| Melee | Magic | -1 |
| Ranged | Melee | -1 |
| Magic | Ranged | -1 |
| Same | Same | +0 |

### Card Counts

| Type | Count | Notes |
|---|---|---|
| Consonant cards | 86 | 28 unique types across 5 tiers |
| Vowel cards | 18 | 12 types; high-freq have 2 copies |
| Mark cards | 13 | 8 types (tone marks, karantoo, yamok) |
| Shared stack start | 4 | grows +1 at turns 3,5,7,9 (max 8) |
| Bonus cards | 20 | 8 L0 / 4 L1 / 5 L2 / 3 L3 |

### Word Power Formula

```
Total Word Power = SyllableScore + ConsonantValue + TripleBonus + BonusCardValue

SyllableScore  = syllable count × 1
ConsonantValue = sum of (tier value × consonants used) per card
TripleBonus    = 0 / +5 (2 of 3 from one Tier5 card) / +15 (all 3)
BonusCardValue = 0 / 1 / 2 / 4 / 6 depending on card level if condition met
```

---

## 7. Open Design Questions (Unresolved in GDD)

These need a decision before implementing the affected module:

| # | Question | Affected Module | Recommendation |
|---|---|---|---|
| 1 | KHAM MAK says "+2 พลังคำ" but table shows HP cost increasing. Which is it? | DemonAbilitySystem, SkillSystem | **Use HP cost** (table is authoritative). Implement as runtime HP cost modifier on Active skills |
| 2 | Shared stack growth: total turn count or per-player turn count? | SharedStackManager | **Total turn count** (simpler, less ambiguous in 3P) |
| 3 | Guardian ป้อมปราการ block + KHAM ANG skip: does the block carry over? | StatusEffectSystem, DemonAbilitySystem | **Block persists until consumed** by actual incoming damage, regardless of skipped turns |
| 4 | KHAM ANG "3+ player turns survived" — does a skipped turn count toward the 3? | DemonAbilitySystem | **Yes, count skipped turns** (demon waited 3 turns regardless) |
| 5 | When Warrior uses สวนกลับ then turn is skipped by KHAM ANG — is reflect still active? | StatusEffectSystem | **Yes, reflect state persists** until consumed |

---

## 8. Critical Implementation Rules (Do Not Forget)

**Reflect chain prevention:**  
Every damage event must carry `bool isReflected`. Warrior สวนกลับ reflects; KHAM FONG reflects. If `isReflected == true` on incoming damage, skip all further reflect checks. A reflected hit from Warrior that hits KHAM FONG does NOT trigger KHAM FONG's reflect.

**TAMRA-PINA overheal:**  
`currentHP` for TAMRA-PINA has NO cap. It can and will exceed `maxHP`. Never clamp. Display as "35 / 20" if needed.

**TAMRA-PINA Devour on absorbed KRASIP:**  
When a Tier1+ demon that absorbed a KRASIP is banished:
1. TAMRA-PINA heals from the Tier1+ demon's full HP
2. TAMRA-PINA heals from KRASIP's full HP (6)
3. Kill count increments by 1 only (not 2)
4. TAMRA-PINA gets +2 damage only once

**Guardian Passive state:**  
`bool wordBuiltLastTurn` resets to `false` at the start of each turn. Set to `true` only in Step 3 if word was successfully built AND not successfully challenged. If KHAM ANG skips the turn entirely, set to `false` (no word was built).

**KRASIP absorption timing:**  
Absorption happens at end of each turn (demon phase end). When multiple Tier1+ demons exist: highest HP absorbs, earliest entry as tiebreak. Update all absorption references before processing the next demon's turn.

**Stealth and AoE:**  
Archer in stealth receives -1 from AoE/ability damage. Stealth does NOT break from AoE. Only breaks when Archer: (a) chooses to attack, (b) uses Active ability. Ultimate does NOT break stealth.

**Demon Active priority:**  
Each round, before any demon uses Active: check all demons, find which one qualifies (ability trigger met), sort by HP descending then Tier descending. Only the first in that sorted list uses Active. All Passives still fire for all demons.

**ScriptableObjects are read-only:**  
Never write `demonData.currentHP = x`. Always have a runtime companion (`DemonRuntimeState`) that holds `currentHP`, `isBanished`, `survivedTurns`, `khamMakCostModifier`, `absorbedKrasip`, etc., with a reference to the ScriptableObject for static values.

---

## 9. Potential Issues

| Issue | Severity | Notes |
|---|---|---|
| Thai font rendering in Unity | High | Must configure TMP font atlas with Noto Sans Thai before any UI work. Thai vowels stack above/below consonants — broken atlas = boxes everywhere |
| PyThaiNLP word corpus ≠ RTGS dictionary | Medium | ~70k words but misses some. Honor-system fallback is acceptable for MVP |
| KHAM MAK cost ambiguity | Medium | Documented in §7 above. Implement as HP cost increase |
| Shared stack growth timing | Medium | Documented in §7 above. Use total turn count |
| TAMRA-PINA HP display overflow | Low | Ensure HP bar handles values > maxHP. Show as "35/20" not a broken bar |
| KRASIP dual-reference state | Medium | When absorbed, KRASIP card must exist in memory as child of host demon — not in Grave, not on field |
| Android SQLite path | Low | Handled in WordDatabase.cs already — copies to persistentDataPath on first launch |
| Reflect chain | Medium | `isReflected` bool on every damage event. Critical correctness issue |
| KHAM ANG one-use exhaustion | Low | Set `bool activeUsed = true` after firing. Never fire again in same combat session |
| Guardian cross-turn state | Low | `wordBuiltLastTurn` bool. Simple but must be in correct lifecycle position |

---

## 10. Recommended Build Order

```
Phase 1 — Foundation (build and test in isolation)
  [ ] ConsonantCardData ScriptableObject
  [ ] BonusCardData ScriptableObject
  [ ] CharacterClassData ScriptableObject
  [ ] DemonData ScriptableObject
  [ ] TypeAdvantageCalc (pure C#, NUnit test immediately)
  [ ] AttackType enum

Phase 2 — Card Management (Systems, no game loop yet)
  [ ] DeckManager (with NUnit tests)
  [ ] SharedStackManager (with NUnit tests)
  [ ] HandManager
  [ ] BonusCardManager
  [ ] DemonDeckManager

Phase 3 — Combat Resolution (Systems)
  [ ] SkillSystem (pure runtime state, NUnit-testable)
  [ ] StatusEffectSystem (stealth, reflect flag, temp armor, death mark)
  [ ] DemonAbilitySystem (each demon separately, tested individually)
  [ ] CombatSystem (wires everything together, integration tests)

Phase 4 — Game Loop
  [ ] GameStateManager (state machine, no logic)
  [ ] TurnManager (6-step executor)
  [ ] DemonAIManager (targeting per demon type)
  [ ] PvEManager (wave, kill count, win/lose)
  [ ] CoopManager (multi-player turn order, HP transfer)

Phase 5 — UI / Polish
  [ ] Thai font setup (DO THIS BEFORE ANY UI WORK)
  [ ] Card display, hand display
  [ ] Word input field + score display
  [ ] HP bars (must handle TAMRA-PINA overheal)
  [ ] Cooldown indicators
```

---

## 11. Project Files Available

The following source files are in the project knowledge base (search them if needed):

| File | Contents |
|---|---|
| `Roi-Kham_Full-Game-Design-Document.md` | GDD v1.4 — authoritative rules, all demon and hero stats |
| `Roi-Kham_Player-Manual.md` | Player-facing rules, quick reference, examples |
| `Roi-Kham_Print-Specification.md` | Exact card counts, consonant tier assignments, physical card layout |
| `ROI-KHAM_LORE_BIBLE_v2.md` | Lore, cosmology, character backstories |
| `ลายผ้าไทยและลายปักไทย.md` | Thai fabric/motif reference (for art, not game logic) |
| `โขนและเครื่องแต่งกายไทย.md` | Khon/costume reference (for art, not game logic) |

**Word System C# files** (built, ready to drop into Unity):  
Located in the outputs directory. Files: `BonusConditionType.cs`, `Models.cs`, `WordEntry.cs`, `IWordDatabase.cs`, `WordDatabase.cs`, `ConsonantValueResolver.cs`, `BonusConditionChecker.cs`, `WordScoreService.cs`, `WordSystemTests.cs`, `build_word_db.py`

---

## 12. Consonant Tier Assignments (from Print Spec)

| Tier | Value | Consonants | Count |
|---|---|---|---|
| 1 | +1 | ก น ร (6 each) + อ (8) | 26 |
| 2 | +2 | ม ง ว (5 each) + ย (7) | 22 |
| 3 | +3 | ด ต ส ล ห ค (3 each) | 18 |
| 4 | +4 | ข ป บ จ พ ท (2 each) | 12 |
| 5 | +5 | Triple cards (1 each × 8 types) | 8 |

**Tier 5 triple card groupings:**
- ผ/ถ/ณ · ศ/ธ/ษ · ญ/ภ/ซ · ฉ/ฐ/ฟ
- ฝ/ฏ/ฎ · ฒ/ฮ/ฑ · ฆ/ฬ/ฌ · ฃ/ฅ/ฤ

---

*Document version: Session 1 handoff — Word System complete*  
*Next session should begin at Phase 2: Card Management Systems*
