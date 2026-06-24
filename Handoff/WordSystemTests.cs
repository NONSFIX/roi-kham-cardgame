// RoiKham.WordSystem.Tests — WordSystemTests.cs
// NUnit tests for all logic layers.
// Run in Unity Test Runner (EditMode) — no scene, no MonoBehaviour needed.
// MockWordDatabase replaces SQLite for deterministic, fast tests.

using System.Collections.Generic;
using NUnit.Framework;
using RoiKham.WordSystem;

namespace RoiKham.WordSystem.Tests
{
    [TestFixture]
    public class ConsonantValueResolverTests
    {
        [Test]
        public void Mangkon_TwoSyllables_Score8()
        {
            // มังกร: ม(T2) ง(T2) ก(T1) ร(T1) — 2 syllables
            // Expected: syllable(2) + consonant(2+2+1+1=6) = 8
            var usages = new[]
            {
                new ConsonantUsage(2, 'ม'),
                new ConsonantUsage(2, 'ง'),
                new ConsonantUsage(1, 'ก'),
                new ConsonantUsage(1, 'ร'),
            };
            var (con, triple) = ConsonantValueResolver.Calculate(usages);
            int syl = ConsonantValueResolver.SyllableScore(2);

            Assert.AreEqual(6, con);
            Assert.AreEqual(0, triple);
            Assert.AreEqual(2, syl);
            Assert.AreEqual(8, syl + con + triple);
        }

        [Test]
        public void Tier5Card_TwoConsonantsUsed_TripleBonus5()
        {
            // Using 2 consonants from one Tier-5 triple card
            var usage = new ConsonantUsage(
                tier:            5,
                cardConsonants:  new[] { 'ศ', 'ธ', 'ษ' },
                usedConsonants:  new[] { 'ศ', 'ธ' }
            );
            var (con, triple) = ConsonantValueResolver.Calculate(new[] { usage });
            Assert.AreEqual(10, con);    // 2 × 5
            Assert.AreEqual(5,  triple); // pair bonus
        }

        [Test]
        public void Tier5Card_AllThreeUsed_TripleBonus15()
        {
            var usage = new ConsonantUsage(5,
                new[] { 'ศ', 'ธ', 'ษ' },
                new[] { 'ศ', 'ธ', 'ษ' });
            var (con, triple) = ConsonantValueResolver.Calculate(new[] { usage });
            Assert.AreEqual(15, con);
            Assert.AreEqual(15, triple);
        }
    }

    // ── BonusConditionChecker ─────────────────────────────────────────────────

    [TestFixture]
    public class BonusConditionCheckerTests
    {
        WordEntry AnimalEntry()   => new() { Word = "ช้าง", POS = "NOUN",
                                             LeadClass = "low", LiveDead = "live",
                                             FinalClass = "กง", Categories = "animal,mammal",
                                             SyllableCount = 1 };

        WordEntry RoyalEntry()    => new() { Word = "เสวย", POS = "VERB",
                                             LeadClass = "low", LiveDead = "live",
                                             FinalClass = "เกย", Categories = "",
                                             IsRoyal = 1 };

        WordEntry DeadWordEntry() => new() { Word = "กัก", POS = "VERB",
                                             LiveDead = "dead", FinalClass = "กก",
                                             LeadClass = "mid", Categories = "" };

        [Test] public void Animal_Category_True()
            => Assert.IsTrue(BonusConditionChecker.Check(
                BonusConditionType.Animal, AnimalEntry(), "ช้าง"));

        [Test] public void Noun_POS_True()
            => Assert.IsTrue(BonusConditionChecker.Check(
                BonusConditionType.Noun, AnimalEntry(), "ช้าง"));

        [Test] public void RoyalVocab_Flag_True()
            => Assert.IsTrue(BonusConditionChecker.Check(
                BonusConditionType.RoyalVocab, RoyalEntry(), "เสวย"));

        [Test] public void DeadWord_LiveDead_True()
            => Assert.IsTrue(BonusConditionChecker.Check(
                BonusConditionType.DeadWord, DeadWordEntry(), "กัก"));

        [Test] public void FinalKok_Or_Kod_FinalClass_True()
            => Assert.IsTrue(BonusConditionChecker.Check(
                BonusConditionType.FinalKok_Or_Kod, DeadWordEntry(), "กัก"));

        [Test] public void RepeatedWord_Yamok_True()
        {
            var entry = new WordEntry { Word = "ดีๆ", LiveDead = "live", SyllableCount = 2 };
            Assert.IsTrue(BonusConditionChecker.Check(
                BonusConditionType.RepeatedWord, entry, "ดีๆ"));
        }

        [Test] public void NullEntry_AlwaysFalse()
            => Assert.IsFalse(BonusConditionChecker.Check(
                BonusConditionType.Animal, null, "anything"));
    }

    // ── WordScoreService (full integration via Mock) ──────────────────────────

    [TestFixture]
    public class WordScoreServiceTests
    {
        IWordDatabase BuildDb(params WordEntry[] entries)
        {
            var dict = new Dictionary<string, WordEntry>();
            foreach (var e in entries) dict[e.Word] = e;
            return new MockWordDatabase(dict);
        }

        [Test]
        public void Mangkon_AnimalBonus_Score9()
        {
            // มังกร is a dragon — classified as animal
            var db = BuildDb(new WordEntry
            {
                Word = "มังกร", SyllableCount = 2, POS = "NOUN",
                LiveDead = "live", FinalClass = "กน", LeadClass = "low",
                Categories = "animal"
            });
            var service = new WordScoreService(db);

            var usages = new[]
            {
                new ConsonantUsage(2, 'ม'),
                new ConsonantUsage(2, 'ง'),
                new ConsonantUsage(1, 'ก'),
                new ConsonantUsage(1, 'ร'),
            };
            // Bonus card Level 0: Animal | Plant (+1)
            var bonus = new BonusCardInfo(0, BonusConditionType.Animal, BonusConditionType.Plant);

            var result = service.Calculate("มังกร", usages, bonus);

            Assert.IsTrue(result.IsValid);
            Assert.AreEqual(2,  result.SyllableScore);
            Assert.AreEqual(6,  result.ConsonantValue);
            Assert.AreEqual(0,  result.TripleBonus);
            Assert.AreEqual(1,  result.BonusValue);       // Animal hit → +1
            Assert.AreEqual(9,  result.TotalWordPower);
            Assert.IsTrue(result.ConditionAMet);
            Assert.AreEqual("Animal", result.MetConditionLabel);
        }

        [Test]
        public void UnknownWord_ReturnsInvalid()
        {
            var db      = BuildDb(); // empty
            var service = new WordScoreService(db);
            var result  = service.Calculate("zzz", System.Array.Empty<ConsonantUsage>(),
                                            new BonusCardInfo(0, BonusConditionType.None, BonusConditionType.None));
            Assert.IsFalse(result.IsValid);
            Assert.AreEqual(0, result.TotalWordPower);
        }

        [Test]
        public void ConditionBMet_WhenAFails()
        {
            var db = BuildDb(new WordEntry
            {
                Word = "แมว", SyllableCount = 1, POS = "NOUN",
                LiveDead = "live", FinalClass = "เกอว", LeadClass = "low",
                Categories = "animal"
            });
            var service = new WordScoreService(db);
            // Bonus card: Fruit (A) | Animal (B) — A will fail, B will hit
            var bonus  = new BonusCardInfo(0, BonusConditionType.Fruit, BonusConditionType.Animal);
            var result = service.Calculate("แมว",
                new[] { new ConsonantUsage(2, 'ม'), new ConsonantUsage(2, 'ว') }, bonus);

            Assert.IsFalse(result.ConditionAMet);
            Assert.IsTrue(result.ConditionBMet);
            Assert.AreEqual(1, result.BonusValue);
        }
    }
}
