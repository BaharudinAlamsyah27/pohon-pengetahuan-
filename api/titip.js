const DEFAULT_REPO = "BaharudinAlamsyah27/pohon-pengetahuan-";

// Rate limit ringan per IP (maks 5 titipan per 10 menit per instance)
const RATE_WINDOW_MS = 10 * 60 * 1000;
const RATE_MAX_REQ = 5;
const rateBuckets = new Map();

function getClientIp(req) {
  const fwd = String(req?.headers?.["x-forwarded-for"] || "").split(",")[0].trim();
  return fwd || req?.socket?.remoteAddress || "unknown";
}

function checkRateLimit(ip) {
  const now = Date.now();
  const arr = (rateBuckets.get(ip) || []).filter((ts) => now - ts < RATE_WINDOW_MS);
  if (arr.length >= RATE_MAX_REQ) {
    rateBuckets.set(ip, arr);
    return false;
  }
  arr.push(now);
  rateBuckets.set(ip, arr);
  if (rateBuckets.size > 500) {
    for (const [k, v] of rateBuckets.entries()) {
      if (!v.some((ts) => now - ts < RATE_WINDOW_MS)) rateBuckets.delete(k);
    }
  }
  return true;
}

function isAllowedOrigin(req) {
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

function cleanStr(val, maxLen) {
  return String(val || "").replace(/\r\n/g, "\n").trim().slice(0, maxLen);
}

function sanitizeForMarkdown(text) {
  return String(text || "")
    .replace(/<!--/g, "< !--")
    .replace(/-->/g, "-- >")
    .replace(/POHON_TITIPAN_DATA/g, "POHON_TITIPAN")
    .replace(/```/g, "'''");
}

function guessPlatformFromUrl(url) {
  const u = (url || "").toLowerCase();
  if (u.includes("x.com/") || u.includes("twitter.com/")) return "X";
  if (u.includes("youtube.com/") || u.includes("youtu.be/")) return "YouTube";
  if (u.includes("instagram.com/")) return "Instagram";
  if (u.includes("threads.net/") || u.includes("threads.com/")) return "Threads";
  if (u.includes("facebook.com/") || u.includes("fb.watch/")) return "Facebook";
  if (u.includes("linkedin.com/")) return "LinkedIn";
  if (u.startsWith("http")) return "web";
  return "lainnya";
}

function makeShortTitle(judul, url, teks) {
  if (judul) return judul.slice(0, 90);
  if (url) {
    try {
      const u = new URL(url);
      return `${u.hostname.replace(/^www\./, "")}${u.pathname.slice(0, 45)}`;
    } catch {
      return url.slice(0, 80);
    }
  }
  const firstLine = (teks || "").split("\n").find((l) => l.trim().length > 0) || "Catatan Baru";
  return firstLine.trim().slice(0, 80);
}

async function createGitHubIssue(token, repo, title, body, withLabel) {
  const payload = withLabel ? { title, body, labels: ["titipan"] } : { title, body };
  return fetch(`https://api.github.com/repos/${repo}/issues`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "Content-Type": "application/json",
      "User-Agent": "pohon-pengetahuan-titip",
      "X-GitHub-Api-Version": "2022-11-28",
    },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(12000),
  });
}

module.exports = async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "POST") {
    res.status(405).json({ error: "Gunakan POST /api/titip" });
    return;
  }
  if (!isAllowedOrigin(req)) {
    res.status(403).json({ error: "Asal permintaan tidak diizinkan." });
    return;
  }
  if (!checkRateLimit(getClientIp(req))) {
    res.status(429).json({ error: "Terlalu banyak kiriman dalam waktu singkat. Coba lagi 10 menit lagi." });
    return;
  }
  const ct = String(req?.headers?.["content-type"] || "").toLowerCase();
  if (ct && !ct.includes("application/json")) {
    res.status(415).json({ error: "Content-Type harus application/json." });
    return;
  }

  let body = req.body;
  if (typeof body === "string") {
    if (body.length > 32768) {
      res.status(413).json({ error: "Ukuran kiriman terlalu besar." });
      return;
    }
    try {
      body = JSON.parse(body);
    } catch {
      res.status(400).json({ error: "Format JSON tidak valid." });
      return;
    }
  }
  body = body || {};

  // Honeypot anti-spam sederhana (tidak terlihat oleh pengguna manusia)
  if (cleanStr(body.website_hp, 50)) {
    res.status(200).json({ ok: true, nomor: 0, pesan: "Terima kasih, titipan diterima." });
    return;
  }

  const nama = cleanStr(body.nama, 60) || "Anonim";
  const url = cleanStr(body.url, 500);
  const judulInput = cleanStr(body.judul, 140);
  const bidang = cleanStr(body.bidang, 60);
  const teksAsli = cleanStr(body.teks_asli, 15000);
  const platform = cleanStr(body.platform, 30) || guessPlatformFromUrl(url);

  if (url.length < 5 && teksAsli.length < 5) {
    res.status(400).json({ error: "Isi minimal link atau teks catatan (minimal 5 karakter)." });
    return;
  }
  if (url) {
    try {
      const parsedUrl = new URL(url);
      const h = parsedUrl.hostname.toLowerCase();
      if (parsedUrl.protocol !== "http:" && parsedUrl.protocol !== "https:") {
        res.status(400).json({ error: "Link harus diawali http:// atau https://" });
        return;
      }
      if (
        h === "localhost" ||
        h === "::1" ||
        h.endsWith(".local") ||
        h.endsWith(".internal") ||
        /^(127\.|10\.|192\.168\.|169\.254\.|0\.|172\.(1[6-9]|2\d|3[01])\.)/.test(h)
      ) {
        res.status(400).json({ error: "Link alamat jaringan lokal/privat tidak diizinkan." });
        return;
      }
    } catch {
      res.status(400).json({ error: "Format link tidak valid." });
      return;
    }
  }

  const token = (process.env.GITHUB_TOKEN || process.env.pohon_key || process.env.POHON_KEY || "").trim();
  const repo = (process.env.GITHUB_REPO || DEFAULT_REPO).trim();
  if (!token) {
    res.status(503).json({
      error: "Kotak Titipan online belum diaktifkan oleh pemilik.",
      needs_setup: true,
    });
    return;
  }

  const shortTitle = makeShortTitle(judulInput, url, teksAsli);
  const issueTitle = `[Titipan] ${shortTitle.replace(/[\r\n]+/g, " ")}`;
  const dataObj = {
    nama,
    url: url || "tidak ada",
    judul: shortTitle,
    platform,
    bidang,
    teks_asli: teksAsli || url,
    waktu: new Date().toISOString(),
  };

  const safeTeksDisplay = sanitizeForMarkdown(teksAsli);
  const safeJson = JSON.stringify(dataObj, null, 2).replace(/```/g, "\\u0060\\u0060\\u0060");

  const issueBody = [
    `**Pengirim:** ${sanitizeForMarkdown(nama)}`,
    `**Platform:** ${sanitizeForMarkdown(platform)}`,
    url ? `**Link:** ${url}` : "",
    bidang ? `**Usulan Topik:** ${sanitizeForMarkdown(bidang)}` : "",
    "",
    "### Catatan / Teks",
    safeTeksDisplay || "(Hanya mengirim link — akan ditarik otomatis saat diproses di laptop)",
    "",
    "<!-- POHON_TITIPAN_DATA -->",
    "```json",
    safeJson,
    "```",
  ]
    .filter(Boolean)
    .join("\n");

  try {
    let resp = await createGitHubIssue(token, repo, issueTitle, issueBody, true);
    if (resp.status === 422) {
      resp = await createGitHubIssue(token, repo, issueTitle, issueBody, false);
    }
    if (!resp.ok) {
      res.status(502).json({
        error: "Gagal menyimpan ke Kotak Titipan saat ini. Coba lagi beberapa saat lagi.",
      });
      return;
    }
    const created = await resp.json();
    res.status(200).json({
      ok: true,
      nomor: created.number,
      pesan: `Berhasil dititipkan (#${created.number})! Pemilik Pohon akan meninjau dan merapikannya.`,
    });
  } catch {
    res.status(500).json({ error: "Gagal menghubungi Kotak Titipan. Coba lagi sebentar." });
  }
};
