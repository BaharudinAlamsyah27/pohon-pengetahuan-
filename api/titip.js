const DEFAULT_REPO = "BaharudinAlamsyah27/pohon-pengetahuan-";

function cleanStr(val, maxLen) {
  return String(val || "").replace(/\r\n/g, "\n").trim().slice(0, maxLen);
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
  if (req.method !== "POST") {
    res.status(405).json({ error: "Gunakan POST /api/titip" });
    return;
  }

  let body = req.body;
  if (typeof body === "string") {
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
  if (url && !/^https?:\/\//i.test(url)) {
    res.status(400).json({ error: "Link harus diawali http:// atau https://" });
    return;
  }

  const token = (process.env.GITHUB_TOKEN || process.env.pohon_key || process.env.POHON_KEY || "").trim();
  const repo = (process.env.GITHUB_REPO || DEFAULT_REPO).trim();
  if (!token) {
    res.status(503).json({
      error: "Kotak Titipan online belum diaktifkan oleh pemilik (GITHUB_TOKEN / pohon_key belum dipasang di Vercel).",
      needs_setup: true,
    });
    return;
  }

  const shortTitle = makeShortTitle(judulInput, url, teksAsli);
  const issueTitle = `[Titipan] ${shortTitle}`;
  const dataObj = {
    nama,
    url: url || "tidak ada",
    judul: shortTitle,
    platform,
    bidang,
    teks_asli: teksAsli || url,
    waktu: new Date().toISOString(),
  };

  const issueBody = [
    `**Pengirim:** ${nama}`,
    `**Platform:** ${platform}`,
    url ? `**Link:** ${url}` : "",
    bidang ? `**Usulan Topik:** ${bidang}` : "",
    "",
    "### Catatan / Teks",
    teksAsli || "(Hanya mengirim link — akan ditarik otomatis saat diproses di laptop)",
    "",
    "<!-- POHON_TITIPAN_DATA -->",
    "```json",
    JSON.stringify(dataObj, null, 2),
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
      const errTxt = await resp.text().catch(() => "");
      res.status(502).json({
        error: `Gagal mengirim ke Kotak Titipan (HTTP ${resp.status}). ${errTxt.slice(0, 120)}`,
      });
      return;
    }
    const created = await resp.json();
    res.status(200).json({
      ok: true,
      nomor: created.number,
      pesan: `Berhasil dititipkan (#${created.number})! Pemilik Pohon akan meninjau dan merapikannya.`,
    });
  } catch (err) {
    res.status(500).json({ error: `Gagal menghubungi Kotak Titipan: ${err?.message || "timeout"}` });
  }
};
