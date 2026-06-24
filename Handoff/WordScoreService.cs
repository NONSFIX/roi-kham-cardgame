// RoiKham.WordSystem — WordScoreService.cs
// Main entry point for the word scoring pipeline.
// Inject IWordDatabase at construction; call Calculate() each turn.
//
// USAGE (Unity):
//   var db      = WordDatabase.LoadFromStreamingAssets();
//   var service = new WordScoreService(db);
//
//   var usages = new[] {
//       new ConsonantUsage(2, 'ม'),   // ม Tier 2
//       new ConsonantUsage(2, 'ง'),   // ง Tier 2
//       new ConsonantUsage(1, 'ก'),   // ก Tier 1
//       new ConsonantUsage(1, 'ร'),   // ร Tier 1
//   };
//   var bonus  = new BonusCardInfo(0, BonusConditionType.Animal, BonusConditionType.Plant);
//   var result = service.Calculate("มังกร", usages, bonus);
//   // result.TotalWordPower == 8  (syl:2 + con:6 + bonus:0)
//   // result.Breakdown == "Syllable(2) + Consonant(6) + Triple(0) + Bonus(0) = 8"

using System.Collections.Generic;

namespace RoiKham.WordSystem
{
    public class WordScoreService
    {
        readonly IWordDatabase _db;

        public WordScoreService(IWordDatabase database)
        {
            _db = database;
        }

        /// <summary>
        /// Calculates the full word score for one turn.
        ///
        /// Parameters:
        ///   word           — Thai word string the player declared
        ///   consonantsUsed — one ConsonantUsage per card played (hand + shared stack)
        ///   bonusCard      — the bonus card flipped this turn
        ///
        /// Returns WordScoreResult with IsValid=false when word is not in dictionary.
        /// </summary>
        public WordScoreResult Calculate(
            string                      word,
            IEnumerable<ConsonantUsage> consonantsUsed,
            BonusCardInfo               bonusCard)
        {
            // ── 1. Dictionary lookup ──────────────────────────────────────────
            var entry = _db.Query(word);
            if (entry == null)
                return WordScoreResult.Invalid(word);

            // ── 2. Syllable score ─────────────────────────────────────────────
            int syllableCount = entry.SyllableCount;
            int syllableScore = ConsonantValueResolver.SyllableScore(syllableCount);

            // ── 3. Consonant value + triple bonus ─────────────────────────────
            var (consonantValue, tripleBonus) = ConsonantValueResolver.Calculate(consonantsUsed);

            // ── 4. Bonus card conditions ──────────────────────────────────────
            bool condA = BonusConditionChecker.Check(bonusCard.ConditionA, entry, word);
            bool condB = BonusConditionChecker.Check(bonusCard.ConditionB, entry, word);

            int                 bonusValue = 0;
            BonusConditionType? metCondition = null;
            string              metLabel     = "";

            // Only one condition counts per word (first match wins: A before B)
            if (condA)
            {
                bonusValue   = bonusCard.BonusValue;
                metCondition = bonusCard.ConditionA;
                metLabel     = bonusCard.ConditionA.ToString();
            }
            else if (condB)
            {
                bonusValue   = bonusCard.BonusValue;
                metCondition = bonusCard.ConditionB;
                metLabel     = bonusCard.ConditionB.ToString();
            }

            // ── 5. Assemble result ────────────────────────────────────────────
            int total = syllableScore + consonantValue + tripleBonus + bonusValue;

            return new WordScoreResult
            {
                IsValid           = true,
                Word              = word,
                SyllableCount     = syllableCount,
                SyllableScore     = syllableScore,
                ConsonantValue    = consonantValue,
                TripleBonus       = tripleBonus,
                BonusValue        = bonusValue,
                TotalWordPower    = total,
                ConditionAMet     = condA,
                ConditionBMet     = condB,
                MetCondition      = metCondition,
                MetConditionLabel = metLabel,
            };
        }
    }
}
