#!/usr/bin/env python3
"""
Mesin Kecerdasan Pohon Pengetahuan (Bagian 21 — zero external dependencies).
Prinsip: skrip mempersempit & menghitung secara transparan, AI menilai makna, pengguna menyetujui.

Algoritma yang tersedia (Python 3 standard library murni):
  1. --ulasan              : Spaced Repetition (SM-2 / Leitner sederhana) -> Top-5 kartu prioritas
  2. --saran               : Skor rekomendasi personal (persona.md) + MMR diversification
  3. --roadmap [bidang]    : Topological Sort (Kahn's Algorithm) + Deteksi Siklus (DFS 3-warna)
  4. --fondasi             : Iterative PageRank (d=0.85) + Cross-Domain Bridge Centrality
  5. --gema                : Deteksi ruang gema per cabang (Shannon Entropy & HHI penulis/sumber)
  6. --kalibrasi           : Kalibrasi sumber/penulis berdasarkan riwayat diterapkan vs ditolak
  7. --mirip <K-XXXX>      : TF-IDF (sublinear TF + smoothed IDF) + Cosine Similarity
  8. --klaster <cabang>    : Greedy Medoid Clustering berbasis TF-IDF untuk usulan pemecahan cabang
  9. --ringkas             : Ringkasan eksekutif seluruh mesin kecerdasan
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import urllib.error
import urllib.request
from collections import Counter, defaultdict, deque
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import bangun_pohon as bp  # noqa: E402

STOPWORDS = {
    # Indonesia
    "yang", "dan", "di", "ke", "dari", "untuk", "pada", "dengan", "ini", "itu", "atau",
    "adalah", "akan", "tidak", "bisa", "juga", "agar", "karena", "oleh", "dalam", "sebagai",
    "jika", "bila", "saat", "ada", "lebih", "hanya", "tetap", "masih", "sudah", "belum",
    "satu", "kita", "saya", "anda", "mereka", "nya", "hal", "jadi", "harus", "seperti",
    "apa", "bagaimana", "mengapa", "kenapa", "siapa", "kapan", "dimana", "mana", "saja",
    "tentang", "cara", "jelaskan", "ringkasan", "ilmu", "sebutkan", "poin", "terpenting",
    "bidang", "perlu", "punya", "catatan", "kartu", "semua",
    # English
    "the", "and", "for", "that", "this", "with", "from", "are", "was", "were", "have",
    "has", "not", "but", "can", "will", "your", "you", "they", "their", "about", "into",
}

TRUST_WEIGHT = {"tinggi": 1.0, "sedang": 0.8, "rendah": 0.45, "belum-diverifikasi": 0.5}
STATUS_WEIGHT = {"belum-dicoba": 1.0, "sedang-dicoba": 0.85, "diterapkan": 0.3, "ditolak": 0.1}


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return [w for w in words if len(w) >= 3 and w not in STOPWORDS]


def days_since(iso_date: str) -> int:
    if not iso_date:
        return 999
    try:
        dt = datetime.strptime(iso_date[:10], "%Y-%m-%d").date()
        return max(0, (date.today() - dt).days)
    except ValueError:
        return 999


def load_active():
    sources = bp.load_sources(ROOT / "sumber")
    all_cards = bp.load_cards(ROOT / "kartu")
    cards = {cid: c for cid, c in all_cards.items() if c["status"] == "aktif"}
    branches = bp.load_branches(ROOT / "cabang")
    return cards, sources, branches


# ======================== 1. TF-IDF & COSINE SIMILARITY ========================

def build_tfidf(cards: dict[str, dict]) -> dict[str, dict[str, float]]:
    docs: dict[str, list[str]] = {}
    df: Counter = Counter()
    for cid, c in cards.items():
        toks = tokenize(f"{c['ide']} {c['ide']} {c['penjelasan']} {' '.join(c['tag'])} {c['cabang']}")
        docs[cid] = toks
        for w in set(toks):
            df[w] += 1
    n_docs = max(len(docs), 1)
    vectors: dict[str, dict[str, float]] = {}
    for cid, toks in docs.items():
        tf = Counter(toks)
        vec: dict[str, float] = {}
        norm_sq = 0.0
        for w, cnt in tf.items():
            w_tf = 1.0 + math.log(cnt)
            w_idf = math.log((n_docs + 1) / (df[w] + 1)) + 1.0
            val = w_tf * w_idf
            vec[w] = val
            norm_sq += val * val
        norm = math.sqrt(norm_sq) or 1.0
        vectors[cid] = {w: v / norm for w, v in vec.items()}
    return vectors


def cosine_sim(v1: dict[str, float], v2: dict[str, float]) -> float:
    if not v1 or not v2:
        return 0.0
    if len(v1) > len(v2):
        v1, v2 = v2, v1
    return sum(val * v2.get(k, 0.0) for k, val in v1.items())


def cmd_mirip(target_id: str, limit: int = 10) -> int:
    cards, _, _ = load_active()
    if target_id not in cards:
        print(f"GALAT: Kartu {target_id} tidak ditemukan.", file=sys.stderr)
        return 1
    vecs = build_tfidf(cards)
    scored = []
    for cid, c in cards.items():
        if cid == target_id:
            continue
        sim = cosine_sim(vecs[target_id], vecs[cid])
        scored.append((sim, cid, c))
    scored.sort(key=lambda x: (-x[0], x[1]))
    print(f"=== KARTU PALING MIRIP DENGAN {target_id} (TF-IDF + Cosine) ===")
    print(f"Target: {cards[target_id]['ide']}\n")
    for sim, cid, c in scored[:limit]:
        print(f"  {cid} | cos={sim:.3f} | {c['cabang']} | {c['ide']}")
    if not scored:
        print("  (Belum ada kartu pembanding lain.)")
    return 0


def cmd_klaster(cabang_slug: str, threshold: float = 0.22) -> int:
    cards, _, _ = load_active()
    sub_cards = {
        cid: c for cid, c in cards.items()
        if c["cabang"] == cabang_slug or c["cabang"].startswith(cabang_slug + "/")
    }
    print(f"=== USULAN SUB-CABANG / KLASTER: {cabang_slug} ({len(sub_cards)} kartu) ===")
    if len(sub_cards) < 6:
        print(f"Catatan ambang (Bagian 21.2): klasterisasi baru optimal saat cabang >30 kartu (saat ini {len(sub_cards)}).")
    if not sub_cards:
        return 0

    vecs = build_tfidf(sub_cards)
    unassigned = sorted(sub_cards.keys())
    clusters: list[list[str]] = []

    while unassigned:
        # Pilih medoid dengan total kemiripan tertinggi ke sisa kartu
        best_seed = max(
            unassigned,
            key=lambda u: sum(cosine_sim(vecs[u], vecs[v]) for v in unassigned if v != u),
        )
        group = [best_seed]
        rest = []
        for cid in unassigned:
            if cid == best_seed:
                continue
            if cosine_sim(vecs[best_seed], vecs[cid]) >= threshold:
                group.append(cid)
            else:
                rest.append(cid)
        clusters.append(group)
        unassigned = rest

    for idx, grp in enumerate(clusters, 1):
        # Ambil 4 kata TF-IDF tertinggi sebagai kandidat nama tema
        agg = Counter()
        for cid in grp:
            for w, val in vecs[cid].items():
                agg[w] += val
        top_terms = ", ".join(w for w, _ in agg.most_common(4))
        print(f"\nKlaster {idx} ({len(grp)} kartu) | kata kunci: {top_terms}")
        for cid in grp[:8]:
            print(f"  - {cid}: {sub_cards[cid]['ide']}")
        if len(grp) > 8:
            print(f"  ... +{len(grp) - 8} kartu lainnya")
    return 0


# ======================== 2. SPACED REPETITION (ULASAN SM-2/LEITNER) ========================

def cmd_ulasan(limit: int = 5) -> int:
    cards, _, _ = load_active()
    print(f"=== ANTREAN ULASAN CERDAS (SM-2 / Leitner Sederhana — {len(cards)} kartu aktif) ===")
    if len(cards) < 50:
        print(f"Info ambang (Bagian 21.2): penjadwalan berjarak penuh optimal di >=50 kartu (saat ini {len(cards)}).")

    # Interval target (hari) per status penerapan
    interval_target = {"sedang-dicoba": 14, "belum-dicoba": 7, "diterapkan": 45, "ditolak": 90}
    scored = []
    for cid, c in cards.items():
        st = c["penerapan"]
        elapsed = days_since(c["terakhir_ditinjau"])
        target = interval_target.get(st, 30)
        overdue_ratio = (elapsed + 1) / max(target, 1)
        trust = TRUST_WEIGHT.get(c["kepercayaan"], 0.5)

        # Prioritas mengikuti Bagian 19.2 + rasio keterlambatan Leitner
        if st == "sedang-dicoba" and elapsed > 14:
            tier = 1
            reason = f"sedang-dicoba, {elapsed} hari tanpa pembaruan (>14 hari)"
        elif st == "belum-dicoba" and c["kepercayaan"] in ("tinggi", "sedang"):
            tier = 2
            reason = f"belum-dicoba, kepercayaan {c['kepercayaan']} (target interval {target} hari)"
        elif elapsed > 30:
            tier = 3
            reason = f"terakhir ditinjau {elapsed} hari lalu (>30 hari)"
        else:
            tier = 4
            reason = f"status {st}, kepercayaan {c['kepercayaan']}, {elapsed} hari sejak ditinjau"

        urgency = round((5 - tier) * 10 + overdue_ratio * 2.5 + trust * 2.0, 2)
        scored.append((tier, -urgency, cid, c, reason))

    scored.sort(key=lambda x: (x[0], x[1], x[2]))
    for idx, (_, neg_urg, cid, c, reason) in enumerate(scored[:limit], 1):
        print(f"{idx}. {cid} [skor={-neg_urg:.1f}] ({c['cabang']} | {c['kepercayaan']} | {c['penerapan']})")
        print(f"   Ide    : {c['ide']}")
        print(f"   Alasan : {reason}")
    if not scored:
        print("  (Belum ada kartu aktif.)")
    return 0


# ======================== 3. REKOMENDASI PERSONAL + MMR ========================

def parse_persona_profile() -> dict:
    pp = ROOT / "persona.md"
    if not pp.is_file():
        return {"stage": "semua-usia", "keywords": set(), "raw_ok": False}
    txt = pp.read_text(encoding="utf-8")
    m_stage = re.search(r"tahap\s+`?([0-9+-]+|sebelum-20|semua-usia)`?", txt, re.I)
    stage = m_stage.group(1) if m_stage else "semua-usia"
    if stage == "semua-usia":
        m_age = re.search(r"Umur:\s*(\d{2})", txt, re.I)
        if m_age:
            age = int(m_age.group(1))
            stage = "sebelum-20" if age < 20 else "20-25" if age <= 25 else "25-30" if age <= 30 else "30-40" if age <= 40 else "40-50" if age <= 50 else "50+"
    secs = bp.parse_sections(txt)
    goal_text = f"{secs.get('Tujuan', '')} {secs.get('Kondisi Saat Ini', '')} {secs.get('Kekuatan & Kelemahan', '')}"
    return {"stage": stage, "keywords": set(tokenize(goal_text)), "raw_ok": True}


def cmd_saran(limit: int = 5) -> int:
    cards, _, _ = load_active()
    prof = parse_persona_profile()
    print(f"=== REKOMENDASI PERSONAL TRANSPARAN (Persona tahap: {prof['stage']} | {len(cards)} kartu) ===")
    if len(cards) < 100:
        print(f"Info ambang (Bagian 21.2): skor statistik penuh optimal di >=100 kartu (saat ini {len(cards)}).")
    if not prof["raw_ok"]:
        print("PERINGATAN: persona.md tidak ditemukan.")
        return 1

    vecs = build_tfidf(cards)
    candidates = []
    for cid, c in cards.items():
        c_toks = set(tokenize(f"{c['ide']} {c['penjelasan']} {' '.join(c['tag'])} {c['cabang']}"))
        overlap = sorted(c_toks & prof["keywords"])
        goal_rel = min(1.0, 0.35 + 0.2 * len(overlap))
        stage_fit = 1.0 if c["tahap"] == prof["stage"] else (0.85 if c["tahap"] == "semua-usia" else 0.45)
        trust_w = TRUST_WEIGHT.get(c["kepercayaan"], 0.5)
        status_w = STATUS_WEIGHT.get(c["penerapan"], 0.5)
        has_conf = any(r["tipe"] == "bertentangan-dengan" for r in c["relasi"])
        conf_w = 0.75 if has_conf else 1.0

        score = round(goal_rel * stage_fit * trust_w * status_w * conf_w, 4)
        alasan = (
            f"relevansi_tujuan={goal_rel:.2f}" + (f" (cocok: {', '.join(overlap[:4])})" if overlap else " (umum)")
            + f" x tahap={stage_fit:.2f} x kepercayaan={trust_w:.2f} x penerapan={status_w:.2f}"
            + (f" x konflik={conf_w:.2f}" if has_conf else "")
        )
        candidates.append({"id": cid, "score": score, "card": c, "alasan": alasan})

    # MMR (Maximal Marginal Relevance, lambda=0.75) agar hasil bervariasi
    selected = []
    pool = sorted(candidates, key=lambda x: (-x["score"], x["id"]))
    lam = 0.75
    while pool and len(selected) < limit:
        if not selected:
            pick = pool.pop(0)
        else:
            best_i, best_val = 0, -1e9
            for i, cand in enumerate(pool):
                max_sim = max(cosine_sim(vecs[cand["id"]], vecs[s["id"]]) for s in selected)
                mmr = lam * cand["score"] - (1 - lam) * max_sim
                if mmr > best_val:
                    best_val, best_i = mmr, i
            pick = pool.pop(best_i)
        selected.append(pick)

    for idx, item in enumerate(selected, 1):
        c = item["card"]
        print(f"{idx}. {c['id']} [skor={item['score']:.3f}] ({c['cabang']} | {c['tahap']} | {c['kepercayaan']})")
        print(f"   Ide    : {c['ide']}")
        print(f"   Kenapa : {item['alasan']}")
    return 0


# ======================== 4. TOPOLOGICAL SORT & CYCLE DETECTION (ROADMAP) ========================

def cmd_roadmap(bidang: str | None = None) -> int:
    cards, _, _ = load_active()
    if bidang:
        cards = {cid: c for cid, c in cards.items() if c["bidang"] == bidang or c["cabang"].startswith(bidang + "/")}
    print(f"=== URUTAN TOPOLOGIS ROADMAP {f'({bidang}) ' if bidang else ''}({len(cards)} kartu) ===")
    if len(cards) < 150:
        print(f"Info ambang (Bagian 21.2): urutan prasyarat kompleks optimal di >=150 kartu (saat ini {len(cards)}).")

    adj: dict[str, set[str]] = {cid: set() for cid in cards}
    indeg: dict[str, int] = {cid: 0 for cid in cards}

    for cid, c in cards.items():
        for r in c["relasi"]:
            tgt = r["ke"]
            if tgt not in cards:
                continue
            # A prasyarat-untuk B => A -> B ; A lanjutan-dari B => B -> A
            if r["tipe"] == "prasyarat-untuk":
                adj[cid].add(tgt)
            elif r["tipe"] == "lanjutan-dari":
                adj[tgt].add(cid)

    for u, nbrs in adj.items():
        for v in nbrs:
            indeg[v] += 1

    # Kahn's Algorithm berlapis (layer by layer = Fase 1, Fase 2, ...)
    q = deque(sorted(cid for cid, d in indeg.items() if d == 0))
    layers: list[list[str]] = []
    visited = 0
    while q:
        layer = list(q)
        q.clear()
        layers.append(layer)
        next_layer = []
        for u in layer:
            visited += 1
            for v in sorted(adj[u]):
                indeg[v] -= 1
                if indeg[v] == 0:
                    next_layer.append(v)
        q.extend(sorted(next_layer))

    for i, layer in enumerate(layers, 1):
        print(f"\nFase {i} ({len(layer)} kartu):")
        for cid in layer[:10]:
            c = cards[cid]
            print(f"  - {cid} [{c['tahap']} | {c['penerapan']}]: {c['ide']}")
        if len(layer) > 10:
            print(f"  ... +{len(layer) - 10} kartu")

    if visited < len(cards):
        cycle_nodes = sorted(cid for cid, d in indeg.items() if d > 0)
        print(f"\n[PERINGATAN SIKLUS] Terdeteksi ketergantungan melingkar pada: {', '.join(cycle_nodes)}")
    else:
        print("\nGraf prasyarat bersih (DAG valid, tanpa siklus).")
    return 0


# ======================== 5. PAGERANK & BRIDGE CENTRALITY ========================

def cmd_fondasi(limit: int = 10) -> int:
    cards, _, _ = load_active()
    print(f"=== KARTU FONDASI (PageRank) & KARTU JEMBATAN ({len(cards)} kartu) ===")
    if len(cards) < 200:
        print(f"Info ambang (Bagian 21.2): centrality/PageRank optimal di >=200 kartu (saat ini {len(cards)}).")
    if not cards:
        return 0

    nodes = sorted(cards.keys())
    n = len(nodes)
    out_links: dict[str, set[str]] = {u: set() for u in nodes}
    in_links: dict[str, set[str]] = {u: set() for u in nodes}

    for cid, c in cards.items():
        for r in c["relasi"]:
            tgt = r["ke"]
            if tgt in cards and tgt != cid:
                out_links[cid].add(tgt)
                in_links[tgt].add(cid)

    # Iterative PageRank (d = 0.85, 30 iterasi)
    d = 0.85
    pr = {u: 1.0 / n for u in nodes}
    for _ in range(30):
        dangling_sum = sum(pr[u] for u in nodes if not out_links[u])
        new_pr = {}
        for u in nodes:
            rank = (1.0 - d) / n + d * (dangling_sum / n)
            for v in in_links[u]:
                rank += d * (pr[v] / len(out_links[v]))
            new_pr[u] = rank
        pr = new_pr

    print("\nTop Kartu Fondasi (PageRank):")
    for cid in sorted(nodes, key=lambda u: (-pr[u], u))[:limit]:
        c = cards[cid]
        print(f"  {cid} | PR={pr[cid]:.4f} | relasi={len(c['relasi'])} | {c['cabang']} | {c['ide']}")

    # Bridge score: jumlah bidang unik tetangga yang berbeda dari bidang kartu ini
    bridges = []
    for cid, c in cards.items():
        other_domains = {
            cards[r["ke"]]["bidang"]
            for r in c["relasi"]
            if r["ke"] in cards and cards[r["ke"]]["bidang"] != c["bidang"]
        }
        if other_domains:
            bridges.append((len(other_domains), cid, sorted(other_domains), c))
    bridges.sort(key=lambda x: (-x[0], x[1]))
    print("\nKartu Jembatan (menghubungkan lintas bidang):")
    if bridges:
        for cnt, cid, doms, c in bridges[:limit]:
            print(f"  {cid} | menghubungkan {c['bidang']} <-> {', '.join(doms)} | {c['ide']}")
    else:
        print("  (Belum ada relasi lintas bidang.)")
    return 0


# ======================== 6. DETEKSI RUANG GEMA (ENTROPY & HHI) ========================

def cmd_gema() -> int:
    cards, sources, _ = load_active()
    print(f"=== DETEKSI RUANG GEMA PER CABANG (Shannon Entropy & HHI) ===")
    if len(cards) < 100:
        print(f"Info ambang (Bagian 21.2): deteksi gema optimal di >=100 kartu (saat ini {len(cards)}).")

    by_branch: dict[str, list[dict]] = defaultdict(list)
    for c in cards.values():
        by_branch[c["cabang"]].append(c)

    for slug in sorted(by_branch.keys()):
        c_list = by_branch[slug]
        author_counts = Counter()
        src_set = set()
        for c in c_list:
            for sid in c["sumber"]:
                src_set.add(sid)
                author = sources.get(sid, {}).get("penulis", "tidak diketahui")
                author_counts[author] += 1
        total = sum(author_counts.values()) or 1
        probs = [cnt / total for cnt in author_counts.values()]
        hhi = sum(p * p for p in probs)  # 1.0 = monopoli 1 penulis, mendekati 0 = sangat beragam
        entropy = -sum(p * math.log2(p) for p in probs if p > 0)
        status = "WASPADA GEMA" if (len(author_counts) <= 2 or hhi >= 0.55) else "BERAGAM"
        print(f"  {slug} | {len(c_list)} kartu | {len(src_set)} sumber | {len(author_counts)} penulis unik | HHI={hhi:.2f} | H={entropy:.2f} -> {status}")
    if not by_branch:
        print("  (Belum ada kartu aktif.)")
    return 0


# ======================== 7. KALIBRASI SUMBER ========================

def cmd_kalibrasi() -> int:
    cards, sources, _ = load_active()
    print("=== KALIBRASI SUMBER / PENULIS (Informasi Pribadi, Bukan Vonis) ===")
    if len(cards) < 200:
        print(f"Info ambang (Bagian 21.2): kalibrasi bermakna setelah >=200 kartu + penerapan terisi (saat ini {len(cards)}).")

    stats: dict[str, Counter] = defaultdict(Counter)
    for c in cards.values():
        st = c["penerapan"]
        for sid in c["sumber"]:
            author = sources.get(sid, {}).get("penulis", "tidak diketahui")
            stats[author][st] += 1
            stats[author]["total"] += 1

    for author, cnt in sorted(stats.items(), key=lambda kv: (-kv[1]["total"], kv[0])):
        print(
            f"  {author} | total={cnt['total']} | diterapkan={cnt['diterapkan']} "
            f"| sedang-dicoba={cnt['sedang-dicoba']} | ditolak={cnt['ditolak']} | belum={cnt['belum-dicoba']}"
        )
    if not stats:
        print("  (Belum ada data sumber.)")
    return 0


# ======================== 8. BIG-DATA COMPARISON, PLAYBOOK & TREN ========================

KNOWN_TOOLS = [
    "claude-fable", "claude-code", "claude-opus", "claude-sonnet", "claude",
    "gemini-4-neon", "gemini", "cursor", "antigravity", "codex", "chatgpt", "gpt",
    "kling", "veo", "runway", "sora", "luma", "pika", "hailuo", "heygen", "elevenlabs",
    "capcut", "opus-clip", "midjourney", "flux", "ideogram", "canva", "figma",
    "perplexity", "notebooklm", "n8n", "make", "zapier", "obsidian",
    "ocr-x", "tiktok", "instagram", "youtube", "threads", "facebook", "seo", "mcp",
]

WORKFLOW_STAGES = [
    ("riset", "1. Riset & Ide", ["riset", "research", "ide", "trend", "tren", "niche", "keyword", "audiens", "validasi", "cari", "seo", "analisis"]),
    ("skrip", "2. Perencanaan, Skrip & Prompt", ["skrip", "script", "prompt", "hook", "outline", "storyboard", "tone", "guideline", "copywriting", "strategi", "skill", "arsitektur"]),
    ("produksi", "3. Produksi & Eksekusi", ["buat", "bikin", "generate", "video", "clipping", "clip", "gambar", "voice", "coding", "app", "build", "render", "rekam", "tulis", "artikel"]),
    ("edit", "4. Editing, Audit & Polish", ["edit", "polish", "audit", "review", "slop", "ui", "desain", "rapikan", "subtitle", "caption", "revisi", "quality"]),
    ("distribusi", "5. Distribusi & Sosmed", ["post", "posting", "upload", "reupload", "repost", "impresi", "viral", "algoritma", "distribusi", "jadwal", "sosmed", "traffic", "funnel"]),
    ("monetisasi", "6. Evaluasi & Monetisasi", ["payout", "monetisasi", "cuan", "ocr", "jual", "konversi", "iklan", "ads", "produk", "bisnis", "revenue", "uang", "gaji"]),
]

def detect_tools_in_card(c: dict) -> list[str]:
    found = [t.lower().strip() for t in (c.get("alat") or []) if t and t.strip()]
    # Abaikan tag platform generik agar sumber X tidak dianggap alat AI
    clean_tags = [t for t in (c.get("tag") or []) if t.lower() not in ("x", "web", "draf-otomatis", "facebook", "instagram", "threads")]
    blob = f"{c['ide']} {c['penjelasan']} {' '.join(clean_tags)}".lower()
    # Match multi-word / hyphenated tools first
    for tool in KNOWN_TOOLS:
        pattern = re.escape(tool).replace(r"\-", r"[\s\-]+")
        if re.search(rf"\b{pattern}\b", blob):
            if tool not in found:
                found.append(tool)
    # Remove overly broad parent if specific variant already found (e.g. claude-code -> drop plain claude)
    for parent in ("claude", "gemini", "gpt"):
        if parent in found and any(t.startswith(parent + "-") for t in found):
            found.remove(parent)
    return found


def detect_workflow_stage(c: dict) -> str:
    explicit = (c.get("tahap_kerja") or "").lower().strip()
    valid_keys = {k for k, _, _ in WORKFLOW_STAGES}
    if explicit in valid_keys:
        return explicit
    blob = f"{c['ide']} {c['penjelasan']} {' '.join(c['tag'])} {c.get('tugas', '')}".lower()
    best_stage, best_hits = "produksi", 0
    for key, _, kws in WORKFLOW_STAGES:
        hits = sum(1 for kw in kws if re.search(rf"\b{re.escape(kw)}", blob))
        if hits > best_hits:
            best_stage, best_hits = key, hits
    return best_stage


# Kamus Sinonim & Gugus Semantik Dwibahasa (ID <-> EN) untuk Pencarian, TextTiling, & Klasifikasi
SYNONYM_CLUSTERS: tuple[tuple[str, ...], ...] = (
    # Kesehatan, Tidur, Biologi, Olahraga & Nutrisi
    ("tidur", "sleep", "istirahat", "rest", "insomnia", "begadang", "circadian", "sirkadian", "rem", "nap"),
    ("sehat", "healthy", "kesehatan", "health", "kebugaran", "wellness", "longevity", "umur", "panjang"),
    ("otak", "brain", "kognitif", "cognitive", "fog", "fokus", "focus", "memori", "memory", "konsentrasi"),
    ("olahraga", "workout", "exercise", "gym", "fitness", "lift", "weights", "beban", "cardio", "lari", "jogging"),
    ("otot", "muscle", "strength", "kekuatan", "atlet", "athlete", "recovery", "pemulihan", "stamina"),
    ("makan", "eat", "nutrisi", "nutrition", "diet", "kalori", "calories", "protein", "puasa", "fasting", "gula", "sugar"),
    ("stres", "stress", "cemas", "anxiety", "burnout", "lelah", "fatigue", "kortisol", "cortisol", "dopamin", "dopamine"),
    ("penampilan", "appearance", "postur", "posture", "grooming", "skincare", "berpakaian", "dress", "rapi"),
    ("biologis", "biological", "metabolisme", "metabolic", "hormon", "hormone", "imun", "immune", "energi", "energy"),
    # Keuangan & Investasi
    ("keuangan", "finance", "financial", "uang", "money", "dana", "cashflow", "anggaran", "budget"),
    ("tabungan", "saving", "menabung", "darurat", "emergency", "hemat", "frugal", "pengeluaran", "expense"),
    ("investasi", "investing", "investment", "saham", "stock", "reksadana", "obligasi", "crypto", "aset", "asset", "dividen"),
    ("gaji", "salary", "income", "penghasilan", "pendapatan", "payout", "bayaran", "cuan", "profit", "margin"),
    ("utang", "debt", "cicilan", "kredit", "pinjaman", "bunga", "interest", "inflasi", "inflation", "pajak", "tax"),
    # Bisnis & Monetisasi
    ("bisnis", "business", "usaha", "startup", "perusahaan", "company", "agency", "agensi", "saas", "microsaas"),
    ("jualan", "sales", "penjualan", "closing", "omzet", "revenue", "arr", "mrr", "monetisasi", "monetize"),
    ("klien", "client", "pelanggan", "customer", "pembeli", "buyer", "pasar", "market", "validasi", "validation"),
    ("produk", "product", "digital", "layanan", "service", "harga", "pricing", "penawaran", "offer", "value"),
    # Sosial Media & Konten
    ("reupload", "repost", "daur", "ulang", "copy", "plagiat", "duplikat", "orisinal", "original"),
    ("viral", "trending", "fyp", "algoritma", "algorithm", "impresi", "impression", "views", "tayangan", "reach"),
    ("konten", "content", "postingan", "post", "thread", "hook", "storytelling", "kreator", "creator", "audiens"),
    ("engagement", "interaksi", "reply", "balasan", "share", "retweet", "bookmark", "followers", "subscriber"),
    ("sosmed", "twitter", "youtube", "tiktok", "instagram", "threads", "linkedin", "ocr"),
    # Digital Marketing & SEO
    ("seo", "search", "google", "traffic", "ranking", "peringkat", "keyword", "organik", "organic", "backlink"),
    ("marketing", "pemasaran", "iklan", "ads", "funnel", "landing", "konversi", "conversion", "ctr", "lead", "prospek"),
    ("copywriting", "naskah", "headline", "judul", "cta", "persuasi", "persuasion", "branding", "merek"),
    # AI, Coding, Prompt, Video & Tulisan
    ("ai", "llm", "claude", "gemini", "gpt", "chatgpt", "openai", "anthropic", "model", "deepseek", "grok"),
    ("prompt", "agent", "agen", "agentic", "mcp", "skill", "workflow", "otomasi", "automation", "context", "rag"),
    ("coding", "code", "kode", "program", "programming", "developer", "cursor", "python", "javascript", "typescript", "api", "github", "repo"),
    ("frontend", "backend", "fullstack", "nextjs", "react", "astro", "vercel", "database", "sql", "supabase", "deploy"),
    ("video", "clipping", "clip", "kling", "veo", "runway", "sora", "heygen", "capcut", "dubbing", "voiceover", "elevenlabs", "avatar"),
    ("menulis", "writing", "tulisan", "artikel", "article", "blog", "newsletter", "gaya", "tone", "voice", "suara"),
    ("benchmark", "perbandingan", "compare", "evaluasi", "akurasi", "latency", "token", "harga", "quota"),
    # Kesuksesan, Karier & Pendidikan
    ("karier", "karir", "career", "kerja", "pekerjaan", "job", "profesi", "promosi", "resign", "remote"),
    ("cpns", "asn", "bumn", "beasiswa", "scholarship", "lpdp", "ausbildung", "magang", "internship", "kuliah", "studi"),
    ("wawancara", "interview", "cv", "resume", "portofolio", "portfolio", "skill", "keahlian", "sertifikat"),
    # Motivasi, Mindset & Produktivitas
    ("disiplin", "discipline", "konsisten", "consistent", "kebiasaan", "habit", "habits", "rutinitas", "routine"),
    ("mindset", "pola", "pikir", "mental", "mentalitas", "psikologi", "psychology", "stoik", "resiliensi"),
    ("produktif", "productivity", "produktivitas", "efisien", "efficiency", "waktu", "time", "prioritas", "deepwork"),
    ("overthinking", "perfeksionis", "prokrastinasi", "menunda", "malas", "takut", "fear", "gagal", "failure", "sukses"),
    # Relasi & Komunikasi
    ("relasi", "relationship", "hubungan", "keluarga", "family", "pasangan", "partner", "teman", "friends", "sosial"),
    ("komunikasi", "communication", "negosiasi", "negotiation", "networking", "jejaring", "empati", "empathy", "konflik"),
)

BILINGUAL_SYNONYMS: dict[str, tuple[str, ...]] = {}
for _cluster in SYNONYM_CLUSTERS:
    for _word in _cluster:
        _others = tuple(w for w in _cluster if w != _word)
        if _word in BILINGUAL_SYNONYMS:
            BILINGUAL_SYNONYMS[_word] = tuple(dict.fromkeys(BILINGUAL_SYNONYMS[_word] + _others))
        else:
            BILINGUAL_SYNONYMS[_word] = _others


def expand_bilingual_tokens(toks: list[str]) -> list[str]:
    out = list(dict.fromkeys(toks))
    for t in toks:
        for syn in BILINGUAL_SYNONYMS.get(t, ()):
            if syn not in out:
                out.append(syn)
    return out


def compute_shingle_jaccard(text_a: str, text_b: str, k: int = 3) -> float:
    """Kemiripan Jaccard berbasis k-word shingles untuk mendeteksi near-duplicate teks."""
    wa = re.findall(r"[a-z0-9\u4e00-\u9fff]+", (text_a or "").lower())
    wb = re.findall(r"[a-z0-9\u4e00-\u9fff]+", (text_b or "").lower())
    if not wa or not wb:
        return 0.0
    if len(wa) < k or len(wb) < k:
        sa, sb = set(wa), set(wb)
    else:
        sa = {tuple(wa[i : i + k]) for i in range(len(wa) - k + 1)}
        sb = {tuple(wb[i : i + k]) for i in range(len(wb) - k + 1)}
    union = len(sa | sb)
    return (len(sa & sb) / union) if union else 0.0


def find_near_duplicate_source(raw_text: str, existing_sources: dict[str, dict], threshold: float = 0.80) -> tuple[str | None, float]:
    """Cari apakah ada sumber di perpustakaan yang hampir identik (Jaccard 3-gram >= threshold)."""
    best_sid, best_sim = None, 0.0
    for sid, src in existing_sources.items():
        sim = compute_shingle_jaccard(raw_text, src.get("teks_asli") or "", k=3)
        if sim > best_sim:
            best_sim, best_sid = sim, sid
    if best_sim >= threshold:
        return best_sid, round(best_sim, 3)
    return None, round(best_sim, 3)


def multinomial_naive_bayes_branch(
    text: str,
    lexicon: dict[str, list[str]],
    existing_cards: dict[str, dict] | None = None,
    alpha: float = 1.0,
) -> list[tuple[str, float]]:
    """
    Klasifikasi Multinomial Naive Bayes dengan Laplace Smoothing (alpha=1.0):
      log P(c | d) = log P(c) + sum_{w in d} count(w, d) * log((count(w, c) + alpha) / (total_c + alpha * |V|))
    Dilatih otomatis dari:
      1) Kamus domain dwibahasa (lexicon) dengan bobot prior seimbang, DAN
      2) Kartu aktif yang sudah tersimpan di Pohon (self-learning seiring pohon tumbuh!).
    """
    class_word_counts: dict[str, Counter] = defaultdict(Counter)
    class_doc_counts: Counter = Counter()
    vocab: set[str] = set()

    # 1. Latih dari kamus domain (bobot 3x agar fondasi stabil saat kartu masih sedikit)
    for branch, kws in lexicon.items():
        class_doc_counts[branch] += 3
        for kw in kws:
            for tok in expand_bilingual_tokens(tokenize(kw) or [kw.lower()]):
                class_word_counts[branch][tok] += 3
                vocab.add(tok)

    # 2. Latih otomatis dari koleksi kartu aktif pengguna (self-learning)
    if existing_cards:
        for c in existing_cards.values():
            if c.get("status") != "aktif":
                continue
            b = c.get("cabang") or ""
            if b not in lexicon:
                b = b.split("/")[0] if b.split("/")[0] in lexicon else ""
            if not b:
                continue
            class_doc_counts[b] += 1
            blob = f"{c.get('ide', '')} {c.get('penjelasan', '')} {' '.join(c.get('tag') or [])}"
            for tok in tokenize(blob):
                class_word_counts[b][tok] += 1
                vocab.add(tok)

    q_toks = expand_bilingual_tokens(tokenize(text))
    if not q_toks or not vocab:
        return []

    total_docs = sum(class_doc_counts.values()) or 1
    v_size = max(len(vocab), 1)
    q_tf = Counter(q_toks)
    results: list[tuple[str, float]] = []

    for branch in lexicon:
        prior = math.log((class_doc_counts[branch] + 0.5) / (total_docs + 0.5 * len(lexicon)))
        tot_w = sum(class_word_counts[branch].values())
        denom = tot_w + alpha * v_size
        log_prob = prior
        matched_any = False
        for w, cnt in q_tf.items():
            wc = class_word_counts[branch][w]
            if wc > 0:
                matched_any = True
            log_prob += cnt * math.log((wc + alpha) / denom)
        if matched_any:
            results.append((branch, round(log_prob, 4)))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


def infer_card_metadata_math(text: str, platform: str = "", url: str = "") -> dict:
    """
    Ekstraksi otomatis metadata kartu (jenis, dasar, kepercayaan, tahap, tag)
    berbasis sinyal statistik, linguistik, dan pola bukti — 0 biaya API.
    """
    low = (text or "").lower()
    url_low = (url or "").lower()

    # 1. Deteksi jenis kartu
    has_numbers = bool(re.search(r"\b\d+(?:[.,]\d+)?\s*(?:%|x|kali|jam|hr|hrs|juta|miliar|ribu|k|m|b|arr|mrr|\$|rp)\b", low))
    has_research = bool(re.search(r"\b(riset|research|study|studi|paper|jurnal|journal|meta-analysis|survei|survey|eksperimen|experiment|data|statistik|benchmark|doi)\b", low))
    has_advice = bool(re.search(r"\b(jangan|gunakan|mulai|hindari|pastikan|lakukan|tips|cara|langkah|stop|never|always|avoid|use|start|should|must|recommended)\b", low))
    has_story = bool(re.search(r"\b(saya dulu|pengalaman saya|bulan lalu|tahun lalu|waktu itu|i spent|months ago|years ago|a month ago|we built|we tried|i tried)\b", low))
    has_principle = bool(re.search(r"\b(hukum|prinsip|aturan|rumus|teori|law|principle|rule|math applies|queueing theory|pareto|compounding)\b", low))

    if has_numbers and (has_research or "%" in low or "x" in low):
        jenis = "data"
    elif has_principle:
        jenis = "prinsip"
    elif has_story:
        jenis = "kisah"
    elif has_advice:
        jenis = "nasihat"
    elif has_research:
        jenis = "fakta"
    else:
        jenis = "opini"

    # 2. Deteksi dasar & kepercayaan secara jujur (AGENTS.md Bagian 9)
    is_official = any(d in url_low for d in ("github.com", "arxiv.org", "nature.com", "pubmed", "docs.", "developers.google", "openai.com", "anthropic.com", "vercel.com"))
    if has_research or is_official:
        dasar = "riset"
        kepercayaan = "sedang" if platform.lower() in ("x", "threads", "instagram", "tiktok", "facebook") else "tinggi"
    elif has_story:
        dasar = "pengalaman-pribadi"
        kepercayaan = "sedang" if has_numbers else "belum-diverifikasi"
    elif has_principle or has_advice:
        dasar = "opini-umum"
        kepercayaan = "belum-diverifikasi"
    else:
        dasar = "tidak-jelas"
        kepercayaan = "belum-diverifikasi"

    # 3. Deteksi tahap hidup otomatis jika usia disebut jelas
    tahap = "semua-usia"
    if re.search(r"\b(sma|remaja|teen|sebelum 20|usia 1[5-9]|di bawah 20)\b", low):
        tahap = "sebelum-20"
    elif re.search(r"\b(20-25|usia 2[0-4]|umur 2[0-4]|early 20s|fresh graduate|kuliah|magang|internship|mahasiswa)\b", low):
        tahap = "20-25"
    elif re.search(r"\b(25-30|usia 2[5-9]|umur 2[5-9]|late 20s|quarter life)\b", low):
        tahap = "25-30"
    elif re.search(r"\b(30-40|usia 3\d|umur 3\d|30s|thirties|kepala tiga)\b", low):
        tahap = "30-40"
    elif re.search(r"\b(40-50|usia 4\d|umur 4\d|40s|forties|kepala empat)\b", low):
        tahap = "40-50"
    elif re.search(r"\b(50\+|usia 5\d|pensiun|retire|retirement|lansia)\b", low):
        tahap = "50+"

    # 4. Ekstraksi Top-4 Tag Domain otomatis berbasis frekuensi & bobot entropi kata
    toks = tokenize(text)
    freq = Counter(t for t in toks if len(t) >= 4 and not t.isdigit() and t not in SOCIAL_NOISE_TOKENS)
    auto_tags = [w for w, _ in freq.most_common(4)]

    return {
        "jenis": jenis,
        "dasar": dasar,
        "kepercayaan": kepercayaan,
        "tahap": tahap,
        "tags": auto_tags,
    }


def find_auto_relations(ide_text: str, penjelasan: str, existing_cards: dict[str, dict], limit: int = 2) -> list[dict]:
    """Temukan hingga 2 kartu tetangga paling mirip (Cosine TF-IDF >= 0.30) untuk relasi otomatis."""
    active = {cid: c for cid, c in existing_cards.items() if c.get("status") == "aktif"}
    if not active:
        return []
    vectors = build_tfidf(active)
    q_toks = tokenize(f"{ide_text} {penjelasan}")
    if not q_toks:
        return []
    tf = Counter(q_toks)
    norm = math.sqrt(sum((1.0 + math.log(v)) ** 2 for v in tf.values())) or 1.0
    q_vec = {w: (1.0 + math.log(v)) / norm for w, v in tf.items()}

    scored = []
    for cid, vec in vectors.items():
        sim = cosine_sim(q_vec, vec)
        if sim >= 0.20:
            scored.append((cid, sim))
    scored.sort(key=lambda x: x[1], reverse=True)
    rels = []
    for cid, sim in scored[:limit]:
        tipe = "memperkuat" if sim >= 0.42 else "terkait"
        rels.append({"tipe": tipe, "ke": cid, "skor": round(sim, 3)})
    return rels


def _is_mostly_non_indonesian(text: str) -> bool:
    """Deteksi cepat apakah teks dominan Inggris/Mandarin/non-Indonesia."""
    if re.search(r"[\u4e00-\u9fff\u3040-\u30ff]", text or ""):
        return True
    low = (text or "").lower()
    en_hits = len(re.findall(r"\b(the|and|your|that|with|this|from|have|about|people|system|because|without|when|more|than|sleep|work|time)\b", low))
    id_hits = len(re.findall(r"\b(yang|dan|untuk|dengan|dari|pada|adalah|tidak|bisa|akan|dalam|atau|juga|karena|saat|jika)\b", low))
    return en_hits >= 2 and en_hits > id_hits


def translate_and_polish_card_gemini(ide_text: str, penjelasan: str) -> tuple[str, str]:
    """
    Jika kartu hasil ekstraksi berbahasa asing (Inggris/Mandarin) dan GEMINI_API_KEY aktif,
    terjemahkan & rapikan menjadi Bahasa Indonesia alami (<1 detik, thinkingBudget: 0).
    Teks Asli di sumber/ tetap suci tidak pernah diubah.
    """
    if not _is_mostly_non_indonesian(f"{ide_text} {penjelasan}"):
        return ide_text, penjelasan
    local_env = load_local_env()
    api_key = (os.environ.get("GEMINI_API_KEY") or local_env.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        return ide_text, penjelasan

    prompt = (
        "Terjemahkan dan rapikan wawasan berikut ke Bahasa Indonesia yang jelas, natural, dan setia pada isi (jangan mengarang tambahan).\n"
        "Balas HANYA format JSON valid: {\"ide\": \"1-2 kalimat inti\", \"penjelasan\": \"2-4 kalimat penjelasan\"}.\n\n"
        f"IDE ASLI: {ide_text}\n"
        f"PENJELASAN ASLI: {penjelasan}"
    )
    for mdl in ("gemini-2.5-flash-lite", "gemini-2.5-flash"):
        try:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{mdl}:generateContent?key={api_key}"
            body = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 512, "thinkingConfig": {"thinkingBudget": 0}},
            }
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            cands = data.get("candidates") or []
            parts = ((cands[0].get("content") or {}).get("parts") or []) if cands else []
            raw = "".join(p.get("text", "") for p in parts).strip()
            m = re.search(r"\{[\s\S]*\}", raw)
            if m:
                parsed = json.loads(m.group(0))
                new_ide = str(parsed.get("ide") or "").strip().replace('"', "'")
                new_penj = str(parsed.get("penjelasan") or "").strip()
                if len(new_ide) >= 12:
                    return new_ide[:240], (new_penj or penjelasan)[:600]
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                continue
            break
        except Exception:
            break
    return ide_text, penjelasan


def query_relevant_cards(query: str, cards: dict[str, dict], limit: int = 80) -> list[dict]:
    """Pencarian Hibrida (RRF): gabungkan FTS5 BM25 + TF-IDF Cosine + ekspansi sinonim ID<->EN."""
    toks = tokenize(query)
    if not toks:
        toks = [w for w in re.findall(r"[a-z0-9]+", (query or "").lower()) if w not in STOPWORDS]
    expanded = expand_bilingual_tokens(toks)
    rrf_scores: dict[str, float] = {cid: 0.0 for cid in cards}
    k_rrf = 30.0

    # 1) Sinyal FTS5 BM25
    q_fts = " OR ".join(expanded[:12]) if expanded else ""
    if q_fts:
        try:
            for rank, row in enumerate(bp.search_fts(q_fts, limit=max(limit, 30)), start=1):
                cid = row["id"]
                if cid in rrf_scores:
                    rrf_scores[cid] += 1.0 / (k_rrf + rank)
        except Exception:
            pass

    # 2) Sinyal TF-IDF Cosine (hibrida leksikal)
    if expanded and cards:
        tfidf_vecs = build_tfidf(cards)
        q_tf: dict[str, float] = {}
        for t in expanded:
            q_tf[t] = q_tf.get(t, 0.0) + (1.0 if t in toks else 0.65)
        q_norm = math.sqrt(sum(v * v for v in q_tf.values())) or 1.0
        q_vec = {k: v / q_norm for k, v in q_tf.items()}
        cos_ranked = sorted(
            ((cid, cosine_sim(q_vec, vec)) for cid, vec in tfidf_vecs.items()),
            key=lambda x: -x[1],
        )
        for rank, (cid, sim) in enumerate(cos_ranked, start=1):
            if sim > 0.01:
                rrf_scores[cid] += 1.0 / (k_rrf + rank)

    # 3) Boost kecocokan frasa / token langsung
    low_q = (query or "").lower().strip()
    for cid, c in cards.items():
        blob = f"{c['ide']} {c['penjelasan']} {' '.join(c['tag'])} {c['cabang']} {' '.join(detect_tools_in_card(c))}".lower()
        if low_q and low_q in blob:
            rrf_scores[cid] += 0.08
        hits = sum(1 for t in toks if re.search(rf"\b{re.escape(t)}\b", blob))
        if hits:
            rrf_scores[cid] += 0.02 * hits

    ranked = [cid for cid, sc in sorted(rrf_scores.items(), key=lambda x: (-x[1], x[0])) if sc > 0]
    return [cards[cid] for cid in ranked[:limit]]


def analyze_compare(query: str) -> dict:
    """Bandingkan alat/model/metode untuk satu topik: kesamaan, perbedaan, peringkat transparan."""
    cards, sources, _ = load_active()
    rel_cards = query_relevant_cards(query, cards, limit=100)
    if not rel_cards:
        return {
            "query": query,
            "total_kartu": 0,
            "grup": [],
            "kesamaan": [],
            "pertentangan": [],
            "catatan": "Belum ada kartu yang cocok dengan kueri ini. Tangkap beberapa postingan terkait terlebih dahulu.",
        }

    vecs = build_tfidf({c["id"]: c for c in rel_cards})
    groups: dict[str, list[dict]] = defaultdict(list)
    for c in rel_cards:
        tools = detect_tools_in_card(c)
        if tools:
            for t in tools:
                groups[t].append(c)
        else:
            groups[c["cabang"]].append(c)

    # Hitung kata TF-IDF per grup untuk Kesamaan (konsensus) & Perbedaan (distinctive terms)
    group_terms: dict[str, Counter] = {}
    term_group_freq: Counter = Counter()
    for gname, gcards in groups.items():
        agg = Counter()
        for c in gcards:
            for w, val in vecs[c["id"]].items():
                agg[w] += val / max(len(gcards), 1)
        group_terms[gname] = agg
        for w in agg:
            term_group_freq[w] += 1

    # Kesamaan: kata kunci yang muncul di >= 2 grup berbeda (atau >=2 kartu jika cuma 1 grup)
    min_shared = 2 if len(groups) >= 2 else 1
    shared_scores = []
    for w, gcnt in term_group_freq.items():
        if gcnt >= min_shared:
            avg_w = sum(group_terms[g][w] for g in groups if w in group_terms[g]) / gcnt
            shared_scores.append((gcnt, avg_w, w))
    shared_scores.sort(key=lambda x: (-x[0], -x[1], x[2]))
    kesamaan = [w for _, _, w in shared_scores[:10]]

    # Skor dan keunggulan unik tiap alat/grup
    ranked_groups = []
    for gname, gcards in groups.items():
        src_set = {sid for c in gcards for sid in c["sumber"]}
        authors = {sources[sid]["penulis"] for sid in src_set if sid in sources}
        avg_trust = sum(TRUST_WEIGHT.get(c["kepercayaan"], 0.5) for c in gcards) / len(gcards)
        diterapkan = sum(1 for c in gcards if c["penerapan"] == "diterapkan")
        ditolak = sum(1 for c in gcards if c["penerapan"] == "ditolak")
        konflik = sum(1 for c in gcards if any(r["tipe"] == "bertentangan-dengan" for r in c["relasi"]))

        # Kalibrasi pribadi: kartu yang berhasil diterapkan menaikkan skor, yang ditolak menurunkan
        cal_bonus = 1.0 + (0.15 * diterapkan) - (0.20 * ditolak)
        cal_bonus = max(0.5, min(1.5, cal_bonus))
        conf_pen = 0.85 if konflik > 0 else 1.0
        # Skor transparan: kepercayaan * dukungan sumber * kalibrasi * penalti konflik
        skor = round(avg_trust * math.log2(1.0 + len(src_set)) * cal_bonus * conf_pen, 3)

        # Distinctive terms (perbedaan khas grup ini vs grup lain)
        others = [g for g in groups if g != gname]
        diff_scores = []
        for w, val in group_terms[gname].items():
            other_avg = (sum(group_terms[og].get(w, 0.0) for og in others) / len(others)) if others else 0.0
            diff = val - other_avg
            if diff > 0.02:
                diff_scores.append((diff, w))
        diff_scores.sort(reverse=True)
        ciri_khas = [w for _, w in diff_scores[:6]]

        ranked_groups.append({
            "nama": gname,
            "skor": skor,
            "jumlah_kartu": len(gcards),
            "jumlah_sumber": len(src_set),
            "jumlah_penulis": len(authors),
            "rata_kepercayaan": round(avg_trust, 2),
            "diterapkan": diterapkan,
            "ditolak": ditolak,
            "konflik": konflik,
            "ciri_khas": ciri_khas,
            "kartu": [{"id": c["id"], "ide": c["ide"], "kepercayaan": c["kepercayaan"], "penerapan": c["penerapan"]} for c in gcards[:8]],
            "alasan": f"kepercayaan={avg_trust:.2f} x log2(1+{len(src_set)} sumber) x kalibrasi={cal_bonus:.2f}" + (f" x konflik={conf_pen}" if konflik else ""),
        })

    ranked_groups.sort(key=lambda x: (-x["skor"], -x["jumlah_sumber"], x["nama"]))

    # Kumpulkan pertentangan eksplisit di antara kartu kandidat
    rel_set = {c["id"] for c in rel_cards}
    pertentangan = []
    seen_pairs = set()
    for c in rel_cards:
        for r in c["relasi"]:
            if r["tipe"] == "bertentangan-dengan" and r["ke"] in rel_set:
                pair = tuple(sorted((c["id"], r["ke"])))
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    pertentangan.append({"a": pair[0], "b": pair[1], "ide_a": cards[pair[0]]["ide"], "ide_b": cards[pair[1]]["ide"]})

    total_src = len({sid for c in rel_cards for sid in c["sumber"]})
    catatan = (
        f"Data masih awal ({len(rel_cards)} kartu dari {total_src} sumber). Kesimpulan peringkat bersifat sementara sampai terkumpul >=3 sumber independen per alat."
        if total_src < 3 else
        f"Dihitung dari {len(rel_cards)} kartu lintas {total_src} sumber independen."
    )
    return {
        "query": query,
        "total_kartu": len(rel_cards),
        "total_sumber": total_src,
        "grup": ranked_groups,
        "kesamaan": kesamaan,
        "pertentangan": pertentangan,
        "catatan": catatan,
    }


def analyze_playbook(topic: str) -> dict:
    """Susun alur kerja 6 tahap dari awal sampai akhir + identifikasi celah pengetahuan."""
    cards, _, _ = load_active()
    rel_cards = query_relevant_cards(topic, cards, limit=120)
    buckets: dict[str, list[dict]] = {k: [] for k, _, _ in WORKFLOW_STAGES}

    for c in rel_cards:
        st = detect_workflow_stage(c)
        trust = TRUST_WEIGHT.get(c["kepercayaan"], 0.5)
        st_w = 1.25 if c["penerapan"] == "diterapkan" else (0.5 if c["penerapan"] == "ditolak" else 1.0)
        src_boost = 1.0 + 0.15 * max(0, len(c["sumber"]) - 1)
        priority = round(trust * st_w * src_boost, 3)
        buckets[st].append({
            "id": c["id"],
            "ide": c["ide"],
            "cabang": c["cabang"],
            "kepercayaan": c["kepercayaan"],
            "penerapan": c["penerapan"],
            "alat": detect_tools_in_card(c),
            "konflik": any(r["tipe"] == "bertentangan-dengan" for r in c["relasi"]),
            "prioritas": priority,
        })

    tahapan = []
    celah = []
    for key, label, _ in WORKFLOW_STAGES:
        items = sorted(buckets[key], key=lambda x: (-x["prioritas"], x["id"]))
        if not items:
            celah.append(label)
        tahapan.append({"kode": key, "label": label, "jumlah": len(items), "kartu": items[:10]})

    return {
        "topik": topic,
        "total_kartu": len(rel_cards),
        "tahapan": tahapan,
        "celah": celah,
    }


def analyze_trends() -> dict:
    """Radar big data: alat, bidang dominan, konflik, dan adopsi di seluruh perpustakaan."""
    cards, sources, _ = load_active()
    tool_counts: Counter = Counter()
    domain_counts: Counter = Counter()
    stage_counts: Counter = Counter()
    for c in cards.values():
        domain_counts[c["bidang"]] += 1
        stage_counts[detect_workflow_stage(c)] += 1
        for t in detect_tools_in_card(c):
            tool_counts[t] += 1

    dominan = ["ai", "bisnis", "sosmed", "digital-marketing"]
    dom_total = sum(domain_counts[d] for d in dominan)
    return {
        "total_kartu": len(cards),
        "total_sumber": len(sources),
        "porsi_4_bab_dominan": round((dom_total / max(len(cards), 1)) * 100, 1),
        "bidang": [{"nama": k, "jumlah": v} for k, v in domain_counts.most_common()],
        "alat_teratas": [{"nama": k, "jumlah": v} for k, v in tool_counts.most_common(15)],
        "tahap_kerja": [{"kode": k, "label": lbl, "jumlah": stage_counts[k]} for k, lbl, _ in WORKFLOW_STAGES],
    }


def cmd_bandingkan(query: str) -> int:
    res = analyze_compare(query)
    print(f"=== PERBANDINGAN ALAT / METODE: '{res['query']}' ({res['total_kartu']} kartu) ===")
    print(f"Catatan: {res['catatan']}")
    if res["kesamaan"]:
        print(f"Kesamaan (konsensus lintas sumber/alat): {', '.join(res['kesamaan'])}")
    for idx, g in enumerate(res["grup"], 1):
        print(f"\n{idx}. [{g['nama']}] skor={g['skor']} ({g['jumlah_kartu']} kartu, {g['jumlah_sumber']} sumber, diterapkan={g['diterapkan']}, ditolak={g['ditolak']})")
        print(f"   Alasan   : {g['alasan']}")
        if g["ciri_khas"]:
            print(f"   Ciri khas: {', '.join(g['ciri_khas'])}")
        for k in g["kartu"][:4]:
            print(f"   - {k['id']} [{k['kepercayaan']} | {k['penerapan']}]: {k['ide']}")
    if res["pertentangan"]:
        print("\nPertentangan terbuka:")
        for p in res["pertentangan"]:
            print(f"  - {p['a']} vs {p['b']}")
    return 0


def cmd_playbook(topic: str) -> int:
    res = analyze_playbook(topic)
    print(f"=== PLAYBOOK ALUR KERJA AWAL -> AKHIR: '{res['topik']}' ({res['total_kartu']} kartu relevan) ===")
    for t in res["tahapan"]:
        print(f"\n{t['label']} ({t['jumlah']} kartu)")
        if not t["kartu"]:
            print("  (Celah pengetahuan — belum ada kartu pada tahap ini)")
        for k in t["kartu"][:5]:
            alat_s = f" | alat: {', '.join(k['alat'])}" if k["alat"] else ""
            print(f"  - {k['id']} [prio={k['prioritas']} | {k['kepercayaan']}{alat_s}]: {k['ide']}")
    if res["celah"]:
        print(f"\nCelah yang perlu dilengkapi: {', '.join(res['celah'])}")
    return 0


def cmd_tren() -> int:
    res = analyze_trends()
    print(f"=== RADAR BIG DATA POHON PENGETAHUAN ({res['total_kartu']} kartu, {res['total_sumber']} sumber) ===")
    print(f"Porsi 4 Bab Dominan (AI, Bisnis, Sosmed, Digital Marketing): {res['porsi_4_bab_dominan']}%")
    print("\nDistribusi Bidang:")
    for b in res["bidang"]:
        print(f"  - {b['nama']}: {b['jumlah']} kartu")
    print("\nAlat / Model Paling Banyak Dibahas:")
    for a in res["alat_teratas"]:
        print(f"  - {a['nama']}: {a['jumlah']} kartu")
    print("\nCakupan 6 Tahap Alur Kerja:")
    for s in res["tahap_kerja"]:
        print(f"  - {s['label']}: {s['jumlah']} kartu")
    return 0


def cmd_ringkas() -> int:
    cmd_tren()
    print()
    cmd_ulasan(limit=5)
    print()
    cmd_saran(limit=5)
    print()
    cmd_gema()
    print()
    cmd_fondasi(limit=5)
    return 0


# ======================== 9. TANYA POHON (LEVEL 1 SINTESIS LOKAL + LEVEL 2 GEMINI RAG) ========================

def load_local_env() -> dict[str, str]:
    env_vars: dict[str, str] = {}
    env_fp = ROOT / ".env"
    if env_fp.is_file():
        for ln in env_fp.read_text(encoding="utf-8", errors="ignore").splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#") or "=" not in ln:
                continue
            k, v = ln.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k:
                env_vars[k] = v
    return env_vars


SYNTAX_QUERY_CUES = {
    "susunan", "tatanan", "kata", "kalimat", "hook", "viral", "rame", "ramai",
    "copywriting", "pola", "struktur", "pembuka", "rahasia", "gaya", "bahasa", "diksinya",
}


def is_syntax_or_viral_query(question: str) -> bool:
    low = (question or "").lower()
    hits = sum(1 for w in SYNTAX_QUERY_CUES if w in low)
    return hits >= 2 or any(p in low for p in ("susunan kata", "tatanan kata", "kenapa rame", "kenapa viral", "rahasia konten"))


def analyze_viral_syntax(cards: dict[str, dict], sources: dict[str, dict], question: str = "") -> dict:
    """
    Analisis Linguistik & Anatomi Tatanan Kata (0 Biaya) langsung dari korpus Akar (sumber) & Daun (kartu):
      1. Pola Kalimat Pembuka (Opening Hook Archetypes: Kuantifikasi/Angka, Imperatif/Aksi, Bukti/Praktek, Kontras/Masalah)
      2. Ritme & Burstiness Kalimat (rata-rata kata per kalimat & simpangan baku panjang kalimat)
      3. Struktur Visual (panah alur '>', daftar bernomor/bullet, kepadatan angka)
      4. Kata & Frasa Pemicu (Unigram & Bigram ber-TF/PMI tertinggi)
    """
    low_q = (question or "").lower()
    target_bidang = ""
    for b in ("ai", "keuangan", "sosmed", "bisnis", "kesehatan", "motivasi-dan-mindset", "digital-marketing"):
        if re.search(rf"\b{re.escape(b)}\b", low_q):
            target_bidang = b
            break

    active_cards = [c for c in cards.values() if c.get("status") == "aktif"]
    if target_bidang:
        dom_cards = [c for c in active_cards if c.get("bidang") == target_bidang or c.get("cabang", "").startswith(target_bidang + "/")]
    else:
        dom_cards = []
    target_cards = dom_cards if len(dom_cards) >= 2 else active_cards

    used_sids = {sid for c in target_cards for sid in c.get("sumber", []) if sid in sources}
    target_sources = [sources[sid] for sid in sorted(used_sids)] if used_sids else list(sources.values())

    hook_patterns = {
        "angka_kuantifikasi": [],      # mis: "5 skills...", "30 skills + 4 live MCP", "$99", "29, looking back at 25"
        "bukti_praktisi": [],          # mis: "Open-sourced my full...", "Pro-tip: ketika bikin app", "Sudah terbukti..."
        "imperatif_pendek": [],        # mis: "Take care of your appearance. Lift the weights."
        "alur_panah_atau_list": [],    # mis: "the play: A > B > C", "1. ... 2. ... 3. ..."
    }

    sent_lengths: list[int] = []
    unigram_freq: dict[str, int] = {}
    bigram_freq: dict[str, int] = {}
    sample_hooks: list[str] = []

    for c in target_cards:
        cid = c["id"]
        sid = (c.get("sumber") or [""])[0]
        raw_src = (sources.get(sid, {}).get("teks_asli") or c.get("penjelasan") or c.get("ide") or "").strip()
        first_line = next((ln.strip() for ln in raw_src.splitlines() if ln.strip()), c["ide"])
        sample_hooks.append(f"[{cid}] \"{first_line[:95]}\"")

        if re.search(r"(\b\d+\b|\$\d+|\d+%|\d+x\b)", first_line.lower()):
            hook_patterns["angka_kuantifikasi"].append(cid)
        if re.search(r"\b(open-sourced|pro-tip|actually use|sudah terbukti|how to|cara|strategi|the play)\b", raw_src.lower()):
            hook_patterns["bukti_praktisi"].append(cid)
        if re.search(r"(>|→|\n\s*[-•1-9][.)]?\s+)", raw_src):
            hook_patterns["alur_panah_atau_list"].append(cid)

        sents = [s.strip() for s in re.split(r"[.!?\n]+", raw_src) if len(s.strip().split()) >= 2]
        for s in sents:
            w_cnt = len(s.split())
            sent_lengths.append(w_cnt)
        if sents and sum(len(s.split()) for s in sents[:2]) / min(2, len(sents)) <= 9:
            hook_patterns["imperatif_pendek"].append(cid)

        toks = [t for t in tokenize(f"{c['ide']} {raw_src}") if len(t) >= 3 and not t.isdigit()]
        for t in toks:
            unigram_freq[t] = unigram_freq.get(t, 0) + 1
        for i in range(len(toks) - 1):
            bg = f"{toks[i]} {toks[i+1]}"
            bigram_freq[bg] = bigram_freq.get(bg, 0) + 1

    n_cards = max(1, len(target_cards))
    avg_len = round(sum(sent_lengths) / max(1, len(sent_lengths)), 1)
    std_len = round(math.sqrt(sum((x - avg_len) ** 2 for x in sent_lengths) / max(1, len(sent_lengths))), 1)

    top_words = [w for w, _ in sorted(unigram_freq.items(), key=lambda x: (-x[1], x[0]))[:10]]
    top_bigrams = [bg for bg, cnt in sorted(bigram_freq.items(), key=lambda x: (-x[1], x[0]))[:6] if cnt >= 2]

    scope_label = f"topik '{target_bidang}'" if (target_bidang and dom_cards) else "seluruh catatan Anda"
    lines = [
        f"Hasil Bedah Susunan Kata dari Koleksi Anda ({len(target_cards)} kartu / {len(target_sources)} sumber pada {scope_label}):",
        "",
        "1. Empat Kebiasaan Kalimat Pembuka (Hook) yang Membuat Postingan Ramai:",
        f"• Membuka dengan Angka Nyata ({len(hook_patterns['angka_kuantifikasi'])} dari {n_cards} kartu — {', '.join(hook_patterns['angka_kuantifikasi'][:5]) or '-'}): langsung menyebut angka di baris pertama (jumlah langkah/skill, harga $, persentase, atau usia) supaya pembaca langsung percaya.",
        f"• Menunjukkan Bukti Praktek Sendiri ({len(hook_patterns['bukti_praktisi'])} dari {n_cards} kartu — {', '.join(hook_patterns['bukti_praktisi'][:5]) or '-'}): memakai kalimat pengalaman nyata seperti 'Open-sourced my full...', 'Pro-tip: ketika bikin app...', 'the play:', atau 'Sudah terbukti...'.",
        f"• Memakai Panah Alur ('>') atau Daftar Bernomor ({len(hook_patterns['alur_panah_atau_list'])} dari {n_cards} kartu — {', '.join(hook_patterns['alur_panah_atau_list'][:5]) or '-'}): meringkas proses rumit jadi panah ('Langkah A > Langkah B > Langkah C') atau poin 1-2-3 agar enak dibaca cepat.",
        f"• Kalimat Pendek & Langsung ke Inti ({len(hook_patterns['imperatif_pendek'])} dari {n_cards} kartu — {', '.join(hook_patterns['imperatif_pendek'][:5]) or '-'}): kalimat pembuka hanya 3–7 kata tanpa basa-basi.",
        "",
        "2. Panjang Kalimat & Kata yang Paling Sering Muncul:",
        f"• Rata-rata panjang kalimat: sekitar {avg_len} kata per kalimat (variasi ±{std_len} kata — artinya kalimat pembukanya sangat pendek, lalu diikuti poin penjelasan padat).",
        f"• Kata yang paling sering dipakai: {', '.join(top_words) if top_words else '-'}.",
    ]
    if top_bigrams:
        lines.append(f"• Pasangan 2-kata yang sering berulang: {', '.join(top_bigrams)}.")

    lines.extend([
        "",
        "3. Contoh Kalimat Pembuka Asli di Koleksi Anda:",
        *[f"  - {h}" for h in sample_hooks[:5]],
        "",
        "4. Tiga Pola Kalimat (Template) yang Bisa Langsung Anda Tiru:",
        "  • Pola 1 (Bukti + Angka): \"[Hasil/Proyek yang saya buka] [Angka] [Alat/Skill] yang saya pakai setiap hari untuk [Manfaat]\" (contoh: " + (", ".join(hook_patterns["angka_kuantifikasi"][:2]) or "K-0003, K-0005") + ")",
        "  • Pola 2 (Panah Strategi '>'): \"Strateginya: [Langkah 1] > [Langkah 2] > [Langkah 3] — ini 3 hal yang paling berpengaruh:\" (contoh: " + (", ".join(hook_patterns["alur_panah_atau_list"][:2]) or "K-0011") + ")",
        "  • Pola 3 (Tips Praktisi): \"Tips penting saat [Mengerjakan X]: jangan langsung [Kesalahan umum], tapi siapkan [Langkah kunci] dulu\" (contoh: " + (", ".join(hook_patterns["bukti_praktisi"][:2]) or "K-0002") + ")",
    ])

    return {
        "teks": "\n".join(lines),
        "kartu": target_cards[:8],
    }


def build_level1_answer(question: str, rel_cards: list[dict], cards: dict[str, dict]) -> tuple[str, list[dict]]:
    if not rel_cards:
        return (
            f"Belum ditemukan kartu yang cocok dengan pertanyaan \"{question}\" di Pohon Pengetahuan.\n"
            "Saran: coba kata kunci lain atau tangkap sumber terkait terlebih dahulu.",
            [],
        )

    lines = [f"Ringkasan dari {len(rel_cards)} kartu relevan (Mode Sintesis Lokal — tanpa LLM):"]
    konflik_list = []
    seen_pairs = set()
    low_trust = []

    for c in rel_cards[:5]:
        lines.append(f"• [{c['id']}] {c['ide']} ({c['cabang']} · kepercayaan: {c['kepercayaan']})")
        if c["kepercayaan"] in ("rendah", "belum-diverifikasi"):
            low_trust.append(c["id"])
        for r in c.get("relasi", []):
            if r.get("tipe") == "bertentangan-dengan" and r.get("ke") in cards:
                pair = tuple(sorted((c["id"], r["ke"])))
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    konflik_list.append({"a": pair[0], "b": pair[1]})

    if konflik_list:
        lines.append("\nPertentangan terbuka:")
        for kf in konflik_list:
            lines.append(f"- [{kf['a']}] vs [{kf['b']}]")
    if low_trust:
        lines.append(f"\nCatatan kualitas: {', '.join(low_trust)} masih berkepercayaan rendah/belum diverifikasi.")
    lines.append("\nTips: untuk kesimpulan naratif yang berpikir dan menyintesis seperti ChatGPT, isi GEMINI_API_KEY gratis di file .env lalu restart server.")
    return "\n".join(lines), konflik_list


def call_gemini_rag(question: str, rel_cards: list[dict], api_key: str, preferred_model: str) -> tuple[str | None, str, str]:
    context_items = []
    for c in rel_cards:
        context_items.append(
            f"[{c['id']}] cabang={c['cabang']} | tahap={c['tahap']} | kepercayaan={c['kepercayaan']} | dasar={c['dasar']}\n"
            f"Ide: {c['ide']}\n"
            f"Penjelasan: {(c.get('penjelasan') or '')[:450]}"
        )
    system_prompt = (
        "Kamu adalah asisten Pohon Pengetahuan. Jawab pertanyaan pengguna HANYA berdasarkan KARTU WAWASAN berikut. "
        "Wajib cantumkan ID kartu seperti [K-0001] pada setiap poin. Jangan mengarang; jika tidak cukup bukti di kartu, "
        "katakan terus terang. Sebutkan tingkat kepercayaan atau pertentangan bila ada. Jawab ringkas dan langsung ke inti dalam Bahasa Indonesia."
    )
    user_prompt = f"KARTU WAWASAN:\n\n" + "\n\n---\n\n".join(context_items) + f"\n\nPERTANYAAN PENGGUNA:\n{question}"

    models_to_try = [preferred_model]
    if preferred_model != "gemini-2.5-flash":
        models_to_try.append("gemini-2.5-flash")

    last_err = ""
    for mdl in models_to_try:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{mdl}:generateContent?key={api_key}"
        body = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096},
        }
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                cands = data.get("candidates") or []
                parts = ((cands[0].get("content") or {}).get("parts") or []) if cands else []
                text = "\n".join(p.get("text", "") for p in parts if p.get("text")).strip()
                if text:
                    return text, mdl, ""
                last_err = "Respon model kosong"
        except urllib.error.HTTPError as exc:
            last_err = f"HTTP {exc.code}"
            if exc.code == 404:
                continue
            break
        except Exception as exc:
            last_err = str(exc)
            break
    return None, preferred_model, last_err


def answer_question(question: str) -> dict:
    cards, sources, _ = load_active()
    syntax_mode = is_syntax_or_viral_query(question)
    syntax_report = analyze_viral_syntax(cards, sources, question) if syntax_mode else None

    rel_cards = query_relevant_cards(question, cards, limit=8)
    if syntax_report and len(rel_cards) < 4:
        seen_ids = {c["id"] for c in rel_cards}
        for sc in syntax_report["kartu"]:
            if sc["id"] not in seen_ids:
                rel_cards.append(sc)
                seen_ids.add(sc["id"])

    if syntax_report:
        level1_text = syntax_report["teks"]
        konflik_list = []
    else:
        level1_text, konflik_list = build_level1_answer(question, rel_cards, cards)

    rujukan = [
        {"id": c["id"], "ide": c["ide"], "cabang": c["cabang"], "kepercayaan": c["kepercayaan"]}
        for c in rel_cards[:8]
    ]

    local_env = load_local_env()
    api_key = (os.environ.get("GEMINI_API_KEY") or local_env.get("GEMINI_API_KEY") or "").strip()
    model_name = (os.environ.get("GEMINI_MODEL") or local_env.get("GEMINI_MODEL") or "gemini-2.5-flash-lite").strip()

    if api_key and rel_cards:
        q_for_llm = f"{question}\n\nDATA ANALISIS LINGUISTIK KORPUS:\n{syntax_report['teks']}" if syntax_report else question
        ai_text, used_model, err = call_gemini_rag(q_for_llm, rel_cards, api_key, model_name)
        if ai_text:
            return {
                "ok": True,
                "mode": f"ai-rag ({used_model})",
                "jawaban": ai_text,
                "rujukan": rujukan,
                "pertentangan": konflik_list,
            }
        return {
            "ok": True,
            "mode": "sintesis-lokal (cadangan)",
            "jawaban": level1_text,
            "rujukan": rujukan,
            "pertentangan": konflik_list,
            "info": f"Gemini API tidak merespons ({err}); menampilkan sintesis lokal.",
        }

    return {
        "ok": True,
        "mode": "sintesis-linguistik-lokal" if syntax_report else "sintesis-lokal",
        "jawaban": level1_text,
        "rujukan": rujukan,
        "pertentangan": konflik_list,
    }


SOCIAL_NOISE_TOKENS = {
    "like", "follow", "retweet", "repost", "subscribe", "share", "comment", "komentar",
    "link", "bio", "dm", "giveaway", "thread", "bookmark", "save", "simpan", "halo",
    "guys", "teman", "cek", "klik", "click", "join", "telegram", "discord", "whatsapp",
}


def split_clean_sentences(raw_text: str) -> list[str]:
    """Pecah teks/transkrip menjadi kalimat bersih untuk diproses TextTiling, Entropi, LexRank & MMR."""
    cleaned = re.sub(r"\r\n", "\n", raw_text or "").strip()
    raw_chunks = re.split(r"(?:\n+)|(?<=[.!?।。！？])\s+", cleaned)
    sents: list[str] = []
    for ch in raw_chunks:
        s = re.sub(r"^\s*(?:[-*•>#]+|\d+[.)])\s*", "", ch).strip()
        s = re.sub(r"\s+", " ", s).strip("[]")
        if s.startswith("Ekstraksi Otomatis Tautan Terlampir:") or s.startswith("--- Ekstraksi Otomatis"):
            continue
        if len(s) >= 22 and len(s.split()) >= 4:
            sents.append(s)
    return sents


def sentence_info_entropy(s: str) -> float:
    """
    Teori Informasi (Shannon Entropy & Penalti KL-Divergence terhadap korpus basa-basi sosmed):
      H(s) = - sum p(w) log2 p(w) * (1 - noise_ratio)
    Kalimat clickbait/basa-basi ('jangan lupa like & follow', 'thread 🧵') otomatis mendapat skor mendekati 0.
    """
    all_words = re.findall(r"[a-z0-9\u4e00-\u9fff]+", s.lower())
    if not all_words:
        return 0.0
    noise_hits = sum(1 for w in all_words if w in SOCIAL_NOISE_TOKENS)
    noise_ratio = noise_hits / len(all_words)
    if noise_ratio >= 0.35:
        return 0.05

    toks = tokenize(s)
    if not toks:
        toks = all_words
    n = len(toks)
    freq: dict[str, int] = {}
    for t in toks:
        freq[t] = freq.get(t, 0) + 1
    entropy = -sum((cnt / n) * math.log2(cnt / n) for cnt in freq.values())
    # Bonus kecil untuk kepadatan informasi (angka, istilah teknis) & penalti noise
    info_density = min(1.3, len(freq) / max(1, len(all_words)) + 0.35)
    return round(max(0.05, entropy * info_density * (1.0 - 0.8 * noise_ratio)), 4)


def text_tiling_segments(sentences: list[str], window: int = 2) -> list[int]:
    """
    TextTiling (Hearst Semantic Boundary Detection):
    Hitung kemiripan kosinus antar blok kalimat berurutan B_t dan B_{t+1},
    cari lembah lokal (depth score), dan beri nomor segmen topik untuk tiap kalimat.
    """
    n = len(sentences)
    if n <= 3:
        return [0] * n
    w = max(1, min(window, n // 2))
    block_vecs: list[dict[str, float]] = []
    for i in range(n):
        chunk = " ".join(sentences[max(0, i - w + 1): min(n, i + w)])
        tf: dict[str, float] = {}
        for t in expand_bilingual_tokens(tokenize(chunk)):
            tf[t] = tf.get(t, 0.0) + 1.0
        norm = math.sqrt(sum(v * v for v in tf.values())) or 1.0
        block_vecs.append({k: v / norm for k, v in tf.items()})

    sims = [cosine_sim(block_vecs[i], block_vecs[i + 1]) for i in range(n - 1)]
    mean_sim = sum(sims) / max(1, len(sims))
    std_sim = math.sqrt(sum((x - mean_sim) ** 2 for x in sims) / max(1, len(sims)))
    threshold = max(0.08, mean_sim - 0.55 * std_sim)

    seg_ids = [0] * n
    cur_seg = 0
    for i, sim_val in enumerate(sims):
        if sim_val < threshold and (i > 0):
            cur_seg += 1
        seg_ids[i + 1] = cur_seg
    return seg_ids


def lexrank_scores(sentences: list[str], d: float = 0.85, iters: int = 25) -> tuple[list[float], list[dict[str, float]]]:
    """
    LexRank / TextRank (Eigenvector Centrality via Power Iteration):
      PR(s_i) = (1 - d)/N + d * sum_{j != i} (W_{ji} / sum_k W_{jk}) * PR(s_j)
    Dikombinasikan dengan bobot prior Shannon Entropy H(s_i).
    """
    n = len(sentences)
    if n == 0:
        return [], []
    df: dict[str, int] = {}
    sent_tfs: list[dict[str, int]] = []
    for s in sentences:
        toks = expand_bilingual_tokens(tokenize(s))
        if not toks:
            toks = re.findall(r"[a-z0-9\u4e00-\u9fff]+", s.lower())
        tf: dict[str, int] = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        sent_tfs.append(tf)
        for t in tf:
            df[t] = df.get(t, 0) + 1

    vecs: list[dict[str, float]] = []
    for tf in sent_tfs:
        w_vec = {t: cnt * (math.log((n + 1) / (df[t] + 1)) + 1.0) for t, cnt in tf.items()}
        norm = math.sqrt(sum(v * v for v in w_vec.values())) or 1.0
        vecs.append({t: v / norm for t, v in w_vec.items()})

    if n == 1:
        return [1.0], vecs

    entropies = [sentence_info_entropy(s) for s in sentences]
    tot_ent = sum(entropies) or 1.0
    priors = [e / tot_ent for e in entropies]

    adj: list[list[float]] = [[0.0] * n for _ in range(n)]
    out_sum = [0.0] * n
    for i in range(n):
        for j in range(i + 1, n):
            sim = cosine_sim(vecs[i], vecs[j])
            if sim > 0.02:
                adj[i][j] = sim
                adj[j][i] = sim
                out_sum[i] += sim
                out_sum[j] += sim

    scores = list(priors)
    for _ in range(iters):
        nxt = [(1.0 - d) * priors[i] for i in range(n)]
        dangling = sum(scores[j] for j in range(n) if out_sum[j] == 0)
        for i in range(n):
            nxt[i] += d * dangling * priors[i]
            for j in range(n):
                if adj[j][i] > 0 and out_sum[j] > 0:
                    nxt[i] += d * scores[j] * (adj[j][i] / out_sum[j])
        scores = nxt

    max_sc = max(scores) or 1.0
    return [round(sc / max_sc, 4) for sc in scores], vecs


def mmr_select(
    sentences: list[str],
    lex_scores: list[float],
    vecs: list[dict[str, float]],
    seg_ids: list[int],
    k: int = 5,
    lambda_param: float = 0.72,
) -> list[int]:
    """
    Maximal Marginal Relevance (MMR):
      MMR = argmax_{i in R \\ S} [ lambda * LexRank(s_i) - (1 - lambda) * max_{j in S} cos(s_i, s_j) ]
    Memilih hingga k poin inti (Daun) yang paling sentral namun bebas duplikasi ide.
    """
    n = len(sentences)
    if n == 0:
        return []
    target_k = max(1, min(k, n))
    selected: list[int] = []
    used_segs: set[int] = set()
    candidates = set(range(n))

    while candidates and len(selected) < target_k:
        best_idx = -1
        best_mmr = -1e9
        for idx in candidates:
            rel = lex_scores[idx]
            # Bonus diversitas segmen TextTiling agar tiap segmen topik terwakili
            seg_bonus = 0.08 if seg_ids[idx] not in used_segs else 0.0
            max_sim = max((cosine_sim(vecs[idx], vecs[j]) for j in selected), default=0.0)
            # Tolak kalimat yang terlalu mirip (>0.68) dengan poin yang sudah terpilih
            if selected and max_sim > 0.68:
                continue
            mmr_val = lambda_param * (rel + seg_bonus) - (1.0 - lambda_param) * max_sim
            if mmr_val > best_mmr:
                best_mmr = mmr_val
                best_idx = idx
        if best_idx == -1:
            break
        selected.append(best_idx)
        used_segs.add(seg_ids[best_idx])
        candidates.remove(best_idx)

    return sorted(selected)


def extract_atomic_insights_math(raw_text: str, max_cards: int = 5) -> list[dict]:
    """
    Pipeline Matematika Utuh (Akar -> Daun, 0 Biaya):
      1. Split & Shannon Entropy Filter (buang basa-basi/clickbait sosmed)
      2. TextTiling (deteksi batas pergantian topik)
      3. LexRank Eigenvector Centrality (temukan kalimat paling inti)
      4. Maximal Marginal Relevance / MMR (pilih 1..k poin atomik bebas redundansi)
    """
    sents = split_clean_sentences(raw_text)
    if not sents:
        fallback = re.sub(r"\s+", " ", (raw_text or "").strip())[:220]
        return [{
            "ide": fallback or "Catatan baru",
            "penjelasan": re.sub(r"\s+", " ", (raw_text or "").strip())[:520],
            "kutipan": fallback[:240],
            "entropi": 1.0,
            "lexrank": 1.0,
            "segmen": 0,
            "alat": [],
            "tahap_kerja": "riset",
        }]

    # Filter kalimat basa-basi dengan Shannon Entropy
    scored_sents = [(s, sentence_info_entropy(s)) for s in sents]
    filtered = [(s, ent) for s, ent in scored_sents if ent >= 0.35] or scored_sents
    clean_sents = [s for s, _ in filtered]
    ent_map = [ent for _, ent in filtered]

    seg_ids = text_tiling_segments(clean_sents)
    lex_sc, vecs = lexrank_scores(clean_sents)

    # Tentukan jumlah Daun (kartu) proporsional terhadap panjang & keragaman segmen
    distinct_segs = len(set(seg_ids))
    auto_k = 1 if len(clean_sents) <= 3 else min(max_cards, max(2, min(distinct_segs + 1, (len(clean_sents) + 2) // 3)))
    chosen_indices = mmr_select(clean_sents, lex_sc, vecs, seg_ids, k=min(max_cards, auto_k))

    results: list[dict] = []
    for idx in chosen_indices:
        core_sent = clean_sents[idx]
        # Ambil kalimat konteks tetangga dalam segmen TextTiling yang sama untuk penjelasan
        context_sents = [core_sent]
        if idx + 1 < len(clean_sents) and seg_ids[idx + 1] == seg_ids[idx] and (idx + 1) not in chosen_indices:
            context_sents.append(clean_sents[idx + 1])
        elif idx - 1 >= 0 and seg_ids[idx - 1] == seg_ids[idx] and (idx - 1) not in chosen_indices:
            context_sents.insert(0, clean_sents[idx - 1])

        ide_text = core_sent.replace('"', "'")[:220]
        penjelasan = " ".join(context_sents)[:520]
        dummy = {"ide": ide_text, "penjelasan": penjelasan, "tag": [], "cabang": "", "alat": [], "tugas": "", "tahap_kerja": ""}
        results.append({
            "ide": ide_text,
            "penjelasan": penjelasan,
            "kutipan": core_sent[:260],
            "entropi": ent_map[idx],
            "lexrank": lex_sc[idx],
            "segmen": seg_ids[idx],
            "alat": detect_tools_in_card(dummy),
            "tahap_kerja": detect_workflow_stage(dummy),
        })
    return results


def compute_hits_akar_daun(cards: dict[str, dict], sources: dict[str, dict], iters: int = 20) -> dict:
    """
    Algoritma HITS (Kleinberg Hubs & Authorities) pada Graf Bipartit Akar (Sumber) -> Daun (Kartu):
      - Hub Score h(S) = Kesuburan Akar (seberapa banyak Daun bermutu/berbintang/diterapkan yang lahir dari sumber S)
      - Authority Score a(K) = Kematangan Daun (kekuatan kartu K ditopang Akar subur & dirujuk kartu lain)
    """
    active = {cid: c for cid, c in cards.items() if c.get("status") == "aktif"}
    if not active:
        return {"akar_subur": [], "daun_matang": []}

    trust_w = {"tinggi": 1.6, "sedang": 1.25, "rendah": 0.85, "belum-diverifikasi": 0.75}
    pen_w = {"diterapkan": 1.8, "sedang-dicoba": 1.25, "belum-dicoba": 1.0, "ditolak": 0.45}

    card_prior: dict[str, float] = {}
    for cid, c in active.items():
        stars = int(c.get("bintang", 0) or 0)
        tw = trust_w.get(c.get("kepercayaan", ""), 0.8)
        pw = pen_w.get(c.get("penerapan", ""), 1.0)
        card_prior[cid] = round(tw * pw * (1.0 + 0.25 * stars), 4)

    hubs: dict[str, float] = {sid: 1.0 for sid in sources}
    auths: dict[str, float] = {cid: card_prior[cid] for cid in active}

    for _ in range(iters):
        # Update Authority (Daun) dari Hub (Akar) + relasi masuk antar kartu
        new_auths: dict[str, float] = {}
        for cid, c in active.items():
            src_sum = sum(hubs.get(sid, 0.5) for sid in c.get("sumber", []))
            rel_sum = sum(auths.get(r["ke"], 0.0) * 0.35 for r in c.get("relasi", []) if r.get("ke") in active)
            new_auths[cid] = card_prior[cid] * (src_sum + rel_sum + 0.2)
        norm_a = math.sqrt(sum(v * v for v in new_auths.values())) or 1.0
        auths = {k: v / norm_a for k, v in new_auths.items()}

        # Update Hub (Akar) dari Authority (Daun) yang dilahirkannya
        new_hubs: dict[str, float] = {}
        for sid in sources:
            born_cards = [cid for cid, c in active.items() if sid in c.get("sumber", [])]
            new_hubs[sid] = sum(auths[cid] * card_prior[cid] for cid in born_cards) + (0.05 if born_cards else 0.0)
        norm_h = math.sqrt(sum(v * v for v in new_hubs.values())) or 1.0
        hubs = {k: v / norm_h for k, v in new_hubs.items()}

    max_h = max(hubs.values(), default=1.0) or 1.0
    max_a = max(auths.values(), default=1.0) or 1.0

    akar_list = []
    for sid, h_val in sorted(hubs.items(), key=lambda x: -x[1]):
        s = sources.get(sid, {})
        born = [cid for cid, c in active.items() if sid in c.get("sumber", [])]
        if not born:
            continue
        akar_list.append({
            "id": sid,
            "judul": s.get("judul", sid),
            "penulis": s.get("penulis", "tidak diketahui"),
            "jumlah_daun": len(born),
            "skor_hub": round((h_val / max_h) * 100, 1),
        })

    daun_list = []
    for cid, a_val in sorted(auths.items(), key=lambda x: -x[1]):
        c = active[cid]
        daun_list.append({
            "id": cid,
            "ide": c["ide"],
            "cabang": c["cabang"],
            "bintang": int(c.get("bintang", 0) or 0),
            "skor_authority": round((a_val / max_a) * 100, 1),
        })

    return {"akar_subur": akar_list[:8], "daun_matang": daun_list[:8]}


def compute_freshness_score(c: dict) -> dict:
    """Hitung skor kesegaran & keandalan gabungan (Knowledge Decay) 0-100."""
    trust_base = {"tinggi": 90, "sedang": 70, "rendah": 40, "belum-diverifikasi": 35}.get(c.get("kepercayaan", ""), 35)
    dasar_bonus = {"riset": 10, "pengalaman-pribadi": 5, "opini-umum": 0, "tidak-jelas": -5}.get(c.get("dasar", ""), 0)
    src_bonus = min(10, max(0, (len(c.get("sumber", [])) - 1) * 5))
    age = days_since(c.get("terakhir_ditinjau") or c.get("dibuat") or "")
    bidang = c.get("bidang", "")
    half_life = 180.0 if bidang in ("ai", "sosmed", "digital-marketing") else 365.0
    decay_factor = math.exp(-age / half_life) if age > 0 else 1.0
    raw_score = max(5, min(100, (trust_base + dasar_bonus + src_bonus) * (0.45 + 0.55 * decay_factor)))
    return {
        "id": c["id"],
        "ide": c["ide"],
        "cabang": c["cabang"],
        "umur_hari": age,
        "skor": round(raw_score, 1),
        "perlu_tinjau": raw_score < 50 or c.get("kepercayaan") in ("rendah", "belum-diverifikasi"),
    }


def analyze_data_science() -> dict:
    """Paket lengkap Sains Data: Matriks Celah, Peluruhan Pengetahuan, Kredibilitas Sumber, Anomali Pertentangan & Jembatan."""
    cards, sources, branches = load_active()
    active_cards = [c for c in cards.values() if c["status"] == "aktif"]

    # 1. Matriks Celah Pengetahuan: Bidang x Tahap Kerja
    stages = ["riset", "skrip", "produksi", "edit", "distribusi", "monetisasi"]
    bidangs = sorted({c["bidang"] for c in active_cards} | {b["slug"].split("/")[0] for b in branches.values()})
    matrix: list[dict] = []
    blind_spots: list[str] = []
    for b in bidangs:
        row_counts = {st: 0 for st in stages}
        b_cards = [c for c in active_cards if c["bidang"] == b]
        for c in b_cards:
            st = detect_workflow_stage(c)
            if st == "semua":
                for s in stages:
                    row_counts[s] += 1
            elif st in row_counts:
                row_counts[st] += 1
        matrix.append({"bidang": b, "total": len(b_cards), "tahap": row_counts})
        if len(b_cards) > 0:
            empties = [s for s in stages if row_counts[s] == 0]
            if empties:
                blind_spots.append(f"{b}: kosong di {', '.join(empties)}")

    # 2. Knowledge Decay & Skor Kesegaran
    freshness = sorted((compute_freshness_score(c) for c in active_cards), key=lambda x: x["skor"])

    # 3. Kredibilitas Sumber / Penulis berbasis penerapan + kepercayaan
    src_stats: dict[str, dict] = {}
    for c in active_cards:
        for sid in c.get("sumber", []):
            s = sources.get(sid, {})
            author = s.get("penulis") or "tidak diketahui"
            platform = s.get("platform") or "lainnya"
            key = f"{author} ({platform})"
            st = src_stats.setdefault(key, {"nama": key, "kartu": 0, "diterapkan": 0, "ditolak": 0, "tinggi_sedang": 0})
            st["kartu"] += 1
            if c.get("penerapan") == "diterapkan":
                st["diterapkan"] += 1
            elif c.get("penerapan") == "ditolak":
                st["ditolak"] += 1
            if c.get("kepercayaan") in ("tinggi", "sedang"):
                st["tinggi_sedang"] += 1
    credibility = []
    for st in src_stats.values():
        score = round((st["diterapkan"] * 3 - st["ditolak"] * 2 + st["tinggi_sedang"] * 1.5) / max(1, st["kartu"]) * 25 + 40, 1)
        st["skor"] = max(0.0, min(100.0, score))
        credibility.append(st)
    credibility.sort(key=lambda x: (-x["skor"], -x["kartu"]))

    # 4. Deteksi Kandidat Pertentangan Otomatis & Saran Pecah Klaster
    vecs = build_tfidf(cards)
    neg_cues = {"jangan", "dilarang", "bukan", "hindari", "tidak", "gagal", "berisiko", "avoid", "never", "stop", "ban"}
    pos_cues = {"wajib", "harus", "boleh", "terbaik", "aman", "efektif", "disarankan", "best", "always", "recommended"}
    existing_conflicts = {tuple(sorted((c["id"], r["ke"]))) for c in active_cards for r in c.get("relasi", []) if r.get("tipe") == "bertentangan-dengan"}
    candidate_conflicts: list[dict] = []
    c_list = active_cards
    for i in range(len(c_list)):
        for j in range(i + 1, len(c_list)):
            a, b = c_list[i], c_list[j]
            if tuple(sorted((a["id"], b["id"]))) in existing_conflicts:
                continue
            sim = cosine_sim(vecs.get(a["id"], {}), vecs.get(b["id"], {}))
            if sim < 0.12:
                continue
            toks_a = set(tokenize(f"{a['ide']} {a['penjelasan']}"))
            toks_b = set(tokenize(f"{b['ide']} {b['penjelasan']}"))
            has_contrast = (bool(toks_a & neg_cues) and bool(toks_b & pos_cues)) or (bool(toks_b & neg_cues) and bool(toks_a & pos_cues))
            if has_contrast:
                candidate_conflicts.append({
                    "a": a["id"], "ide_a": a["ide"],
                    "b": b["id"], "ide_b": b["ide"],
                    "kemiripan": round(sim, 3),
                })
    candidate_conflicts.sort(key=lambda x: -x["kemiripan"])

    # 5. Jembatan Lintas-Bidang (Cross-Domain Bridges)
    bridges: list[dict] = []
    for c in active_cards:
        linked_domains = {cards[r["ke"]]["bidang"] for r in c.get("relasi", []) if r["ke"] in cards and cards[r["ke"]]["bidang"] != c["bidang"]}
        if linked_domains or len(detect_tools_in_card(c)) >= 2:
            bridges.append({
                "id": c["id"],
                "ide": c["ide"],
                "bidang": c["bidang"],
                "lintas_bidang": sorted(linked_domains),
                "alat_terkait": detect_tools_in_card(c),
            })

    # 6. Saran Pecah Cabang Otomatis (>=12 kartu dalam satu cabang)
    split_suggestions: list[dict] = []
    for slug, br in branches.items():
        direct = [c for c in active_cards if c["cabang"] == slug]
        if len(direct) >= 12:
            term_freq: dict[str, int] = {}
            for c in direct:
                for t in set(tokenize(f"{c['ide']} {' '.join(c['tag'])}")):
                    term_freq[t] = term_freq.get(t, 0) + 1
            top_terms = [t for t, _ in sorted(term_freq.items(), key=lambda x: -x[1])[:4]]
            split_suggestions.append({"cabang": slug, "jumlah": len(direct), "saran_subcabang": top_terms})

    hits = compute_hits_akar_daun(cards, sources)

    return {
        "total_kartu": len(active_cards),
        "matriks_celah": matrix,
        "blind_spots": blind_spots[:10],
        "kesegaran": freshness[:12],
        "kredibilitas_sumber": credibility[:12],
        "kandidat_pertentangan": candidate_conflicts[:8],
        "jembatan_lintas_bidang": bridges[:8],
        "saran_pecah_cabang": split_suggestions,
        "hits_akar_subur": hits["akar_subur"],
        "hits_daun_matang": hits["daun_matang"],
    }


def cmd_sains() -> int:
    d = analyze_data_science()
    print(f"=== AUDIT SAINS DATA ({d['total_kartu']} kartu) ===")
    print("\n-- Blind Spots (Matriks Celah) --")
    for bs in d["blind_spots"] or ["(Semua bidang aktif punya cakupan dasar)"]:
        print(" -", bs)
    print("\n-- Kesegaran Terendah (Perlu Tinjau) --")
    for f in d["kesegaran"][:5]:
        print(f" - {f['id']} ({f['cabang']}): skor {f['skor']}/100 | umur {f['umur_hari']}h")
    print("\n-- Kredibilitas Sumber --")
    for cr in d["kredibilitas_sumber"][:5]:
        print(f" - {cr['nama']}: skor {cr['skor']} ({cr['kartu']} kartu, diterapkan {cr['diterapkan']})")
    return 0


def cmd_tanya(question: str) -> int:
    res = answer_question(question)
    print(f"=== TANYA POHON [{res['mode']}] ===")
    print(res["jawaban"])
    if res["rujukan"]:
        print("\nRujukan kartu:", ", ".join(r["id"] for r in res["rujukan"]))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Mesin Kecerdasan Pohon Pengetahuan (Bagian 21).")
    parser.add_argument("--ringkas", action="store_true", help="Ringkasan seluruh mesin kecerdasan")
    parser.add_argument("--ulasan", action="store_true", help="Antrean ulasan SM-2 / Leitner")
    parser.add_argument("--saran", action="store_true", help="Rekomendasi personal transparan + MMR")
    parser.add_argument("--roadmap", nargs="?", const="", metavar="BIDANG", help="Urutan topologis + deteksi siklus")
    parser.add_argument("--fondasi", action="store_true", help="PageRank (kartu fondasi) + Bridge Centrality")
    parser.add_argument("--gema", action="store_true", help="Deteksi ruang gema (Shannon Entropy & HHI)")
    parser.add_argument("--kalibrasi", action="store_true", help="Kalibrasi penulis berdasarkan status penerapan")
    parser.add_argument("--mirip", type=str, metavar="K-XXXX", help="Cari kartu mirip (TF-IDF + Cosine)")
    parser.add_argument("--klaster", type=str, metavar="CABANG", help="Usulan klaster sub-cabang berbasis TF-IDF")
    parser.add_argument("--bandingkan", type=str, metavar="KUERI", help="Bandingkan alat/metode: kesamaan, perbedaan, peringkat terbaik")
    parser.add_argument("--playbook", type=str, metavar="TOPIK", help="Susun tahapan kerja sempurna awal -> akhir + celah")
    parser.add_argument("--tren", action="store_true", help="Radar big data alat, bidang dominan, dan tahap kerja")
    parser.add_argument("--sains", action="store_true", help="Audit Sains Data: matriks celah, kesegaran, kredibilitas, anomali")
    parser.add_argument("--tanya", type=str, metavar="PERTANYAAN", help="Tanya-jawab berbasis kartu (Sintesis Lokal / Gemini RAG)")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    if args.ringkas:
        return cmd_ringkas()
    if args.ulasan:
        return cmd_ulasan(limit=args.limit)
    if args.saran:
        return cmd_saran(limit=args.limit)
    if args.roadmap is not None:
        return cmd_roadmap(args.roadmap or None)
    if args.fondasi:
        return cmd_fondasi(limit=args.limit)
    if args.gema:
        return cmd_gema()
    if args.kalibrasi:
        return cmd_kalibrasi()
    if args.mirip:
        return cmd_mirip(args.mirip, limit=args.limit)
    if args.klaster:
        return cmd_klaster(args.klaster)
    if args.bandingkan:
        return cmd_bandingkan(args.bandingkan)
    if args.playbook:
        return cmd_playbook(args.playbook)
    if args.tren:
        return cmd_tren()
    if args.sains:
        return cmd_sains()
    if args.tanya:
        return cmd_tanya(args.tanya)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
