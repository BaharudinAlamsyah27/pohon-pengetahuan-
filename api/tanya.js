const fs = require("fs");
const path = require("path");

const STOPWORDS = new Set([
  "yang", "dan", "di", "ke", "dari", "untuk", "pada", "dengan", "ini", "itu", "atau",
  "adalah", "akan", "tidak", "bisa", "juga", "agar", "karena", "oleh", "dalam", "sebagai",
  "jika", "bila", "saat", "ada", "lebih", "hanya", "tetap", "masih", "sudah", "belum",
  "apa", "bagaimana", "mengapa", "kenapa", "siapa", "kapan", "dimana", "tentang", "cara",
  "the", "and", "for", "that", "this", "with", "from", "are", "was", "have", "not", "how", "what",
]);

function tokenize(text) {
  return (String(text || "").toLowerCase().match(/[a-z0-9]+/g) || []).filter(
    (w) => w.length >= 2 && !STOPWORDS.has(w)
  );
}

async function loadPublicDataset(req) {
  const candidates = [
    path.join(process.cwd(), "situs", "data.json"),
    path.join(__dirname, "..", "situs", "data.json"),
  ];
  for (const fp of candidates) {
    if (fs.existsSync(fp)) {
      return JSON.parse(fs.readFileSync(fp, "utf-8"));
    }
  }
  const host = req?.headers?.["x-forwarded-host"] || req?.headers?.host;
  const proto = req?.headers?.["x-forwarded-proto"] || "https";
  if (host) {
    try {
      const resp = await fetch(`${proto}://${host}/data.json`, { signal: AbortSignal.timeout(5000) });
      if (resp.ok) return await resp.json();
    } catch {}
  }
  return { kartu: [] };
}

function rankCards(question, cards, limit = 8) {
  const qTokens = tokenize(question);
  if (!cards.length) return [];
  const docTokens = cards.map((c) => {
    const blob = `${c.ide || ""} ${c.ide || ""} ${c.penjelasan || ""} ${(c.tag || []).join(" ")} ${c.cabang || ""}`;
    return tokenize(blob);
  });
  const df = {};
  docTokens.forEach((toks) => {
    new Set(toks).forEach((w) => {
      df[w] = (df[w] || 0) + 1;
    });
  });

  const nDocs = cards.length;
  const scored = cards.map((c, idx) => {
    const toks = docTokens[idx];
    const tf = {};
    toks.forEach((w) => {
      tf[w] = (tf[w] || 0) + 1;
    });
    let score = 0;
    qTokens.forEach((qt) => {
      if (tf[qt]) {
        const idf = Math.log((nDocs + 1) / ((df[qt] || 0) + 1)) + 1;
        score += (1 + Math.log(tf[qt])) * idf;
      } else {
        Object.keys(tf).forEach((dw) => {
          if (dw.includes(qt) || qt.includes(dw)) score += 0.4;
        });
      }
    });
    return { card: c, score };
  });

  const hits = scored.filter((x) => x.score > 0).sort((a, b) => b.score - a.score);
  return hits.slice(0, limit).map((x) => x.card);
}

function buildLevel1Synthesis(question, relCards) {
  if (!relCards.length) {
    return `Belum ada kartu publik yang cocok dengan pertanyaan "${question}".`;
  }
  const lines = [`Berdasarkan ${relCards.length} kartu publik teratas:`];
  const lowTrust = [];
  relCards.slice(0, 5).forEach((c) => {
    const detail = c.penjelasan && c.penjelasan !== c.ide ? `${c.ide} (${c.penjelasan.slice(0, 200)})` : c.ide;
    lines.push(`- [${c.id}] (${c.cabang} · kepercayaan: ${c.kepercayaan}) — ${detail}`);
    if (c.kepercayaan === "rendah" || c.kepercayaan === "belum-diverifikasi") {
      lowTrust.push(c.id);
    }
  });
  if (lowTrust.length) {
    lines.push(`\nPeringatan kualitas: kartu ${lowTrust.join(", ")} masih berkepercayaan rendah/belum diverifikasi.`);
  }
  return lines.join("\n");
}

async function callGeminiRag(question, relCards, apiKey, preferredModel) {
  const contextText = relCards
    .map(
      (c) =>
        `[${c.id}] cabang=${c.cabang} | tahap=${c.tahap} | kepercayaan=${c.kepercayaan} | dasar=${c.dasar}\nIde: ${c.ide}\nPenjelasan: ${(c.penjelasan || "").slice(0, 450)}`
    )
    .join("\n\n---\n\n");

  const systemPrompt =
    "Kamu adalah asisten Pohon Pengetahuan. Jawab pertanyaan pengguna HANYA berdasarkan KARTU WAWASAN berikut. Wajib cantumkan ID kartu seperti [K-0001] pada setiap poin. Jangan mengarang; jika tidak cukup bukti di kartu, katakan terus terang. Sebutkan tingkat kepercayaan atau pertentangan bila ada. Jawab ringkas dan langsung ke inti dalam Bahasa Indonesia.";

  const models = preferredModel === "gemini-2.5-flash" ? [preferredModel] : [preferredModel, "gemini-2.5-flash"];
  let lastErr = "";

  for (const mdl of models) {
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${mdl}:generateContent?key=${encodeURIComponent(apiKey)}`;
    try {
      const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: AbortSignal.timeout(25000),
        body: JSON.stringify({
          systemInstruction: { parts: [{ text: systemPrompt }] },
          contents: [{ role: "user", parts: [{ text: `KARTU WAWASAN:\n\n${contextText}\n\nPERTANYAAN PENGGUNA:\n${question}` }] }],
          generationConfig: { temperature: 0.2, maxOutputTokens: 4096 },
        }),
      });
      if (!resp.ok) {
        lastErr = `HTTP ${resp.status}`;
        if (resp.status === 404) continue;
        break;
      }
      const data = await resp.json();
      const parts = data?.candidates?.[0]?.content?.parts || [];
      const text = parts.map((p) => p.text || "").join("\n").trim();
      if (text) return { text, model: mdl, err: "" };
      lastErr = "Respon kosong";
    } catch (err) {
      lastErr = err?.message || "Timeout/network";
      break;
    }
  }
  return { text: null, model: preferredModel, err: lastErr };
}

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.status(405).json({ error: "Gunakan POST /api/tanya" });
    return;
  }

  let body = req.body;
  if (typeof body === "string") {
    try {
      body = JSON.parse(body);
    } catch {
      res.status(400).json({ error: "JSON tidak valid" });
      return;
    }
  }
  const pertanyaan = String(body?.pertanyaan || "").trim().slice(0, 500);
  if (pertanyaan.length < 2) {
    res.status(400).json({ error: "Pertanyaan terlalu pendek (minimal 2 karakter)" });
    return;
  }

  try {
    const dataset = await loadPublicDataset(req);
    const cards = Array.isArray(dataset.kartu) ? dataset.kartu : [];
    const relCards = rankCards(pertanyaan, cards, 8);
    const level1Text = buildLevel1Synthesis(pertanyaan, relCards);
    const rujukan = relCards.map((c) => ({
      id: c.id,
      ide: c.ide,
      cabang: c.cabang,
      kepercayaan: c.kepercayaan,
    }));

    const apiKey = (process.env.GEMINI_API_KEY || "").trim();
    const preferredModel = (process.env.GEMINI_MODEL || "gemini-3.5-flash-lite").trim();

    if (apiKey && relCards.length > 0) {
      const rag = await callGeminiRag(pertanyaan, relCards, apiKey, preferredModel);
      if (rag.text) {
        res.status(200).json({ ok: true, mode: `ai-rag (${rag.model})`, jawaban: rag.text, rujukan, pertentangan: [] });
        return;
      }
      res.status(200).json({
        ok: true,
        mode: "sintesis-lokal (cadangan)",
        jawaban: level1Text,
        rujukan,
        pertentangan: [],
        info: `Gemini API tidak merespons (${rag.err}); menampilkan sintesis lokal.`,
      });
      return;
    }

    res.status(200).json({ ok: true, mode: "sintesis-lokal", jawaban: level1Text, rujukan, pertentangan: [] });
  } catch (err) {
    res.status(500).json({ error: err?.message || "Gagal memproses pertanyaan" });
  }
};
