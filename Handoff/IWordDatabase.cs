// RoiKham.WordSystem — IWordDatabase.cs
// Interface for all word database implementations.
// WordScoreService depends only on this — never on the concrete SQLite class.
// Swap in MockWordDatabase during NUnit tests without touching game logic.

namespace RoiKham.WordSystem
{
    public interface IWordDatabase
    {
        /// <summary>
        /// Returns the full WordEntry for the given Thai word,
        /// or null if the word is not in the database.
        /// </summary>
        WordEntry Query(string word);

        /// <summary>Convenience: true when Query(word) != null.</summary>
        bool IsValid(string word);

        void Close();
    }
}
