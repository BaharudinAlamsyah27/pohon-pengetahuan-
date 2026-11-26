#!/usr/bin/env python3
"""
Server lokal minimal untuk Pohon Pengetahuan (Bagian 21.1 #5).
Aturan keamanan ketat:
  - Hanya mendengarkan 127.0.0.1 (tidak pernah bisa diakses dari jaringan luar).
  - Hanya boleh mengubah field penerapan, penerapan-catatan, dan terakhir-ditinjau pada kartu/K-XXXX.md
    serta menambah 1 entri ke log.md.
  - Memuat Teks Asli sumber secara on-demand (GET /api/sumber/S-XXXX).
  - Tidak pernah ikut dipublikasikan ke situs/.

Jalankan:
  python scripts/server_lokal.py
Lalu buka:
  http://127.0.0.1:8765/
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_STATUS = {"belum-dicoba", "sedang-dicoba", "diterapkan", "ditolak"}
ALLOWED_JENIS = {"postingan", "artikel", "transkrip-video", "transkrip-podcast", "catatan"}
CARD_ID_RE = re.compile(r"^K-\d{4,6}$")
SRC_ID_RE = re.compile(r"^S-\d{4,6}$")

# Impor fungsi bangun ulang, ambil_link, jurnal_engine, dan mesin_cerdas
sys.path.insert(0, str(ROOT / "scripts"))
import ambil_link  # noqa: E402
import bangun_pohon  # noqa: E402
import jurnal_engine  # noqa: E402
import mesin_cerdas  # noqa: E402


def next_source_id() -> str:
    sumber_dir = ROOT / "sumber"
    sumber_dir.mkdir(parents=True, exist_ok=True)
    max_num = 0
    for fp in sumber_dir.glob("S-*.md"):
        m = re.match(r"^S-(\d+)$", fp.stem)
        if m:
            max_num = max(max_num, int(m.group(1)))
    return f"S-{max_num + 1:04d}"


def next_card_id() -> str:
    kartu_dir = ROOT / "kartu"
    kartu_dir.mkdir(parents=True, exist_ok=True)
    max_num = 0
    for fp in kartu_dir.glob("K-*.md"):
        m = re.match(r"^K-(\d+)$", fp.stem)
        if m:
            max_num = max(max_num, int(m.group(1)))
    return f"K-{max_num + 1:04d}"


BIDANG_KEYWORDS = {
    "ai/video-dan-clipping": [
        "video ai", "clipping", "kling", "veo", "runway", "sora", "heygen", "capcut", "opus clip",
        "dubbing", "avatar ai", "storyboard", "elevenlabs", "voiceover", "lip sync", "lipsync",
        "text to video", "image to video", "seedance", "luma", "pika", "midjourney video", "shorts ai",
        "reels ai", "edit video ai", "faceless video", "b-roll", "subtitle otomatis",
    ],
    "ai/tulisan-dan-artikel": [
        "tone-of-voice", "tone of voice", "artikel ai", "sample writing", "blog ai", "thread ai",
        "copywriting ai", "menulis dengan ai", "gaya bahasa ai", "humanize ai", "ai writer",
        "newsletter ai", "ghostwriting ai", "prompt menulis", "detektor ai", "anti ai slop",
    ],
    "ai/coding-dan-proyek": [
        "claude code", "cursor", "coding", "bikin app", "github", "repo", "api", "python",
        "nextjs", "next.js", "vercel", "ui slop", "frontend", "backend", "fullstack", "typescript",
        "javascript", "colab", "supabase", "postgres", "sqlite", "docker", "vscode", "windsurf",
        "antigravity", "vibe coding", "deploy", "astro", "react", "tailwind", "flutter", "android",
        "sdk", "cli", "terminal", "debug", "refactor", "git", "codebase", "framework",
    ],
    "ai/prompt-dan-agen": [
        "prompt", "prompting", "ai agent", "agents", "agentic", "skill", "skills", "mcp",
        "workflow", "context engineering", "n8n", "otomasi", "automation", "rag", "embedding",
        "vector database", "system prompt", "few-shot", "chain of thought", "tool calling",
        "multi-agent", "subagent", "langchain", "langgraph", "crewai", "openclaw", "explee",
    ],
    "ai/perbandingan-model": [
        "fable", "opus", "sonnet", "haiku", "gemini", "benchmark", "tonality", "dibanding model",
        "perbandingan model", "gpt-5", "gpt-4", "claude", "vs gpt", "vs claude", "vs gemini",
        "deepseek", "grok", "llama", "qwen", "mistral", "context window", "token pricing",
        "model terbaik", "best model", "arena elo", "swe-bench",
    ],
    "ai": [
        "ai", "llm", "claude", "gemini", "gpt", "chatgpt", "artificial intelligence",
        "machine learning", "deep learning", "openai", "anthropic", "google ai", "ai studio",
        "neural network", "transformer", "fine-tuning", "inference", "multimodal", "agi",
    ],
    "digital-marketing": [
        "seo", "ai-search", "geo", "digital marketing", "copywriting", "funnel", "landing page",
        "iklan", "ads", "meta ads", "google ads", "tiktok ads", "konversi", "conversion",
        "ctr", "roas", "lead", "leads", "marketing", "pemasaran", "email marketing", "backlink",
        "keyword research", "organic traffic", "programmatic seo", "cro", "retargeting",
    ],
    "sosmed": [
        "ocr", "impresi", "impression", "reupload", "repost", "viral", "algoritma", "algorithm",
        "payout", "tiktok", "instagram", "threads", "youtube", "konten", "hook", "followers",
        "cenblu", "creator", "kreator", "engagement", "fyp", "retention", "watch time",
        "thumbnail", "storytelling", "mutual reply", "bookmark", "reach", "monetisasi x",
    ],
    "bisnis": [
        "bisnis", "business", "produk digital", "validasi", "omzet", "jualan", "client", "klien",
        "agency", "agensi", "saas", "micro-saas", "revenue", "scale", "pasar", "market",
        "startup", "monetize", "monetisasi", "arr", "mrr", "b2b", "b2c", "pricing", "offer",
        "margin", "profit", "bootstrapping", "solopreneur", "gtm", "go-to-market", "sales rep",
        "closing", "customer", "pelanggan", "mvp", "product-market fit",
    ],
    "keuangan": [
        "tabungan", "menabung", "investasi", "investing", "saham", "stock", "reksadana",
        "obligasi", "crypto", "bitcoin", "gaji", "salary", "utang", "debt", "dana darurat",
        "emergency fund", "anggaran", "budget", "keuangan", "finance", "financial", "money",
        "saving", "income", "wealth", "aset", "asset", "dividen", "inflasi", "pajak", "tax",
        "cashflow", "arus kas", "passive income", "compounding", "bunga majemuk", "frugal",
    ],
    "kesehatan": [
        "tidur", "sleep", "olahraga", "workout", "exercise", "gym", "lift", "weights", "athlete",
        "makan", "eat", "nutrisi", "nutrition", "diet", "healthy", "kesehatan", "health", "otot",
        "muscle", "postur", "posture", "appearance", "penampilan", "skincare", "grooming",
        "stres", "stress", "mental", "dokter", "medis", "fitness", "brain fog", "biological",
        "circadian", "sirkadian", "longevity", "recovery", "pemulihan", "istirahat", "begadang",
        "insomnia", "kafein", "caffeine", "hormon", "hormone", "tubuh", "otak", "fatigue",
        "burnout", "kalori", "protein", "puasa", "fasting", "cardio", "jogging", "lari",
        "kortisol", "cortisol", "dopamin", "dopamine", "metabolisme", "metabolic", "imun",
        "vitamin", "suplemen", "supplement", "hidrasi", "air putih", "gula darah", "blood sugar",
    ],
    "kesuksesan": [
        "karier", "karir", "career", "cpns", "asn", "bumn", "beasiswa", "scholarship", "lpdp",
        "ausbildung", "jepang", "jerman", "magang", "internship", "wawancara", "interview",
        "success", "achievement", "promosi", "cv", "resume", "portofolio", "portfolio",
        "fresh graduate", "lulusan baru", "kerja remote", "remote work", "freelance", "upskilling",
    ],
    "motivasi-dan-mindset": [
        "mindset", "disiplin", "discipline", "kebiasaan", "habit", "habits", "overthinking",
        "perfeksionis", "fokus", "focus", "konsisten", "consistent", "malas", "takut", "motivasi",
        "motivation", "routine", "rutinitas", "self-improvement", "will be your year",
        "akan menjadi tahunmu", "deep work", "prokrastinasi", "menunda", "stoik", "stoicism",
        "resiliensi", "grit", "mentalitas", "produktivitas", "productivity", "time management",
        "manajemen waktu", "prioritas", "pareto", "atomic habits",
    ],
    "relasi": [
        "relasi", "relationship", "komunikasi", "communication", "jejaring", "networking",
        "keluarga", "family", "pasangan", "partner", "teman", "friends", "negosiasi",
        "negotiation", "empati", "empathy", "menikah", "marriage", "parenting", "persuasif",
        "public speaking", "charisma", "karisma", "leadership", "kepemimpinan", "tim",
    ],
    "agama": [
        "agama", "islam", "quran", "alquran", "hadis", "hadits", "sunnah", "fiqih", "tauhid",
        "akhlak", "ibadah", "sholat", "salat", "puasa", "sedekah", "zakat", "doa", "dzikir",
        "tafsir", "ulama", "ustadz", "kajian", "dakwah", "akhirat", "tawakal", "syukur", "sabar",
    ],
    "berita": [
        "berita", "news", "breaking", "pemerintah", "presiden", "menteri", "undang-undang",
        "geopolitik", "ekonomi makro", "inflasi nasional", "pilpres", "kebijakan publik",
        "peristiwa", "konflik dunia", "bursa global", "laporan resmi",
    ],
    "kliping-hiburan": [
        "meme", "guyonan", "lucu", "ngakak", "receh", "absurd", "shitpost", "candaan",
        "parodi", "komedi", "lawak", "hiburan", "wkwk", "lmao", "rofl",
    ],
}

TOP_BRANCHES = {
    "ai", "bisnis", "sosmed", "digital-marketing",
    "keuangan", "kesuksesan", "kesehatan", "motivasi-dan-mindset", "relasi",
    "agama", "berita", "kliping-hiburan", "lainnya",
}

VALID_BRANCHES = {
    "ai", "ai/video-dan-clipping", "ai/tulisan-dan-artikel", "ai/coding-dan-proyek",
    "ai/prompt-dan-agen", "ai/perbandingan-model",
    "bisnis", "sosmed", "digital-marketing",
    "keuangan", "kesuksesan", "kesehatan", "motivasi-dan-mindset", "relasi",
    "agama", "berita", "kliping-hiburan", "lainnya",
}


def _classify_branch_gemini(text: str) -> str | None:
    """Lapis 1: Klasifikasi topik berbasis pemahaman makna (semantik) via cascade 6 penyedia AI gratis."""
    if not mesin_cerdas.has_any_free_llm_key():
        return None
    prompt = (
        "Pilih TEPAT SATU nama topik paling cocok untuk teks berikut:\n"
        "- kesehatan: tidur/sleep, olahraga, nutrisi, diet, tubuh, otak, brain fog, biologis, kebugaran, energi, medis\n"
        "- keuangan: tabungan, gaji, investasi, saham, utang, dana darurat, finansial\n"
        "- bisnis: startup, SaaS, omzet, klien, produk digital, jualan, strategi usaha\n"
        "- sosmed: konten viral, algoritma X/YouTube/TikTok/IG, OCR X, impresi, engagement, kreator\n"
        "- digital-marketing: SEO, iklan/ads, funnel, landing page, copywriting, konversi\n"
        "- kesuksesan: karier, CPNS, beasiswa, magang, kerja, wawancara, pencapaian\n"
        "- motivasi-dan-mindset: disiplin, kebiasaan, fokus, overthinking, mentalitas, psikologi diri\n"
        "- relasi: hubungan, komunikasi, keluarga, pasangan, teman, networking\n"
        "- agama: ilmu agama, akhlak, ibadah, tafsir, hadis, nasihat ulama, spiritualitas\n"
        "- berita: berita terkini, kebijakan pemerintah, peristiwa dunia, geopolitik, tren sesaat\n"
        "- kliping-hiburan: guyonan, meme, lelucon, hiburan ringan, konten absurd tanpa pelajaran serius\n"
        "- ai/coding-dan-proyek: coding dengan AI, Claude Code, Cursor, Python, GitHub, API, bikin aplikasi\n"
        "- ai/prompt-dan-agen: prompt engineering, agen AI, MCP, skill AI, workflow otomasi\n"
        "- ai/video-dan-clipping: video AI, dubbing, voiceover, CapCut, Kling, Veo, Runway, Sora\n"
        "- ai/tulisan-dan-artikel: menulis dengan AI, gaya bahasa/tone-of-voice, artikel/blog AI\n"
        "- ai/perbandingan-model: membandingkan model AI (Claude vs Gemini vs GPT), benchmark LLM\n"
        "- ai: berita/konsep AI umum di luar sub-topik AI di atas\n"
        "- lainnya: jika tidak masuk semua topik di atas\n\n"
        "Aturan: balas HANYA satu slug topik persis seperti di sebelah kiri tanda titik dua (contoh: kesehatan), tanpa penjelasan.\n\n"
        f"Teks:\n{text[:1200]}"
    )
    raw, _mdl, _err = mesin_cerdas.call_free_llm_cascade("", prompt, json_mode=False, max_tokens=64, temperature=0.0)
    if not raw:
        return None
    ans = raw.strip().lower().strip("`\"'. \n")
    if ans in VALID_BRANCHES:
        return ans
    for b in sorted(VALID_BRANCHES, key=len, reverse=True):
        if b in ans:
            return b
    return None


def guess_branch(text: str) -> tuple[str, int]:
    # Lapis 1: Pemahaman makna otomatis via Gemini AI (jika GEMINI_API_KEY tersedia & online)
    ai_branch = _classify_branch_gemini(text)
    if ai_branch:
        return ai_branch, 99

    # Lapis 2+3 (Offline — Reciprocal Rank Fusion):
    # Gabungkan 3 sinyal matematika: (a) Word-Boundary Weighted Lexicon,
    # (b) Multinomial Naive Bayes (Laplace smoothing, self-learning dari kartu/),
    # (c) Nearest-Neighbor TF-IDF Cosine ke kartu yang sudah ada.
    low = text.lower()
    lex_scores: list[tuple[str, int]] = []
    for b, kws in BIDANG_KEYWORDS.items():
        score = 0
        for kw in kws:
            if re.search(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", low):
                score += 2 if " " in kw else 1
        if score > 0:
            lex_scores.append((b, score))
    lex_scores.sort(key=lambda x: x[1], reverse=True)

    cards = bangun_pohon.load_cards(ROOT / "kartu")
    nb_ranked = mesin_cerdas.multinomial_naive_bayes_branch(text, BIDANG_KEYWORDS, existing_cards=cards)

    rrf: dict[str, float] = {}
    k_rrf = 12.0
    # Bobot leksikon presisi lebih tinggi (1.4x) + Naive Bayes self-learning (1.0x)
    for rank, (b, sc) in enumerate(lex_scores, 1):
        rrf[b] = rrf.get(b, 0.0) + (1.4 / (k_rrf + rank)) + min(0.15, sc * 0.025)
    for rank, (b, _lp) in enumerate(nb_ranked[:6], 1):
        rrf[b] = rrf.get(b, 0.0) + (1.0 / (k_rrf + rank))

    if cards:
        rel = mesin_cerdas.query_relevant_cards(text[:400], cards, limit=3)
        for rank, rc in enumerate(rel, 1):
            cb = rc.get("cabang") or ""
            if cb in VALID_BRANCHES:
                rrf[cb] = rrf.get(cb, 0.0) + (0.6 / (k_rrf + rank))

    if rrf:
        best_b = max(rrf.items(), key=lambda x: x[1])[0]
        raw_lex = dict(lex_scores).get(best_b, 0)
        return best_b, max(1, raw_lex)
    return "lainnya", 0


def ensure_top_branch_exists(slug: str, today: str) -> str:
    """Buat cabang utama BARU beserta entri di indeks.md jika belum ada."""
    slug = re.sub(r"[^a-z0-9-]+", "-", slug.lower().strip()).strip("-")
    if not slug or len(slug) < 2:
        raise ValueError("Nama cabang baru minimal 2 karakter huruf/angka.")
    pretty_name = slug.replace("-", " ").title()
    cab_dir = ROOT / "cabang" / slug
    cab_fp = cab_dir / "_cabang.md"
    if not cab_fp.is_file():
        cab_dir.mkdir(parents=True, exist_ok=True)
        cab_fp.write_text(
            f"---\n"
            f"cabang: {slug}\n"
            f"nama: {pretty_name}\n"
            f"induk: -\n"
            f"jumlah-kartu: 0\n"
            f"jumlah-sumber: 0\n"
            f"diperbarui: {today}\n"
            f'catatan-sudut-pandang: "belum ada sumber"\n'
            f"---\n\n"
            f"## Ringkasan\n"
            f"Cabang utama {pretty_name} (dibuat otomatis untuk topik baru).\n\n"
            f"## Poin Kunci\n- (belum ada)\n\n"
            f"## Pertentangan / Perdebatan\n- (belum ada)\n\n"
            f"## Lanjutan Timeline\n- Sebelumnya: -\n- Berikutnya: -\n\n"
            f"## Sub-cabang\n- (belum ada)\n\n"
            f"## Daftar Kartu\n- (belum ada)\n",
            encoding="utf-8",
        )
    idx_fp = ROOT / "indeks.md"
    if idx_fp.is_file():
        idx_txt = idx_fp.read_text(encoding="utf-8")
        if f"`cabang/{slug}/_cabang.md`" not in idx_txt:
            new_row = f"| {pretty_name} | 0 | Topik baru: {pretty_name} | `cabang/{slug}/_cabang.md` |"
            lines = idx_txt.rstrip().splitlines()
            lines.append(new_row)
            idx_fp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    TOP_BRANCHES.add(slug)
    VALID_BRANCHES.add(slug)
    return slug


def auto_slug_from_text(text: str) -> str:
    """Ekstrak 1-2 kata topik dominan untuk membuat sub-cabang otomatis saat topik benar-benar baru."""
    toks = [t for t in mesin_cerdas.tokenize(text) if len(t) >= 4 and not t.isdigit()]
    if not toks:
        return "topik-baru"
    freq: dict[str, int] = {}
    for t in toks:
        freq[t] = freq.get(t, 0) + 1
    top = [w for w, _ in sorted(freq.items(), key=lambda x: (-x[1], x[0]))[:2]]
    return "-".join(top)


def ensure_subbranch_exists(sub_slug: str, today: str) -> str:
    """Buat sub-cabang baru di bawah salah satu bidang utama (otomatis membuat induk jika belum ada)."""
    sub_slug = sub_slug.lower().strip().strip("/")
    if not re.match(r"^[a-z0-9-]+/[a-z0-9-]+$", sub_slug):
        raise ValueError("Format sub-cabang harus 'induk/sub-cabang' dengan huruf kecil dan tanda hubung (mis: ai/audio-musik)")
    parent, child = sub_slug.split("/", 1)
    if not (ROOT / "cabang" / parent / "_cabang.md").is_file():
        ensure_top_branch_exists(parent, today)

    sub_dir = ROOT / "cabang" / parent / child
    sub_fp = sub_dir / "_cabang.md"
    pretty_name = child.replace("-", " ").title()

    if not sub_fp.is_file():
        sub_dir.mkdir(parents=True, exist_ok=True)
        sub_fp.write_text(
            f"---\n"
            f"cabang: {sub_slug}\n"
            f"nama: {pretty_name}\n"
            f"induk: {parent}\n"
            f"jumlah-kartu: 0\n"
            f"jumlah-sumber: 0\n"
            f"diperbarui: {today}\n"
            f'catatan-sudut-pandang: "belum ada sumber"\n'
            f"---\n\n"
            f"## Ringkasan\n"
            f"Sub-cabang {pretty_name} di bawah bidang {parent}.\n\n"
            f"## Poin Kunci\n- (belum ada)\n\n"
            f"## Pertentangan / Perdebatan\n- (belum ada)\n\n"
            f"## Lanjutan Timeline\n- Sebelumnya: -\n- Berikutnya: -\n\n"
            f"## Sub-cabang\n- (belum ada)\n\n"
            f"## Daftar Kartu\n- (belum ada)\n",
            encoding="utf-8",
        )

        # Daftarkan sub-cabang baru ke _cabang.md induk
        parent_fp = ROOT / "cabang" / parent / "_cabang.md"
        if parent_fp.is_file():
            ptxt = parent_fp.read_text(encoding="utf-8")
            sub_line = f"- {pretty_name} → `cabang/{sub_slug}/_cabang.md` (0 kartu)"
            if f"cabang/{sub_slug}/_cabang.md" not in ptxt:
                m_sub = re.search(r"(## Sub-cabang\s*\n)([\s\S]*?)(\n## Daftar Kartu)", ptxt)
                if m_sub:
                    head, sec_body, tail = m_sub.group(1), m_sub.group(2), m_sub.group(3)
                    lines = [ln for ln in sec_body.splitlines() if ln.strip() and not ln.strip().startswith("- (belum ada)") and not ln.strip().startswith("- (akan dibuat otomatis")]
                    lines.append(sub_line)
                    ptxt = ptxt[:m_sub.start()] + head + "\n".join(lines) + "\n" + tail + ptxt[m_sub.end():]
                    parent_fp.write_text(ptxt, encoding="utf-8")
    return sub_slug


def rebuild_local_artifacts() -> None:
    """Sinkronkan FTS5 (.indeks.db), data.json, dan peta-pohon.html lokal."""
    bangun_pohon.build_fts_index(
        bangun_pohon.load_cards(ROOT / "kartu"),
        bangun_pohon.load_sources(ROOT / "sumber"),
    )
    dataset = bangun_pohon.build_dataset("lokal")
    (ROOT / "data.json").write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
    bangun_pohon.render_html(ROOT / "scripts" / "template_peta.html", dataset, ROOT / "peta-pohon.html")


def recount_branch_and_index(cabang_slug: str, today: str) -> None:
    """Perbarui jumlah-kartu, jumlah-sumber, diperbarui pada _cabang.md serta jumlah di indeks.md."""
    bidang = cabang_slug.split("/")[0]
    cards = bangun_pohon.load_cards(ROOT / "kartu")

    for target_slug in dict.fromkeys([cabang_slug, bidang]):
        cab_fp = ROOT / "cabang" / Path(*target_slug.split("/")) / "_cabang.md"
        if not cab_fp.is_file():
            continue
        txt = cab_fp.read_text(encoding="utf-8")
        b_cards = [
            c for c in cards.values()
            if c["status"] == "aktif" and (c["cabang"] == target_slug or c["cabang"].startswith(target_slug + "/"))
        ]
        b_srcs = {s for c in b_cards for s in c["sumber"]}
        txt = re.sub(r"^jumlah-kartu:\s*\d+", f"jumlah-kartu: {len(b_cards)}", txt, count=1, flags=re.M)
        txt = re.sub(r"^jumlah-sumber:\s*\d+", f"jumlah-sumber: {len(b_srcs)}", txt, count=1, flags=re.M)
        txt = re.sub(r"^diperbarui:\s*.*$", f"diperbarui: {today}", txt, count=1, flags=re.M)

        # Sintesis Ringkasan Cabang Otomatis: dipicu bila ada >=5 kartu baru sejak sintesis terakhir
        m_last = re.search(r"^kartu-saat-sintesis:\s*(\d+)", txt, flags=re.M)
        last_synth = int(m_last.group(1)) if m_last else 0
        if len(b_cards) >= 5 and (len(b_cards) - last_synth) >= 5 and target_slug == cabang_slug:
            m_ring = re.search(r"(## Ringkasan[^\n]*\n)([\s\S]*?)(\n## Poin Kunci)", txt)
            old_ring = m_ring.group(2).strip() if m_ring else ""
            synth = mesin_cerdas.synthesize_branch_summary_llm(target_slug, old_ring, b_cards)
            if synth and m_ring:
                txt = txt[:m_ring.start()] + m_ring.group(1) + synth["ringkasan"] + "\n" + m_ring.group(3) + txt[m_ring.end():]
                if synth.get("poin_kunci"):
                    m_pk = re.search(r"(## Poin Kunci\s*\n)([\s\S]*?)(\n## Pertentangan)", txt)
                    if m_pk:
                        pk_body = "\n".join(f"- {p}" for p in synth["poin_kunci"])
                        txt = txt[:m_pk.start()] + m_pk.group(1) + pk_body + "\n" + m_pk.group(3) + txt[m_pk.end():]
                txt = set_fm_field(txt, "disintesis", today)
                txt = set_fm_field(txt, "kartu-saat-sintesis", str(len(b_cards)))

        cab_fp.write_text(txt, encoding="utf-8")

    idx_fp = ROOT / "indeks.md"
    if idx_fp.is_file():
        cnt = sum(1 for c in cards.values() if c["status"] == "aktif" and (c["bidang"] == bidang or c["cabang"].startswith(bidang + "/")))
        lines = idx_fp.read_text(encoding="utf-8").splitlines()
        new_lines = []
        for ln in lines:
            if f"`cabang/{bidang}/_cabang.md`" in ln and ln.startswith("|"):
                parts = ln.split("|")
                if len(parts) >= 5:
                    parts[2] = f" {cnt} "
                    ln = "|".join(parts)
            new_lines.append(ln)
        idx_fp.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


INVERSE_REL_MAP = {
    "lanjutan-dari": "prasyarat-untuk",
    "prasyarat-untuk": "lanjutan-dari",
    "memperkuat": "memperkuat",
    "bertentangan-dengan": "bertentangan-dengan",
    "contoh-dari": "terkait",
    "terkait": "terkait",
}


def add_inverse_relation(target_cid: str, rel_type: str, from_cid: str) -> None:
    """Tulis relasi balik secara otomatis (2 arah) ke kartu lama sesuai tabel invers."""
    inv_type = INVERSE_REL_MAP.get(rel_type)
    if not inv_type or not CARD_ID_RE.match(target_cid) or target_cid == from_cid:
        return
    fp = ROOT / "kartu" / f"{target_cid}.md"
    if not fp.is_file():
        return
    txt = fp.read_text(encoding="utf-8").replace("\r\n", "\n")
    if f"ke: {from_cid}" in txt:
        return
    new_entry = f"  - {{tipe: {inv_type}, ke: {from_cid}}}"
    if re.search(r"^relasi:\s*\[\s*\]\s*$", txt, flags=re.M):
        txt = re.sub(r"^relasi:\s*\[\s*\]\s*$", f"relasi:\n{new_entry}", txt, count=1, flags=re.M)
    elif re.search(r"^relasi:\s*$", txt, flags=re.M):
        txt = re.sub(r"^relasi:\s*$", f"relasi:\n{new_entry}", txt, count=1, flags=re.M)
    else:
        return
    fp.write_text(txt, encoding="utf-8")


def sync_branch_and_index(cabang_slug: str, cid: str, ide_short: str, tahap: str, today: str, kepercayaan: str = "belum-diverifikasi") -> None:
    """Tambahkan entri draf kartu tepat di bawah '## Daftar Kartu' dan sinkronkan cabang induk & indeks.md."""
    cab_fp = ROOT / "cabang" / Path(*cabang_slug.split("/")) / "_cabang.md"
    if cab_fp.is_file():
        txt = cab_fp.read_text(encoding="utf-8")
        entry = f"- {cid} | {ide_short} | {tahap} | {kepercayaan}"
        marker = "## Daftar Kartu"
        pos = txt.find(marker)
        if pos != -1 and entry not in txt:
            head, tail = txt[:pos], txt[pos:]
            if "- (belum ada)" in tail:
                tail = tail.replace("- (belum ada)", entry, 1)
            else:
                tail = tail.rstrip() + "\n" + entry + "\n"
            txt = head + tail
            cab_fp.write_text(txt, encoding="utf-8")
    recount_branch_and_index(cabang_slug, today)


def create_new_source(
    judul: str,
    jenis: str,
    penulis: str,
    platform: str,
    url: str,
    teks_asli: str,
    bidang_pilihan: str = "",
    tahap_pilihan: str = "semua-usia",
    buat_draf: bool = True,
    subcabang_baru: str = "",
    max_daun: int = 3,
) -> dict:
    """Buat file sumber/S-XXXX.md (Akar) + ekstraksi kartu atomik (Daun) via TextTiling + Entropy + LexRank + MMR."""
    sid = next_source_id()
    fp = ROOT / "sumber" / f"{sid}.md"
    if fp.exists():
        raise FileExistsError(f"{sid} sudah ada")
    today = date.today().isoformat()
    clean_judul = re.sub(r"[\r\n]+", " ", judul).replace('"', "'").strip()[:140] or f"Sumber {sid}"
    clean_penulis = re.sub(r"[\r\n]+", " ", penulis).strip()[:100] or "tidak diketahui"
    clean_platform = re.sub(r"[\r\n]+", " ", platform).strip()[:40] or "lainnya"
    clean_url = re.sub(r"[\r\n]+", " ", url).strip() or "tidak ada"
    clean_jenis = jenis if jenis in ALLOWED_JENIS else "postingan"
    raw_text = teks_asli.replace("\r\n", "\n").strip()

    # Normalisasi URL (buang parameter pelacakan ?s=20, ?t=..., ?utm_...) & cegah duplikat / near-duplicate
    def _canon_url(u: str) -> str:
        if not u or u == "tidak ada":
            return ""
        p = urlparse(u)
        if p.hostname and any(d in p.hostname.lower() for d in ("x.com", "twitter.com")):
            return f"https://x.com{p.path.rstrip('/')}"
        return f"{p.scheme}://{p.netloc}{p.path.rstrip('/')}".lower()

    canon_new = _canon_url(clean_url)
    existing_sources = bangun_pohon.load_sources(ROOT / "sumber")
    for esid, es in existing_sources.items():
        if canon_new and _canon_url((es.get("url") or "").strip()) == canon_new:
            raise ValueError(f"Sumber dengan URL ini sudah tersimpan di {esid}.")
        if (es.get("teks_asli") or "").strip() == raw_text:
            raise ValueError(f"Teks sumber yang sama persis sudah tersimpan di {esid}.")
    near_sid, near_sim = mesin_cerdas.find_near_duplicate_source(raw_text, existing_sources, threshold=0.82)
    if near_sid:
        raise ValueError(f"Postingan yang hampir identik ({int(near_sim * 100)}% mirip) sudah tersimpan di {near_sid}.")

    extra_tags: list[str] = []
    existing_cards_snapshot = bangun_pohon.load_cards(ROOT / "kartu")
    max_cards_lim = max(1, min(5, int(max_daun or 3)))

    # Pipeline 1-Panggilan Terstruktur (hemat 50% kuota API: langsung tebak cabang + ekstrak + cek duplikat sekaligus!)
    candidate_neighbors = mesin_cerdas.query_relevant_cards(f"{clean_judul} {raw_text[:600]}", existing_cards_snapshot, limit=12)
    structured_ai = mesin_cerdas.extract_structured_cards_gemini(
        raw_text=raw_text,
        candidate_neighbors=candidate_neighbors,
        valid_branches=VALID_BRANCHES,
        max_cards=max_cards_lim,
        platform=clean_platform,
    ) if buat_draf else None

    if subcabang_baru:
        if "/" in subcabang_baru:
            cabang_slug = ensure_subbranch_exists(subcabang_baru, today)
        else:
            cabang_slug = ensure_top_branch_exists(subcabang_baru, today)
    elif bidang_pilihan and (
        bidang_pilihan in VALID_BRANCHES
        or (ROOT / "cabang" / Path(*bidang_pilihan.split("/")) / "_cabang.md").is_file()
    ):
        cabang_slug = bidang_pilihan
    elif structured_ai and structured_ai.get("kartu") and structured_ai["kartu"][0].get("cabang"):
        cabang_slug = structured_ai["kartu"][0]["cabang"]
    else:
        cabang_slug, score = guess_branch(f"{clean_judul} {raw_text}")
        if score == 0:
            topic_slug = auto_slug_from_text(f"{clean_judul} {raw_text}")
            cabang_slug = ensure_top_branch_exists(topic_slug, today)
            extra_tags.append("cabang-otomatis")

    bidang = cabang_slug.split("/")[0]
    valid_tahap = {"sebelum-20", "20-25", "25-30", "30-40", "40-50", "50+", "semua-usia"}
    meta_auto = mesin_cerdas.infer_card_metadata_math(f"{clean_judul} {raw_text}", platform=clean_platform, url=clean_url)
    default_tahap = tahap_pilihan if (tahap_pilihan in valid_tahap and tahap_pilihan != "semua-usia") else meta_auto["tahap"]

    created_cids: list[str] = []
    created_entries: list[tuple[str, str, str, str, str]] = []  # (cid, ide_short, card_cabang, card_tahap, card_trust)
    merged_into_cid: str | None = None

    extracted_points = []
    if not structured_ai:
        extracted_points = mesin_cerdas.extract_atomic_insights_math(raw_text, max_cards=max_cards_lim)

    user_forced_branch = bool(subcabang_baru or bidang_pilihan)
    source_saripati_items: list[str] = []
    used_branches: set[str] = set()
    ragu_warnings: list[str] = []

    # Penanganan Duplikat Semantik (AGENTS.md Bagian 4 Langkah 4): tambahkan sumber baru ke kartu lama
    if buat_draf and structured_ai and structured_ai.get("duplikat_dari") and len(structured_ai.get("kartu") or []) <= 1:
        dup_id = structured_ai["duplikat_dari"]
        dup_fp = ROOT / "kartu" / f"{dup_id}.md"
        if dup_fp.is_file():
            dtxt = dup_fp.read_text(encoding="utf-8").replace("\r\n", "\n")
            if f"[[{sid}]]" not in dtxt:
                dtxt = re.sub(r"^(sumber:\s*.+)$", rf"\1, [[{sid}]]", dtxt, count=1, flags=re.M)
                dup_fp.write_text(dtxt, encoding="utf-8")
            merged_into_cid = dup_id
            created_cids.append(dup_id)
            source_saripati_items.append(structured_ai["kartu"][0]["ide"] if structured_ai.get("kartu") else clean_judul)
            used_branches.add(existing_cards_snapshot.get(dup_id, {}).get("cabang") or cabang_slug)

    if buat_draf and not merged_into_cid:
        cur_num = int(next_card_id().split("-")[1])
        items_to_create = structured_ai["kartu"] if structured_ai else extracted_points
        for idx_pt, pt in enumerate(items_to_create):
            cid = f"K-{cur_num + idx_pt:04d}"
            created_cids.append(cid)

            if structured_ai:
                ide_text = pt["ide"].replace('"', "'").strip()
                penjelasan = pt["penjelasan"]
                kutipan_2 = pt["kutipan"]
                card_cabang = cabang_slug if user_forced_branch else (pt["cabang"] or cabang_slug)
                card_bidang = card_cabang.split("/")[0]
                card_tahap = default_tahap if (tahap_pilihan != "semua-usia") else (pt["tahap"] or default_tahap)
                card_jenis = pt["jenis"]
                card_trust = pt["kepercayaan"]
                card_dasar = pt["dasar"]
                konsep_list = pt.get("konsep") or []
                kondisi_berlaku = pt.get("kondisi_berlaku") or "umum"
                keyakinan_ai = float(pt.get("keyakinan", 0.85))
                grounding_sc = float(pt.get("grounding", 1.0))
                model_ekstrak = structured_ai.get("model") or "ai"
                versi_prompt = structured_ai.get("versi_prompt") or mesin_cerdas.PROMPT_VERSION
                tags_all = (pt.get("tag") or []) + [clean_platform.lower()] + extra_tags
                if keyakinan_ai < 0.65:
                    tags_all.append("perlu-tinjau-cabang")
                    ragu_warnings.append(f"{cid} (keyakinan {int(keyakinan_ai*100)}%)")
                if grounding_sc < 0.50:
                    tags_all.append("cek-kesetiaan")
                    ragu_warnings.append(f"{cid} (grounding {int(grounding_sc*100)}%)")
                dummy = {"ide": ide_text, "penjelasan": penjelasan, "tag": tags_all, "cabang": card_cabang, "alat": [], "tugas": "", "tahap_kerja": ""}
                detected_tools = mesin_cerdas.detect_tools_in_card(dummy)
                detected_stage = mesin_cerdas.detect_workflow_stage(dummy)
                rel_list = list(pt.get("relasi") or [])
                has_conflict_prop = any(r.get("tipe") == "bertentangan-dengan" for r in rel_list)
                conflict_note = " | [usulan pertentangan otomatis — perlu konfirmasi pengguna]" if has_conflict_prop else ""
                agent_note = f"[inferensi AI] 1-call terstruktur ({model_ekstrak}, prompt {versi_prompt}, keyakinan={keyakinan_ai}, grounding={grounding_sc}){conflict_note}."
            else:
                raw_ide = pt["ide"].strip().strip("[]")
                raw_penj = pt["penjelasan"]
                ide_text, penjelasan = raw_ide.replace('"', "'").strip(), raw_penj
                kutipan_words = (pt["kutipan"] or raw_ide).split()
                kutipan_2 = " ".join(kutipan_words[:14]) + ("..." if len(kutipan_words) > 14 else "")
                card_cabang = cabang_slug
                card_bidang = bidang
                card_tahap = default_tahap
                pt_meta = mesin_cerdas.infer_card_metadata_math(f"{raw_ide} {raw_penj}", platform=clean_platform, url=clean_url)
                card_jenis = pt_meta["jenis"]
                card_trust = pt_meta["kepercayaan"]
                card_dasar = pt_meta["dasar"]
                konsep_list = mesin_cerdas.normalize_concepts(pt_meta["tags"][:3])
                kondisi_berlaku = "umum"
                model_ekstrak = "ekstraktif-offline"
                versi_prompt = "math-v1"
                tags_all = ["draf-ekstraktif"] + pt_meta["tags"] + [clean_platform.lower()] + extra_tags
                detected_tools = pt["alat"]
                detected_stage = pt["tahap_kerja"]
                rel_list = mesin_cerdas.find_auto_relations(ide_text, penjelasan, existing_cards_snapshot, limit=2)
                agent_note = f"[inferensi AI] Draf ekstraktif offline (perlu ditinjau) — TextTiling #{pt['segmen'] + 1}, LexRank={pt['lexrank']}, Entropi={pt['entropi']}."

            used_branches.add(card_cabang)
            ide_short = " ".join(ide_text.split()[:12])
            source_saripati_items.append(ide_text)
            created_entries.append((cid, ide_short, card_cabang, card_tahap, card_trust))
            alat_yaml = f"[{', '.join(detected_tools)}]" if detected_tools else "[]"
            konsep_yaml = "[" + ", ".join(dict.fromkeys(konsep_list)) + "]" if konsep_list else "[]"
            tags_yaml = "[" + ", ".join(dict.fromkeys(tags_all)) + "]"

            # Relasi berurutan antar Daun + relasi ke kartu lama (otomatis ditulis 2 arah!)
            rel_lines: list[str] = []
            inverse_queue: list[tuple[str, str]] = []
            if idx_pt > 0:
                prev_cid = created_cids[idx_pt - 1]
                rel_lines.append(f"  - {{tipe: lanjutan-dari, ke: {prev_cid}}}")
                inverse_queue.append((prev_cid, "lanjutan-dari"))
            seen_rel_targets: set[str] = {created_cids[idx_pt - 1]} if idx_pt > 0 else set()
            for r in rel_list:
                rk, rt = r.get("ke", ""), r.get("tipe", "terkait")
                if rk and rk != cid and rk not in seen_rel_targets:
                    rel_lines.append(f"  - {{tipe: {rt}, ke: {rk}}}")
                    inverse_queue.append((rk, rt))
                    seen_rel_targets.add(rk)
            rel_yaml = ("\n" + "\n".join(rel_lines)) if rel_lines else "[]"

            card_md = (
                f"---\n"
                f"id: {cid}\n"
                f'ide: "{ide_text}"\n'
                f"bidang: {card_bidang}\n"
                f"cabang: {card_cabang}\n"
                f"tahap: {card_tahap}\n"
                f"jenis: {card_jenis}\n"
                f"kepercayaan: {card_trust}\n"
                f"dasar: {card_dasar}\n"
                f"konsep: {konsep_yaml}\n"
                f'kondisi-berlaku: "{kondisi_berlaku}"\n'
                f"model-ekstrak: {model_ekstrak}\n"
                f"versi-prompt: {versi_prompt}\n"
                f"tag: {tags_yaml}\n"
                f"sumber: [[{sid}]]\n"
                f"relasi: {rel_yaml}\n"
                f"dibuat: {today}\n"
                f"status: aktif\n"
                f"publik: tidak\n"
                f"penerapan: belum-dicoba\n"
                f'penerapan-catatan: ""\n'
                f"terakhir-ditinjau: {today}\n"
                f"bintang: 0\n"
                f'catatan-khusus: ""\n'
                f"alat: {alat_yaml}\n"
                f"tugas: {card_cabang.split('/')[-1]}\n"
                f"tahap-kerja: {detected_stage}\n"
                f"---\n\n"
                f"## Ide\n{penjelasan}\n\n"
                f"## Kutipan Pendukung\n> {kutipan_2}\n\n"
                f"## Catatan Agen\n"
                f"{agent_note}\n"
            )
            (ROOT / "kartu" / f"{cid}.md").write_text(card_md, encoding="utf-8")
            for target_cid, r_type in inverse_queue:
                add_inverse_relation(target_cid, r_type, cid)

    created_cid = created_cids[0] if created_cids else None
    kartu_list_str = "[" + ", ".join(created_cids) + "]" if created_cids else "[]"
    saripati_txt = (
        " | ".join(f"({i+1}) {txt}" for i, txt in enumerate(source_saripati_items))[:420]
        if source_saripati_items else re.sub(r"\s+", " ", raw_text)[:320]
    )

    content = (
        f"---\n"
        f"id: {sid}\n"
        f'judul: "{clean_judul}"\n'
        f"jenis: {clean_jenis}\n"
        f"penulis: {clean_penulis}\n"
        f"platform: {clean_platform}\n"
        f"url: {clean_url}\n"
        f"tanggal-terbit: tidak diketahui\n"
        f"tanggal-masuk: {today}\n"
        f"bidang: [{bidang}]\n"
        f"kartu: {kartu_list_str}\n"
        f"---\n\n"
        f"## Saripati\n"
        f"{saripati_txt}\n\n"
        f"## Teks Asli\n"
        f"{raw_text}\n"
    )
    fp.write_text(content, encoding="utf-8")

    for cid, ide_short, c_cabang, c_tahap, c_trust in created_entries:
        sync_branch_and_index(c_cabang, cid, ide_short, c_tahap, today, kepercayaan=c_trust)

    # Append ke sumber/_katalog.md dan log.md
    kat_fp = ROOT / "sumber" / "_katalog.md"
    branches_summary = ", ".join(sorted(used_branches)) if used_branches else cabang_slug
    with kat_fp.open("a", encoding="utf-8") as f:
        f.write(f'\n{sid} | {today} | {clean_jenis} | {clean_penulis} | "{clean_judul}" | bidang: {bidang} | {len(created_cids)} kartu')

    log_fp = ROOT / "log.md"
    with log_fp.open("a", encoding="utf-8") as f:
        if merged_into_cid:
            extra = f" -> digabung ke {merged_into_cid} ({branches_summary})"
        elif created_cids:
            extra = f" -> daun {', '.join(created_cids)} ({branches_summary})"
        else:
            extra = " | menunggu ekstraksi kartu"
        f.write(f'\n[{today}] TANGKAP {sid} | "{clean_judul}" ({clean_platform}){extra}')

    # Sinkronkan FTS5, data.json & peta-pohon.html lokal
    rebuild_local_artifacts()
    return {
        "ok": True,
        "id": sid,
        "kartu_id": created_cid,
        "kartu_ids": created_cids,
        "digabung_ke": merged_into_cid,
        "peringatan_ragu": ragu_warnings,
        "bidang": branches_summary,
        "file": f"sumber/{sid}.md",
    }


def set_fm_field(content: str, key: str, val: str) -> str:
    pat = re.compile(rf"^{re.escape(key)}:\s*.*$", re.M)
    if pat.search(content):
        return pat.sub(f"{key}: {val}", content, count=1)
    return content.replace("\n---\n", f"\n{key}: {val}\n---\n", 1)


def update_card_penerapan(card_id: str, status: str, catatan: str | None) -> None:
    fp = ROOT / "kartu" / f"{card_id}.md"
    if not fp.is_file():
        raise FileNotFoundError(f"Kartu {card_id} tidak ditemukan")
    today = date.today().isoformat()
    safe_note = (catatan or "").replace("\r", " ").replace("\n", " ").replace('"', "'").strip()[:300]
    txt = fp.read_text(encoding="utf-8").replace("\r\n", "\n")

    txt = set_fm_field(txt, "penerapan", status)
    if catatan is not None:
        txt = set_fm_field(txt, "penerapan-catatan", f'"{safe_note}"')
    txt = set_fm_field(txt, "terakhir-ditinjau", today)
    fp.write_text(txt, encoding="utf-8")

    # Append ke log.md
    log_fp = ROOT / "log.md"
    note_part = f' | catatan: "{safe_note}"' if (catatan is not None and safe_note) else ""
    with log_fp.open("a", encoding="utf-8") as f:
        f.write(f"\n[{today}] PENERAPAN {card_id} -> {status}{note_part}")

    # Sinkronkan indeks & data.json lokal
    rebuild_local_artifacts()


def edit_card(card_id: str, payload: dict) -> dict:
    """CRUD Edit Kartu: ubah ide, penjelasan, cabang, tahap, kepercayaan, bintang (0-5), atau catatan khusus."""
    fp = ROOT / "kartu" / f"{card_id}.md"
    if not fp.is_file():
        raise FileNotFoundError(f"Kartu {card_id} tidak ditemukan")
    raw = fp.read_text(encoding="utf-8")
    fm, body = bangun_pohon.parse_frontmatter(raw)
    old_cabang = str(fm.get("cabang") or fm.get("bidang") or "lainnya").strip()
    today = date.today().isoformat()
    text = raw

    if "ide" in payload and str(payload["ide"]).strip():
        clean_ide = re.sub(r"[\r\n]+", " ", str(payload["ide"])).replace('"', "'").strip()[:220]
        text = set_fm_field(text, "ide", clean_ide)
    if "tahap" in payload and str(payload["tahap"]).strip() in {"sebelum-20", "20-25", "25-30", "30-40", "40-50", "50+", "semua-usia"}:
        text = set_fm_field(text, "tahap", str(payload["tahap"]).strip())
    if "kepercayaan" in payload and str(payload["kepercayaan"]).strip() in {"tinggi", "sedang", "rendah", "belum-diverifikasi"}:
        text = set_fm_field(text, "kepercayaan", str(payload["kepercayaan"]).strip())
    if "bintang" in payload:
        try:
            stars = max(0, min(5, int(payload["bintang"])))
        except Exception:
            stars = 0
        text = set_fm_field(text, "bintang", str(stars))
    if "catatan_khusus" in payload:
        clean_note = str(payload["catatan_khusus"]).replace("\r\n", " ").replace("\n", " ").replace('"', "'").strip()[:500]
        text = set_fm_field(text, "catatan-khusus", f'"{clean_note}"')

    new_cabang = old_cabang
    if "cabang" in payload and str(payload["cabang"]).strip():
        cand = str(payload["cabang"]).strip().lower()
        if (ROOT / "cabang" / Path(*cand.split("/")) / "_cabang.md").is_file():
            new_cabang = cand
        elif "/" in cand:
            new_cabang = ensure_subbranch_exists(cand, today)
        else:
            new_cabang = ensure_top_branch_exists(cand, today)
        text = set_fm_field(text, "cabang", new_cabang)
        text = set_fm_field(text, "bidang", new_cabang.split("/")[0])

    if "penjelasan" in payload:
        new_penj = str(payload["penjelasan"]).strip()
        m_ide = re.search(r"(## Ide\s*\n)([\s\S]*?)(\n## Kutipan Pendukung|\n## Catatan Agen|\Z)", text)
        if m_ide and new_penj:
            text = text[:m_ide.start()] + m_ide.group(1) + new_penj + "\n\n" + text[m_ide.end():].lstrip("\n")

    text = set_fm_field(text, "terakhir-ditinjau", today)
    fp.write_text(text, encoding="utf-8")

    recount_branch_and_index(old_cabang, today)
    if new_cabang != old_cabang:
        recount_branch_and_index(new_cabang, today)
        # Active Learning: catat koreksi cabang manual agar Naive Bayes makin pintar setiap hari
        kor_rec = {
            "ts": today,
            "id": card_id,
            "dari": old_cabang,
            "cabang": new_cabang,
            "teks": f"{fm.get('ide', '')} {body[:260]}",
        }
        with (ROOT / ".koreksi_cabang.jsonl").open("a", encoding="utf-8") as kf:
            kf.write(json.dumps(kor_rec, ensure_ascii=False) + "\n")

    with (ROOT / "log.md").open("a", encoding="utf-8") as f:
        f.write(f"\n[{today}] EDIT {card_id} | cabang: {new_cabang}")

    rebuild_local_artifacts()
    return {"ok": True, "id": card_id, "cabang": new_cabang}


def polish_draft_cards(card_id: str = "") -> dict:
    """Rapikan & terjemahkan kartu draf-ekstraktif / berbahasa asing ke Bahasa Indonesia (maks 5 kartu per klik)."""
    cards = bangun_pohon.load_cards(ROOT / "kartu")
    targets = []
    if card_id and card_id in cards:
        targets = [cards[card_id]]
    else:
        for cid, c in sorted(cards.items()):
            if c.get("status") != "aktif":
                continue
            is_draft = any(t in ("draf-ekstraktif", "ekstraksi-matematika", "draf-otomatis") for t in (c.get("tag") or []))
            is_foreign = mesin_cerdas._is_mostly_non_indonesian(f"{c.get('ide', '')} {c.get('penjelasan', '')}")
            if is_draft or is_foreign:
                targets.append(c)
            if len(targets) >= 5:
                break

    if not targets:
        return {"ok": True, "dirapikan": [], "pesan": "Semua kartu sudah rapi dalam Bahasa Indonesia!"}

    today = date.today().isoformat()
    polished_ids: list[str] = []
    for c in targets:
        cid = c["id"]
        fp = ROOT / "kartu" / f"{cid}.md"
        if not fp.is_file():
            continue
        new_ide, new_penj = mesin_cerdas.translate_and_polish_card_gemini(c["ide"], c["penjelasan"])
        txt = fp.read_text(encoding="utf-8").replace("\r\n", "\n")
        clean_ide = new_ide.replace('"', "'").strip()
        txt = set_fm_field(txt, "ide", f'"{clean_ide}"')
        new_tags = [t for t in (c.get("tag") or []) if t not in ("draf-ekstraktif", "ekstraksi-matematika", "draf-otomatis")]
        if not new_tags:
            new_tags = [c.get("bidang", "lainnya")]
        txt = set_fm_field(txt, "tag", "[" + ", ".join(dict.fromkeys(new_tags)) + "]")
        txt = set_fm_field(txt, "terakhir-ditinjau", today)
        m_ide = re.search(r"(## Ide\s*\n)([\s\S]*?)(\n## Kutipan Pendukung|\n## Catatan Agen|\Z)", txt)
        if m_ide and new_penj:
            txt = txt[:m_ide.start()] + m_ide.group(1) + new_penj + "\n\n" + txt[m_ide.end():].lstrip("\n")
        fp.write_text(txt, encoding="utf-8")
        polished_ids.append(cid)

    if polished_ids:
        with (ROOT / "log.md").open("a", encoding="utf-8") as f:
            f.write(f"\n[{today}] RAPIKAN-DRAF {', '.join(polished_ids)} | diterjemahkan & dirapikan otomatis")
        rebuild_local_artifacts()
    return {"ok": True, "dirapikan": polished_ids, "pesan": f"{len(polished_ids)} kartu berhasil dirapikan: {', '.join(polished_ids)}"}


def archive_card(card_id: str, alasan: str = "") -> None:
    """Tandai kartu sebagai status: usang tanpa menghapus file (AGENTS.md Bagian 2.2 & 14)."""
    fp = ROOT / "kartu" / f"{card_id}.md"
    if not fp.is_file():
        raise FileNotFoundError(f"Kartu {card_id} tidak ditemukan")
    today = date.today().isoformat()
    txt = fp.read_text(encoding="utf-8").replace("\r\n", "\n")
    fm, _ = bangun_pohon.parse_frontmatter(txt)
    cabang_slug = str(fm.get("cabang") or fm.get("bidang") or "lainnya").strip()

    if re.search(r"^status:\s*.*$", txt, re.M):
        txt = re.sub(r"^status:\s*.*$", "status: usang", txt, count=1, flags=re.M)
    else:
        txt = txt.replace("\n---\n", "\nstatus: usang\n---\n", 1)
    fp.write_text(txt, encoding="utf-8")

    safe_reason = alasan.replace("\r", " ").replace("\n", " ").replace('"', "'").strip()[:200]
    reason_part = f' | alasan: "{safe_reason}"' if safe_reason else ""
    log_fp = ROOT / "log.md"
    with log_fp.open("a", encoding="utf-8") as f:
        f.write(f"\n[{today}] ARSIP {card_id} -> status: usang{reason_part}")

    recount_branch_and_index(cabang_slug, today)
    rebuild_local_artifacts()


class PohonHandler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/peta-pohon.html"):
            fp = ROOT / "peta-pohon.html"
            if not fp.is_file():
                self.send_error(404, "peta-pohon.html belum dibangun")
                return
            data = fp.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if path == "/data.json":
            fp = ROOT / "data.json"
            if not fp.is_file():
                self.send_error(404)
                return
            data = fp.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if path.startswith("/assets/"):
            fname = path.removeprefix("/assets/").strip()
            if not re.match(r"^[A-Za-z0-9._-]+\.(png|jpg|jpeg|webp|svg|gif)$", fname, re.I):
                self.send_error(400, "Nama berkas aset tidak valid")
                return
            fp = ROOT / "assets" / fname
            if not fp.is_file():
                self.send_error(404, "Aset tidak ditemukan")
                return
            ext = fp.suffix.lower()
            mime = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
                ".svg": "image/svg+xml",
                ".gif": "image/gif",
            }.get(ext, "application/octet-stream")
            data = fp.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if path.startswith("/api/sumber/"):
            sid = path.removeprefix("/api/sumber/").strip()
            if not SRC_ID_RE.match(sid):
                self._send_json(400, {"error": "ID sumber tidak valid"})
                return
            fp = ROOT / "sumber" / f"{sid}.md"
            if not fp.is_file():
                self._send_json(404, {"error": "Sumber tidak ditemukan"})
                return
            _, body = bangun_pohon.parse_frontmatter(fp.read_text(encoding="utf-8"))
            secs = bangun_pohon.parse_sections(body)
            self._send_json(200, {"id": sid, "teks_asli": secs.get("Teks Asli", "")})
            return

        if path == "/api/analisis":
            qs = parse_qs(parsed.query)
            jenis = (qs.get("jenis", ["tren"])[0] or "tren").strip()
            q = (qs.get("q", [""])[0] or "").strip()[:200]
            try:
                if jenis == "bandingkan":
                    self._send_json(200, mesin_cerdas.analyze_compare(q or "ai"))
                elif jenis == "playbook":
                    self._send_json(200, mesin_cerdas.analyze_playbook(q or "ai"))
                elif jenis == "sains":
                    self._send_json(200, mesin_cerdas.analyze_data_science())
                else:
                    self._send_json(200, mesin_cerdas.analyze_trends())
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        if path == "/api/jurnal":
            qs = parse_qs(parsed.query)
            tahun = (qs.get("tahun", [""])[0] or "").strip()[:4]
            bulan = (qs.get("bulan", [""])[0] or "").strip()[:2]
            level = (qs.get("level", [""])[0] or "").strip()[:20]
            dimensi = (qs.get("dimensi", [""])[0] or "").strip()[:30]
            q = (qs.get("q", [""])[0] or "").strip()[:200]
            try:
                self._send_json(200, jurnal_engine.list_jurnal(tahun=tahun, bulan=bulan, level=level, q=q, dimensi=dimensi))
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        if path == "/api/jurnal/kompas":
            try:
                self._send_json(200, {"ok": True, "items": jurnal_engine.list_kompas_sikap()})
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        if path == "/api/jurnal/biografi":
            qs = parse_qs(parsed.query)
            tahun = (qs.get("tahun", [""])[0] or "").strip()[:4]
            level = (qs.get("level", [""])[0] or "").strip()[:20]
            try:
                self._send_json(200, jurnal_engine.get_biografi_dan_pertumbuhan(tahun=tahun, level=level))
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        if path == "/api/briefing":
            try:
                self._send_json(200, mesin_cerdas.build_weekly_briefing())
            except Exception as exc:
                self._send_json(500, {"error": f"Gagal menyusun briefing: {exc}"})
            return

        if path.startswith("/api/jurnal/"):
            tgl = path.removeprefix("/api/jurnal/").strip()
            try:
                jurnal_engine.validate_date_str(tgl)
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            item = jurnal_engine.get_jurnal(tgl)
            if not item:
                self._send_json(404, {"ok": False, "error": "Belum ada catatan untuk tanggal ini", "tanggal": tgl})
                return
            self._send_json(200, {"ok": True, "item": item})
            return

        self.send_error(404, "Tidak ditemukan")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in ("/api/penerapan", "/api/status-lokal", "/api/ambil-link", "/api/simpan-sumber", "/api/arsipkan-kartu", "/api/edit-kartu", "/api/tanya", "/api/tanya-feedback", "/api/ekstrak-matematika", "/api/ocr-gambar", "/api/baca-pdf", "/api/rapikan-draf", "/api/keputusan", "/api/jurnal", "/api/jurnal/refleksi", "/api/jurnal/kompas"):
            self.send_error(404, "Endpoint tidak dikenal")
            return
        max_len = 16_000_000 if parsed.path == "/api/baca-pdf" else (8_000_000 if parsed.path == "/api/ocr-gambar" else (2_000_000 if parsed.path == "/api/jurnal" else (512_000 if parsed.path in ("/api/simpan-sumber", "/api/ekstrak-matematika") else (32_768 if parsed.path in ("/api/edit-kartu", "/api/jurnal/kompas") else 4096))))
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > max_len:
                self._send_json(400, {"error": "Ukuran body tidak valid"})
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            self._send_json(400, {"error": "JSON tidak valid"})
            return

        if parsed.path == "/api/keputusan":
            dilema = str(payload.get("dilema", "")).strip()[:800]
            if len(dilema) < 4:
                self._send_json(400, {"error": "Tuliskan dilema/keputusan minimal 4 karakter"})
                return
            try:
                out = mesin_cerdas.advise_decision(dilema)
            except Exception as exc:
                self._send_json(500, {"error": f"Gagal memproses konsultasi keputusan: {exc}"})
                return
            self._send_json(200, out)
            return

        if parsed.path == "/api/jurnal/refleksi":
            tgl = str(payload.get("tanggal", "")).strip()
            auto_meta = bool(payload.get("auto_meta", True))
            try:
                jurnal_engine.validate_date_str(tgl)
                out = jurnal_engine.analyze_and_reflect_journal(tgl, apply_auto_meta=auto_meta)
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            except FileNotFoundError as exc:
                self._send_json(404, {"error": str(exc)})
                return
            except Exception as exc:
                self._send_json(500, {"error": f"Gagal membuat refleksi AI: {exc}"})
                return
            self._send_json(200, out)
            return

        if parsed.path == "/api/jurnal/kompas":
            try:
                out = jurnal_engine.save_kompas_sikap(
                    sikap=str(payload.get("sikap", "")),
                    tanggal=str(payload.get("tanggal", "")),
                    kartu=payload.get("kartu") if isinstance(payload.get("kartu"), list) else [],
                    dimensi=payload.get("dimensi") if isinstance(payload.get("dimensi"), list) else [],
                )
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            except Exception as exc:
                self._send_json(500, {"error": f"Gagal menyimpan Kompas Sikap: {exc}"})
                return
            self._send_json(200, out)
            return

        if parsed.path == "/api/jurnal":
            try:
                out = jurnal_engine.save_jurnal(payload)
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            except Exception as exc:
                self._send_json(500, {"error": f"Gagal menyimpan jurnal: {exc}"})
                return
            self._send_json(200, out)
            return

        if parsed.path == "/api/ambil-link":
            url = str(payload.get("url", "")).strip()
            if not url:
                self._send_json(400, {"error": "URL kosong"})
                return
            res = ambil_link.fetch_url(url)
            self._send_json(200 if res.get("ok") else 422, res)
            return

        if parsed.path == "/api/ekstrak-matematika":
            teks = str(payload.get("teks_asli", "")).strip()
            max_daun = int(payload.get("max_daun", 3) or 3)
            if len(teks) < 5:
                self._send_json(400, {"error": "Teks minimal 5 karakter"})
                return
            pts = mesin_cerdas.extract_atomic_insights_math(teks, max_cards=max(1, min(5, max_daun)))
            cabang_guess, sc = guess_branch(teks)
            self._send_json(200, {"ok": True, "cabang_usulan": cabang_guess, "skor_cabang": sc, "daun": pts})
            return

        if parsed.path == "/api/baca-pdf":
            file_b64 = str(payload.get("file_b64", "")).strip()
            fname = str(payload.get("filename", "dokumen.pdf")).strip()[:140]
            if not file_b64:
                self._send_json(400, {"error": "File kosong"})
                return
            local_env = mesin_cerdas.load_local_env()
            api_key = (local_env.get("GEMINI_API_KEY") or "").strip()
            res = ambil_link.extract_pdf_text(file_b64, filename=fname, api_key=api_key)
            self._send_json(200 if res.get("ok") else 422, res)
            return

        if parsed.path == "/api/ocr-gambar":
            img_b64 = str(payload.get("image_b64", "")).strip()
            mime = str(payload.get("mime_type", "image/png")).strip()
            local_env = mesin_cerdas.load_local_env()
            api_key = (local_env.get("GEMINI_API_KEY") or "").strip()
            res = ambil_link.extract_image_text(img_b64, mime_type=mime, api_key=api_key)
            self._send_json(200 if res.get("ok") else 422, res)
            return

        if parsed.path == "/api/rapikan-draf":
            cid = str(payload.get("id", "")).strip()
            if cid and not CARD_ID_RE.match(cid):
                self._send_json(400, {"error": "Format ID kartu harus K-XXXX"})
                return
            try:
                out = polish_draft_cards(cid)
            except Exception as exc:
                self._send_json(500, {"error": f"Gagal merapikan draf: {exc}"})
                return
            self._send_json(200, out)
            return

        if parsed.path == "/api/simpan-sumber":
            teks = str(payload.get("teks_asli", "")).strip()
            if len(teks) < 5:
                self._send_json(400, {"error": "Teks asli terlalu pendek (minimal 5 karakter)"})
                return
            try:
                out = create_new_source(
                    judul=str(payload.get("judul", "")),
                    jenis=str(payload.get("jenis", "postingan")),
                    penulis=str(payload.get("penulis", "tidak diketahui")),
                    platform=str(payload.get("platform", "lainnya")),
                    url=str(payload.get("url", "tidak ada")),
                    teks_asli=teks,
                    bidang_pilihan=str(payload.get("bidang", "")).strip(),
                    tahap_pilihan=str(payload.get("tahap", "semua-usia")).strip(),
                    buat_draf=bool(payload.get("buat_draf", True)),
                    subcabang_baru=str(payload.get("subcabang_baru", "")).strip(),
                    max_daun=int(payload.get("max_daun", 3) or 3),
                )
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            except Exception as exc:
                self._send_json(500, {"error": f"Gagal menyimpan sumber: {exc}"})
                return
            self._send_json(200, out)
            return

        if parsed.path == "/api/tanya":
            pertanyaan = str(payload.get("pertanyaan", "")).strip()[:500]
            if len(pertanyaan) < 2:
                self._send_json(400, {"error": "Pertanyaan terlalu pendek (minimal 2 karakter)"})
                return
            try:
                out = mesin_cerdas.answer_question(pertanyaan)
            except Exception as exc:
                self._send_json(500, {"error": f"Gagal memproses pertanyaan: {exc}"})
                return
            self._send_json(200, out)
            return

        if parsed.path == "/api/tanya-feedback":
            fb = {
                "ts": date.today().isoformat(),
                "pertanyaan": str(payload.get("pertanyaan", ""))[:200],
                "nilai": "positif" if payload.get("positif") else "negatif",
                "mode": str(payload.get("mode", ""))[:40],
            }
            fb_fp = ROOT / ".tanya_feedback.jsonl"
            with fb_fp.open("a", encoding="utf-8") as f:
                f.write(json.dumps(fb, ensure_ascii=False) + "\n")
            self._send_json(200, {"ok": True})
            return

        if parsed.path == "/api/edit-kartu":
            cid = str(payload.get("id", "")).strip()
            if not CARD_ID_RE.match(cid):
                self._send_json(400, {"error": "Format ID kartu harus K-XXXX"})
                return
            try:
                out = edit_card(cid, payload)
            except FileNotFoundError as exc:
                self._send_json(404, {"error": str(exc)})
                return
            except Exception as exc:
                self._send_json(500, {"error": f"Gagal memperbarui kartu: {exc}"})
                return
            self._send_json(200, out)
            return

        if parsed.path == "/api/arsipkan-kartu":
            cid = str(payload.get("id", "")).strip()
            alasan = str(payload.get("alasan", "")).strip()
            if not CARD_ID_RE.match(cid):
                self._send_json(400, {"error": "Format ID kartu harus K-XXXX"})
                return
            try:
                archive_card(cid, alasan)
            except FileNotFoundError as exc:
                self._send_json(404, {"error": str(exc)})
                return
            except Exception as exc:
                self._send_json(500, {"error": f"Gagal mengarsipkan: {exc}"})
                return
            self._send_json(200, {"ok": True, "id": cid, "status": "usang"})
            return

        cid = str(payload.get("id", "")).strip()
        status = str(payload.get("status", payload.get("penerapan", ""))).strip()
        catatan = payload.get("catatan", None)
        if catatan is not None:
            catatan = str(catatan)

        if not CARD_ID_RE.match(cid):
            self._send_json(400, {"error": "Format ID kartu harus K-XXXX"})
            return
        if status not in ALLOWED_STATUS:
            self._send_json(400, {"error": "Status penerapan tidak valid"})
            return

        try:
            update_card_penerapan(cid, status, catatan)
        except FileNotFoundError as exc:
            self._send_json(404, {"error": str(exc)})
            return
        except Exception as exc:
            self._send_json(500, {"error": f"Gagal memperbarui: {exc}"})
            return

        self._send_json(200, {"ok": True, "id": cid, "penerapan": status, "diperbarui": date.today().isoformat()})

    def log_message(self, fmt: str, *args) -> None:
        print(f"[server-lokal] {self.address_string()} - {fmt % args}")


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8765
    server = HTTPServer(("127.0.0.1", port), PohonHandler)
    print(f"Pohon Pengetahuan (Lokal) berjalan di http://127.0.0.1:{port}/  (Ctrl+C untuk berhenti)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer dihentikan.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
