#!/usr/bin/env python3
"""
Mesin Pembangun, Indeks FTS5 (BM25), Filter, Deteksi Tetangga, dan Audit Pohon Pengetahuan.
Zero external dependencies (Python 3 standard library + sqlite3 FTS5).

Penggunaan:
  python scripts/bangun_pohon.py --mode lokal
  python scripts/bangun_pohon.py --mode publik
  python scripts/bangun_pohon.py --cek
  python scripts/bangun_pohon.py --indeks
  python scripts/bangun_pohon.py --cari "reupload ocr" --limit 20
  python scripts/bangun_pohon.py --tetangga "larangan reupload konten di X"
  python scripts/bangun_pohon.py --filter --bidang keuangan --tampilan belum-diverifikasi
  python scripts/bangun_pohon.py --pindah-cabang K-0001 K-0002 --ke keuangan/monetisasi-konten
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sqlite3
import sys
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / ".indeks.db"
TIMELINE_STAGES = ["sebelum-20", "20-25", "25-30", "30-40", "40-50", "50+"]
INVERSE_REL = {
    "lanjutan-dari": "prasyarat-untuk",
    "prasyarat-untuk": "lanjutan-dari",
    "memperkuat": "memperkuat",
    "bertentangan-dengan": "bertentangan-dengan",
    "terkait": "terkait",
    "contoh-dari": "terkait",
    "menggantikan": "terkait",
}


def strip_quotes(val: str) -> str:
    val = val.strip()
    if len(val) >= 2 and ((val[0] == '"' and val[-1] == '"') or (val[0] == "'" and val[-1] == "'")):
        return val[1:-1]
    return val


def parse_inline_list(val: str) -> list[str]:
    val = val.strip()
    if not (val.startswith("[") and val.endswith("]")):
        return [strip_quotes(val)] if val else []
    inner = val[1:-1].strip()
    if not inner:
        return []
    return [strip_quotes(x) for x in inner.split(",") if x.strip()]


def parse_frontmatter(text: str) -> tuple[dict, str]:
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        if text.endswith("\n---"):
            end = len(text) - 4
        else:
            return {}, text
    raw_fm = text[4:end]
    body = text[end + 5:] if end + 5 <= len(text) else ""
    data: dict = {}
    current_key = None

    for line in raw_fm.split("\n"):
        if not line.strip() or line.strip().startswith("#"):
            continue
        if re.match(r"^\s*-\s+", line) and current_key:
            item_str = re.sub(r"^\s*-\s+", "", line).strip()
            if not isinstance(data.get(current_key), list):
                data[current_key] = []
            if item_str.startswith("{") and item_str.endswith("}"):
                obj = {}
                for part in item_str[1:-1].split(","):
                    if ":" in part:
                        k, v = part.split(":", 1)
                        obj[k.strip()] = strip_quotes(v.strip())
                data[current_key].append(obj)
            else:
                data[current_key].append(strip_quotes(item_str))
            continue

        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            v_clean = v.strip()
            if "#" in v_clean and k not in ("ide", "judul", "penulis", "url", "penerapan-catatan", "catatan-khusus") and not (v_clean.startswith('"') or v_clean.startswith("'")):
                v_clean = v_clean.split("#", 1)[0].strip()
            current_key = k
            if v_clean == "":
                data[k] = [] if k in ("relasi", "tag", "alat", "bidang", "kartu", "sumber") else ""
            elif v_clean.startswith("[") and v_clean.endswith("]") and k in ("relasi", "tag", "alat", "bidang", "kartu", "sumber"):
                data[k] = parse_inline_list(v_clean)
            else:
                data[k] = strip_quotes(v_clean)

    return data, body.strip()


def parse_sections(body: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current = "_intro"
    buf: list[str] = []
    for line in body.split("\n"):
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            sections[current] = "\n".join(buf).strip()
            current = m.group(1).strip()
            buf = []
        else:
            buf.append(line)
    sections[current] = "\n".join(buf).strip()
    return sections


def extract_wikilinks(val) -> list[str]:
    raw = " ".join(str(x) for x in val) if isinstance(val, list) else str(val or "")
    links = re.findall(r"\[\[([^\]]+)\]\]", raw)
    return links if links else re.findall(r"\b[SK]-\d+\b", raw)


def parse_indeks_order(indeks_path: Path) -> list[dict]:
    order = []
    if not indeks_path.exists():
        return order
    for line in indeks_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("|") and "cabang/" in line:
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) >= 4:
                m = re.search(r"cabang/([^/`]+)/_cabang\.md", parts[3])
                if m:
                    order.append({
                        "slug": m.group(1),
                        "nama": parts[0],
                        "ringkasan": parts[2],
                        "jumlah_tercatat": int(parts[1]) if parts[1].isdigit() else 0,
                    })
    return order


def _as_str(val, default: str = "") -> str:
    if isinstance(val, list):
        return ", ".join(str(x) for x in val)
    return str(val if val is not None else default)


def load_sources(sumber_dir: Path) -> dict[str, dict]:
    sources: dict[str, dict] = {}
    if not sumber_dir.exists():
        return sources
    for fp in sorted(sumber_dir.glob("S-*.md")):
        raw = fp.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(raw)
        secs = parse_sections(body)
        sid = _as_str(fm.get("id") or fp.stem)
        sources[sid] = {
            "id": sid,
            "file": str(fp.relative_to(ROOT)).replace("\\", "/"),
            "judul": _as_str(fm.get("judul"), sid),
            "jenis": _as_str(fm.get("jenis"), "catatan"),
            "penulis": _as_str(fm.get("penulis"), "tidak diketahui"),
            "platform": _as_str(fm.get("platform"), "lainnya"),
            "url": _as_str(fm.get("url"), "tidak ada"),
            "tanggal_terbit": _as_str(fm.get("tanggal-terbit"), "tidak diketahui"),
            "tanggal_masuk": _as_str(fm.get("tanggal-masuk"), ""),
            "bidang": fm.get("bidang", []) if isinstance(fm.get("bidang"), list) else parse_inline_list(str(fm.get("bidang", ""))),
            "kartu": fm.get("kartu", []) if isinstance(fm.get("kartu"), list) else parse_inline_list(str(fm.get("kartu", ""))),
            "saripati": secs.get("Saripati", ""),
            "teks_asli": secs.get("Teks Asli", ""),
        }
    return sources


def load_cards(kartu_dir: Path) -> dict[str, dict]:
    cards: dict[str, dict] = {}
    if not kartu_dir.exists():
        return cards
    for fp in sorted(kartu_dir.glob("K-*.md")):
        raw = fp.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(raw)
        secs = parse_sections(body)
        cid = _as_str(fm.get("id") or fp.stem)
        relasi = fm.get("relasi", [])
        if not isinstance(relasi, list):
            relasi = []
        clean_rel = [{"tipe": r["tipe"], "ke": r["ke"]} for r in relasi if isinstance(r, dict) and r.get("tipe") and r.get("ke")]
        quote_raw = secs.get("Kutipan Pendukung", "")
        kutipan = " ".join(re.sub(r"^>\s?", "", ln) for ln in quote_raw.splitlines() if ln.strip()).strip()

        cards[cid] = {
            "id": cid,
            "file": str(fp.relative_to(ROOT)).replace("\\", "/"),
            "ide": _as_str(fm.get("ide"), ""),
            "bidang": _as_str(fm.get("bidang"), "lainnya"),
            "cabang": _as_str(fm.get("cabang"), _as_str(fm.get("bidang"), "lainnya")),
            "tahap": _as_str(fm.get("tahap"), "semua-usia"),
            "jenis": _as_str(fm.get("jenis"), "opini"),
            "kepercayaan": _as_str(fm.get("kepercayaan"), "belum-diverifikasi"),
            "dasar": _as_str(fm.get("dasar"), "tidak-jelas"),
            "tag": fm.get("tag", []) if isinstance(fm.get("tag"), list) else parse_inline_list(str(fm.get("tag", ""))),
            "konsep": fm.get("konsep", []) if isinstance(fm.get("konsep"), list) else parse_inline_list(str(fm.get("konsep", ""))),
            "sumber": extract_wikilinks(fm.get("sumber", "")),
            "relasi": clean_rel,
            "dibuat": _as_str(fm.get("dibuat"), ""),
            "status": _as_str(fm.get("status"), "aktif"),
            "publik": _as_str(fm.get("publik"), "tidak").lower() == "ya",
            "penerapan": _as_str(fm.get("penerapan"), "belum-dicoba"),
            "penerapan_catatan": _as_str(fm.get("penerapan-catatan"), ""),
            "terakhir_ditinjau": _as_str(fm.get("terakhir-ditinjau"), _as_str(fm.get("dibuat"), "")),
            "bintang": int(fm.get("bintang", 0) or 0) if _as_str(fm.get("bintang", "0")).strip().isdigit() else 0,
            "catatan_khusus": _as_str(fm.get("catatan-khusus"), ""),
            "alat": fm.get("alat", []) if isinstance(fm.get("alat"), list) else parse_inline_list(str(fm.get("alat", ""))),
            "tugas": fm.get("tugas", ""),
            "tahap_kerja": fm.get("tahap-kerja", ""),
            "penjelasan": secs.get("Ide", ""),
            "kutipan": kutipan,
            "catatan_agen": secs.get("Catatan Agen", ""),
        }
    return cards


def load_branches(cabang_dir: Path) -> dict[str, dict]:
    branches: dict[str, dict] = {}
    if not cabang_dir.exists():
        return branches
    for fp in sorted(cabang_dir.rglob("_cabang.md")):
        raw = fp.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(raw)
        secs = parse_sections(body)
        rel_dir = str(fp.parent.relative_to(cabang_dir)).replace("\\", "/")
        slug = fm.get("cabang") or rel_dir

        def bullet_lines(sec_name: str) -> list[str]:
            txt = next((v for k, v in secs.items() if k.lower().startswith(sec_name.lower())), "")
            items = []
            for ln in txt.splitlines():
                ln = ln.strip()
                if ln.startswith("- "):
                    val = ln[2:].strip()
                    if val and not val.startswith("("):
                        items.append(val)
            return items

        ringkasan = next((v for k, v in secs.items() if k.lower().startswith("ringkasan")), "")
        branches[slug] = {
            "slug": slug,
            "nama": fm.get("nama", slug.split("/")[-1].replace("-", " ").title()),
            "induk": fm.get("induk", ""),
            "file": str(fp.relative_to(ROOT)).replace("\\", "/"),
            "jumlah_kartu_tercatat": int(fm.get("jumlah-kartu", 0)) if str(fm.get("jumlah-kartu", "0")).isdigit() else 0,
            "jumlah_sumber_tercatat": int(fm.get("jumlah-sumber", 0)) if str(fm.get("jumlah-sumber", "0")).isdigit() else 0,
            "diperbarui": fm.get("diperbarui", ""),
            "catatan_sudut_pandang": fm.get("catatan-sudut-pandang", ""),
            "ringkasan": ringkasan,
            "poin_kunci": bullet_lines("Poin Kunci"),
            "pertentangan": bullet_lines("Pertentangan"),
            "lanjutan_timeline": bullet_lines("Lanjutan Timeline"),
            "sub_cabang": bullet_lines("Sub-cabang"),
        }
    return branches


# ======================== SQLITE FTS5 (BM25) INDEX ========================

def build_fts_index(cards: dict[str, dict], sources: dict[str, dict]) -> int:
    """Bangun ulang .indeks.db (SQLite FTS5) dari Markdown. Turunan murni (Bagian 21.1)."""
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.executescript("""
            CREATE TABLE kartu_meta (
                id TEXT PRIMARY KEY,
                ide TEXT,
                bidang TEXT,
                cabang TEXT,
                tahap TEXT,
                jenis TEXT,
                kepercayaan TEXT,
                dasar TEXT,
                penerapan TEXT,
                status TEXT,
                penulis TEXT,
                tag TEXT,
                alat TEXT,
                tugas TEXT,
                tahap_kerja TEXT,
                sumber TEXT,
                has_conflict INTEGER,
                is_orphan INTEGER,
                dibuat TEXT,
                terakhir_ditinjau TEXT
            );
            CREATE VIRTUAL TABLE kartu_fts USING fts5(
                id UNINDEXED,
                ide,
                penjelasan,
                tag,
                cabang,
                penulis,
                alat,
                tugas,
                konsep,
                tokenize='porter unicode61'
            );
            CREATE VIRTUAL TABLE kartu_trigram USING fts5(
                id UNINDEXED,
                teks_gabungan,
                tokenize='trigram'
            );
        """)
        count = 0
        for cid, c in sorted(cards.items()):
            penulis_list = sorted({
                sources[sid]["penulis"]
                for sid in c["sumber"] if sid in sources and sources[sid].get("penulis")
            })
            penulis_str = ", ".join(penulis_list) if penulis_list else "tidak diketahui"
            tag_str = ", ".join(c["tag"])
            konsep_str = ", ".join(c.get("konsep", []))
            alat_str = ", ".join(c.get("alat", []))
            tugas_str = str(c.get("tugas", ""))
            tahap_kerja_str = str(c.get("tahap_kerja", ""))
            sumber_str = ", ".join(c["sumber"])
            has_conflict = 1 if any(r["tipe"] == "bertentangan-dengan" for r in c["relasi"]) else 0
            is_orphan = 1 if len(c["relasi"]) == 0 else 0

            cur.execute(
                """INSERT INTO kartu_meta VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    cid, c["ide"], c["bidang"], c["cabang"], c["tahap"], c["jenis"],
                    c["kepercayaan"], c["dasar"], c["penerapan"], c["status"],
                    penulis_str, tag_str, alat_str, tugas_str, tahap_kerja_str, sumber_str,
                    has_conflict, is_orphan, c["dibuat"], c["terakhir_ditinjau"],
                ),
            )
            cur.execute(
                """INSERT INTO kartu_fts (id, ide, penjelasan, tag, cabang, penulis, alat, tugas, konsep) VALUES (?,?,?,?,?,?,?,?,?)""",
                (cid, c["ide"], c["penjelasan"], tag_str, c["cabang"], penulis_str, alat_str, tugas_str, konsep_str),
            )
            trigram_blob = f"{c['ide']} {c['penjelasan']} {tag_str} {konsep_str} {c['cabang']} {alat_str}"
            cur.execute(
                """INSERT INTO kartu_trigram (id, teks_gabungan) VALUES (?,?)""",
                (cid, trigram_blob),
            )
            count += 1
        conn.commit()
        return count
    finally:
        conn.close()


def ensure_fts_index() -> sqlite3.Connection:
    if not DB_PATH.exists():
        build_fts_index(load_cards(ROOT / "kartu"), load_sources(ROOT / "sumber"))
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def sanitize_fts_query(raw: str) -> str:
    tokens = re.findall(r"[\w-]+", raw.lower())
    if not tokens:
        return ""
    return " OR ".join(f'"{t}"*' for t in tokens[:16])


def search_fts(query: str, limit: int = 20) -> list[dict]:
    q_fts = sanitize_fts_query(query)
    if not q_fts:
        return []
    conn = ensure_fts_index()
    try:
        rows = conn.execute(
            """
            SELECT m.*, bm25(kartu_fts, 10.0, 4.0, 6.0, 3.0, 2.0, 8.0, 6.0, 9.0) AS skor
            FROM kartu_fts
            JOIN kartu_meta m ON m.id = kartu_fts.id
            WHERE kartu_fts MATCH ? AND m.status = 'aktif'
            ORDER BY skor ASC
            LIMIT ?
            """,
            (q_fts, limit),
        ).fetchall()
        results = [dict(r) for r in rows]
        seen_ids = {r["id"] for r in results}

        # Indeks kedua (FTS5 Trigram) untuk menangkap imbuhan Indonesia (mis: investasi/berinvestasi)
        if len(results) < limit:
            tri_tokens = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) >= 4][:6]
            if tri_tokens:
                q_tri = " OR ".join(f'"{t}"' for t in tri_tokens)
                try:
                    tri_rows = conn.execute(
                        """
                        SELECT m.*, bm25(kartu_trigram) AS skor
                        FROM kartu_trigram
                        JOIN kartu_meta m ON m.id = kartu_trigram.id
                        WHERE kartu_trigram MATCH ? AND m.status = 'aktif'
                        ORDER BY skor ASC
                        LIMIT ?
                        """,
                        (q_tri, limit),
                    ).fetchall()
                    for tr in tri_rows:
                        d = dict(tr)
                        if d["id"] not in seen_ids:
                            results.append(d)
                            seen_ids.add(d["id"])
                            if len(results) >= limit:
                                break
                except sqlite3.OperationalError:
                    pass
        return results
    finally:
        conn.close()


def find_neighbors(idea_text: str, limit: int = 20) -> list[dict]:
    """Top-20 FTS5 lalu hitung kemiripan teks untuk deteksi duplikat & kandidat relasi."""
    candidates = search_fts(idea_text, limit=limit)
    idea_low = idea_text.lower().strip()
    idea_words = set(re.findall(r"\w+", idea_low))
    enriched = []
    for c in candidates:
        cand_low = (c["ide"] or "").lower()
        cand_words = set(re.findall(r"\w+", cand_low))
        jaccard = len(idea_words & cand_words) / max(len(idea_words | cand_words), 1)
        seq_ratio = SequenceMatcher(None, idea_low, cand_low).ratio()
        sim = round(0.55 * jaccard + 0.45 * seq_ratio, 3)
        c["kemiripan"] = sim
        c["indikasi"] = "KEMUNGKINAN DUPLIKAT" if sim >= 0.65 else ("TETANGGA DEKAT" if sim >= 0.30 else "TERKAIT")
        enriched.append(c)
    enriched.sort(key=lambda x: (-x["kemiripan"], x["skor"]))
    return enriched


def filter_cards_cli(args) -> list[dict]:
    conn = ensure_fts_index()
    try:
        clauses = ["status = 'aktif'"]
        params: list = []
        if args.bidang:
            clauses.append("(bidang = ? OR cabang LIKE ?)")
            params.extend([args.bidang, args.bidang + "/%"])
        if args.tahap:
            clauses.append("tahap = ?")
            params.append(args.tahap)
        if args.jenis:
            clauses.append("jenis = ?")
            params.append(args.jenis)
        if args.kepercayaan:
            clauses.append("kepercayaan = ?")
            params.append(args.kepercayaan)
        if args.penerapan:
            clauses.append("penerapan = ?")
            params.append(args.penerapan)
        if args.penulis:
            clauses.append("LOWER(penulis) LIKE ?")
            params.append(f"%{args.penulis.lower()}%")
        if args.tag:
            clauses.append("LOWER(tag) LIKE ?")
            params.append(f"%{args.tag.lower()}%")
        if args.tampilan == "pertentangan-terbuka":
            clauses.append("has_conflict = 1")
        elif args.tampilan == "belum-diverifikasi":
            clauses.append("kepercayaan = 'belum-diverifikasi'")
        elif args.tampilan == "kartu-yatim":
            clauses.append("is_orphan = 1")
        elif args.tampilan == "draf-otomatis":
            clauses.append("LOWER(tag) LIKE '%draf-otomatis%'")

        sql = f"SELECT * FROM kartu_meta WHERE {' AND '.join(clauses)} ORDER BY id ASC LIMIT ?"
        params.append(args.limit)
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def move_cards_branch(card_ids: list[str], target_branch: str) -> int:
    """Pindahkan header cabang: & bidang: sejumlah kartu secara atomik (Bagian 6)."""
    if not re.match(r"^[a-z0-9-]+(?:/[a-z0-9-]+){0,3}$", target_branch):
        print(f"GALAT: Nama cabang tidak valid: '{target_branch}' (huruf kecil, tanda hubung, maks 4 tingkat).", file=sys.stderr)
        return 1
    target_bidang = target_branch.split("/")[0]
    moved = []
    for cid in card_ids:
        fp = ROOT / "kartu" / f"{cid}.md"
        if not fp.exists():
            print(f"LEWATI: {cid} tidak ditemukan di kartu/", file=sys.stderr)
            continue
        txt = fp.read_text(encoding="utf-8")
        new_txt = re.sub(r"^cabang:\s*.*$", f"cabang: {target_branch}", txt, count=1, flags=re.M)
        new_txt = re.sub(r"^bidang:\s*.*$", f"bidang: {target_bidang}", new_txt, count=1, flags=re.M)
        fp.write_text(new_txt, encoding="utf-8")
        moved.append(cid)

    if moved:
        log_fp = ROOT / "log.md"
        entry = f"\n[{date.today().isoformat()}] PINDAH-CABANG {', '.join(moved)} -> {target_branch}"
        with log_fp.open("a", encoding="utf-8") as f:
            f.write(entry)
        build_fts_index(load_cards(ROOT / "kartu"), load_sources(ROOT / "sumber"))
        print(f"OK: {len(moved)} kartu dipindah ke '{target_branch}' ({', '.join(moved)}). Indeks diperbarui.")
    else:
        print("Tidak ada kartu yang dipindahkan.")
    return 0


# ======================== DATASET & BUILD ========================

def build_dataset(mode: str) -> dict:
    indeks_order = parse_indeks_order(ROOT / "indeks.md")
    sources = load_sources(ROOT / "sumber")
    cards = load_cards(ROOT / "kartu")
    branches = load_branches(ROOT / "cabang")
    is_publik = (mode == "publik")

    if is_publik:
        active_cards = {cid: c for cid, c in cards.items() if c["publik"] and c["status"] == "aktif"}
    else:
        active_cards = {cid: c for cid, c in cards.items() if c["status"] == "aktif"}

    allowed_ids = set(active_cards.keys())
    out_cards = []
    used_sources: set[str] = set()
    for cid in sorted(active_cards.keys()):
        c = dict(active_cards[cid])
        penulis_list = sorted({sources[sid]["penulis"] for sid in c["sumber"] if sid in sources and sources[sid].get("penulis")})
        c["penulis"] = ", ".join(penulis_list) if penulis_list else "tidak diketahui"
        if is_publik:
            c["relasi"] = [r for r in c["relasi"] if r["ke"] in allowed_ids]
            c.pop("penerapan", None)
            c.pop("penerapan_catatan", None)
            c.pop("terakhir_ditinjau", None)
            c.pop("catatan_khusus", None)
            c.pop("publik", None)
        used_sources.update(c["sumber"])
        out_cards.append(c)

    # Teks Asli TIDAK ditanam ke JSON/HTML (Bagian 21.1 #5 — dimuat on-demand via server_lokal.py)
    out_sources = []
    for sid in sorted(sources.keys()):
        if is_publik and sid not in used_sources:
            continue
        s = dict(sources[sid])
        s.pop("teks_asli", None)
        if is_publik:
            s["kartu"] = [kid for kid in s["kartu"] if kid in allowed_ids]
        out_sources.append(s)

    branch_cards: dict[str, list[dict]] = {}
    for c in out_cards:
        cab = c["cabang"]
        branch_cards.setdefault(cab, []).append(c)
        top = cab.split("/")[0]
        if top != cab:
            branch_cards.setdefault(top, []).append(c)

    out_branches = []
    top_order_map = {item["slug"]: idx for idx, item in enumerate(indeks_order)}
    for slug, b in branches.items():
        b_cards = branch_cards.get(slug, [])
        if is_publik and len(b_cards) == 0:
            continue
        b_sources = set()
        for c in b_cards:
            b_sources.update(c["sumber"])
        b_copy = dict(b)
        b_copy["jumlah_kartu"] = len(b_cards)
        b_copy["jumlah_sumber"] = len(b_sources)
        b_copy["urutan"] = top_order_map.get(slug.split("/")[0], 999)
        if is_publik:
            b_copy["ringkasan"] = " ".join(c["ide"] for c in b_cards[:3])
            b_copy["poin_kunci"] = [f"{c['ide']} ({c['id']})" for c in b_cards[:5]]
            b_copy["pertentangan"] = []
        out_branches.append(b_copy)
    out_branches.sort(key=lambda x: (x["urutan"], x["slug"]))

    ref_counts: dict[str, int] = {c["id"]: 0 for c in out_cards}
    for c in out_cards:
        for r in c["relasi"]:
            if r["ke"] in ref_counts and r["tipe"] in ("prasyarat-untuk", "lanjutan-dari", "terkait", "memperkuat"):
                ref_counts[r["ke"]] += 1
        ref_counts[c["id"]] += sum(1 for r in c["relasi"] if r["tipe"] == "prasyarat-untuk")

    root_candidates = [c for c in out_cards if c["tahap"] == "semua-usia" and c["kepercayaan"] in ("sedang", "tinggi")]
    root_candidates.sort(key=lambda c: (-ref_counts.get(c["id"], 0), c["id"]))
    roots = [c["id"] for c in root_candidates[:7]]

    penerapan_stats = {}
    if not is_publik:
        for st in ("belum-dicoba", "sedang-dicoba", "diterapkan", "ditolak"):
            penerapan_stats[st] = sum(1 for c in out_cards if c.get("penerapan") == st)

    return {
        "mode": mode,
        "dibangun": date.today().isoformat(),
        "ringkasan": {
            "total_kartu": len(out_cards),
            "total_sumber": len(out_sources),
            "total_cabang": len(out_branches),
            "penerapan": penerapan_stats,
        },
        "urutan_indeks": [x["slug"] for x in indeks_order],
        "tahap_baku": TIMELINE_STAGES,
        "akar": roots,
        "cabang": out_branches,
        "kartu": out_cards,
        "sumber": out_sources,
    }


def run_audit() -> int:
    indeks_order = parse_indeks_order(ROOT / "indeks.md")
    sources = load_sources(ROOT / "sumber")
    cards = load_cards(ROOT / "kartu")
    branches = load_branches(ROOT / "cabang")
    warnings: list[str] = []

    for cid, c in cards.items():
        if not c["sumber"]:
            warnings.append(f"[TANPA SUMBER] {cid} tidak menautkan ke sumber mana pun.")
        for sid in c["sumber"]:
            if sid not in sources:
                warnings.append(f"[TAUTAN RUSAK] {cid} merujuk sumber {sid} yang tidak ada.")
        for r in c["relasi"]:
            target = r["ke"]
            if target not in cards:
                warnings.append(f"[TAUTAN RUSAK] {cid} ({r['tipe']}) -> {target} tidak ditemukan.")
            else:
                expected_inv = INVERSE_REL.get(r["tipe"])
                if expected_inv:
                    target_rels = [(tr["tipe"], tr["ke"]) for tr in cards[target]["relasi"]]
                    if (expected_inv, cid) not in target_rels and (r["tipe"], cid) not in target_rels:
                        warnings.append(f"[RELASI 1 ARAH] {cid} --{r['tipe']}--> {target} belum memiliki relasi balik.")

    for sid, s in sources.items():
        if not s["kartu"]:
            warnings.append(f"[SUMBER KOSONG] {sid} belum memiliki daftar kartu.")

    direct_counts: dict[str, int] = {}
    branch_sources: dict[str, set[str]] = {}
    for c in cards.values():
        if c["status"] != "aktif":
            continue
        direct_counts[c["cabang"]] = direct_counts.get(c["cabang"], 0) + 1
        branch_sources.setdefault(c["cabang"], set()).update(c["sumber"])

    for slug, cnt in direct_counts.items():
        if cnt > 30:
            warnings.append(f"[WAJIB PECAH] Cabang {slug} punya {cnt} kartu langsung (>30).")
        if len(branch_sources.get(slug, set())) <= 2:
            warnings.append(f"[SUDUT PANDANG TERBATAS] Cabang {slug} hanya bersandar pada {len(branch_sources.get(slug, set()))} sumber.")

    top_counts: dict[str, int] = {}
    for c in cards.values():
        if c["status"] == "aktif":
            top = c["cabang"].split("/")[0]
            top_counts[top] = top_counts.get(top, 0) + 1
    for item in indeks_order:
        actual = top_counts.get(item["slug"], 0)
        if actual != item["jumlah_tercatat"]:
            warnings.append(f"[INDEKS TIDAK SINKRON] {item['slug']}: tertulis {item['jumlah_tercatat']}, aktual {actual}.")

    st_counts = {k: 0 for k in ("belum-dicoba", "sedang-dicoba", "diterapkan", "ditolak")}
    unverified = 0
    for c in cards.values():
        if c["status"] == "aktif":
            st = c.get("penerapan", "belum-dicoba")
            st_counts[st] = st_counts.get(st, 0) + 1
            if c.get("kepercayaan") == "belum-diverifikasi":
                unverified += 1

    print("=== STATUS POHON PENGETAHUAN ===")
    print(f"Sumber   : {len(sources)}")
    print(f"Kartu    : {len(cards)} (aktif: {sum(1 for c in cards.values() if c['status'] == 'aktif')}, belum-diverifikasi: {unverified})")
    print(f"Cabang   : {len(branches)}")
    print(f"Penerapan: belum-dicoba={st_counts['belum-dicoba']}, sedang-dicoba={st_counts['sedang-dicoba']}, diterapkan={st_counts['diterapkan']}, ditolak={st_counts['ditolak']}")
    if warnings:
        print(f"\nPeringatan ({len(warnings)}):")
        for w in warnings:
            print(f"  - {w}")
    else:
        print("\nTidak ada peringatan konsistensi.")
    return 0


def render_html(template_path: Path, dataset: dict, out_html: Path) -> None:
    tpl = template_path.read_text(encoding="utf-8")
    json_str = json.dumps(dataset, ensure_ascii=False).replace("</", "<\\/")
    out_html.write_text(tpl.replace("__POHON_DATA_PLACEHOLDER__", json_str), encoding="utf-8")


def precheck_public(dataset: dict) -> list[str]:
    issues: list[str] = []
    src_map = {s["id"]: s for s in dataset["sumber"]}
    phone_re = re.compile(r"(?:\+62|08)\d{8,12}")
    email_re = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    for c in dataset["kartu"]:
        cid = c["id"]
        if not c["sumber"]:
            issues.append(f"[GAGAL] {cid}: kartu publik tanpa sumber.")
        else:
            has_attr = any(
                (src_map.get(sid, {}).get("url") not in ("", "tidak ada", None))
                or (src_map.get(sid, {}).get("penulis") not in ("", "tidak diketahui", None))
                for sid in c["sumber"]
            )
            if not has_attr:
                issues.append(f"[GAGAL] {cid}: sumber tidak punya url maupun penulis yang bisa dicantumkan.")
        text_blob = f"{c['ide']} {c['penjelasan']} {c['kutipan']}"
        if phone_re.search(text_blob) or email_re.search(text_blob):
            issues.append(f"[GAGAL] {cid}: terdeteksi pola nomor telepon atau email.")
        if c["kutipan"]:
            sentences = [s for s in re.split(r"[.!?]+", c["kutipan"]) if s.strip()]
            if len(sentences) > 2:
                issues.append(f"[PERIKSA] {cid}: kutipan pendukung tampak lebih dari 2 kalimat.")
        if c["bidang"] in ("kesehatan", "keuangan") and c["kepercayaan"] in ("rendah", "belum-diverifikasi"):
            issues.append(f"[INFO] {cid}: kartu {c['bidang']} berkepercayaan {c['kepercayaan']} (label wajib tampil jelas).")
    return issues


def render_static_public_pages(dataset: dict, situs_dir: Path) -> None:
    card_map = {c["id"]: c for c in dataset["kartu"]}
    src_map = {s["id"]: s for s in dataset["sumber"]}
    base_css = (
        "body{font-family:Inter,system-ui,sans-serif;max-width:860px;margin:0 auto;padding:24px;"
        "background:#F8F9FA;color:#141A17;line-height:1.6}"
        "@media(prefers-color-scheme:dark){body{background:#0E1311;color:#E8EFEA}.box{background:#151C19;border-color:#232E28}}"
        ".box{background:#fff;border:1px solid #D6DDD9;border-radius:10px;padding:18px;margin:14px 0}"
        ".badge{display:inline-block;font-size:12px;font-weight:600;padding:2px 8px;border-radius:6px;border:1px solid #D6DDD9;margin-right:6px}"
        "a{color:#2B6CB0;text-decoration:none}a:hover{text-decoration:underline}"
        "blockquote{margin:12px 0;padding:10px 14px;border-left:3px solid #2B6CB0;background:rgba(43,108,176,.06)}"
        "footer{margin-top:32px;padding-top:14px;border-top:1px solid #D6DDD9;font-size:12.5px;color:#687770}"
    )
    footer_html = "<footer>Dihasilkan dari catatan pribadi. Isi bukan nasihat medis, hukum, atau keuangan.</footer>"

    kartu_out = situs_dir / "kartu"
    kartu_out.mkdir(parents=True, exist_ok=True)
    for c in dataset["kartu"]:
        rels_html = "".join(
            f'<li><span class="badge">{html.escape(r["tipe"])}</span> '
            f'<a href="{html.escape(r["ke"])}.html">{html.escape(r["ke"])}</a> — '
            f'{html.escape(card_map[r["ke"]]["ide"])}</li>'
            for r in c["relasi"] if r["ke"] in card_map
        ) or "<li>Belum ada relasi publik.</li>"

        srcs_html = ""
        for sid in c["sumber"]:
            s = src_map.get(sid)
            if not s:
                continue
            link = (
                f' · <a href="{html.escape(s["url"])}" target="_blank" rel="noopener noreferrer">Buka sumber asli ↗</a>'
                if s.get("url") and s["url"] != "tidak ada" else ""
            )
            srcs_html += f'<li><strong>{html.escape(s["judul"])}</strong> ({html.escape(s["penulis"])}, {html.escape(s["platform"])}){link}</li>'

        quote_html = f'<blockquote>{html.escape(c["kutipan"])}</blockquote>' if c["kutipan"] else ""
        page = (
            f'<!DOCTYPE html><html lang="id"><head><meta charset="UTF-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(c["id"])} — Pohon Pengetahuan</title><style>{base_css}</style></head><body>'
            f'<p><a href="../index.html">← Kembali ke Pohon</a> · {html.escape(c["bidang"])} / {html.escape(c["tahap"])}</p>'
            f'<div class="box">'
            f'<span class="badge">{html.escape(c["id"])}</span>'
            f'<span class="badge">{html.escape(c["jenis"])}</span>'
            f'<span class="badge">kepercayaan: {html.escape(c["kepercayaan"])}</span>'
            f'<span class="badge">dasar: {html.escape(c["dasar"])}</span>'
            f'<h1>{html.escape(c["ide"])}</h1>'
            f'<p>{html.escape(c["penjelasan"])}</p>{quote_html}</div>'
            f'<div class="box"><h2>Relasi</h2><ul>{rels_html}</ul></div>'
            f'<div class="box"><h2>Sumber Asli</h2><ul>{srcs_html}</ul>'
            f'<p style="font-size:12.5px;color:#687770">Teks lengkap tersimpan di perpustakaan pribadi.</p></div>'
            f'{footer_html}</body></html>'
        )
        (kartu_out / f'{c["id"]}.html').write_text(page, encoding="utf-8")

    for b in dataset["cabang"]:
        b_dir = situs_dir / "cabang" / Path(*b["slug"].split("/"))
        b_dir.mkdir(parents=True, exist_ok=True)
        depth = len(b["slug"].split("/")) + 1
        rel_root = "../" * depth
        b_cards = [c for c in dataset["kartu"] if c["cabang"] == b["slug"] or c["cabang"].startswith(b["slug"] + "/")]
        list_html = "".join(
            f'<li><a href="{rel_root}kartu/{html.escape(c["id"])}.html">{html.escape(c["id"])}</a> '
            f'— {html.escape(c["ide"])} <span class="badge">{html.escape(c["kepercayaan"])}</span></li>'
            for c in b_cards
        ) or "<li>Belum ada kartu publik.</li>"
        page = (
            f'<!DOCTYPE html><html lang="id"><head><meta charset="UTF-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(b["nama"])} — Pohon Pengetahuan</title><style>{base_css}</style></head><body>'
            f'<p><a href="{rel_root}index.html">← Kembali ke Pohon</a></p>'
            f'<div class="box"><h1>{html.escape(b["nama"])}</h1>'
            f'<p>{html.escape(b["ringkasan"])}</p>'
            f'<h2>Daftar Kartu Publik ({len(b_cards)})</h2><ul>{list_html}</ul></div>'
            f'{footer_html}</body></html>'
        )
        (b_dir / "index.html").write_text(page, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Mesin Pohon Pengetahuan (Build, Audit, FTS5 Search, Filter, Pindah Cabang).")
    parser.add_argument("--mode", choices=["lokal", "publik"], default="lokal")
    parser.add_argument("--cek", action="store_true", help="Audit konsistensi STATUS/RAPIKAN")
    parser.add_argument("--indeks", action="store_true", help="Bangun ulang indeks SQLite FTS5 (.indeks.db)")
    parser.add_argument("--cari", type=str, help="Cari kartu cepat berperingkat BM25 (FTS5)")
    parser.add_argument("--tetangga", type=str, help="Cari Top-20 kandidat duplikat & relasi dari sebuah ide")
    parser.add_argument("--filter", action="store_true", help="Filter kartu bertingkat")
    parser.add_argument("--bidang", type=str)
    parser.add_argument("--tahap", type=str)
    parser.add_argument("--jenis", type=str)
    parser.add_argument("--kepercayaan", type=str)
    parser.add_argument("--penerapan", type=str)
    parser.add_argument("--penulis", type=str)
    parser.add_argument("--tag", type=str)
    parser.add_argument("--tampilan", choices=["pertentangan-terbuka", "belum-diverifikasi", "kartu-yatim", "draf-otomatis"])
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--pindah-cabang", nargs="+", metavar="ID", help="Pindahkan daftar ID kartu ke cabang baru")
    parser.add_argument("--ke", type=str, help="Cabang tujuan untuk --pindah-cabang")
    args = parser.parse_args()

    if args.cek:
        return run_audit()

    if args.indeks:
        n = build_fts_index(load_cards(ROOT / "kartu"), load_sources(ROOT / "sumber"))
        print(f"OK [indeks]: .indeks.db dibangun ({n} kartu terindeks FTS5/BM25).")
        return 0

    if args.cari:
        res = search_fts(args.cari, limit=args.limit)
        print(f"Hasil FTS5 untuk '{args.cari}' ({len(res)} kartu):")
        for r in res:
            print(f"  {r['id']} | {r['cabang']} | {r['tahap']} | {r['kepercayaan']} | {r['ide']}")
        return 0

    if args.tetangga:
        res = find_neighbors(args.tetangga, limit=args.limit)
        print(f"Kandidat tetangga/duplikat ({len(res)}):")
        for r in res:
            print(f"  {r['id']} | mirip={r['kemiripan']:.2f} ({r['indikasi']}) | {r['cabang']} | {r['ide']}")
        return 0

    if args.filter:
        res = filter_cards_cli(args)
        print(f"Hasil filter ({len(res)} kartu):")
        for r in res:
            print(f"  {r['id']} | {r['cabang']} | {r['tahap']} | {r['jenis']} | {r['kepercayaan']} | {r['penerapan']} | {r['ide']}")
        return 0

    if args.pindah_cabang:
        if not args.ke:
            print("GALAT: Sertakan --ke <nama-cabang> saat memakai --pindah-cabang.", file=sys.stderr)
            return 1
        return move_cards_branch(args.pindah_cabang, args.ke)

    template_path = ROOT / "scripts" / "template_peta.html"
    if not template_path.exists():
        print(f"GALAT: Template tidak ditemukan di {template_path}", file=sys.stderr)
        return 1

    dataset = build_dataset(args.mode)

    if args.mode == "lokal":
        n = build_fts_index(load_cards(ROOT / "kartu"), load_sources(ROOT / "sumber"))
        (ROOT / "data.json").write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
        render_html(template_path, dataset, ROOT / "peta-pohon.html")
        print(
            f"OK [lokal]: peta-pohon.html, data.json & .indeks.db dibuat "
            f"({dataset['ringkasan']['total_kartu']} kartu, "
            f"{dataset['ringkasan']['total_sumber']} sumber, "
            f"{dataset['ringkasan']['total_cabang']} cabang, {n} FTS5)."
        )
    else:
        issues = precheck_public(dataset)
        for msg in issues:
            print(msg)
        if any(m.startswith("[GAGAL]") for m in issues):
            print("DIBATALKAN: Perbaiki temuan [GAGAL] sebelum membangun situs publik.", file=sys.stderr)
            return 1 

        situs_dir = ROOT / "situs"
        if situs_dir.exists():
            shutil.rmtree(situs_dir)
        situs_dir.mkdir(parents=True, exist_ok=True)
        (situs_dir / "data.json").write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
        render_html(template_path, dataset, situs_dir / "index.html")
        render_static_public_pages(dataset, situs_dir)
        assets_src = ROOT / "assets"
        if assets_src.is_dir():
            assets_dst = situs_dir / "assets"
            assets_dst.mkdir(parents=True, exist_ok=True)
            for img_fp in assets_src.iterdir():
                if img_fp.is_file() and img_fp.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"}:
                    shutil.copy2(img_fp, assets_dst / img_fp.name)
        print(
            f"OK [publik]: situs/ dibangun ulang "
            f"({dataset['ringkasan']['total_kartu']} kartu publik, "
            f"{dataset['ringkasan']['total_cabang']} cabang publik)."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
