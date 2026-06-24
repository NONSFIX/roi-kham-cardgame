// RoiKham.WordSystem — WordEntry.cs
// SQLite-net row model. Every field matches a column in words.db.
// Pre-computed at build time by build_word_db.py using PyThaiNLP.
// Read-only at runtime — never write back to this table.

using SQLite;

namespace RoiKham.WordSystem
{
    [Table("words")]
    public class WordEntry
    {
        /// <summary>Thai word string — primary key for all lookups.</summary>
        [PrimaryKey]
        public string Word { get; set; }

        /// <summary>Number of syllables. Source: PyThaiNLP syllable_tokenize().</summary>
        public int SyllableCount { get; set; }

        /// <summary>
        /// Part of speech. Values: NOUN | VERB | ADJ | ADV | PRON | INTJ | PREP | CONJ
        /// Source: PyThaiNLP pos_tag (Orchid corpus), normalised.
        /// Empty string when unknown.
        /// </summary>
        public string POS { get; set; }

        /// <summary>
        /// คำเป็น / คำตาย.  Values: "live" | "dead" | "unknown"
        /// Source: computed from final consonant phonology.
        /// </summary>
        public string LiveDead { get; set; }

        /// <summary>
        /// Final consonant class (แม่). Values: กก | กด | กบ | กง | กน | กม | เกย | เกอว | none
        /// Source: computed from last phonetic consonant of the word.
        /// </summary>
        public string FinalClass { get; set; }

        /// <summary>
        /// Leading consonant class. Values: mid | high | low
        /// Source: lookup table against the 44 Thai consonants.
        /// </summary>
        public string LeadClass { get; set; }

        /// <summary>1 if loanword / transliteration. Source: PyThaiNLP loanword corpus.</summary>
        public int IsForeign { get; set; }

        /// <summary>1 if royal vocabulary (ราชาศัพท์). Source: manually curated royal_vocab.txt.</summary>
        public int IsRoyal { get; set; }

        /// <summary>1 if word contains ะ (ประวิสรรชนีย์).</summary>
        public int HasVissajaniya { get; set; }

        /// <summary>1 if word starts with บัน or บรร.</summary>
        public int HasBunBrr { get; set; }

        /// <summary>
        /// Comma-separated semantic category tags.
        /// Example: "animal,mammal" or "food,fruit"
        /// Source: PyThaiNLP WordNet hypernym chain.
        /// Empty when no category resolved.
        /// </summary>
        public string Categories { get; set; }
    }
}
