#!/usr/bin/env python3
"""
Modul Jurnal Harian, Timeline Biografi & Kompas Karakter (Khusus Lokal).
- 100% Python standard library (0 dependensi eksternal).
- Sumber kebenaran tunggal: Markdown murni di jurnal/YYYY/MM/YYYY-MM-DD.md.
- DILARANG KERAS dipublikasikan ke situs/ (diverifikasi periksa_kebocoran.py).
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JURNAL_DIR = ROOT / "jurnal"
KOMPAS_FILE = JURNAL_DIR / "_kompas_sikap.md"

sys.path.insert(0, str(ROOT / "scripts"))
import bangun_pohon  # noqa: E402
import mesin_cerdas  # noqa: E402

DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")

ALLOWED_SUASANA = {"tenang", "semangat", "biasa", "lelah", "cemas", "syukur"}
ALLOWED_PRESTASI = {"besar", "menengah", "kecil", "catatan"}
ALLOWED_DIMENSI = ("disiplin", "kesehatan", "skill-karier", "mental-sikap", "relasi")

DIMENSI_LABELS = {
    "disiplin": "Disiplin",
    "kesehatan": "Kesehatan",
    "skill-karier": "Skill & Karier",
    "mental-sikap": "Mental & Sikap",
    "relasi": "Relasi",
}


def validate_date_str(tgl: str) -> tuple[str, str, str]:
    """Validasi format YYYY-MM-DD secara ketat (mencegah path traversal)."""
    s = (tgl or "").strip()
    m = DATE_RE.match(s)
    if not m:
        raise ValueError("Format tanggal harus YYYY-MM-DD (contoh: 2026-11-26)")
    y, mo, d = m.groups()
    try:
        date(int(y), int(mo), int(d))
    except ValueError as exc:
        raise ValueError(f"Tanggal tidak valid: {s}") from exc
    return y, mo, d


def journal_path_for(tgl: str) -> Path:
    y, mo, _ = validate_date_str(tgl)
    return JURNAL_DIR / y / mo / f"{tgl}.md"


def _parse_list_val(raw: str) -> list[str]:
    s = raw.strip()
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [x.strip().strip("\"'") for x in inner.split(",") if x.strip().strip("\"'")]
    return [s.strip("\"'")] if s else []


def parse_journal_file(fp: Path) -> dict:
    """Baca satu file jurnal Markdown (YAML frontmatter + isi bebas)."""
    text = fp.read_text(encoding="utf-8").replace("\r\n", "\n")
    fm: dict = {}
    body = text
    if text.startswith("---\n"):
        parts = text.split("\n---\n", 1)
        if len(parts) == 2:
            raw_fm, body = parts[0][4:], parts[1].lstrip("\n")
            for line in raw_fm.splitlines():
                if ":" not in line:
                    continue
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip().strip("\"'")

    tgl = fm.get("tanggal") or fp.stem
    suasana = fm.get("suasana", "biasa").lower()
    if suasana not in ALLOWED_SUASANA:
        suasana = "biasa"

    try:
        energi = int(fm.get("energi", 3))
    except ValueError:
        energi = 3
    energi = max(1, min(5, energi))

    prestasi_level = fm.get("prestasi_level", "kecil").lower()
    if prestasi_level not in ALLOWED_PRESTASI:
        prestasi_level = "kecil"

    prestasi_ringkas = fm.get("prestasi_ringkas", "")
    dimensi = [d for d in _parse_list_val(fm.get("dimensi", "[]")) if d in ALLOWED_DIMENSI]
    kartu_terkait = [k for k in _parse_list_val(fm.get("kartu_terkait", "[]")) if re.match(r"^K-\d{4,6}$", k)]
    diperbarui = fm.get("diperbarui") or tgl

    # Pisahkan isi catatan utama dan tanggapan AI (jika ada di Fase 2)
    catatan = body.strip()
    refleksi_ai = ""
    m_cat = re.search(r"^## Catatan Hari Ini\s*\n([\s\S]*?)(?=^## Tanggapan & Refleksi AI\s*$|\Z)", body, re.M)
    if m_cat:
        catatan = m_cat.group(1).strip()
    m_ai = re.search(r"^## Tanggapan & Refleksi AI\s*\n([\s\S]*)\Z", body, re.M)
    if m_ai:
        refleksi_ai = m_ai.group(1).strip()

    words = re.findall(r"\S+", catatan)
    cuplikan = " ".join(catatan.split())[:180]
    if len(" ".join(catatan.split())) > 180:
        cuplikan += "..."

    try:
        rel_path = str(fp.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        rel_path = str(fp).replace("\\", "/")

    return {
        "tanggal": tgl,
        "tahun": tgl[:4] if len(tgl) >= 4 else "",
        "bulan": tgl[5:7] if len(tgl) >= 7 else "",
        "suasana": suasana,
        "energi": energi,
        "prestasi_level": prestasi_level,
        "prestasi_ringkas": prestasi_ringkas,
        "dimensi": dimensi,
        "kartu_terkait": kartu_terkait,
        "diperbarui": diperbarui,
        "isi": catatan,
        "refleksi_ai": refleksi_ai,
        "cuplikan": cuplikan,
        "jumlah_kata": len(words),
        "path_relatif": rel_path,
    }


def list_jurnal(tahun: str = "", bulan: str = "", level: str = "", q: str = "", dimensi: str = "") -> dict:
    """Daftar seluruh entri jurnal terurut terbaru -> terlama, lengkap dengan metadata filter."""
    JURNAL_DIR.mkdir(parents=True, exist_ok=True)
    all_entries: list[dict] = []
    for fp in JURNAL_DIR.rglob("*.md"):
        if fp.name.startswith("_"):
            continue
        if not DATE_RE.match(fp.stem):
            continue
        try:
            all_entries.append(parse_journal_file(fp))
        except Exception:
            continue

    all_entries.sort(key=lambda x: x["tanggal"], reverse=True)

    tahun_set = sorted({e["tahun"] for e in all_entries if e["tahun"]}, reverse=True)
    bulan_set = sorted({e["bulan"] for e in all_entries if e["bulan"] and (not tahun or e["tahun"] == tahun)})

    q_low = (q or "").strip().lower()
    filtered = []
    for e in all_entries:
        if tahun and e["tahun"] != tahun:
            continue
        if bulan and e["bulan"] != bulan:
            continue
        if level and e["prestasi_level"] != level:
            continue
        if dimensi and dimensi not in e["dimensi"]:
            continue
        if q_low:
            hay = " ".join([
                e["tanggal"],
                e["suasana"],
                e["prestasi_ringkas"],
                " ".join(e["dimensi"]),
                " ".join(e["kartu_terkait"]),
                e["isi"],
            ]).lower()
            if q_low not in hay:
                continue
        # Ringkas daftar tanpa mengirim seluruh teks panjang bila tidak diperlukan
        item = dict(e)
        item.pop("isi", None)
        item.pop("refleksi_ai", None)
        filtered.append(item)

    total_kata = sum(e["jumlah_kata"] for e in all_entries)
    level_counts = {lvl: sum(1 for e in all_entries if e["prestasi_level"] == lvl) for lvl in ("besar", "menengah", "kecil", "catatan")}

    return {
        "ok": True,
        "total_semua": len(all_entries),
        "total_terfilter": len(filtered),
        "total_kata": total_kata,
        "tahun_tersedia": tahun_set,
        "bulan_tersedia": bulan_set,
        "hitung_level": level_counts,
        "items": filtered,
    }


def get_jurnal(tgl: str) -> dict | None:
    """Ambil isi utuh satu hari jurnal."""
    fp = journal_path_for(tgl)
    if not fp.is_file():
        return None
    return parse_journal_file(fp)


def save_jurnal(payload: dict) -> dict:
    """Simpan atau perbarui jurnal harian ke jurnal/YYYY/MM/YYYY-MM-DD.md."""
    tgl = str(payload.get("tanggal") or date.today().isoformat()).strip()
    validate_date_str(tgl)

    suasana = str(payload.get("suasana", "biasa")).strip().lower()
    if suasana not in ALLOWED_SUASANA:
        suasana = "biasa"

    try:
        energi = int(payload.get("energi", 3))
    except (TypeError, ValueError):
        energi = 3
    energi = max(1, min(5, energi))

    prestasi_level = str(payload.get("prestasi_level", "kecil")).strip().lower()
    if prestasi_level not in ALLOWED_PRESTASI:
        prestasi_level = "kecil"

    prestasi_ringkas = str(payload.get("prestasi_ringkas", "")).replace("\r", " ").replace("\n", " ").replace('"', "'").strip()[:240]

    raw_dim = payload.get("dimensi") or []
    if isinstance(raw_dim, str):
        raw_dim = [x.strip() for x in raw_dim.split(",") if x.strip()]
    dimensi = [d for d in dict.fromkeys(str(x).strip().lower() for x in raw_dim) if d in ALLOWED_DIMENSI]

    raw_kartu = payload.get("kartu_terkait") or []
    if isinstance(raw_kartu, str):
        raw_kartu = [x.strip() for x in raw_kartu.split(",") if x.strip()]
    kartu_terkait = [k for k in dict.fromkeys(str(x).strip().upper() for x in raw_kartu) if re.match(r"^K-\d{4,6}$", k)]

    isi = str(payload.get("isi", "")).replace("\r\n", "\n").strip()
    if not isi:
        raise ValueError("Isi catatan jurnal tidak boleh kosong.")

    refleksi_ai = str(payload.get("refleksi_ai", "")).replace("\r\n", "\n").strip()

    fp = journal_path_for(tgl)
    is_new = not fp.is_file()

    # Pertahankan refleksi_ai lama jika user hanya mengedit catatan tanpa mengirim refleksi_ai baru
    if not is_new and not refleksi_ai:
        existing = parse_journal_file(fp)
        refleksi_ai = existing.get("refleksi_ai", "")
        if not kartu_terkait and existing.get("kartu_terkait"):
            kartu_terkait = existing["kartu_terkait"]

    today = date.today().isoformat()
    fp.parent.mkdir(parents=True, exist_ok=True)

    dim_str = "[" + ", ".join(dimensi) + "]"
    kartu_str = "[" + ", ".join(kartu_terkait) + "]"

    md_parts = [
        "---",
        f"tanggal: {tgl}",
        f"suasana: {suasana}",
        f"energi: {energi}",
        f"prestasi_level: {prestasi_level}",
        f'prestasi_ringkas: "{prestasi_ringkas}"',
        f"dimensi: {dim_str}",
        f"kartu_terkait: {kartu_str}",
        f"diperbarui: {today}",
        "---",
        "",
        "## Catatan Hari Ini",
        isi,
    ]
    if refleksi_ai:
        md_parts.extend(["", "## Tanggapan & Refleksi AI", refleksi_ai])
    md_parts.append("")

    fp.write_text("\n".join(md_parts), encoding="utf-8")

    # Catat ke log.md (hanya metadata singkat, bukan isi pribadi)
    aksi = "JURNAL-BARU" if is_new else "JURNAL-EDIT"
    kata_cnt = len(re.findall(r"\S+", isi))
    with (ROOT / "log.md").open("a", encoding="utf-8") as lf:
        lf.write(f"\n[{today}] {aksi} {tgl} | level: {prestasi_level} | {kata_cnt} kata | dimensi: {dim_str}")

    saved = parse_journal_file(fp)
    return {"ok": True, "baru": is_new, "item": saved}


# ======================== FASE 2: OTAK PENDUKUNG & KOMPAS SIKAP ========================

DIMENSI_HINTS = {
    "disiplin": ["disiplin", "konsisten", "rutin", "fokus", "jadwal", "bangun pagi", "selesai", "tuntas", "target", "deep work", "habit", "kebiasaan"],
    "kesehatan": ["tidur", "olahraga", "lari", "gym", "workout", "makan", "sehat", "lelah", "capek", "stres", "energi", "jalan kaki", "istirahat", "begadang"],
    "skill-karier": ["belajar", "coding", "proyek", "kerja", "karier", "magang", "cpns", "beasiswa", "ai", "bisnis", "konten", "portofolio", "skill", "deploy", "bikin"],
    "mental-sikap": ["tenang", "sabar", "syukur", "overthinking", "cemas", "marah", "kecewa", "percaya diri", "mindset", "sikap", "emosi", "refleksi", "mengeluh"],
    "relasi": ["teman", "keluarga", "orang tua", "pasangan", "tim", "klien", "ngobrol", "diskusi", "komunikasi", "bantu", "ketemu", "sosial"],
}

PRESTASI_BESAR_HINTS = [
    "lulus", "diterima", "menang", "rilis", "launch", "selesai besar", "milestone", "pecah rekor",
    "promosi", "deal", "closing", "tamat", "berhasil bangun", "lolos", "juara", "gaji pertama",
]
PRESTASI_MENENGAH_HINTS = [
    "selesai", "berhasil", "tuntas", "kelar", "kemajuan", "progres", "fitur", "konsisten",
    "latihan", "olahraga", "belajar", "submit", "kirim", "presentasi",
]


def _heuristic_extract_meta(isi: str, cur_level: str = "kecil", cur_dimensi: list[str] | None = None) -> tuple[str, str, list[str]]:
    """Ekstraksi deterministik (offline 0-biaya) untuk level prestasi, ringkasan, dan dimensi."""
    low = isi.lower()
    detected_dim = list(cur_dimensi or [])
    for d, kws in DIMENSI_HINTS.items():
        if d not in detected_dim and any(kw in low for kw in kws):
            detected_dim.append(d)
    if not detected_dim:
        detected_dim = ["mental-sikap"]

    level = cur_level if cur_level in ALLOWED_PRESTASI else "kecil"
    if any(k in low for k in PRESTASI_BESAR_HINTS):
        level = "besar"
    elif any(k in low for k in PRESTASI_MENENGAH_HINTS):
        level = "menengah" if level in ("kecil", "catatan") else level

    # Ambil kalimat pertama yang informatif sebagai ringkasan
    first_sent = re.split(r"(?<=[.!?])\s+|\n+", isi.strip())[0].strip()
    ringkas = (first_sent[:115] + "...") if len(first_sent) > 118 else first_sent
    return level, ringkas, detected_dim[:4]


def find_related_cards_for_journal(isi: str, suasana: str = "", dimensi: list[str] | None = None, limit: int = 5) -> list[dict]:
    """Cari 3-5 kartu paling relevan dari Pohon Pengetahuan (kartu/) untuk menanggapi jurnal."""
    all_cards = bangun_pohon.load_cards(ROOT / "kartu")
    active_cards = {cid: c for cid, c in all_cards.items() if c.get("status") == "aktif"}
    if not active_cards:
        return []

    extra_terms = []
    if suasana in ("lelah", "cemas"):
        extra_terms.append("tidur stres overthinking mental kesehatan")
    elif suasana in ("semangat", "syukur"):
        extra_terms.append("disiplin konsisten kebiasaan progres")
    for d in (dimensi or []):
        if d == "kesehatan":
            extra_terms.append("tidur olahraga dopamin otak kesehatan")
        elif d == "mental-sikap":
            extra_terms.append("mindset percaya diri mengeluh fokus disiplin")
        elif d == "skill-karier":
            extra_terms.append("karier ai coding proyek belajar")
        elif d == "disiplin":
            extra_terms.append("kebiasaan konsisten rutin produktivitas")
        elif d == "relasi":
            extra_terms.append("komunikasi asertif tegas relasi")

    query = f"{isi[:700]} {' '.join(extra_terms)}".strip()
    ranked = mesin_cerdas.query_relevant_cards(query, active_cards, limit=max(10, limit * 2))

    # Prioritaskan bidang pengembangan diri (mental/kesehatan/sikap/kesuksesan) jika skor setara
    priority_domains = {"motivasi-dan-mindset", "kesehatan", "kesuksesan", "relasi"}
    selected: list[dict] = []
    seen: set[str] = set()
    for c in ranked:
        cid = c["id"]
        if cid in seen:
            continue
        selected.append(c)
        seen.add(cid)
        if len(selected) >= limit:
            break

    # Jika kurang dari 3 kartu, tambahkan dari bidang mental/kesehatan aktif agar cermin refleksi tetap kaya
    if len(selected) < min(3, len(active_cards)):
        fallback_pool = [c for cid, c in sorted(active_cards.items()) if cid not in seen and c.get("bidang") in priority_domains]
        fallback_pool += [c for cid, c in sorted(active_cards.items()) if cid not in seen and c.get("bidang") not in priority_domains]
        for c in fallback_pool:
            selected.append(c)
            seen.add(c["id"])
            if len(selected) >= min(limit, 3):
                break

    out = []
    for c in selected[:limit]:
        out.append({
            "id": c["id"],
            "ide": c.get("ide", ""),
            "bidang": c.get("bidang", ""),
            "cabang": c.get("cabang", ""),
            "kepercayaan": c.get("kepercayaan", "sedang"),
            "penjelasan": (c.get("penjelasan") or "")[:280],
        })
    return out


def _extract_json_dict(raw: str) -> dict | None:
    if not raw:
        return None
    txt = raw.strip()
    if txt.startswith("```"):
        txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", txt, flags=re.S).strip()
    try:
        obj = json.loads(txt)
        return obj if isinstance(obj, dict) else None
    except Exception:
        m = re.search(r"\{[\s\S]*\}", txt)
        if m:
            try:
                obj = json.loads(m.group(0))
                return obj if isinstance(obj, dict) else None
            except Exception:
                return None
    return None


def analyze_and_reflect_journal(tgl: str, apply_auto_meta: bool = True) -> dict:
    """
    Fase 2: Analisis jurnal harian + hasilkan Tanggapan, Cermin Refleksi & Pernyataan Sikap
    berbasis 3-5 kartu nyata [K-XXXX] dari Pohon Pengetahuan via cascade 6 penyedia AI gratis
    (dengan fallback deterministik lokal jika offline/limit).
    """
    entry = get_jurnal(tgl)
    if not entry:
        raise FileNotFoundError(f"Jurnal untuk tanggal {tgl} tidak ditemukan. Simpan catatan terlebih dahulu.")

    isi = entry["isi"]
    related = find_related_cards_for_journal(isi, suasana=entry["suasana"], dimensi=entry["dimensi"], limit=5)
    valid_card_ids = {c["id"] for c in related}

    h_level, h_ringkas, h_dim = _heuristic_extract_meta(isi, entry["prestasi_level"], entry["dimensi"])

    mode = "lokal-deterministik"
    model_used = "fallback-lokal"
    ref_data: dict | None = None

    if mesin_cerdas.has_any_free_llm_key() and related:
        ctx_lines = []
        for c in related:
            ctx_lines.append(
                f"- [{c['id']}] ({c['cabang']} | kepercayaan: {c['kepercayaan']}) "
                f"Ide: {c['ide']} | Ringkas: {c['penjelasan']}"
            )
        system_prompt = (
            "Anda adalah pendamping refleksi pribadi untuk sistem Pohon Pengetahuan milik satu pengguna. "
            "Tugas Anda: membaca catatan jurnal penghujung hari pengguna, lalu memberikan cermin refleksi dan "
            "pernyataan sikap yang BERPIJAK pada kartu wawasan milik pengguna sendiri (bukan nasihat klise generik).\n"
            "Aturan WAJIB:\n"
            "1. Gunakan Bahasa Indonesia yang hangat, jujur, ringkas, dan tidak menggurui.\n"
            "2. WAJIB kutip ID kartu nyata dalam format [K-XXXX] hanya dari daftar Kartu Konteks yang diberikan. DILARANG mengarang ID kartu.\n"
            "3. Jika ada tambahan saran di luar kartu konteks, tandai dengan [inferensi AI].\n"
            "4. Jika menyinggung kesehatan/keuangan, tetap beri pengingat bahwa catatan ini bukan pengganti dokter/penasihat keuangan.\n"
            "5. Balas HANYA dengan objek JSON valid sesuai skema."
        )
        user_prompt = (
            f"Tanggal: {entry['tanggal']} | Suasana: {entry['suasana']} | Energi: {entry['energi']}/5\n"
            f"Catatan Jurnal Pengguna:\n{isi[:3500]}\n\n"
            f"Kartu Konteks dari Pohon Pengetahuan Pengguna:\n" + "\n".join(ctx_lines) + "\n\n"
            "Keluarkan JSON persis dengan kunci berikut:\n"
            "{\n"
            '  "prestasi_level": "besar | menengah | kecil | catatan",\n'
            '  "prestasi_ringkas": "1 kalimat ringkas <= 110 karakter tentang pencapaian/inti hari ini",\n'
            '  "dimensi": ["pilih 1-3 dari: disiplin, kesehatan, skill-karier, mental-sikap, relasi"],\n'
            '  "cermin_refleksi": "2-4 kalimat cermin refleksi spesifik terhadap hari ini sambil mengutip [K-XXXX]",\n'
            '  "pernyataan_sikap": "1-2 kalimat prinsip/pernyataan sikap yang bisa dipegang dan disimpan ke Kompas Sikap, sertakan [K-XXXX]",\n'
            '  "langkah_besok": "1 langkah kecil konkret (<=15 menit) untuk besok, sertakan [K-XXXX]",\n'
            '  "kartu_dikutip": ["K-XXXX"]\n'
            "}"
        )
        raw, mdl, _err = mesin_cerdas.call_free_llm_cascade(
            system_prompt, user_prompt, json_mode=True, max_tokens=900, temperature=0.25
        )
        parsed = _extract_json_dict(raw or "")
        if parsed and parsed.get("cermin_refleksi"):
            ref_data = parsed
            mode = "ai-cascade"
            model_used = mdl or "free-llm"

    if ref_data:
        ai_lvl = str(ref_data.get("prestasi_level", "")).strip().lower()
        final_level = ai_lvl if ai_lvl in ALLOWED_PRESTASI else h_level
        ai_ringkas = str(ref_data.get("prestasi_ringkas", "")).strip()[:200]
        final_ringkas = ai_ringkas or h_ringkas
        raw_dims = ref_data.get("dimensi") if isinstance(ref_data.get("dimensi"), list) else []
        ai_dims = [str(d).strip().lower() for d in raw_dims if str(d).strip().lower() in ALLOWED_DIMENSI]
        final_dims = list(dict.fromkeys((entry["dimensi"] or []) + (ai_dims or h_dim)))[:5]

        cermin = str(ref_data.get("cermin_refleksi", "")).strip()
        sikap = str(ref_data.get("pernyataan_sikap", "")).strip()
        langkah = str(ref_data.get("langkah_besok", "")).strip()

        raw_cited = ref_data.get("kartu_dikutip") if isinstance(ref_data.get("kartu_dikutip"), list) else []
        cited_in_text = re.findall(r"K-\d{4,6}", f"{cermin} {sikap} {langkah}")
        kartu_terkait = [
            cid for cid in dict.fromkeys([str(x).strip().upper() for x in raw_cited] + cited_in_text)
            if cid in valid_card_ids
        ]
        if not kartu_terkait:
            kartu_terkait = [c["id"] for c in related[:3]]
    else:
        final_level = h_level
        final_ringkas = h_ringkas
        final_dims = list(dict.fromkeys((entry["dimensi"] or []) + h_dim))[:5]
        kartu_terkait = [c["id"] for c in related[:3]]
        if related:
            c1 = related[0]
            c2 = related[1] if len(related) > 1 else c1
            cermin = (
                f"Catatan hari ini menyoroti tema {', '.join(DIMENSI_LABELS.get(d, d) for d in final_dims[:2])}. "
                f"Dari otak ilmu Anda sendiri, [{c1['id']}] mengingatkan bahwa {c1['ide']}"
                + (f" Sementara [{c2['id']}] menambahkan sudut pandang: {c2['ide']}" if c2["id"] != c1["id"] else "")
            )
            sikap = f"Saya memilih memegang prinsip dari [{c1['id']}]: {c1['ide']}"
            langkah = f"Luangkan 10-15 menit besok untuk meninjau ulang dan mempraktekkan satu poin inti dari [{c1['id']}]."
        else:
            cermin = "[inferensi AI] Belum ada kartu aktif di Pohon Pengetahuan untuk dirujuk, namun konsistensi mencatat hari ini sudah menjadi langkah reflektif yang baik."
            sikap = "[inferensi AI] Saya merawat kejujuran pada progres harian tanpa menunggu kondisi sempurna."
            langkah = "[inferensi AI] Tambahkan 1-2 kartu ilmu relevan di Pohon Pengetahuan agar cermin refleksi berikutnya bersitasi kartu Anda."

    # Format blok Markdown untuk disimpan di file jurnal harian
    refleksi_md = "\n".join([
        f"**Cermin Refleksi:** {cermin}",
        "",
        f"**Pernyataan Sikap:** {sikap}",
        "",
        f"**Langkah Kecil Besok:** {langkah}",
        "",
        f"_Rujukan Pohon Pengetahuan: {', '.join(f'[[{cid}]]' for cid in kartu_terkait)} | Mesin: {model_used}_",
    ])

    # Simpan pembaruan kembali ke file Markdown jurnal
    save_payload = {
        "tanggal": entry["tanggal"],
        "suasana": entry["suasana"],
        "energi": entry["energi"],
        "prestasi_level": final_level if apply_auto_meta else entry["prestasi_level"],
        "prestasi_ringkas": (entry["prestasi_ringkas"] or final_ringkas) if apply_auto_meta else entry["prestasi_ringkas"],
        "dimensi": final_dims if apply_auto_meta else entry["dimensi"],
        "kartu_terkait": kartu_terkait,
        "isi": isi,
        "refleksi_ai": refleksi_md,
    }
    saved_res = save_jurnal(save_payload)

    return {
        "ok": True,
        "mode": mode,
        "model": model_used,
        "item": saved_res["item"],
        "refleksi": {
            "cermin_refleksi": cermin,
            "pernyataan_sikap": sikap,
            "langkah_besok": langkah,
            "prestasi_level_saran": final_level,
            "prestasi_ringkas_saran": final_ringkas,
            "dimensi_saran": final_dims,
            "kartu_terkait": kartu_terkait,
        },
        "kartu_rujukan": related,
    }


def list_kompas_sikap() -> list[dict]:
    """Baca daftar Pernyataan Sikap pribadi dari jurnal/_kompas_sikap.md."""
    if not KOMPAS_FILE.is_file():
        return []
    text = KOMPAS_FILE.read_text(encoding="utf-8").replace("\r\n", "\n")
    items: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        # Format: - [YYYY-MM-DD] (dimensi: a, b | kartu: K-0001) Pernyataan sikap...
        m = re.match(r"^- \[(\d{4}-\d{2}-\d{2})\]\s*(?:\(([^)]*)\)\s*)?(.+)$", line)
        if not m:
            continue
        tgl, meta, sikap = m.group(1), m.group(2) or "", m.group(3).strip()
        dims = []
        kartus = re.findall(r"K-\d{4,6}", f"{meta} {sikap}")
        mdim = re.search(r"dimensi:\s*([^|]+)", meta)
        if mdim:
            dims = [x.strip() for x in mdim.group(1).split(",") if x.strip() in ALLOWED_DIMENSI]
        items.append({
            "tanggal": tgl,
            "dimensi": dims,
            "kartu": list(dict.fromkeys(kartus)),
            "sikap": sikap,
        })
    items.reverse()
    return items


def save_kompas_sikap(sikap: str, tanggal: str = "", kartu: list[str] | None = None, dimensi: list[str] | None = None) -> dict:
    """Tambahkan 1 pernyataan sikap baru ke jurnal/_kompas_sikap.md (khusus lokal)."""
    clean_sikap = " ".join(str(sikap or "").split()).strip()
    if len(clean_sikap) < 6:
        raise ValueError("Pernyataan sikap terlalu pendek (minimal 6 karakter).")
    tgl = (tanggal or date.today().isoformat()).strip()
    validate_date_str(tgl)

    clean_dims = [d for d in dict.fromkeys(str(x).strip().lower() for x in (dimensi or [])) if d in ALLOWED_DIMENSI]
    clean_kartu = [k for k in dict.fromkeys(str(x).strip().upper() for x in (kartu or [])) if re.match(r"^K-\d{4,6}$", k)]

    JURNAL_DIR.mkdir(parents=True, exist_ok=True)
    if not KOMPAS_FILE.is_file():
        KOMPAS_FILE.write_text(
            "# Kompas Sikap Pribadi (Khusus Lokal)\n\n"
            "Kumpulan prinsip dan pernyataan sikap yang disaring dari jurnal harian & Pohon Pengetahuan.\n\n",
            encoding="utf-8",
        )

    existing = list_kompas_sikap()
    if any(x["sikap"].lower() == clean_sikap.lower() for x in existing):
        return {"ok": True, "duplikat": True, "pesan": "Pernyataan sikap ini sudah ada di Kompas Sikap.", "items": existing}

    meta_parts = []
    if clean_dims:
        meta_parts.append("dimensi: " + ", ".join(clean_dims))
    if clean_kartu:
        meta_parts.append("kartu: " + ", ".join(clean_kartu))
    meta_str = f" ({' | '.join(meta_parts)})" if meta_parts else ""

    entry_line = f"- [{tgl}]{meta_str} {clean_sikap}\n"
    with KOMPAS_FILE.open("a", encoding="utf-8") as f:
        f.write(entry_line)

    today = date.today().isoformat()
    with (ROOT / "log.md").open("a", encoding="utf-8") as lf:
        lf.write(f"\n[{today}] KOMPAS-SIKAP | dari jurnal {tgl} | kartu: [{', '.join(clean_kartu)}]")

    return {"ok": True, "duplikat": False, "pesan": "Disimpan ke Kompas Sikap (jurnal/_kompas_sikap.md).", "items": list_kompas_sikap()}


# ======================== FASE 3: TIMELINE BIOGRAFI & PERTUMBUHAN KARAKTER ========================

LEVEL_WEIGHTS = {"besar": 3.0, "menengah": 2.0, "kecil": 1.0, "catatan": 0.5}


def _compute_streaks(sorted_dates_asc: list[str]) -> tuple[int, int]:
    """Hitung rentetan hari berturut-turut (saat ini & terpanjang) dari daftar tanggal YYYY-MM-DD."""
    if not sorted_dates_asc:
        return 0, 0
    parsed = []
    for d in sorted_dates_asc:
        try:
            y, m, dd = d.split("-")
            parsed.append(date(int(y), int(m), int(dd)))
        except Exception:
            continue
    if not parsed:
        return 0, 0
    uniq = sorted(set(parsed))
    longest = 1
    run = 1
    for i in range(1, len(uniq)):
        if (uniq[i] - uniq[i - 1]).days == 1:
            run += 1
            if run > longest:
                longest = run
        else:
            run = 1
    # Current streak: hitung mundur dari entri terakhir jika <= 1 hari dari hari ini
    today = date.today()
    current = 0
    if (today - uniq[-1]).days <= 1:
        current = 1
        for i in range(len(uniq) - 1, 0, -1):
            if (uniq[i] - uniq[i - 1]).days == 1:
                current += 1
            else:
                break
    return current, longest


def get_biografi_dan_pertumbuhan(tahun: str = "", level: str = "") -> dict:
    """
    Fase 3: Agregasi Timeline Biografi (kronologis lintas tahun/bulan, filter level prestasi)
    serta Evaluasi Pertumbuhan 5 Dimensi Karakter & Tren Bulanan berbasis bukti catatan harian.
    """
    JURNAL_DIR.mkdir(parents=True, exist_ok=True)
    all_entries: list[dict] = []
    for fp in JURNAL_DIR.rglob("*.md"):
        if fp.name.startswith("_") or not DATE_RE.match(fp.stem):
            continue
        try:
            all_entries.append(parse_journal_file(fp))
        except Exception:
            continue

    all_entries.sort(key=lambda x: x["tanggal"])  # kronologis menaik untuk hitung tren
    tahun_tersedia = sorted({e["tahun"] for e in all_entries if e["tahun"]}, reverse=True)

    # Filter untuk kalkulasi pertumbuhan (berdasarkan tahun jika dipilih)
    scoped = [e for e in all_entries if (not tahun or e["tahun"] == tahun)]

    # Filter tambahan level untuk tampilan Timeline Biografi
    tl_entries = [e for e in scoped if (not level or e["prestasi_level"] == level)]
    tl_entries_desc = list(reversed(tl_entries))

    # Kelompokkan Timeline Biografi: Tahun -> Bulan -> Milestones
    grouped_map: dict[str, dict[str, list[dict]]] = {}
    for e in tl_entries_desc:
        y = e["tahun"] or "Lainnya"
        m = e["bulan"] or "00"
        grouped_map.setdefault(y, {}).setdefault(m, []).append({
            "tanggal": e["tanggal"],
            "tahun": y,
            "bulan": m,
            "suasana": e["suasana"],
            "energi": e["energi"],
            "prestasi_level": e["prestasi_level"],
            "prestasi_ringkas": e["prestasi_ringkas"],
            "dimensi": e["dimensi"],
            "kartu_terkait": e["kartu_terkait"],
            "cuplikan": e["cuplikan"],
            "jumlah_kata": e["jumlah_kata"],
        })

    timeline_groups = []
    for y in sorted(grouped_map.keys(), reverse=True):
        months_list = []
        for m in sorted(grouped_map[y].keys(), reverse=True):
            months_list.append({
                "bulan": m,
                "items": grouped_map[y][m],
            })
        timeline_groups.append({
            "tahun": y,
            "total": sum(len(mo["items"]) for mo in months_list),
            "bulan_list": months_list,
        })

    # Evaluasi 5 Dimensi Karakter & Kemampuan berbasis bukti nyata
    dim_raw: dict[str, dict] = {
        d: {"kode": d, "nama": DIMENSI_LABELS[d], "frekuensi": 0, "bobot": 0.0, "bukti": []}
        for d in ALLOWED_DIMENSI
    }
    for e in scoped:
        w = LEVEL_WEIGHTS.get(e["prestasi_level"], 1.0)
        for d in e["dimensi"]:
            if d in dim_raw:
                dim_raw[d]["frekuensi"] += 1
                dim_raw[d]["bobot"] += w
                dim_raw[d]["bukti"].append({
                    "tanggal": e["tanggal"],
                    "level": e["prestasi_level"],
                    "ringkas": e["prestasi_ringkas"] or e["cuplikan"][:95],
                })

    max_bobot = max([v["bobot"] for v in dim_raw.values()] + [1.0])
    dimensi_stats = []
    for d in ALLOWED_DIMENSI:
        info = dim_raw[d]
        skor = round((info["bobot"] / max_bobot) * 100) if info["bobot"] > 0 else 0
        dimensi_stats.append({
            "kode": d,
            "nama": info["nama"],
            "frekuensi": info["frekuensi"],
            "bobot": round(info["bobot"], 1),
            "skor": skor,
            "bukti_terbaru": list(reversed(info["bukti"]))[:3],
        })

    # Tren Bulanan (maks 12 bulan terakhir dalam cakupan)
    monthly_map: dict[str, dict] = {}
    for e in scoped:
        mk = f"{e['tahun']}-{e['bulan']}"
        if mk not in monthly_map:
            monthly_map[mk] = {
                "bulan_key": mk,
                "jumlah_hari": 0,
                "total_energi": 0,
                "total_kata": 0,
                "besar": 0,
                "menengah": 0,
                "kecil": 0,
                "catatan": 0,
                "dimensi": {d: 0 for d in ALLOWED_DIMENSI},
            }
        rec = monthly_map[mk]
        rec["jumlah_hari"] += 1
        rec["total_energi"] += e["energi"]
        rec["total_kata"] += e["jumlah_kata"]
        lvl = e["prestasi_level"]
        if lvl in ("besar", "menengah", "kecil", "catatan"):
            rec[lvl] += 1
        for d in e["dimensi"]:
            if d in rec["dimensi"]:
                rec["dimensi"][d] += 1

    tren_bulanan = []
    for mk in sorted(monthly_map.keys())[-12:]:
        rec = monthly_map[mk]
        rec["rata_energi"] = round(rec["total_energi"] / max(1, rec["jumlah_hari"]), 2)
        tren_bulanan.append(rec)

    suasana_counts: dict[str, int] = {}
    for e in scoped:
        suasana_counts[e["suasana"]] = suasana_counts.get(e["suasana"], 0) + 1

    level_counts = {lvl: sum(1 for e in scoped if e["prestasi_level"] == lvl) for lvl in ("besar", "menengah", "kecil", "catatan")}
    rata_energi = round(sum(e["energi"] for e in scoped) / len(scoped), 2) if scoped else 0.0
    streak_now, streak_max = _compute_streaks([e["tanggal"] for e in all_entries])

    return {
        "ok": True,
        "tahun_tersedia": tahun_tersedia,
        "total_hari": len(scoped),
        "total_timeline": len(tl_entries_desc),
        "rata_energi": rata_energi,
        "streak_saat_ini": streak_now,
        "streak_terpanjang": streak_max,
        "hitung_level": level_counts,
        "suasana_stats": suasana_counts,
        "timeline": timeline_groups,
        "dimensi_stats": dimensi_stats,
        "tren_bulanan": tren_bulanan,
    }


