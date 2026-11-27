#!/usr/bin/env python3
"""
Mesin Bedah Ebook Tebal (hingga 700+ halaman) untuk Pohon Pengetahuan.
Memecah PDF besar per-bab (dari daftar isi PDF / pola Bab-Chapter / segmen halaman),
meringkas tiap bab secara bertahap lewat cascade AI gratis (Bahasa Indonesia editorial),
lalu menyimpan 1 Sumber (S-XXXX) + seri Kartu berantai (lanjutan-dari <-> prasyarat-untuk).

Pemakaian CLI:
  python scripts/bedah_ebook.py "C:/Users/ASUS/Downloads/buku.pdf" --bidang kesuksesan --max-kartu 15
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import math
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import bangun_pohon  # noqa: E402
import mesin_cerdas  # noqa: E402

MAX_PAGES = 750
MAX_CARDS_CAP = 20


def _clean_page_text(txt: str) -> str:
    txt = (txt or "").replace("\r\n", "\n").replace("\r", "\n")
    txt = re.sub(r"[ \t]{2,}", " ", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt.strip()


def _sample_chapter_text(text: str, limit: int = 5200) -> str:
    """Ambil sampel merata (awal + tengah + akhir bab) agar inti bab panjang tetap tertangkap."""
    t = text.strip()
    if len(t) <= limit:
        return t
    part = limit // 3
    mid = len(t) // 2
    return (
        t[:part].rstrip()
        + "\n\n[... bagian tengah bab ...]\n\n"
        + t[mid - part // 2 : mid + part // 2].strip()
        + "\n\n[... bagian akhir bab ...]\n\n"
        + t[-part:].lstrip()
    )


def _extract_outline_chapters(reader) -> list[tuple[str, int]]:
    """Coba ambil daftar bab tingkat-atas dari metadata Outline/TOC PDF."""
    chapters: list[tuple[str, int]] = []
    try:
        outline = reader.outline
        if not outline:
            return []
        for item in outline:
            if isinstance(item, list):
                continue
            title = str(getattr(item, "title", "") or "").strip()
            try:
                pno = reader.get_destination_page_number(item)
            except Exception:
                continue
            if title and isinstance(pno, int) and pno >= 0:
                chapters.append((re.sub(r"\s+", " ", title)[:90], pno))
    except Exception:
        return []
    # Dedup halaman yang sama & urutkan
    seen_pages: set[int] = set()
    uniq: list[tuple[str, int]] = []
    for title, pno in sorted(chapters, key=lambda x: x[1]):
        if pno not in seen_pages:
            seen_pages.add(pno)
            uniq.append((title, pno))
    return uniq


def extract_ebook_segments(
    pdf_bytes: bytes,
    max_segments: int = 12,
    max_pages: int = MAX_PAGES,
) -> dict:
    """Baca PDF hingga 750 halaman dan pecah menjadi segmen bab/bagian yang rapi."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Paket 'pypdf' belum terpasang. Jalankan: pip install pypdf") from exc

    reader = PdfReader(io.BytesIO(pdf_bytes))
    total_pages = len(reader.pages)
    if total_pages == 0:
        raise ValueError("File PDF kosong (0 halaman).")
    read_pages = min(total_pages, max_pages)

    meta_title = ""
    meta_author = ""
    try:
        if reader.metadata:
            meta_title = str(reader.metadata.get("/Title") or "").strip()
            meta_author = str(reader.metadata.get("/Author") or "").strip()
    except Exception:
        pass

    # Ekstrak teks per halaman (hemat memori)
    page_texts: list[str] = []
    non_empty = 0
    for i in range(read_pages):
        try:
            pt = _clean_page_text(reader.pages[i].extract_text() or "")
        except Exception:
            pt = ""
        if len(pt) >= 20:
            non_empty += 1
        page_texts.append(pt)

    if non_empty == 0:
        raise ValueError(
            "PDF ini tampaknya berupa hasil scan gambar penuh tanpa lapisan teks. "
            "Untuk PDF scan, gunakan tombol 'Baca Teks dari Gambar' pada halaman penting atau jalankan OCR terlebih dahulu."
        )

    target_k = max(1, min(MAX_CARDS_CAP, int(max_segments or 12)))
    outline_chaps = _extract_outline_chapters(reader)
    segments: list[dict] = []

    if 2 <= len(outline_chaps) <= target_k + 4:
        # Gunakan daftar bab asli dari PDF
        for idx, (ctitle, start_p) in enumerate(outline_chaps):
            if start_p >= read_pages:
                break
            end_p = outline_chaps[idx + 1][1] if idx + 1 < len(outline_chaps) else read_pages
            end_p = min(read_pages, max(start_p + 1, end_p))
            body = "\n\n".join(t for t in page_texts[start_p:end_p] if t).strip()
            if len(body) >= 40:
                segments.append({
                    "judul_bab": ctitle,
                    "hal_mulai": start_p + 1,
                    "hal_akhir": end_p,
                    "teks": body,
                })

    if not segments:
        # Bagi rata menjadi target_k bagian (ideal untuk buku 50–700 halaman tanpa TOC)
        pages_per_seg = max(1, math.ceil(read_pages / target_k))
        for start_p in range(0, read_pages, pages_per_seg):
            end_p = min(read_pages, start_p + pages_per_seg)
            body = "\n\n".join(t for t in page_texts[start_p:end_p] if t).strip()
            if len(body) < 30:
                continue
            first_line = next((ln.strip() for ln in body.splitlines() if 4 <= len(ln.strip()) <= 85), "")
            seg_no = len(segments) + 1
            judul_bab = first_line if first_line else f"Bagian {seg_no} (Hal. {start_p + 1}-{end_p})"
            segments.append({
                "judul_bab": judul_bab[:90],
                "hal_mulai": start_p + 1,
                "hal_akhir": end_p,
                "teks": body,
            })

    # Gabungkan segmen berlebih jika melampaui target_k
    if len(segments) > target_k:
        merged: list[dict] = []
        group_sz = math.ceil(len(segments) / target_k)
        for i in range(0, len(segments), group_sz):
            grp = segments[i : i + group_sz]
            merged.append({
                "judul_bab": f"{grp[0]['judul_bab']} (s.d. Hal. {grp[-1]['hal_akhir']})"[:95],
                "hal_mulai": grp[0]["hal_mulai"],
                "hal_akhir": grp[-1]["hal_akhir"],
                "teks": "\n\n".join(g["teks"] for g in grp),
            })
        segments = merged

    return {
        "total_halaman": total_pages,
        "halaman_dibaca": read_pages,
        "halaman_berisi_teks": non_empty,
        "meta_judul": meta_title,
        "meta_penulis": meta_author,
        "segmen": segments,
    }


def process_ebook_to_tree(
    pdf_bytes: bytes,
    filename: str = "ebook.pdf",
    judul_override: str = "",
    penulis_override: str = "",
    bidang_pilihan: str = "",
    max_kartu: int = 12,
) -> dict:
    """Bedah ebook penuh -> 1 Sumber (S-XXXX) + seri Kartu berantai (K-XXXX..K-YYYY) + rebuild lokal."""
    import server_lokal as sl  # impor lokal agar tidak circular di top-level

    extracted = extract_ebook_segments(pdf_bytes, max_segments=max_kartu)
    segments = extracted["segmen"]
    if not segments:
        raise ValueError("Tidak ada segmen teks yang bisa diekstrak dari ebook ini.")

    today = date.today().isoformat()
    sid = sl.next_source_id()
    clean_fname = Path(filename or "ebook.pdf").stem.replace("_", " ").replace("-", " ").strip()
    judul_buku = (judul_override or extracted["meta_judul"] or clean_fname or "Ebook Pembelajaran").replace('"', "'").strip()[:120]
    penulis_buku = (penulis_override or extracted["meta_penulis"] or "tidak diketahui").replace('"', "'").strip()[:80]

    # Prediksi bidang utama jika tidak dipilih
    sample_all = " ".join(_sample_chapter_text(s["teks"], 600) for s in segments[:4])
    if bidang_pilihan:
        default_cabang = bidang_pilihan.strip().lower()
    else:
        default_cabang, _ = sl.guess_branch(f"{judul_buku} {sample_all}")
    default_bidang = default_cabang.split("/")[0]

    existing_cards, _, _ = mesin_cerdas.load_active()
    created_cids: list[str] = []
    created_entries: list[tuple[str, str, str, str, str]] = []
    used_branches: set[str] = set()
    saripati_lines: list[str] = []
    teks_asli_blocks: list[str] = [
        f"EBOOK: {judul_buku} | Penulis: {penulis_buku} | Total Halaman: {extracted['total_halaman']} (dibaca {extracted['halaman_dibaca']}, dipecah menjadi {len(segments)} bagian)\n"
    ]

    for idx, seg in enumerate(segments):
        cid = sl.next_card_id()
        hal_label = f"Hal. {seg['hal_mulai']}-{seg['hal_akhir']}"
        seg_sample = _sample_chapter_text(seg["teks"], limit=5000)
        teks_asli_blocks.append(f"### Bagian {idx + 1}: {seg['judul_bab']} ({hal_label})\n{seg_sample[:1800]}")

        neighbors = mesin_cerdas.query_relevant_cards(f"{judul_buku} {seg['judul_bab']} {seg_sample[:300]}", existing_cards, limit=6, use_vectors=False)
        ai_res = mesin_cerdas.extract_structured_cards_gemini(
            f"[Ebook: {judul_buku} | {seg['judul_bab']} ({hal_label})]\n\n{seg_sample}",
            platform="ebook-pdf",
            max_cards=1,
            neighbors=neighbors,
        )

        if ai_res and ai_res.get("kartu"):
            pt = ai_res["kartu"][0]
            ide_text = pt["ide"].replace('"', "'").strip()
            penjelasan = pt["penjelasan"]
            kutipan_2 = pt["kutipan"] or seg["judul_bab"]
            card_cabang = bidang_pilihan.strip().lower() if bidang_pilihan else (pt["cabang"] or default_cabang)
            card_bidang = card_cabang.split("/")[0]
            card_tahap = pt.get("tahap") or "semua-usia"
            card_jenis = pt.get("jenis") or "prinsip"
            card_trust = pt.get("kepercayaan") or "sedang"
            card_dasar = pt.get("dasar") or "riset"
            konsep_list = pt.get("konsep") or []
            kondisi_berlaku = pt.get("kondisi_berlaku") or "umum"
            tags_all = (pt.get("tag") or []) + ["ebook", f"bab-{idx + 1}"]
            model_ekstrak = ai_res.get("model") or "ai"
            versi_prompt = ai_res.get("versi_prompt") or mesin_cerdas.PROMPT_VERSION
            bias_warn = str(pt.get("peringatan_bias") or "").strip()
            bias_line = f"\n[peringatan-bias] {bias_warn}" if bias_warn else ""
            agent_note = f"[inferensi AI] Bedah Ebook Bagian {idx + 1}/{len(segments)} ({hal_label}, {model_ekstrak}, prompt {versi_prompt}).{bias_line}"
        else:
            # Cadangan offline 0-kuota jika API AI sedang istirahat
            pts = mesin_cerdas.extract_atomic_insights_math(seg_sample, max_cards=1)
            p0 = pts[0] if pts else {"ide": seg["judul_bab"], "penjelasan": seg_sample[:600], "kutipan": seg["judul_bab"]}
            ide_text = f"{seg['judul_bab']}: {p0['ide']}"[:220].replace('"', "'").strip()
            penjelasan = p0["penjelasan"]
            kutipan_2 = (p0.get("kutipan") or seg["judul_bab"])[:120]
            card_cabang = default_cabang
            card_bidang = default_bidang
            card_tahap = "semua-usia"
            card_jenis = "prinsip"
            card_trust = "sedang"
            card_dasar = "riset"
            konsep_list = []
            kondisi_berlaku = "umum"
            tags_all = ["ebook", "draf-ekstraktif", f"bab-{idx + 1}"]
            model_ekstrak = "ekstraktif-offline"
            versi_prompt = "math-v1"
            agent_note = f"[inferensi AI] Bedah Ebook offline Bagian {idx + 1}/{len(segments)} ({hal_label})."

        used_branches.add(card_cabang)
        rel_lines: list[str] = []
        if idx > 0:
            prev_cid = created_cids[idx - 1]
            rel_lines.append(f"  - {{tipe: lanjutan-dari, ke: {prev_cid}}}")
            sl.add_inverse_relation(prev_cid, "lanjutan-dari", cid)
        rel_yaml = ("\n" + "\n".join(rel_lines)) if rel_lines else "[]"
        konsep_yaml = "[" + ", ".join(dict.fromkeys(konsep_list)) + "]" if konsep_list else "[]"
        tags_yaml = "[" + ", ".join(dict.fromkeys(tags_all)) + "]"

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
            f"publik: ya\n"
            f"penerapan: belum-dicoba\n"
            f'penerapan-catatan: ""\n'
            f"terakhir-ditinjau: {today}\n"
            f"bintang: 0\n"
            f'catatan-khusus: ""\n'
            f"alat: []\n"
            f"tugas: {card_cabang.split('/')[-1]}\n"
            f"tahap-kerja: riset\n"
            f"---\n\n"
            f"## Ide\n({hal_label}) {penjelasan}\n\n"
            f"## Kutipan Pendukung\n> {kutipan_2}\n\n"
            f"## Catatan Agen\n{agent_note}\n"
        )
        (ROOT / "kartu" / f"{cid}.md").write_text(card_md, encoding="utf-8")
        created_cids.append(cid)
        ide_short = " ".join(ide_text.split()[:12])
        created_entries.append((cid, ide_short, card_cabang, card_tahap, card_trust))
        saripati_lines.append(f"- Bagian {idx + 1} ({hal_label}): {ide_text}")

    # Simpan 1 Sumber Ebook di sumber/S-XXXX.md
    bidang_list = sorted({b.split("/")[0] for b in used_branches}) or [default_bidang]
    src_md = (
        f"---\n"
        f"id: {sid}\n"
        f'judul: "{judul_buku}"\n'
        f"jenis: artikel\n"
        f"penulis: {penulis_buku}\n"
        f"platform: ebook-pdf\n"
        f"url: tidak ada\n"
        f"tanggal-terbit: tidak diketahui\n"
        f"tanggal-masuk: {today}\n"
        f"bidang: [{', '.join(bidang_list)}]\n"
        f"kartu: [{', '.join(created_cids)}]\n"
        f"---\n\n"
        f"## Saripati\nRingkasan ebook **{judul_buku}** ({extracted['total_halaman']} halaman, dipecah menjadi {len(created_cids)} bab/kartu berantai):\n"
        + "\n".join(saripati_lines[:20])
        + "\n\n## Teks Asli\n"
        + "\n\n".join(teks_asli_blocks)
        + "\n"
    )
    (ROOT / "sumber" / f"{sid}.md").write_text(src_md, encoding="utf-8")

    # Perbarui katalog sumber, cabang, log, & bangun ulang indeks
    kat_fp = ROOT / "sumber" / "_katalog.md"
    with kat_fp.open("a", encoding="utf-8") as f:
        f.write(f'\n{sid} | {today} | ebook-pdf | {penulis_buku} | "{judul_buku}" | bidang: {", ".join(bidang_list)} | {len(created_cids)} kartu')

    for br in sorted(used_branches):
        sl.ensure_branch_and_append(br, [e for e in created_entries if e[2] == br], today)

    log_fp = ROOT / "log.md"
    with log_fp.open("a", encoding="utf-8") as f:
        f.write(
            f"\n[{today}] BEDAH EBOOK {sid} -> {created_cids[0]}..{created_cids[-1]} "
            f"({extracted['total_halaman']} hal, {len(created_cids)} kartu) | judul: \"{judul_buku[:60]}\""
        )

    sl.rebuild_local_artifacts()
    return {
        "ok": True,
        "id": sid,
        "judul": judul_buku,
        "total_halaman": extracted["total_halaman"],
        "halaman_dibaca": extracted["halaman_dibaca"],
        "jumlah_kartu": len(created_cids),
        "kartu_ids": created_cids,
        "cabang": sorted(used_branches),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Bedah Ebook PDF hingga 700+ halaman menjadi seri kartu Pohon Pengetahuan.")
    parser.add_argument("pdf_path", help="Path file PDF ebook di komputer Anda")
    parser.add_argument("--judul", default="", help="Judul buku (opsional)")
    parser.add_argument("--penulis", default="", help="Penulis buku (opsional)")
    parser.add_argument("--bidang", default="", help="Cabang tujuan (opsional, mis. kesuksesan atau ai)")
    parser.add_argument("--max-kartu", type=int, default=12, help="Jumlah maksimal kartu/bab (default 12, maks 20)")
    args = parser.parse_args()

    fp = Path(args.pdf_path).expanduser()
    if not fp.is_file():
        print(f"ERROR: File tidak ditemukan: {fp}", file=sys.stderr)
        return 1
    out = process_ebook_to_tree(
        pdf_bytes=fp.read_bytes(),
        filename=fp.name,
        judul_override=args.judul,
        penulis_override=args.penulis,
        bidang_pilihan=args.bidang,
        max_kartu=args.max_kartu,
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
