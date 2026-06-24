// RoiKham.WordSystem — Models.cs
// Plain C# structs / classes — no MonoBehaviour dependency.
// Safe to use in NUnit tests without a Unity runtime.

namespace RoiKham.WordSystem
{
    // ── Input ──────────────────────────────────────────────────────────────────

    /// <summary>
    /// Represents one consonant card's contribution to the current word.
    /// The player selects which consonant(s) from a card they are using.
    /// Tier 5 cards carry 3 consonants; only the subset used here is counted.
    /// </summary>
    public readonly struct ConsonantUsage
    {
        /// <summary>Card tier (1–5). Determines value per consonant used.</summary>
        public readonly int Tier;

        /// <summary>All consonants printed on this physical card (1–3 chars).</summary>
        public readonly char[] CardConsonants;

        /// <summary>
        /// The consonants from this card that the player is using in the word.
        /// Must be a subset of CardConsonants.
        /// </summary>
        public readonly char[] UsedConsonants;

        public ConsonantUsage(int tier, char[] cardConsonants, char[] usedConsonants)
        {
            Tier           = tier;
            CardConsonants = cardConsonants;
            UsedConsonants = usedConsonants;
        }

        // Convenience constructor for Tier 1–4 (single consonant per card)
        public ConsonantUsage(int tier, char consonant)
        {
            Tier           = tier;
            CardConsonants = new[] { consonant };
            UsedConsonants = new[] { consonant };
        }
    }

    /// <summary>
    /// Describes which bonus card is active for a turn.
    /// In Unity this is populated from a BonusCardData ScriptableObject.
    /// Kept as a plain struct here so logic stays decoupled from Unity.
    /// </summary>
    public readonly struct BonusCardInfo
    {
        public readonly int                Level;       // 0 | 1 | 2 | 3
        public readonly BonusConditionType ConditionA;
        public readonly BonusConditionType ConditionB;

        public int BonusValue => Level switch
        {
            0 => 1,
            1 => 2,
            2 => 4,
            3 => 6,
            _ => 0
        };

        public BonusCardInfo(int level, BonusConditionType a, BonusConditionType b)
        {
            Level      = level;
            ConditionA = a;
            ConditionB = b;
        }
    }

    // ── Output ─────────────────────────────────────────────────────────────────

    /// <summary>
    /// Full result returned by WordScoreService.Calculate().
    /// Contains every value needed by the game UI and combat system.
    /// </summary>
    public class WordScoreResult
    {
        // ── Validity ─────────────────────────────────────────────────────────
        /// <summary>False when word is not found in the database (challenge succeeds).</summary>
        public bool   IsValid { get; set; }
        public string Word    { get; set; }

        // ── Score components ─────────────────────────────────────────────────
        /// <summary>Syllable count from database.</summary>
        public int SyllableCount { get; set; }

        /// <summary>+1 per syllable. Formula: SyllableCount × 1.</summary>
        public int SyllableScore { get; set; }

        /// <summary>Sum of (Tier value × consonants used) across all cards.</summary>
        public int ConsonantValue { get; set; }

        /// <summary>+5 if two consonants from one Tier-5 card; +15 if all three.</summary>
        public int TripleBonus { get; set; }

        /// <summary>Bonus from current bonus card if any condition was met.</summary>
        public int BonusValue { get; set; }

        /// <summary>Final Word Power = SyllableScore + ConsonantValue + TripleBonus + BonusValue.</summary>
        public int TotalWordPower { get; set; }

        // ── Bonus detail ──────────────────────────────────────────────────────
        public bool                 ConditionAMet     { get; set; }
        public bool                 ConditionBMet     { get; set; }
        public bool                 AnyBonusMet       => ConditionAMet || ConditionBMet;
        public BonusConditionType?  MetCondition      { get; set; }
        public string               MetConditionLabel { get; set; }

        // ── Debug / UI ────────────────────────────────────────────────────────
        public string Breakdown =>
            IsValid
                ? $"Syllable({SyllableScore}) + Consonant({ConsonantValue}) + Triple({TripleBonus}) + Bonus({BonusValue}) = {TotalWordPower}"
                : $"'{Word}' — not in dictionary";

        public static WordScoreResult Invalid(string word) =>
            new() { IsValid = false, Word = word };
    }
}
