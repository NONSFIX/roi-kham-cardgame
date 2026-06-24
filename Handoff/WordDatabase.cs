// RoiKham.WordSystem — WordDatabase.cs
// Concrete SQLite-backed implementation of IWordDatabase.
// Uses SQLite-net (install via: https://github.com/praeclarum/sqlite-net)
//
// SETUP:
//   1. Add sqlite-net-pcl to your project via NuGet or Unity Package Manager.
//   2. Copy words.db → Assets/StreamingAssets/words.db
//   3. Call WordDatabase.LoadFromStreamingAssets() at game startup.
//   4. Pass the returned instance to WordScoreService.

using System;
using System.IO;
using SQLite;
using UnityEngine;

namespace RoiKham.WordSystem
{
    public class WordDatabase : IWordDatabase, IDisposable
    {
        static readonly string DbFileName = "words.db";

        readonly SQLiteConnection _conn;

        // ── Construction ──────────────────────────────────────────────────────

        public WordDatabase(string absolutePath)
        {
            _conn = new SQLiteConnection(absolutePath, SQLiteOpenFlags.ReadOnly);
        }

        /// <summary>
        /// Preferred factory method for Unity builds.
        /// Handles the Android StreamingAssets-to-persistentDataPath copy automatically.
        /// Call once at startup (e.g. from a GameBootstrap MonoBehaviour).
        /// </summary>
        public static WordDatabase LoadFromStreamingAssets()
        {
            string path = ResolveDbPath();
            return new WordDatabase(path);
        }

        static string ResolveDbPath()
        {
#if UNITY_ANDROID && !UNITY_EDITOR
            // Android: StreamingAssets lives inside the APK (not a normal file path).
            // We must copy the file to persistentDataPath before SQLite can open it.
            string dest = Path.Combine(Application.persistentDataPath, DbFileName);

            if (!File.Exists(dest))
            {
                string src = Path.Combine(Application.streamingAssetsPath, DbFileName);
                using var www = UnityEngine.Networking.UnityWebRequest.Get(src);
                www.SendWebRequest();
                while (!www.isDone) { }   // blocking copy at startup — acceptable here

                if (www.result != UnityEngine.Networking.UnityWebRequest.Result.Success)
                    throw new Exception($"WordDatabase: failed to copy db on Android — {www.error}");

                File.WriteAllBytes(dest, www.downloadHandler.data);
            }
            return dest;
#else
            return Path.Combine(Application.streamingAssetsPath, DbFileName);
#endif
        }

        // ── IWordDatabase ─────────────────────────────────────────────────────

        /// <summary>O(log n) primary-key lookup. Returns null when not found.</summary>
        public WordEntry Query(string word)
        {
            if (string.IsNullOrEmpty(word)) return null;
            return _conn.Find<WordEntry>(word);
        }

        public bool IsValid(string word) => Query(word) != null;

        public void Close()   => _conn.Close();
        public void Dispose() => _conn.Dispose();
    }

    // ── Mock for unit tests ───────────────────────────────────────────────────

    /// <summary>
    /// In-memory database for NUnit tests.
    /// Populate Entries before running tests; no SQLite file needed.
    /// </summary>
    public class MockWordDatabase : IWordDatabase
    {
        readonly System.Collections.Generic.Dictionary<string, WordEntry> _entries;

        public MockWordDatabase(
            System.Collections.Generic.Dictionary<string, WordEntry> entries = null)
        {
            _entries = entries ?? new System.Collections.Generic.Dictionary<string, WordEntry>();
        }

        public WordEntry Query(string word) =>
            _entries.TryGetValue(word, out var e) ? e : null;

        public bool IsValid(string word) => _entries.ContainsKey(word);

        public void Close() { }
    }
}
