// RoiKham.WordSystem — BonusConditionChecker.cs
// Pure static class — no Unity dependencies, NUnit-testable.
//
// Resolution strategy per condition:
//   DB-sourced  — reads pre-computed fields from WordEntry (POS, FinalClass, etc.)
//   Deterministic — pure string/char logic, no DB field needed
//   Category    — checks WordEntry.Categories comma list
//
// When entry == null (word not in DB), all checks return false.

using System;
using System.Collections.Generic;
using System.Linq;

namespace RoiKham.WordSystem
{
    public static class BonusConditionChecker
    {
        // ── Category string map ───────────────────────────────────────────────
        // BonusConditionType → expected substring in WordEntry.Categories

        static readonly Dictionary<BonusConditionType, string> CategoryMap = new()
        {
            [BonusConditionType.Animal]         = "animal",
            [BonusConditionType.Plant]          = "plant",
            [BonusConditionType.Food]           = "food",
            [BonusConditionType.Drink]          = "drink",
            [BonusConditionType.Vehicle]        = "vehicle",
            [BonusConditionType.HouseItem]      = "house_item",
            [BonusConditionType.BodyPart]       = "body_part",
            [BonusConditionType.FamilyMember]   = "family",
            [BonusConditionType.Color]          = "color",
            [BonusConditionType.Shape]          = "shape",
            [BonusConditionType.Nature]         = "nature",
            [BonusConditionType.Weather]        = "weather",
            [BonusConditionType.Sport]          = "sport",
            [BonusConditionType.Hobby]          = "hobby",
            [BonusConditionType.Fruit]          = "fruit",
            [BonusConditionType.Vegetable]      = "vegetable",
            [BonusConditionType.SynonymPair]    = "synonym_pair",
            [BonusConditionType.CompoundWord]   = "compound",
            [BonusConditionType.SamatWord]      = "samat",
            [BonusConditionType.Transliteration]= "transliteration",
            [BonusConditionType.CoinedTerm]     = "coined",
        };

        // Final class groupings (GDD §Bonus Level 2)
        static readonly Dictionary<BonusConditionType, string[]> FinalClassMap = new()
        {
            [BonusConditionType.FinalKok_Or_Kod]    = new[] { "กก", "กด" },
            [BonusConditionType.FinalKob_Or_Kong]   = new[] { "กบ", "กง" },
            [BonusConditionType.FinalKon_Or_Kom]    = new[] { "กน", "กม" },
            [BonusConditionType.FinalKoey_Or_Koew]  = new[] { "เกย", "เกอว" },
        };

        // ── Public API ────────────────────────────────────────────────────────

        /// <summary>
        /// Returns true if this condition is satisfied for the given word.
        /// entry    — row from WordDatabase (null if word not found → always false)
        /// rawWord  — original Thai string, used for deterministic checks (ๆ, บัน, etc.)
        /// </summary>
        public static bool Check(
            BonusConditionType condition,
            WordEntry          entry,
            string             rawWord)
        {
            if (entry == null)                    return false;
            if (condition == BonusConditionType.None) return false;

            // Semantic category
            if (CategoryMap.TryGetValue(condition, out string cat))
                return HasCategory(entry, cat);

            // Final consonant class
            if (FinalClassMap.TryGetValue(condition, out string[] classes))
                return classes.Contains(entry.FinalClass);

            // Everything else
            return condition switch
            {
                // POS
                BonusConditionType.Noun              => PosIs(entry, "NOUN"),
                BonusConditionType.Verb              => PosIs(entry, "VERB"),
                BonusConditionType.Pronoun           => PosIs(entry, "PRON"),
                BonusConditionType.Interjection      => PosIs(entry, "INTJ"),
                BonusConditionType.Adjective         => PosIs(entry, "ADJ"),
                BonusConditionType.PrepOrConjunction => PosIs(entry, "PREP") || PosIs(entry, "CONJ"),

                // Consonant initial class
                BonusConditionType.MidOrHighInitial => entry.LeadClass is "mid" or "high",
                BonusConditionType.LowInitial       => entry.LeadClass == "low",

                // Live / dead word
                BonusConditionType.LiveWord => entry.LiveDead == "live",
                BonusConditionType.DeadWord => entry.LiveDead == "dead",

                // Vocabulary type
                BonusConditionType.RoyalVocab   => entry.IsRoyal == 1,
                BonusConditionType.ForeignLoan  => entry.IsForeign == 1,

                // Structural / deterministic (rawWord)
                BonusConditionType.HasVissajaniya => entry.HasVissajaniya == 1,
                BonusConditionType.HasBunBrr      => entry.HasBunBrr == 1,
                BonusConditionType.RepeatedWord   => rawWord?.Contains('ๆ') == true,

                _ => false
            };
        }

        // ── Helpers ───────────────────────────────────────────────────────────

        static bool HasCategory(WordEntry entry, string category)
        {
            if (string.IsNullOrEmpty(entry.Categories)) return false;
            return entry.Categories
                .Split(',', StringSplitOptions.RemoveEmptyEntries)
                .Any(c => c.Trim().Equals(category, StringComparison.OrdinalIgnoreCase));
        }

        static bool PosIs(WordEntry entry, string pos) =>
            string.Equals(entry.POS, pos, StringComparison.OrdinalIgnoreCase);
    }
}
