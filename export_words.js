// Regenerate prototype/words.js from Handoff/words.db
// Requires Node.js 22+ (built-in node:sqlite)
//
// Usage:
//   node export_words.js

const { DatabaseSync } = require("node:sqlite");
const fs = require("fs");
const path = require("path");

const ROOT     = __dirname;
const DB_PATH  = path.join(ROOT, "Handoff", "words.db");
const OUT_PATH = path.join(ROOT, "prototype", "words.js");

// PyThaiNLP Orchid POS → game POS
const POS_MAP = {
  NCMN:"NOUN", NCNM:"NOUN", NPRP:"NOUN", NTTL:"NOUN", NONM:"NOUN", FIXN:"NOUN",
  CNIT:"NOUN", CFQC:"NOUN", CLTV:"NOUN", CMTR:"NOUN",
  VACT:"VERB", VATT:"VERB", FIXV:"VERB", XVAE:"VERB", XVAM:"VERB", XVBM:"VERB", XVMM:"VERB",
  VSTA:"ADJ",
  ADVI:"ADV", ADVN:"ADV", ADVP:"ADV", ADVS:"ADV", NEG:"ADV",
  PPRS:"PRON", PREL:"PRON",
  EAFF:"INTJ", EITT:"INTJ",
  JCMP:"CONJ", JCRG:"CONJ", JSBR:"CONJ",
  PDMN:"PREP", PNTR:"PREP",
};

function mapLC(lc) {
  return lc === "ต่ำ" ? "low" : "mid";
}
function mapFC(fc) {
  return (!fc || fc === "สระ") ? "none" : fc;
}

const db = new DatabaseSync(DB_PATH);
const rows = db.prepare(
  "SELECT word, syllables, pos, leading_class, final_class, live_dead, has_sara_a, has_ban_bor, " +
  "COALESCE(categories, '') AS categories " +
  "FROM words WHERE pos <> 'PUNC' AND word <> ''"
).all();
db.close();

console.log(`Exporting ${rows.length} words…`);

const out = {};
for (const r of rows) {
  out[r.word] = [
    r.syllables,
    POS_MAP[r.pos] || "NOUN",
    r.live_dead || "live",
    mapFC(r.final_class),
    mapLC(r.leading_class),
    r.has_sara_a ? 1 : 0,
    r.has_ban_bor ? 1 : 0,
    r.categories || "",   // index [7] — comma-separated semantic categories
  ];
}

const header = `// Roi-Kham Word Database — generated from Handoff/words.db\n` +
  `// ${rows.length} words · [syllables, pos, live_dead, final_class, lead_class, has_sara_a, has_ban_bor, categories]\n` +
  `window.WORD_DB = `;

fs.writeFileSync(OUT_PATH, header + JSON.stringify(out) + ";\n", "utf8");

const mb = (fs.statSync(OUT_PATH).size / 1024 / 1024).toFixed(2);
console.log(`Done → ${OUT_PATH}  (${mb} MB, ${Object.keys(out).length} words)`);
