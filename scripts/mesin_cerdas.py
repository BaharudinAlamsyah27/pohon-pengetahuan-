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
import hashlib
import json
import math
import os
import re
import sqlite3
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


def stem_id(word: str) -> str:
    """Stemmer imbuhan Bahasa Indonesia ringan (0 dependensi) untuk menyatukan kata dasar."""
    w = (word or "").lower().strip()
    if len(w) <= 4 or not w.isalpha():
        return w
    # 1. Hapus partikel & posesif akhir (-lah, -kah, -pun, -nya, -ku, -mu)
    for suf in ("lah", "kah", "tah", "pun", "nya"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            w = w[: -len(suf)]
            break
    # 2. Hapus awalan umum (meng-, meny-, mem-, men-, me-, ber-, ter-, per-, di-, ke-, se-, pe-)
    for pref, repl in (
        ("meng", ""), ("meny", "s"), ("mem", ""), ("men", ""), ("ber", ""),
        ("ter", ""), ("per", ""), ("peng", ""), ("peny", "s"), ("pem", ""), ("pen", ""),
        ("di", ""), ("ke", ""), ("se", ""), ("me", ""), ("pe", ""),
    ):
        if w.startswith(pref) and len(w) - len(pref) >= 4:
            cand = repl + w[len(pref) :]
            if len(cand) >= 4:
                w = cand
                break
    # 3. Hapus akhiran derivasi (-kan, -an, -i)
    for suf in ("kan", "an", "i"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            w = w[: -len(suf)]
            break
    return w


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    out: list[str] = []
    for w in words:
        if len(w) < 3 or w in STOPWORDS:
            continue
        out.append(w)
        st = stem_id(w)
        if st != w and len(st) >= 3 and st not in STOPWORDS:
            out.append(st)
    return out


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
    "perplexity", "notebooklm", "n8n", "make.com", "zapier", "obsidian",
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

    # 3. Active Learning: pelajari koreksi cabang manual pengguna (.koreksi_cabang.jsonl, bobot 5x!)
    kor_fp = ROOT / ".koreksi_cabang.jsonl"
    if kor_fp.is_file():
        for ln in kor_fp.read_text(encoding="utf-8", errors="ignore").splitlines()[-300:]:
            try:
                rec = json.loads(ln)
                kb = str(rec.get("cabang") or "").strip()
                kt = str(rec.get("teks") or "").strip()
                if kb in lexicon and kt:
                    class_doc_counts[kb] += 5
                    for tok in tokenize(kt):
                        class_word_counts[kb][tok] += 5
                        vocab.add(tok)
            except Exception:
                continue

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
    Jika kartu hasil ekstraksi berbahasa asing (Inggris/Mandarin) dan ada API key gratis aktif,
    terjemahkan & rapikan menjadi Bahasa Indonesia alami lewat cascade 6 penyedia gratis.
    Teks Asli di sumber/ tetap suci tidak pernah diubah.
    """
    if not _is_mostly_non_indonesian(f"{ide_text} {penjelasan}") or not has_any_free_llm_key():
        return ide_text, penjelasan
    prompt = (
        "Terjemahkan dan rapikan wawasan berikut ke Bahasa Indonesia yang jelas, natural, dan setia pada isi (jangan mengarang).\n"
        'Balas HANYA JSON valid: {"ide": "1-2 kalimat inti", "penjelasan": "2-4 kalimat penjelasan"}.\n\n'
        f"IDE ASLI: {ide_text}\n"
        f"PENJELASAN ASLI: {penjelasan}"
    )
    raw, _mdl, _err = call_free_llm_cascade("", prompt, json_mode=True, max_tokens=1024, temperature=0.1)
    if raw:
        try:
            m = re.search(r"\{[\s\S]*\}", raw)
            if m:
                parsed = json.loads(m.group(0))
                new_ide = str(parsed.get("ide") or "").strip().replace('"', "'")
                new_penj = str(parsed.get("penjelasan") or "").strip()
                if len(new_ide) >= 12:
                    return new_ide[:240], (new_penj or penjelasan)[:1200]
        except Exception:
            pass
    return ide_text, penjelasan


def synthesize_branch_summary_llm(cabang_slug: str, old_summary: str, active_cards: list[dict]) -> dict | None:
    """
    Sintesis ulang Ringkasan & Poin Kunci cabang (<=260 kata) via cascade 6 penyedia AI gratis.
    Dipicu otomatis setiap >=5 kartu baru masuk ke sebuah cabang.
    """
    if not active_cards or not has_any_free_llm_key():
        return None
    card_lines = "\n".join(
        f"- [{c['id']}] ({c.get('kepercayaan', '?')}): {c.get('ide', '')[:180]}"
        for c in active_cards[:25]
    )
    prompt = (
        f"Sintesis ulang ringkasan cabang '{cabang_slug}' dalam Bahasa Indonesia yang padat dan jernih.\n"
        "Balas HANYA JSON valid:\n"
        '{"ringkasan": "maksimal 220 kata merangkum tema besar cabang ini", '
        '"poin_kunci": ["maksimal 5 poin kunci singkat dengan sitasi [[K-XXXX]]"]}\n\n'
        f"RINGKASAN LAMA:\n{(old_summary or '')[:600]}\n\n"
        f"DAFTAR KARTU AKTIF:\n{card_lines}"
    )
    raw, _mdl, _err = call_free_llm_cascade("", prompt, json_mode=True, max_tokens=1024, temperature=0.2)
    if not raw:
        return None
    try:
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return None
        parsed = json.loads(m.group(0))
        ring = str(parsed.get("ringkasan") or "").strip()
        poin = [str(p).strip().lstrip("-• ") for p in (parsed.get("poin_kunci") or []) if str(p).strip()][:5]
        if len(ring) >= 30:
            return {"ringkasan": ring, "poin_kunci": poin}
    except Exception:
        pass
    return None

PROMPT_VERSION = "v2.1"
KAMUS_KONSEP_PATH = ROOT / "scripts" / "kamus_konsep.json"


def normalize_concepts(raw_concepts: list[str]) -> list[str]:
    """Normalisasi konsep memakai kamus alias yang tumbuh sendiri (duit/uang/finansial -> keuangan-pribadi)."""
    alias_map: dict[str, str] = {}
    if KAMUS_KONSEP_PATH.is_file():
        try:
            data = json.loads(KAMUS_KONSEP_PATH.read_text(encoding="utf-8"))
            for canon, aliases in data.items():
                alias_map[canon] = canon
                for a in aliases:
                    alias_map[str(a).lower().strip()] = canon
        except Exception:
            pass
    out: list[str] = []
    for k in raw_concepts or []:
        slug = re.sub(r"[^a-z0-9-]+", "-", str(k).lower().strip()).strip("-")
        if len(slug) < 2:
            continue
        out.append(alias_map.get(slug, slug))
    return list(dict.fromkeys(out))[:5]


def check_grounding_score(ide: str, penjelasan: str, raw_text: str) -> float:
    """Pemeriksa kesetiaan (grounding) deterministik: cek angka & istilah kunci terhadap teks sumber."""
    raw_low = (raw_text or "").lower()
    # Cek apakah angka spesifik di ide/penjelasan benar-benar ada di sumber (cegah halusinasi angka)
    nums = re.findall(r"\b\d+(?:[.,]\d+)?%?\b", f"{ide} {penjelasan}")
    if nums:
        num_hits = sum(1 for n in nums if n.rstrip("%") in raw_low)
        num_score = num_hits / len(nums)
    else:
        num_score = 1.0
    # Cek tumpang tindih istilah (termasuk sinonim dwibahasa agar tetap adil untuk terjemahan EN->ID)
    card_toks = set(expand_bilingual_tokens(tokenize(f"{ide} {penjelasan}")))
    src_toks = set(expand_bilingual_tokens(tokenize(raw_text)))
    if not card_toks or not src_toks:
        return round(num_score, 2)
    lex_overlap = len(card_toks & src_toks) / max(1, min(len(card_toks), 12))
    return round(min(1.0, 0.55 * num_score + 0.45 * min(1.0, lex_overlap)), 2)


def rerank_cards_llm(question: str, candidates: list[dict], top_k: int = 6) -> list[dict]:
    """Re-ranking ringan oleh AI: menyaring Top-20 kandidat FTS/TF-IDF menjadi Top-6 paling presisi."""
    if len(candidates) <= top_k or not has_any_free_llm_key():
        return candidates[:top_k]
    lines = "\n".join(
        f"- {c['id']} ({c['cabang']}): {c['ide'][:130]}"
        for c in candidates[:20]
    )
    prompt = (
        f"Pilih maksimal {top_k} ID kartu paling relevan untuk menjawab pertanyaan berikut, urutkan dari paling relevan.\n"
        'Balas HANYA JSON valid: {"ids": ["K-XXXX", ...]}.\n\n'
        f"PERTANYAAN: {question}\n\nKANDIDAT:\n{lines}"
    )
    raw, _mdl, _err = call_free_llm_cascade("", prompt, json_mode=True, max_tokens=256, temperature=0.0)
    if raw:
        try:
            m = re.search(r"\{[\s\S]*\}", raw)
            if m:
                ids = json.loads(m.group(0)).get("ids") or []
                cmap = {c["id"]: c for c in candidates}
                ranked = [cmap[i] for i in ids if i in cmap]
                if ranked:
                    for c in candidates:
                        if c["id"] not in {r["id"] for r in ranked} and len(ranked) < top_k:
                            ranked.append(c)
                    return ranked[:top_k]
        except Exception:
            pass
    return candidates[:top_k]


def parse_nl_filter(query: str) -> dict:
    """Parser filter bahasa alami (0 biaya): ubah kalimat biasa jadi filter terstruktur."""
    low = (query or "").lower().strip()
    out = {"bidang": "", "kepercayaan": "", "penerapan": "", "tahap": "", "sisa_q": low}
    for b in ("kesehatan", "keuangan", "bisnis", "sosmed", "digital-marketing", "kesuksesan", "motivasi-dan-mindset", "relasi", "ai"):
        if re.search(rf"\b{re.escape(b)}\b", low):
            out["bidang"] = b
            break
    if re.search(r"\b(kepercayaan tinggi|terpercaya|tinggi)\b", low):
        out["kepercayaan"] = "tinggi"
    elif re.search(r"\b(kepercayaan sedang|sedang)\b", low):
        out["kepercayaan"] = "sedang"
    elif re.search(r"\b(kepercayaan rendah|rendah)\b", low):
        out["kepercayaan"] = "rendah"
    elif re.search(r"\b(belum diverifikasi|belum dicek)\b", low):
        out["kepercayaan"] = "belum-diverifikasi"
    if re.search(r"\b(belum dicoba|belum diterapkan)\b", low):
        out["penerapan"] = "belum-dicoba"
    elif re.search(r"\b(sedang dicoba)\b", low):
        out["penerapan"] = "sedang-dicoba"
    elif re.search(r"\b(sudah diterapkan|diterapkan)\b", low):
        out["penerapan"] = "diterapkan"
    elif re.search(r"\b(ditolak)\b", low):
        out["penerapan"] = "ditolak"
    for th in ("sebelum-20", "20-25", "25-30", "30-40", "40-50", "50+"):
        if th in low:
            out["tahap"] = th
            break
    return out


ALLOWED_JENIS_KARTU = {"fakta", "data", "nasihat", "opini", "kisah", "prinsip"}
ALLOWED_DASAR_KARTU = {"riset", "pengalaman-pribadi", "opini-umum", "tidak-jelas"}
ALLOWED_TRUST_KARTU = {"tinggi", "sedang", "rendah", "belum-diverifikasi"}
ALLOWED_TAHAP_KARTU = {"sebelum-20", "20-25", "25-30", "30-40", "40-50", "50+", "semua-usia"}
ALLOWED_REL_TIPE = {"lanjutan-dari", "prasyarat-untuk", "memperkuat", "bertentangan-dengan", "contoh-dari", "terkait"}


def _verify_quote_in_source(quote: str, raw_text: str) -> str:
    """Pencegah halusinasi: pastikan kata-kata kutipan benar-benar ada di teks asli (<=14 kata)."""
    q_clean = re.sub(r"\s+", " ", (quote or "").strip().strip('"\'“”'))
    raw_low = (raw_text or "").lower()
    q_words = re.findall(r"[a-z0-9\u4e00-\u9fff]+", q_clean.lower())
    if q_words:
        hits = sum(1 for w in q_words if w in raw_low)
        if hits / len(q_words) >= 0.70:
            ws = q_clean.split()
            return " ".join(ws[:14]) + ("..." if len(ws) > 14 else "")
    # Fallback: ambil potongan kalimat pertama yang pasti ada di raw_text
    fallback_ws = re.sub(r"\s+", " ", (raw_text or "").strip()).split()[:14]
    return " ".join(fallback_ws) + ("..." if len(fallback_ws) == 14 else "")


def _split_long_text_chunks(raw_text: str, chunk_size: int = 4500, max_chunks: int = 4) -> list[str]:
    """Pecah transkrip YouTube / artikel panjang / PDF per batas paragraf agar hemat memori & tidak terpotong."""
    text = (raw_text or "").strip()
    if len(text) <= chunk_size + 1000:
        return [text]
    paras = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks: list[str] = []
    buf: list[str] = []
    cur_len = 0
    for p in paras:
        if cur_len + len(p) > chunk_size and buf:
            chunks.append("\n\n".join(buf))
            if len(chunks) >= max_chunks:
                return chunks
            buf = [p]
            cur_len = len(p)
        else:
            buf.append(p)
            cur_len += len(p) + 2
    if buf and len(chunks) < max_chunks:
        chunks.append("\n\n".join(buf))
    return chunks or [text[:chunk_size]]


def extract_structured_cards_gemini(
    raw_text: str,
    candidate_neighbors: list[dict],
    valid_branches: set[str],
    max_cards: int = 3,
    platform: str = "X",
) -> dict | None:
    """
    Pipeline 1-Panggilan Terstruktur (Arsitektur Claude) + Chunked Map-Reduce untuk teks panjang (>5.500 karakter):
    Mengirim teks sumber + Top-12 kartu tetangga dalam panggilan JSON terstruktur,
    menghasilkan kartu terjemahan Bahasa Indonesia, cabang per kartu (bisa multi-cabang),
    3-5 konsep abstrak (jembatan metafora), metadata valid, dan relasi (termasuk usulan pertentangan).
    """
    if not has_any_free_llm_key() or len((raw_text or "").strip()) < 15:
        return None

    # Jika teks sangat panjang (transkrip YouTube / PDF / X Article > 5.500 karakter), jalankan Chunked Map-Reduce!
    chunks = _split_long_text_chunks(raw_text, chunk_size=4500, max_chunks=4)
    if len(chunks) > 1:
        merged_cards: list[dict] = []
        used_model = ""
        per_chunk_lim = max(1, (max(1, min(5, max_cards)) + len(chunks) - 1) // len(chunks))
        for ch in chunks:
            sub = extract_structured_cards_gemini(
                raw_text=ch,
                candidate_neighbors=candidate_neighbors,
                valid_branches=valid_branches,
                max_cards=per_chunk_lim,
                platform=platform,
            )
            if sub and sub.get("kartu"):
                used_model = used_model or sub.get("model", "ai")
                for c in sub["kartu"]:
                    if not any(compute_shingle_jaccard(c["ide"], ex["ide"], k=3) >= 0.65 for ex in merged_cards):
                        merged_cards.append(c)
            if len(merged_cards) >= max(1, min(5, max_cards)):
                break
        if merged_cards:
            return {
                "duplikat_dari": None,
                "kartu": merged_cards[: max(1, min(5, max_cards))],
                "model": f"{used_model} (map-reduce {len(chunks)} segmen)",
                "versi_prompt": PROMPT_VERSION,
            }
        return None

    neighbor_lines = []
    valid_neighbor_ids = set()
    for nb in candidate_neighbors[:12]:
        nid = nb.get("id", "")
        if nid:
            valid_neighbor_ids.add(nid)
            neighbor_lines.append(f"- [{nid}] ({nb.get('cabang', '')}): {nb.get('ide', '')[:160]}")
    neighbors_blob = "\n".join(neighbor_lines) if neighbor_lines else "(belum ada kartu tetangga)"

    max_c = max(1, min(5, max_cards))
    card_count_rule = (
        "Ekstrak teks sumber menjadi TEPAT 1 kartu utuh dalam Bahasa Indonesia yang jernih & tertata: buat 1 kalimat judul 'ide' utama yang kuat, lalu susun seluruh poin/langkah turunannya secara rapi (1., 2., 3., ...) di dalam 'penjelasan'."
        if max_c == 1
        else f"Ekstrak teks sumber menjadi 1 hingga {max_c} kartu wawasan atomik dalam Bahasa Indonesia yang jernih, alami, dan setia pada sumber."
    )
    prompt = (
        f"Kamu adalah analis & editor Pohon Pengetahuan. {card_count_rule}\n"
        "JANGAN mengarang di luar isi sumber. Satu sumber BOLEH menghasilkan kartu di cabang berbeda jika topiknya berbeda.\n\n"
        "ATURAN BAHASA & TERJEMAHAN EDITORIAL (WAJIB):\n"
        "- Tulis 'ide' dan 'penjelasan' dalam Bahasa Indonesia yang mengalir alami, baku-santai, dan mudah dipindai (gaya editor buku non-fiksi).\n"
        "- DILARANG menerjemahkan mentah kata-per-kata (word-for-word) yang terasa kaku atau rancu.\n"
        "- Ubah idiom/ungkapan asing (Inggris, Portugis, dll.) ke padanan makna alami Bahasa Indonesia tanpa mengubah fakta.\n"
        "- Pertahankan istilah teknis universal (API, prompt, framework, Rust, SaaS, SEO, queueing theory, dopamine, self-talk, dll.) bila lebih tepat & tidak rancu.\n"
        "- Khusus field 'kutipan', biarkan PERSIS dalam bahasa asli sumber (<=12 kata) sebagai bukti otentik.\n\n"
        "DAFTAR CABANG YANG DIIZINKAN:\n"
        "- kesehatan (tidur/sleep, olahraga, nutrisi, otak, brain fog, biologi, medis)\n"
        "- keuangan (tabungan, gaji, investasi, saham, utang, dana darurat)\n"
        "- bisnis (startup, SaaS, omzet, klien, produk digital, jualan)\n"
        "- sosmed (algoritma X/YouTube/TikTok/IG, OCR X, konten viral, impresi, kreator)\n"
        "- digital-marketing (SEO, iklan/ads, funnel, copywriting, konversi)\n"
        "- kesuksesan (karier, CPNS, beasiswa, magang, kerja, wawancara)\n"
        "- motivasi-dan-mindset (disiplin, kebiasaan, fokus, overthinking, produktivitas)\n"
        "- relasi (hubungan, komunikasi, keluarga, pasangan, negosiasi)\n"
        "- agama (ilmu agama, akhlak, ibadah, tafsir, hadis, nasihat ulama, spiritualitas)\n"
        "- berita (berita terkini, kebijakan pemerintah, peristiwa dunia, geopolitik, tren sesaat)\n"
        "- kliping-hiburan (guyonan, meme, lelucon, hiburan ringan, konten absurd tanpa pelajaran serius)\n"
        "- ai/coding-dan-proyek (coding AI, Cursor, Claude Code, Python, GitHub, API)\n"
        "- ai/prompt-dan-agen (prompt, agen AI, MCP, skill AI, workflow otomasi)\n"
        "- ai/video-dan-clipping (video AI, Kling, Veo, Runway, CapCut, ElevenLabs)\n"
        "- ai/tulisan-dan-artikel (menulis AI, tone-of-voice, artikel AI)\n"
        "- ai/perbandingan-model (perbandingan model LLM, benchmark Claude/Gemini/GPT)\n"
        "- ai (AI umum lainnya)\n"
        "- lainnya\n\n"
        f"KARTU TETANGGA YANG SUDAH ADA (untuk cek duplikat & relasi):\n{neighbors_blob}\n\n"
        "Balas HANYA JSON valid persis dengan skema ini:\n"
        '{\n'
        '  "duplikat_dari": null atau "K-XXXX" jika seluruh teks sama persis idenya dengan kartu lama,\n'
        '  "kartu": [\n'
        '    {\n'
        '      "ide": "1-2 kalimat klaim inti dalam Bahasa Indonesia",\n'
        '      "penjelasan": "2-4 kalimat bukti & penjelasan setia sumber dalam Bahasa Indonesia",\n'
        '      "kondisi_berlaku": "syarat berlaku singkat jika disebut (mis. pemula/modal kecil/usia 20-an) atau umum",\n'
        '      "keyakinan": 0.0 sampai 1.0 (seberapa yakin cabang & ekstraksi ini tepat),\n'
        '      "kutipan": "kutipan singkat <=12 kata yang PERSIS ada di teks asli",\n'
        '      "cabang": "salah satu slug cabang di atas",\n'
        '      "tahap": "sebelum-20|20-25|25-30|30-40|40-50|50+|semua-usia",\n'
        '      "jenis": "fakta|data|nasihat|opini|kisah|prinsip",\n'
        '      "dasar": "riset|pengalaman-pribadi|opini-umum|tidak-jelas",\n'
        '      "kepercayaan": "sedang|rendah|belum-diverifikasi",\n'
        '      "konsep": ["3 sampai 5 konsep abstrak huruf-kecil-strip, misal: manajemen-risiko, diversifikasi"],\n'
        '      "tag": ["2 sampai 4 tag spesifik"],\n'
        '      "relasi": [{"tipe": "memperkuat|terkait|lanjutan-dari|prasyarat-untuk|bertentangan-dengan", "ke": "K-XXXX"}]\n'
        '    }\n'
        '  ]\n'
        '}\n\n'
        f"TEKS SUMBER ({platform}):\n{raw_text[:5500]}"
    )

    for attempt in range(2):
        raw, used_mdl, _err = call_free_llm_cascade(
            system_prompt="",
            user_prompt=prompt,
            json_mode=True,
            max_tokens=2048,
            temperature=0.1,
        )
        if not raw:
            continue
        try:
            m = re.search(r"\{[\s\S]*\}", raw)
            if not m:
                continue
            parsed = json.loads(m.group(0))
            raw_cards = parsed.get("kartu") or []
            if not isinstance(raw_cards, list) or not raw_cards:
                continue

            # Validasi ketat hasil AI (anti-halusinasi & kepatuhan skema)
            validated_cards: list[dict] = []
            for rc in raw_cards[: max(1, min(5, max_cards))]:
                if not isinstance(rc, dict):
                    continue
                ide = str(rc.get("ide") or "").strip().replace('"', "'")
                if len(ide) < 10:
                    continue
                penj = str(rc.get("penjelasan") or ide).strip()
                kutipan = _verify_quote_in_source(str(rc.get("kutipan") or ""), raw_text)
                cab = str(rc.get("cabang") or "").strip().lower()
                if cab not in valid_branches:
                    cab = ""
                tahap = str(rc.get("tahap") or "semua-usia").strip()
                if tahap not in ALLOWED_TAHAP_KARTU:
                    tahap = "semua-usia"
                jenis = str(rc.get("jenis") or "opini").strip()
                if jenis not in ALLOWED_JENIS_KARTU:
                    jenis = "opini"
                dasar = str(rc.get("dasar") or "tidak-jelas").strip()
                if dasar not in ALLOWED_DASAR_KARTU:
                    dasar = "tidak-jelas"
                trust = str(rc.get("kepercayaan") or "belum-diverifikasi").strip()
                if trust not in ALLOWED_TRUST_KARTU:
                    trust = "belum-diverifikasi"
                if platform.lower() in ("x", "threads", "instagram", "tiktok", "facebook") and trust == "tinggi":
                    trust = "sedang"
                konsep = normalize_concepts(rc.get("konsep") or [])
                kondisi = str(rc.get("kondisi_berlaku") or "umum").strip().replace('"', "'")[:120]
                try:
                    keyakinan = max(0.0, min(1.0, float(rc.get("keyakinan", 0.85))))
                except Exception:
                    keyakinan = 0.85
                grounding = check_grounding_score(ide, penj, raw_text)
                tags = [
                    re.sub(r"[^a-z0-9-]+", "-", str(t).lower().strip()).strip("-")
                    for t in (rc.get("tag") or [])
                    if str(t).strip()
                ]
                tags = [t for t in dict.fromkeys(tags) if len(t) >= 2][:4]
                rels = []
                for r in (rc.get("relasi") or []):
                    if isinstance(r, dict):
                        rt = str(r.get("tipe") or "").strip()
                        rk = str(r.get("ke") or "").strip()
                        if rt in ALLOWED_REL_TIPE and rk in valid_neighbor_ids:
                            rels.append({"tipe": rt, "ke": rk})
                validated_cards.append({
                    "ide": ide[:240],
                    "penjelasan": penj[:1200],
                    "kutipan": kutipan,
                    "cabang": cab,
                    "tahap": tahap,
                    "jenis": jenis,
                    "dasar": dasar,
                    "kepercayaan": trust,
                    "konsep": konsep,
                    "kondisi_berlaku": kondisi,
                    "keyakinan": round(keyakinan, 2),
                    "grounding": grounding,
                    "tag": tags,
                    "relasi": rels[:3],
                })
            if validated_cards:
                dup = parsed.get("duplikat_dari")
                dup_id = str(dup).strip() if dup and str(dup).strip() in valid_neighbor_ids else None
                return {"duplikat_dari": dup_id, "kartu": validated_cards, "model": used_mdl, "versi_prompt": PROMPT_VERSION}
        except Exception:
            continue
    return None


# ===================== PENCARIAN MAKNA: LOCAL VECTOR EMBEDDINGS (SQLite .indeks.db) =====================

EMBED_DB_PATH = ROOT / ".indeks.db"
EMBED_MODELS = ["gemini-embedding-001", "text-embedding-004"]


def _init_vector_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS kartu_vektor ("
        "id TEXT PRIMARY KEY, "
        "content_hash TEXT NOT NULL, "
        "vec TEXT NOT NULL)"
    )


def _cosine_dense(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def get_text_embedding(text: str, api_key: str = "") -> list[float] | None:
    """Ambil vektor makna (256 dimensi) lewat Gemini Embedding API gratis (0 dependensi)."""
    key = (api_key or "").strip()
    if not key:
        env = load_local_env()
        key = (os.environ.get("GEMINI_API_KEY") or env.get("GEMINI_API_KEY") or "").strip()
    if not key:
        return None
    snippet = (text or "").strip()[:1500]
    if len(snippet) < 3:
        return None
    for mdl in EMBED_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{mdl}:embedContent?key={key}"
        payload = {
            "model": f"models/{mdl}",
            "content": {"parts": [{"text": snippet}]},
            "outputDimensionality": 256,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            vals = (data.get("embedding") or {}).get("values")
            if isinstance(vals, list) and len(vals) >= 64:
                return [float(v) for v in vals]
        except Exception:
            continue
    return None


def load_or_update_card_vectors(cards: dict[str, dict], max_new: int = 12) -> dict[str, list[float]]:
    """Muat vektor kartu dari SQLite .indeks.db; hitung otomatis hingga max_new kartu baru/berubah."""
    vecs: dict[str, list[float]] = {}
    if not cards:
        return vecs
    env = load_local_env()
    api_key = (os.environ.get("GEMINI_API_KEY") or env.get("GEMINI_API_KEY") or "").strip()
    try:
        conn = sqlite3.connect(str(EMBED_DB_PATH), timeout=5)
        _init_vector_table(conn)
        cached = {
            row[0]: (row[1], row[2])
            for row in conn.execute("SELECT id, content_hash, vec FROM kartu_vektor").fetchall()
        }
        updated = 0
        for cid, c in cards.items():
            blob = f"{c.get('cabang', '')} | {c.get('ide', '')} | {(c.get('penjelasan') or '')[:500]} | {' '.join(c.get('konsep') or [])}"
            h = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
            if cid in cached and cached[cid][0] == h:
                try:
                    vecs[cid] = json.loads(cached[cid][1])
                    continue
                except Exception:
                    pass
            if api_key and updated < max_new:
                emb = get_text_embedding(blob, api_key=api_key)
                if emb:
                    vecs[cid] = emb
                    conn.execute(
                        "INSERT OR REPLACE INTO kartu_vektor (id, content_hash, vec) VALUES (?, ?, ?)",
                        (cid, h, json.dumps(emb)),
                    )
                    updated += 1
        if updated:
            conn.commit()
        conn.close()
    except Exception:
        pass
    return vecs


def query_relevant_cards(query: str, cards: dict[str, dict], limit: int = 80, use_vectors: bool = True) -> list[dict]:
    """Pencarian Hibrida (RRF): FTS5 BM25 + TF-IDF Cosine + Vector Embedding Makna + sinonim ID<->EN."""
    # Kecualikan cabang kliping-hiburan dari Tanya AI, Saran, dan Tanggapan Jurnal agar otak utama tetap bersih
    cards = {cid: c for cid, c in cards.items() if c.get("cabang") != "kliping-hiburan" and c.get("bidang") != "kliping-hiburan"}
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

    # 3) Sinyal Vector Embeddings Makna (Hybrid Semantic RAG — menemukan makna sama meski 0 kata sama!)
    if use_vectors and query and len(query.strip()) >= 4 and cards:
        try:
            card_vecs = load_or_update_card_vectors(cards, max_new=8)
            if card_vecs:
                q_emb = get_text_embedding(query)
                if q_emb:
                    sem_ranked = sorted(
                        ((cid, _cosine_dense(q_emb, vec)) for cid, vec in card_vecs.items() if cid in rrf_scores),
                        key=lambda x: -x[1],
                    )
                    for rank, (cid, sim) in enumerate(sem_ranked[:25], start=1):
                        if sim >= 0.45:
                            rrf_scores[cid] += 1.35 / (k_rrf + rank)
        except Exception:
            pass

    # 4) Boost kecocokan frasa / token langsung
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


FREE_OPENAI_PROVIDERS = [
    ("GROQ_API_KEY", "groq", "https://api.groq.com/openai/v1/chat/completions", ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]),
    ("OPENROUTER_API_KEY", "openrouter", "https://openrouter.ai/api/v1/chat/completions", ["openrouter/free"]),
    ("MISTRAL_API_KEY", "mistral", "https://api.mistral.ai/v1/chat/completions", ["mistral-small-latest"]),
    ("CEREBRAS_API_KEY", "cerebras", "https://api.cerebras.ai/v1/chat/completions", ["llama-3.3-70b", "qwen-3.8-27b"]),
    ("NVIDIA_API_KEY", "nvidia-nim", "https://integrate.api.nvidia.com/v1/chat/completions", ["meta/llama-3.3-70b-instruct"]),
]


def has_any_free_llm_key() -> bool:
    local_env = load_local_env()
    keys = ["GEMINI_API_KEY"] + [p[0] for p in FREE_OPENAI_PROVIDERS]
    return any((os.environ.get(k) or local_env.get(k) or "").strip() for k in keys)


def call_free_llm_cascade(
    system_prompt: str,
    user_prompt: str,
    json_mode: bool = False,
    max_tokens: int = 2048,
    temperature: float = 0.2,
    preferred_gemini_model: str = "",
) -> tuple[str | None, str, str]:
    """
    Cascade otomatis ke 6 penyedia LLM API 100% Gratis (tanpa kartu kredit):
      1. Google AI Studio (GEMINI_API_KEY -> gemini-3.5-flash-lite / gemini-2.5-flash)
      2. Groq (GROQ_API_KEY -> llama-3.3-70b-versatile / llama-3.1-8b-instant)
      3. OpenRouter (OPENROUTER_API_KEY -> openrouter/free)
      4. Mistral AI (MISTRAL_API_KEY -> mistral-small-latest)
      5. Cerebras (CEREBRAS_API_KEY -> llama-3.3-70b)
      6. NVIDIA NIM (NVIDIA_API_KEY -> meta/llama-3.3-70b-instruct)
    Jika satu penyedia kena limit kuota (HTTP 429) atau error, otomatis pindah ke penyedia berikutnya.
    """
    local_env = load_local_env()
    last_err = "Belum ada API key gratis di .env"

    # 1. Google Gemini API (Native)
    gem_key = (os.environ.get("GEMINI_API_KEY") or local_env.get("GEMINI_API_KEY") or "").strip()
    if gem_key:
        pref = preferred_gemini_model or (os.environ.get("GEMINI_MODEL") or local_env.get("GEMINI_MODEL") or "gemini-3.5-flash-lite").strip()
        gem_models = list(dict.fromkeys([pref, "gemini-3.5-flash-lite", "gemini-2.5-flash"]))
        for mdl in gem_models:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{mdl}:generateContent?key={gem_key}"
            gen_cfg: dict = {"temperature": temperature, "maxOutputTokens": max_tokens}
            if json_mode:
                gen_cfg["responseMimeType"] = "application/json"
            body: dict = {
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                "generationConfig": gen_cfg,
            }
            if system_prompt:
                body["systemInstruction"] = {"parts": [{"text": system_prompt}]}
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
                txt = "\n".join(p.get("text", "") for p in parts if p.get("text")).strip()
                if txt:
                    return txt, mdl, ""
            except urllib.error.HTTPError as exc:
                last_err = f"gemini {mdl} HTTP {exc.code}"
                continue
            except Exception as exc:
                last_err = f"gemini {mdl}: {exc}"
                continue

    # 2..6. Penyedia OpenAI-Compatible Gratis (Groq, OpenRouter, Mistral, Cerebras, NVIDIA NIM)
    for env_var, prov_name, endpoint, models in FREE_OPENAI_PROVIDERS:
        key = (os.environ.get(env_var) or local_env.get(env_var) or "").strip()
        if not key:
            continue
        for mdl in models:
            msgs = []
            if system_prompt:
                msgs.append({"role": "system", "content": system_prompt})
            msgs.append({"role": "user", "content": user_prompt})
            payload: dict = {
                "model": mdl,
                "messages": msgs,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if json_mode and prov_name in ("groq", "mistral", "cerebras"):
                payload["response_format"] = {"type": "json_object"}
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
                "User-Agent": "PohonPengetahuan/1.0",
            }
            if prov_name == "openrouter":
                headers["HTTP-Referer"] = "https://pohon-pengetahuan.vercel.app"
                headers["X-Title"] = "Pohon Pengetahuan"
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=25) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                choices = data.get("choices") or []
                txt = (((choices[0].get("message") or {}).get("content")) or "").strip() if choices else ""
                if txt:
                    return txt, f"{prov_name}/{mdl}", ""
            except urllib.error.HTTPError as exc:
                last_err = f"{prov_name}/{mdl} HTTP {exc.code}"
                continue
            except Exception as exc:
                last_err = f"{prov_name}/{mdl}: {exc}"
                continue

    return None, "none", last_err


def call_gemini_rag(question: str, rel_cards: list[dict], api_key: str, preferred_model: str) -> tuple[str | None, str, str]:
    context_items = []
    for c in rel_cards:
        context_items.append(
            f"[{c['id']}] cabang={c['cabang']} | tahap={c['tahap']} | kepercayaan={c['kepercayaan']} | dasar={c['dasar']}\n"
            f"Ide: {c['ide']}\n"
            f"Penjelasan: {(c.get('penjelasan') or '')[:450]}"
        )
    system_prompt = (
        "Kamu adalah partner berpikir (otak kedua) milik pengguna di Pohon Pengetahuan. "
        "Gaya bicara: hangat, cerdas, mengalir alami seperti mentor/rekan diskusi manusia dalam Bahasa Indonesia yang jernih — "
        "JANGAN kaku seperti laporan robot dan JANGAN memulai dengan kalimat klise seperti 'Berdasarkan kartu wawasan yang diberikan'. "
        "Mulai langsung dengan jawaban inti yang jelas, lalu rangkai poin-poin pendukung secara natural dengan menyisipkan ID kartu seperti [K-0001] di dalam kalimat. "
        "ATURAN FAKTA MUTLAK: Semua klaim wajib bersumber HANYA dari KARTU WAWASAN di bawah (jangan mengarang); jika bukti di kartu belum cukup, katakan jujur dengan ramah. "
        "Singgung catatan kepercayaan/pertentangan secara halus bila relevan."
    )
    user_prompt = f"KARTU WAWASAN:\n\n" + "\n\n---\n\n".join(context_items) + f"\n\nPERTANYAAN PENGGUNA:\n{question}"
    return call_free_llm_cascade(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        json_mode=False,
        max_tokens=4096,
        temperature=0.45,
        preferred_gemini_model=preferred_model,
    )


def advise_decision(dilemma: str) -> dict:
    """
    Mode Konsultasi Keputusan (Lensa CEO · COO · CFO):
    Menilai dilema pengguna dari 3 sudut pandang eksekutif berbasis kartu Pohon Pengetahuan + persona.md.
    """
    cards, _sources, _ = load_active()
    rel_cands = query_relevant_cards(dilemma, cards, limit=16)
    rel_cards = rerank_cards_llm(dilemma, rel_cands, top_k=8) if len(rel_cands) > 8 else rel_cands[:8]

    persona_fp = ROOT / "persona.md"
    persona_txt = persona_fp.read_text(encoding="utf-8", errors="ignore")[:1800] if persona_fp.is_file() else "(persona.md belum diisi)"

    rujukan = [
        {"id": c["id"], "ide": c["ide"], "cabang": c["cabang"], "kepercayaan": c["kepercayaan"]}
        for c in rel_cards
    ]
    conflicts = []
    seen_c = set()
    for c in rel_cards:
        for r in c.get("relasi") or []:
            if r.get("tipe") == "bertentangan-dengan":
                pair = tuple(sorted([c["id"], r["ke"]]))
                if pair not in seen_c:
                    seen_c.add(pair)
                    conflicts.append({"a": pair[0], "b": pair[1]})

    context_blob = "\n\n".join(
        f"[{c['id']}] cabang={c['cabang']} | kepercayaan={c['kepercayaan']} | kondisi={c.get('kondisi_berlaku') or 'umum'}\n"
        f"Ide: {c['ide']}\nPenjelasan: {(c.get('penjelasan') or '')[:350]}"
        for c in rel_cards
    ) or "(Belum ada kartu relevan di Pohon Pengetahuan)"

    if has_any_free_llm_key():
        sys_p = (
            "Kamu adalah Dewan Penasihat Eksekutif Pribadi (CEO, COO, CFO) untuk pemilik Pohon Pengetahuan. "
            "Jawab HANYA berdasarkan KARTU WAWASAN dan PROFIL PERSONA berikut. Wajib sitasi [K-XXXX] untuk setiap poin dari kartu. "
            "Tambahan di luar kartu wajib diberi label [inferensi AI]. Jangan menjamin hasil; gunakan bahasa realistis & Bahasa Indonesia tegas.\n\n"
            "Format keluaran WAJIB 4 bagian:\n"
            "## 🎯 Lensa CEO (Visi, Strategi & Jangka Panjang)\n"
            "## ⚙️ Lensa COO (Eksekusi, Kapasitas & Langkah 7 Hari)\n"
            "## 💰 Lensa CFO (Risiko, Biaya, Pertentangan & Celah Data)\n"
            "## 🧭 Rekomendasi Keputusan Akhir"
        )
        usr_p = (
            f"PROFIL PERSONA:\n{persona_txt}\n\n"
            f"KARTU WAWASAN RELEVAN:\n{context_blob}\n\n"
            f"DILEMA / KEPUTUSAN YANG DIHADAPI:\n{dilemma}"
        )
        ai_txt, used_mdl, _err = call_free_llm_cascade(sys_p, usr_p, json_mode=False, max_tokens=2048, temperature=0.2)
        if ai_txt:
            return {"ok": True, "mode": f"dewan-eksekutif ({used_mdl})", "analisis": ai_txt, "rujukan": rujukan, "pertentangan": conflicts}

    # Cadangan offline 0-biaya
    lines = [
        "## 🎯 Lensa CEO (Visi & Strategi — Mode Offline)",
        *(f"- [{c['id']}] ({c['cabang']}) {c['ide']}" for c in rel_cards[:3]),
        "\n## ⚙️ Lensa COO (Langkah Eksekusi 7 Hari)",
        "- Pilih 1 eksperimen terkecil berbiaya rendah dari kartu di atas, uji selama 7 hari, lalu catat hasilnya di Jurnal.",
        "\n## 💰 Lensa CFO (Risiko & Catatan Kualitas)",
        f"- Ditemukan {len(conflicts)} pertentangan terbuka dan {sum(1 for c in rel_cards if c['kepercayaan'] in ('rendah', 'belum-diverifikasi'))} kartu berkepercayaan rendah/belum diverifikasi.",
    ]
    return {"ok": True, "mode": "dewan-eksekutif (offline)", "analisis": "\n".join(lines), "rujukan": rujukan, "pertentangan": conflicts}


def build_weekly_briefing() -> dict:
    """
    Briefing Mingguan Eksekutif:
      1. Kartu baru 7 hari terakhir
      2. 1 Eksperimen Prioritas Minggu Ini (SM-2 + persona)
      3. Pertentangan terbuka & kartu ragu (perlu-tinjau-cabang / cek-kesetiaan)
      4. Celah pengetahuan (cabang dengan <=1 sumber)
    """
    cards, sources, branches = load_active()
    recent_cards = [c for c in cards.values() if days_since(c.get("dibuat", "")) <= 7]
    recent_cards.sort(key=lambda c: c.get("dibuat", ""), reverse=True)

    # Pilih 1 eksperimen prioritas (belum dicoba, kepercayaan sedang/tinggi, bukan kliping-hiburan)
    exp_pool = [
        c for c in cards.values()
        if c.get("penerapan") == "belum-dicoba"
        and c.get("cabang") != "kliping-hiburan"
        and c.get("kepercayaan") in ("tinggi", "sedang")
    ]
    exp_pool.sort(key=lambda c: (-TRUST_WEIGHT.get(c["kepercayaan"], 0.5), -days_since(c.get("terakhir_ditinjau", "")), c["id"]))
    top_exp = exp_pool[0] if exp_pool else (next(iter(cards.values()), None))

    ragu_cards = [
        {"id": c["id"], "ide": c["ide"][:110], "cabang": c["cabang"]}
        for c in cards.values()
        if any(t in ("perlu-tinjau-cabang", "cek-kesetiaan", "draf-ekstraktif") for t in (c.get("tag") or []))
    ][:6]

    conflicts = []
    seen_p = set()
    for c in cards.values():
        for r in c.get("relasi") or []:
            if r.get("tipe") == "bertentangan-dengan" and r["ke"] in cards:
                p = tuple(sorted([c["id"], r["ke"]]))
                if p not in seen_p:
                    seen_p.add(p)
                    conflicts.append({"a": p[0], "b": p[1], "ide_a": cards[p[0]]["ide"][:90], "ide_b": cards[p[1]]["ide"][:90]})

    thin_branches = []
    for slug, b in branches.items():
        if slug in ("lainnya", "kliping-hiburan"):
            continue
        b_cards = [c for c in cards.values() if c["cabang"] == slug or c["cabang"].startswith(slug + "/")]
        b_srcs = {s for c in b_cards for s in c["sumber"]}
        if 0 < len(b_srcs) <= 1:
            thin_branches.append({"cabang": slug, "kartu": len(b_cards), "sumber": len(b_srcs)})

    applied_cnt = sum(1 for c in cards.values() if c.get("penerapan") == "diterapkan")
    trying_cnt = sum(1 for c in cards.values() if c.get("penerapan") == "sedang-dicoba")

    return {
        "ok": True,
        "tanggal": date.today().isoformat(),
        "ringkasan_eksekutif": {
            "total_kartu_aktif": len(cards),
            "kartu_baru_7_hari": len(recent_cards),
            "sudah_diterapkan": applied_cnt,
            "sedang_dicoba": trying_cnt,
            "rasio_eksekusi_persen": round((applied_cnt / max(1, len(cards))) * 100, 1),
        },
        "eksperimen_minggu_ini": {
            "id": top_exp["id"],
            "ide": top_exp["ide"],
            "cabang": top_exp["cabang"],
            "kepercayaan": top_exp["kepercayaan"],
        } if top_exp else None,
        "kartu_baru": [{"id": c["id"], "ide": c["ide"][:110], "cabang": c["cabang"]} for c in recent_cards[:6]],
        "pertentangan_terbuka": conflicts[:5],
        "kartu_perlu_tinjau": ragu_cards,
        "celah_sumber_tunggal": thin_branches[:6],
    }


def answer_question(question: str) -> dict:
    cards, sources, _ = load_active()
    syntax_mode = is_syntax_or_viral_query(question)
    syntax_report = analyze_viral_syntax(cards, sources, question) if syntax_mode else None

    rel_candidates = query_relevant_cards(question, cards, limit=20)
    rel_cards = rerank_cards_llm(question, rel_candidates, top_k=8) if len(rel_candidates) > 8 else rel_candidates[:8]
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
    model_name = (os.environ.get("GEMINI_MODEL") or local_env.get("GEMINI_MODEL") or "gemini-3.5-flash-lite").strip()

    if has_any_free_llm_key() and rel_cards:
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


def analyze_deep_intelligence() -> dict:
    """
    Mesin 4 Lompatan Kecerdasan:
      1. Indeks Vector Embedding Makna (.indeks.db / kartu_vektor)
      2. Penemu Pola Lintas-Cabang (Cross-Domain Synthesis)
      3. Detektor Pertentangan & Evolusi Prinsip (Kartu vs Kartu & Kartu vs Kompas Sikap Jurnal)
      4. Kurator Aksi Adaptif (Jurnal terbaru + persona.md -> 1-2 kartu paling relevan hari ini)
    """
    cards_all, _, _ = load_active()
    cards = {
        cid: c for cid, c in cards_all.items()
        if c.get("cabang") != "kliping-hiburan" and c.get("bidang") != "kliping-hiburan"
    }
    if not cards:
        return {"ok": True, "vektor_terindeks": 0, "total_kartu": 0, "lintas_cabang": [], "pertentangan": [], "aksi_adaptif": [], "sintesis_ai": ""}

    # 1. Perbarui cache vector embedding (maks 15 kartu per panggilan agar cepat)
    vecs = load_or_update_card_vectors(cards, max_new=15)
    tfidf_vecs = build_tfidf(cards)

    # 2. Temukan pasangan kartu paling kuat dari BIDANG BERBEDA (Cross-Domain Bridges)
    cids = sorted(cards.keys())
    bridges: list[dict] = []
    for i in range(len(cids)):
        c1 = cards[cids[i]]
        b1 = c1.get("bidang") or (c1.get("cabang") or "").split("/")[0]
        for j in range(i + 1, len(cids)):
            c2 = cards[cids[j]]
            b2 = c2.get("bidang") or (c2.get("cabang") or "").split("/")[0]
            if b1 == b2:
                continue
            sem_sim = _cosine_dense(vecs.get(cids[i], []), vecs.get(cids[j], [])) if (cids[i] in vecs and cids[j] in vecs) else 0.0
            lex_sim = cosine_sim(tfidf_vecs.get(cids[i], {}), tfidf_vecs.get(cids[j], {}))
            shared_k = sorted(set(c1.get("konsep") or []) & set(c2.get("konsep") or []))
            score = (sem_sim * 0.65 if sem_sim > 0 else 0.0) + lex_sim * 0.35 + len(shared_k) * 0.12
            if score >= 0.18 or (sem_sim >= 0.58):
                bridges.append({
                    "dari": c1["id"],
                    "cabang_a": c1["cabang"],
                    "ide_a": c1["ide"][:120],
                    "ke": c2["id"],
                    "cabang_b": c2["cabang"],
                    "ide_b": c2["ide"][:120],
                    "skor": round(score, 3),
                    "konsep_bersama": shared_k,
                })
    bridges.sort(key=lambda x: -x["skor"])
    top_bridges = bridges[:5]

    # 3. Detektor Pertentangan & Evolusi Prinsip (antar-kartu + vs Kompas Sikap Jurnal)
    conflicts: list[dict] = []
    seen_pairs: set[tuple[str, str]] = set()
    for cid, c in cards.items():
        for rel in c.get("relasi") or []:
            if rel.get("tipe") == "bertentangan-dengan":
                other = rel.get("ke", "")
                pair = tuple(sorted([cid, other]))
                if other in cards and pair not in seen_pairs:
                    seen_pairs.add(pair)
                    conflicts.append({
                        "jenis": "antar-kartu",
                        "a": cid,
                        "ide_a": c["ide"][:110],
                        "b": other,
                        "ide_b": cards[other]["ide"][:110],
                    })
    # Cek Kompas Sikap di jurnal/ (pribadi lokal saja)
    kompas_lines: list[str] = []
    kompas_fp = ROOT / "jurnal" / "_kompas_sikap.md"
    if kompas_fp.is_file():
        for ln in kompas_fp.read_text(encoding="utf-8", errors="ignore").splitlines():
            if ln.strip().startswith("- "):
                kompas_lines.append(ln.strip()[2:][:160])

    # 4. Kurator Aksi Adaptif (Jurnal 3 hari terakhir + persona.md -> pilih 2 kartu belum-dicoba paling relevan)
    jurnal_snippets: list[str] = []
    jurnal_dir = ROOT / "jurnal"
    if jurnal_dir.is_dir():
        jfiles = sorted(
            [p for p in jurnal_dir.rglob("*.md") if not p.name.startswith("_")],
            key=lambda p: p.name,
            reverse=True,
        )[:3]
        for jf in jfiles:
            jurnal_snippets.append(jf.read_text(encoding="utf-8", errors="ignore")[:500])
    persona_txt = (ROOT / "persona.md").read_text(encoding="utf-8", errors="ignore")[:800] if (ROOT / "persona.md").is_file() else ""
    context_query = " ".join(jurnal_snippets) + " " + persona_txt
    untried = {cid: c for cid, c in cards.items() if c.get("penerapan") in ("belum-dicoba", "sedang-dicoba")}
    adaptive_pool = query_relevant_cards(context_query[:600], untried or cards, limit=3, use_vectors=True) if context_query.strip() else list((untried or cards).values())[:3]
    aksi_adaptif = [
        {
            "id": c["id"],
            "cabang": c["cabang"],
            "ide": c["ide"],
            "penerapan": c.get("penerapan", "belum-dicoba"),
            "kepercayaan": c.get("kepercayaan", "sedang"),
        }
        for c in adaptive_pool[:2]
    ]

    # 5. Sintesis AI Hangat (Cross-Domain Prinsip Emas + Aksi Adaptif Hari Ini)
    sintesis_ai = ""
    if has_any_free_llm_key() and (top_bridges or aksi_adaptif):
        bridge_txt = "\n".join(
            f"- [{b['dari']}] ({b['cabang_a']}): {b['ide_a']}  <-->  [{b['ke']}] ({b['cabang_b']}): {b['ide_b']}"
            for b in top_bridges[:4]
        ) or "(belum ada jembatan lintas-cabang kuat)"
        aksi_txt = "\n".join(f"- [{a['id']}] ({a['cabang']}): {a['ide']}" for a in aksi_adaptif)
        kompas_txt = "\n".join(f"- {k}" for k in kompas_lines[:5]) or "(belum ada Kompas Sikap)"
        sys_p = (
            "Kamu adalah mentor strategis & otak kedua pengguna di Pohon Pengetahuan. "
            "Tulis ringkasan singkat, hangat, mengalir alami dalam Bahasa Indonesia dengan 3 bagian padat:\n"
            "1) **Pola Emas Lintas-Cabang**: tarik 1-2 wawasan besar yang menghubungkan kartu lintas bidang di bawah (wajib sebut ID [K-XXXX]).\n"
            "2) **Cek Evolusi Prinsip**: soroti singkat jika ada ketegangan menarik antara kartu atau dengan Kompas Sikap (jika belum ada, katakan selaras).\n"
            "3) **1 Langkah Aksi Hari Ini**: pilih 1 kartu adaptif paling berdampak dan beri 1 langkah konkret 10 menit yang bisa langsung dicoba hari ini."
        )
        usr_p = f"JEMBATAN LINTAS-CABANG:\n{bridge_txt}\n\nKARTU AKSI ADAPTIF:\n{aksi_txt}\n\nKOMPAS SIKAP JURNAL:\n{kompas_txt}"
        ai_out, _, _ = call_free_llm_cascade(sys_p, usr_p, json_mode=False, max_tokens=1400, temperature=0.45)
        if ai_out:
            sintesis_ai = ai_out

    return {
        "ok": True,
        "vektor_terindeks": len(vecs),
        "total_kartu": len(cards),
        "lintas_cabang": top_bridges,
        "pertentangan": conflicts,
        "kompas_sikap_count": len(kompas_lines),
        "aksi_adaptif": aksi_adaptif,
        "sintesis_ai": sintesis_ai,
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
