// RoiKham.WordSystem — ConsonantValueResolver.cs
// Pure static class — no Unity dependencies, NUnit-testable.
// Calculates consonant point total and Tier-5 triple bonus from card usages.

using System.Collections.Generic;

namespace RoiKham.WordSystem
{
    public static class ConsonantValueResolver
    {
        // Tier → point value per consonant used (GDD §2.3)
        public static int TierValue(int tier) => tier switch
        {
            1 => 1,
            2 => 2,
            3 => 3,
            4 => 4,
            5 => 5,
            _ => 0
        };

        /// <summary>
        /// Returns (consonantValue, tripleBonus) for the given set of card usages.
        ///
        /// consonantValue: sum of TierValue(tier) × count(usedConsonants) per card.
        ///
        /// tripleBonus: for Tier-5 cards only —
        ///   2 consonants used from one card → +5
        ///   3 consonants used from one card → +15
        ///   (GDD §2.3 — Triple Cards special rule)
        /// </summary>
        public static (int consonantValue, int tripleBonus) Calculate(
            IEnumerable<ConsonantUsage> usages)
        {
            int consonantValue = 0;
            int tripleBonus    = 0;

            foreach (var usage in usages)
            {
                int usedCount    = usage.UsedConsonants?.Length ?? 0;
                consonantValue  += TierValue(usage.Tier) * usedCount;

                if (usage.Tier == 5)
                {
                    tripleBonus += usedCount switch
                    {
                        2 => 5,
                        3 => 15,
                        _ => 0
                    };
                }
            }

            return (consonantValue, tripleBonus);
        }

        /// <summary>
        /// Syllable score: +1 per syllable, regardless of count.
        /// (GDD §4.2 — คะแนนพยางค์)
        /// </summary>
        public static int SyllableScore(int syllableCount) => syllableCount;
    }
}
