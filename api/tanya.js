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

const FREE_OPENAI_PROVIDERS = [
  ["GROQ_API_KEY", "groq", "https://api.groq.com/openai/v1/chat/completions", ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]],
  ["OPENROUTER_API_KEY", "openrouter", "https://openrouter.ai/api/v1/chat/completions", ["openrouter/free"]],
  ["MISTRAL_API_KEY", "mistral", "https://api.mistral.ai/v1/chat/completions", ["mistral-small-latest"]],
  ["CEREBRAS_API_KEY", "cerebras", "https://api.cerebras.ai/v1/chat/completions", ["llama-3.3-70b", "qwen-3.8-27b"]],
  ["NVIDIA_API_KEY", "nvidia-nim", "https://integrate.api.nvidia.com/v1/chat/completions", ["meta/llama-3.3-70b-instruct"]],
];

async function callFreeLlmCascade(question, relCards) {
  const contextText = relCards
    .map(
      (c) =>
        `[${c.id}] cabang=${c.cabang} | tahap=${c.tahap} | kepercayaan=${c.kepercayaan} | dasar=${c.dasar}\nIde: ${c.ide}\nPenjelasan: ${(c.penjelasan || "").slice(0, 450)}`
    )
    .join("\n\n---\n\n");
  const systemPrompt =
    "Kamu adalah asisten Pohon Pengetahuan. Jawab pertanyaan pengguna HANYA berdasarkan KARTU WAWASAN berikut. Wajib cantumkan ID kartu seperti [K-0001] pada setiap poin. Jangan mengarang; jika tidak cukup bukti di kartu, katakan terus terang. Sebutkan tingkat kepercayaan bila rendah/belum diverifikasi. Jawab ringkas dalam Bahasa Indonesia.";
  const userPrompt = `KARTU WAWASAN:\n\n${contextText}\n\nPERTANYAAN PENGGUNA:\n${question}`;

  let lastErr = "Belum ada API key gratis";

  // 1. Google Gemini API
  const gemKey = (process.env.GEMINI_API_KEY || "").trim();
  if (gemKey) {
    const preferredModel = (process.env.GEMINI_MODEL || "gemini-3.5-flash-lite").trim();
    const models = [...new Set([preferredModel, "gemini-3.5-flash-lite", "gemini-2.5-flash"])];
    for (const mdl of models) {
      const url = `https://generativelanguage.googleapis.com/v1beta/models/${mdl}:generateContent?key=${encodeURIComponent(gemKey)}`;
      try {
        const resp = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: AbortSignal.timeout(25000),
          body: JSON.stringify({
            systemInstruction: { parts: [{ text: systemPrompt }] },
            contents: [{ role: "user", parts: [{ text: userPrompt }] }],
            generationConfig: { temperature: 0.2, maxOutputTokens: 4096 },
          }),
        });
        if (!resp.ok) {
          lastErr = `gemini/${mdl} HTTP ${resp.status}`;
          continue;
        }
        const data = await resp.json();
        const parts = data?.candidates?.[0]?.content?.parts || [];
        const text = parts.map((p) => p.text || "").join("\n").trim();
        if (text) return { text, model: mdl, err: "" };
      } catch (err) {
        lastErr = err?.message || "Timeout/network";
      }
    }
  }

  // 2..6. OpenAI-Compatible Free Providers (Groq, OpenRouter, Mistral, Cerebras, NVIDIA NIM)
  for (const [envVar, provName, endpoint, models] of FREE_OPENAI_PROVIDERS) {
    const key = (process.env[envVar] || "").trim();
    if (!key) continue;
    for (const mdl of models) {
      const headers = {
        "Content-Type": "application/json",
        Authorization: `Bearer ${key}`,
      };
      if (provName === "openrouter") {
        headers["HTTP-Referer"] = "https://pohon-pengetahuan.vercel.app";
        headers["X-Title"] = "Pohon Pengetahuan";
      }
      try {
        const resp = await fetch(endpoint, {
          method: "POST",
          headers,
          signal: AbortSignal.timeout(25000),
          body: JSON.stringify({
            model: mdl,
            messages: [
              { role: "system", content: systemPrompt },
              { role: "user", content: userPrompt },
            ],
            temperature: 0.2,
            max_tokens: 4096,
          }),
        });
        if (!resp.ok) {
          lastErr = `${provName}/${mdl} HTTP ${resp.status}`;
          continue;
        }
        const data = await resp.json();
        const text = (data?.choices?.[0]?.message?.content || "").trim();
        if (text) return { text, model: `${provName}/${mdl}`, err: "" };
      } catch (err) {
        lastErr = err?.message || "Timeout/network";
      }
    }
  }
  return { text: null, model: "none", err: lastErr };
}

const TANYA_RATE_WINDOW_MS = 5 * 60 * 1000;
const TANYA_RATE_MAX = 15;
const tanyaRateBuckets = new Map();

function checkTanyaRate(req) {
  const ip = String(req?.headers?.["x-forwarded-for"] || "").split(",")[0].trim() || req?.socket?.remoteAddress || "unknown";
  const now = Date.now();
  const arr = (tanyaRateBuckets.get(ip) || []).filter((ts) => now - ts < TANYA_RATE_WINDOW_MS);
  if (arr.length >= TANYA_RATE_MAX) {
    tanyaRateBuckets.set(ip, arr);
    return false;
  }
  arr.push(now);
  tanyaRateBuckets.set(ip, arr);
  if (tanyaRateBuckets.size > 500) {
    for (const [k, v] of tanyaRateBuckets.entries()) {
      if (!v.some((ts) => now - ts < TANYA_RATE_WINDOW_MS)) tanyaRateBuckets.delete(k);
    }
  }
  return true;
}

function isAllowedTanyaOrigin(req) {
  const origin = String(req?.headers?.origin || "").trim();
  if (!origin) return true;
  const host = String(req?.headers?.["x-forwarded-host"] || req?.headers?.host || "").trim();
  try {
    const oHost = new URL(origin).host;
    return oHost === host || oHost === "pohon-pengetahuan.vercel.app" || oHost.endsWith(".vercel.app");
  } catch {
    return false;
  }
}

module.exports = async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "POST") {
    res.status(405).json({ error: "Gunakan POST /api/tanya" });
    return;
  }
  if (!isAllowedTanyaOrigin(req)) {
    res.status(403).json({ error: "Asal permintaan tidak diizinkan." });
    return;
  }
  if (!checkTanyaRate(req)) {
    res.status(429).json({ error: "Terlalu banyak pertanyaan dalam waktu singkat. Coba lagi 5 menit lagi." });
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

    const hasAnyKey = ["GEMINI_API_KEY", ...FREE_OPENAI_PROVIDERS.map((p) => p[0])].some((k) =>
      Boolean((process.env[k] || "").trim())
    );

    if (hasAnyKey && relCards.length > 0) {
      const rag = await callFreeLlmCascade(pertanyaan, relCards);
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
        info: "Penyedia AI sedang sibuk; menampilkan ringkasan langsung dari kartu publik.",
      });
      return;
    }

    res.status(200).json({ ok: true, mode: "sintesis-lokal", jawaban: level1Text, rujukan, pertentangan: [] });
  } catch {
    res.status(500).json({ error: "Gagal memproses pertanyaan saat ini." });
  }
};
