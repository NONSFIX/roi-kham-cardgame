// RoiKham.WordSystem — BonusConditionType.cs
// Maps every condition on all 20 bonus cards (GDD v1.4)
// Used by BonusConditionChecker to resolve checks against WordEntry data.

namespace RoiKham.WordSystem
{
    public enum BonusConditionType
    {
        None = 0,

        // ── Level 0  (+1) ─── semantic categories ──────────────────────────
        Animal,         // สัตว์
        Plant,          // พืช
        Food,           // อาหาร
        Drink,          // เครื่องดื่ม
        Vehicle,        // พาหนะ
        HouseItem,      // สิ่งของในบ้าน
        BodyPart,       // อวัยวะ
        FamilyMember,   // สมาชิกในครอบครัว
        Color,          // สี
        Shape,          // รูปร่าง
        Nature,         // ธรรมชาติ
        Weather,        // สภาพอากาศ
        Sport,          // กีฬา
        Hobby,          // งานอดิเรก
        Fruit,          // ผลไม้
        Vegetable,      // ผัก

        // ── Level 1  (+2) ─── grammatical / structural ─────────────────────
        Noun,               // คำนาม
        Verb,               // คำกริยา
        Pronoun,            // คำสรรพนาม
        Interjection,       // คำอุทาน
        MidOrHighInitial,   // อักษรกลาง/สูง เป็นพยัญชนะต้น
        LowInitial,         // อักษรต่ำ เป็นพยัญชนะต้น
        HasVissajaniya,     // ประวิสรรชนีย์ (มี ะ)
        HasBunBrr,          // คำที่ขึ้นต้นด้วย บัน/บรร

        // ── Level 2  (+4) ─── advanced grammatical ─────────────────────────
        LiveWord,               // คำเป็น
        DeadWord,               // คำตาย
        RoyalVocab,             // ราชาศัพท์
        ForeignLoan,            // คำจากภาษาต่างประเทศ
        FinalKok_Or_Kod,        // แม่กก หรือ แม่กด
        FinalKob_Or_Kong,       // แม่กบ หรือ แม่กง
        FinalKon_Or_Kom,        // แม่กน หรือ แม่กม
        FinalKoey_Or_Koew,      // แม่เกย หรือ แม่เกอว
        Adjective,              // คำวิเศษณ์
        PrepOrConjunction,      // คำบุพบท หรือ คำเชื่อม

        // ── Level 3  (+6) ─── complex word structures ──────────────────────
        RepeatedWord,       // คำซ้ำ (contains ๆ)
        SynonymPair,        // คำซ้อน
        CompoundWord,       // คำประสม
        SamatWord,          // คำสมาส
        Transliteration,    // คำทับศัพท์
        CoinedTerm,         // คำบัญญัติ
    }
}
