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

# Impor fungsi bangun ulang, ambil_link, dan mesin_cerdas
sys.path.insert(0, str(ROOT / "scripts"))
import ambil_link  # noqa: E402
import bangun_pohon  # noqa: E402
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
    "ai/video-dan-clipping": ["video ai", "clipping", "kling", "veo", "runway", "sora", "heygen", "capcut", "opus clip", "dubbing", "avatar ai", "storyboard", "elevenlabs"],
    "ai/tulisan-dan-artikel": ["tone-of-voice", "tone of voice", "artikel ai", "sample writing", "blog ai", "thread ai", "copywriting ai"],
    "ai/coding-dan-proyek": ["claude code", "cursor", "coding", "bikin app", "github", "repo", "api", "python", "nextjs", "vercel", "ui slop", "frontend", "typescript", "javascript", "colab"],
    "ai/prompt-dan-agen": ["prompt", "ai agent", "agents", "agentic", "skill", "skills", "mcp", "workflow", "context engineering", "n8n", "otomasi", "automation"],
    "ai/perbandingan-model": ["fable", "opus", "sonnet", "gemini", "benchmark", "tonality", "dibanding model", "perbandingan model", "gpt-5", "claude", "vs gpt", "vs claude", "vs gemini"],
    "ai": ["ai", "llm", "claude", "gemini", "gpt", "chatgpt", "artificial intelligence", "machine learning", "openai", "anthropic"],
    "digital-marketing": ["seo", "ai-search", "digital marketing", "copywriting", "funnel", "landing page", "iklan", "ads", "konversi", "ctr", "lead", "marketing"],
    "sosmed": ["ocr", "impresi", "reupload", "repost", "viral", "algoritma", "payout", "tiktok", "instagram", "threads", "youtube", "konten", "hook", "followers", "cenblu", "creator", "engagement"],
    "bisnis": ["bisnis", "business", "produk digital", "validasi", "omzet", "jualan", "client", "agency", "saas", "micro-saas", "revenue", "scale", "pasar", "startup", "monetize", "arr"],
    "keuangan": ["tabungan", "investasi", "saham", "gaji", "utang", "dana darurat", "anggaran", "keuangan", "finance", "money", "saving", "investing", "income", "wealth"],
    "kesehatan": ["tidur", "sleep", "olahraga", "workout", "gym", "lift", "weights", "athlete", "makan", "eat", "nutrisi", "nutrition", "diet", "healthy", "kesehatan", "health", "otot", "muscle", "postur", "posture", "appearance", "penampilan", "skincare", "grooming", "stres", "stress", "mental", "dokter", "medis", "fitness", "brain fog", "biological", "circadian", "longevity", "recovery", "istirahat", "begadang", "kafein", "caffeine", "hormon", "hormone", "tubuh", "otak", "fatigue", "burnout", "kalori", "protein"],
    "kesuksesan": ["karier", "karir", "career", "cpns", "beasiswa", "scholarship", "ausbildung", "jepang", "jerman", "magang", "internship", "wawancara", "interview", "success", "achievement"],
    "motivasi-dan-mindset": ["mindset", "disiplin", "discipline", "kebiasaan", "habit", "habits", "overthinking", "perfeksionis", "fokus", "focus", "konsisten", "consistent", "malas", "takut", "motivasi", "motivation", "routine", "self-improvement", "will be your year", "akan menjadi tahunmu"],
    "relasi": ["relasi", "relationship", "komunikasi", "communication", "jejaring", "networking", "keluarga", "family", "pasangan", "teman", "friends", "negosiasi", "negotiation"],
}

TOP_BRANCHES = {
    "ai", "bisnis", "sosmed", "digital-marketing",
    "keuangan", "kesuksesan", "kesehatan", "motivasi-dan-mindset", "relasi", "lainnya",
}

VALID_BRANCHES = {
    "ai", "ai/video-dan-clipping", "ai/tulisan-dan-artikel", "ai/coding-dan-proyek",
    "ai/prompt-dan-agen", "ai/perbandingan-model",
    "bisnis", "sosmed", "digital-marketing",
    "keuangan", "kesuksesan", "kesehatan", "motivasi-dan-mindset", "relasi", "lainnya",
}


def _classify_branch_gemini(text: str) -> str | None:
    """Lapis 1: Klasifikasi topik berbasis pemahaman makna (semantik) via Gemini Free Tier."""
    local_env = mesin_cerdas.load_local_env()
    api_key = (os.environ.get("GEMINI_API_KEY") or local_env.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        return None
    import urllib.request
    import urllib.error
    branches_list = ", ".join(sorted(VALID_BRANCHES))
    prompt = (
        f"Pilih TEPAT SATU nama topik paling cocok untuk teks berikut dari daftar ini:\n"
        f"{branches_list}\n\n"
        f"Aturan: balas HANYA nama topik yang persis sama dengan salah satu di daftar (contoh: kesehatan), tanpa tanda baca atau penjelasan lain.\n\n"
        f"Teks:\n{text[:1200]}"
    )
    for mdl in ("gemini-2.5-flash-lite", "gemini-2.5-flash"):
        try:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{mdl}:generateContent?key={api_key}"
            body = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.0, "maxOutputTokens": 256, "thinkingConfig": {"thinkingBudget": 0}},
            }
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            cands = data.get("candidates") or []
            parts = ((cands[0].get("content") or {}).get("parts") or []) if cands else []
            ans = "".join(p.get("text", "") for p in parts).strip().lower().strip("`\"'. \n")
            if ans in VALID_BRANCHES:
                return ans
            for b in sorted(VALID_BRANCHES, key=len, reverse=True):
                if b in ans:
                    return b
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                continue
            break
        except Exception:
            break
    return None


def guess_branch(text: str) -> tuple[str, int]:
    # Lapis 1: Pemahaman makna otomatis via Gemini AI (jika GEMINI_API_KEY tersedia)
    ai_branch = _classify_branch_gemini(text)
    if ai_branch:
        return ai_branch, 99

    # Lapis 2 (Offline): Pencocokan kata utuh (word-boundary) agar 'ai' tidak cocok dengan 'brain' / 'daily'
    low = text.lower()
    best_b, best_score = "lainnya", 0
    for b, kws in BIDANG_KEYWORDS.items():
        score = 0
        for kw in kws:
            if re.search(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", low):
                score += 2 if " " in kw else 1
        if score > best_score:
            best_b, best_score = b, score
    # Fallback TF-IDF ke kartu yang sudah ada jika kata kunci belum menangkap
    if best_score == 0:
        cards = bangun_pohon.load_cards(ROOT / "kartu")
        if cards:
            rel = mesin_cerdas.query_relevant_cards(text[:300], cards, limit=3)
            if rel:
                return rel[0]["cabang"], 1
    return best_b, best_score


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


def sync_branch_and_index(cabang_slug: str, cid: str, ide_short: str, tahap: str, today: str) -> None:
    """Tambahkan entri draf kartu tepat di bawah '## Daftar Kartu' dan sinkronkan cabang induk & indeks.md."""
    cab_fp = ROOT / "cabang" / Path(*cabang_slug.split("/")) / "_cabang.md"
    if cab_fp.is_file():
        txt = cab_fp.read_text(encoding="utf-8")
        entry = f"- {cid} | {ide_short} | {tahap} | belum-diverifikasi"
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

    # Cegah duplikat klik ganda: periksa URL atau teks asli yang identik
    existing_sources = bangun_pohon.load_sources(ROOT / "sumber")
    for esid, es in existing_sources.items():
        if clean_url != "tidak ada" and (es.get("url") or "").strip() == clean_url:
            raise ValueError(f"Sumber dengan URL ini sudah tersimpan di {esid}.")
        if (es.get("teks_asli") or "").strip() == raw_text:
            raise ValueError(f"Teks sumber yang sama persis sudah tersimpan di {esid}.")

    extra_tags: list[str] = []
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
    else:
        cabang_slug, score = guess_branch(f"{clean_judul} {raw_text}")
        if score == 0:
            topic_slug = auto_slug_from_text(f"{clean_judul} {raw_text}")
            cabang_slug = ensure_top_branch_exists(topic_slug, today)
            extra_tags.append("cabang-otomatis")

    bidang = cabang_slug.split("/")[0]
    valid_tahap = {"sebelum-20", "20-25", "25-30", "30-40", "40-50", "50+", "semua-usia"}
    tahap = tahap_pilihan if tahap_pilihan in valid_tahap else "semua-usia"

    created_cids: list[str] = []
    created_entries: list[tuple[str, str]] = []
    extracted_points = mesin_cerdas.extract_atomic_insights_math(raw_text, max_cards=max(1, min(5, int(max_daun or 3))))

    if buat_draf:
        cur_num = int(next_card_id().split("-")[1])
        for idx_pt, pt in enumerate(extracted_points):
            cid = f"K-{cur_num + idx_pt:04d}"
            created_cids.append(cid)
            ide_text = pt["ide"].strip().strip("[]")
            ide_short = " ".join(ide_text.split()[:12])
            created_entries.append((cid, ide_short))
            penjelasan = pt["penjelasan"]
            kutipan_2 = pt["kutipan"]
            detected_tools = pt["alat"]
            detected_stage = pt["tahap_kerja"]
            alat_yaml = f"[{', '.join(detected_tools)}]" if detected_tools else "[]"
            tags_all = ["ekstraksi-matematika", clean_platform.lower()] + extra_tags
            tags_yaml = "[" + ", ".join(dict.fromkeys(tags_all)) + "]"

            # Relasi berurutan antar Daun yang lahir dari Akar yang sama
            rel_yaml = "[]"
            if idx_pt > 0:
                prev_cid = created_cids[idx_pt - 1]
                rel_yaml = f"\n  - {{tipe: lanjutan-dari, ke: {prev_cid}}}"

            card_md = (
                f"---\n"
                f"id: {cid}\n"
                f'ide: "{ide_text}"\n'
                f"bidang: {bidang}\n"
                f"cabang: {cabang_slug}\n"
                f"tahap: {tahap}\n"
                f"jenis: opini\n"
                f"kepercayaan: belum-diverifikasi\n"
                f"dasar: tidak-jelas\n"
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
                f"tugas: {cabang_slug.split('/')[-1]}\n"
                f"tahap-kerja: {detected_stage}\n"
                f"---\n\n"
                f"## Ide\n{penjelasan}\n\n"
                f"## Kutipan Pendukung\n> {kutipan_2}\n\n"
                f"## Catatan Agen\n"
                f"[inferensi AI] Diekstrak otomatis dengan pipeline matematika (TextTiling segmen #{pt['segmen'] + 1}, LexRank={pt['lexrank']}, Entropi={pt['entropi']}).\n"
            )
            (ROOT / "kartu" / f"{cid}.md").write_text(card_md, encoding="utf-8")

    created_cid = created_cids[0] if created_cids else None
    kartu_list_str = "[" + ", ".join(created_cids) + "]" if created_cids else "[]"
    saripati_txt = (
        " | ".join(f"({i+1}) {p['ide']}" for i, p in enumerate(extracted_points))[:420]
        if extracted_points else re.sub(r"\s+", " ", raw_text)[:320]
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

    for cid, ide_short in created_entries:
        sync_branch_and_index(cabang_slug, cid, ide_short, tahap, today)

    # Append ke sumber/_katalog.md dan log.md
    kat_fp = ROOT / "sumber" / "_katalog.md"
    with kat_fp.open("a", encoding="utf-8") as f:
        f.write(f'\n{sid} | {today} | {clean_jenis} | {clean_penulis} | "{clean_judul}" | bidang: {bidang} | {len(created_cids)} kartu')

    log_fp = ROOT / "log.md"
    with log_fp.open("a", encoding="utf-8") as f:
        extra = f" -> daun {', '.join(created_cids)} ({cabang_slug})" if created_cids else " | menunggu ekstraksi kartu"
        f.write(f'\n[{today}] TANGKAP {sid} | "{clean_judul}" ({clean_platform}){extra}')

    # Sinkronkan FTS5, data.json & peta-pohon.html lokal
    rebuild_local_artifacts()
    return {"ok": True, "id": sid, "kartu_id": created_cid, "kartu_ids": created_cids, "bidang": cabang_slug, "file": f"sumber/{sid}.md"}


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

    with (ROOT / "log.md").open("a", encoding="utf-8") as f:
        f.write(f"\n[{today}] EDIT {card_id} | cabang: {new_cabang}")

    rebuild_local_artifacts()
    return {"ok": True, "id": card_id, "cabang": new_cabang}


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

        self.send_error(404, "Tidak ditemukan")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in ("/api/penerapan", "/api/status-lokal", "/api/ambil-link", "/api/simpan-sumber", "/api/arsipkan-kartu", "/api/edit-kartu", "/api/tanya", "/api/tanya-feedback", "/api/ekstrak-matematika", "/api/ocr-gambar"):
            self.send_error(404, "Endpoint tidak dikenal")
            return
        max_len = 8_000_000 if parsed.path == "/api/ocr-gambar" else (512_000 if parsed.path in ("/api/simpan-sumber", "/api/ekstrak-matematika") else (32_768 if parsed.path == "/api/edit-kartu" else 4096))
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > max_len:
                self._send_json(400, {"error": "Ukuran body tidak valid"})
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            self._send_json(400, {"error": "JSON tidak valid"})
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

        if parsed.path == "/api/ocr-gambar":
            img_b64 = str(payload.get("image_b64", "")).strip()
            mime = str(payload.get("mime_type", "image/png")).strip()
            local_env = mesin_cerdas.load_local_env()
            api_key = (local_env.get("GEMINI_API_KEY") or "").strip()
            res = ambil_link.extract_image_text(img_b64, mime_type=mime, api_key=api_key)
            self._send_json(200 if res.get("ok") else 422, res)
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
