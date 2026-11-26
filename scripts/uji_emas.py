#!/usr/bin/env python3
"""
Set Uji Emas (Golden Evaluation Set) — Pohon Pengetahuan.
Jalankan setiap kali prompt, kamus, atau algoritma berubah:
  python scripts/uji_emas.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import bangun_pohon as bp
import mesin_cerdas as mc
import server_lokal as sl

GOLDEN_BRANCH_CASES = [
    ("kesehatan", "Same math applies to sleep. 6hr vs 8hr pushes your system near 100% capacity, multiplying errors, brain fog, and biological debt by 12x."),
    ("kesehatan", "Terlalu sering scrolling media sosial memicu gangguan reseptor dopamin di otak dan kelelahan mental."),
    ("keuangan", "Strategi gaji bulanan fresh graduate usia 22 tahun: sisihkan 20% dana darurat dan investasi reksadana."),
    ("bisnis", "Micro-SaaS mencapai $50k MRR tanpa sales rep lewat B2B pricing dan retensi klien."),
    ("sosmed", "Rahasia algoritma X dan FYP TikTok: hook 3 detik pertama menaikkan watch time dan payout OCR."),
    ("ai/coding-dan-proyek", "Cara bangun fullstack app dengan Cursor, Next.js, Supabase, dan deploy ke Vercel."),
    ("ai/video-dan-clipping", "Workflow faceless video AI pakai Kling, voiceover ElevenLabs, dan edit otomatis di CapCut."),
    ("ai/prompt-dan-agen", "Paket 30 skill SEO open-source dan 4 server MCP untuk agen AI otomasi workflow."),
    ("motivasi-dan-mindset", "Stop overthinking dan prokrastinasi, ubah self-talk negatif menjadi kebiasaan belajar setiap hari."),
    ("relasi", "Komunikasi empati dan negosiasi sehat dengan pasangan serta keluarga."),
]


def run_all() -> int:
    passed = 0
    total = 0

    # 1. Akurasi Klasifikasi Offline (Multinomial Naive Bayes + Lexicon + RRF)
    orig_ai = sl._classify_branch_gemini
    sl._classify_branch_gemini = lambda _t: None
    try:
        cls_ok = 0
        for exp, txt in GOLDEN_BRANCH_CASES:
            got, _ = sl.guess_branch(txt)
            total += 1
            if got == exp:
                passed += 1
                cls_ok += 1
            else:
                print(f"[FAIL-KLASIFIKASI] exp={exp} got={got} | {txt[:50]}")
        print(f"1. Klasifikasi Offline : {cls_ok}/{len(GOLDEN_BRANCH_CASES)} ({int(cls_ok/len(GOLDEN_BRANCH_CASES)*100)}%)")
    finally:
        sl._classify_branch_gemini = orig_ai

    # 2. Normalisasi Konsep (alias -> kanonik)
    total += 1
    norm = mc.normalize_concepts(["duit", "uang", "finansial", "brain-fog", "dialog-batin"])
    if norm == ["keuangan-pribadi", "kabut-otak", "self-talk"]:
        passed += 1
        print(f"2. Normalisasi Konsep  : PASS ({norm})")
    else:
        print(f"[FAIL-KONSEP] got={norm}")

    # 3. Pemeriksa Kesetiaan (Grounding — angka benar vs angka halusinasi)
    total += 2
    g_ok = mc.check_grounding_score("Tidur 6 jam vs 8 jam melipatgandakan kesalahan 12x", "Kurang tidur memicu kabut otak", "6hr vs 8hr pushes capacity multiplying errors by 12x and brain fog")
    g_bad = mc.check_grounding_score("Tidur 3 jam menaikkan gaji 999%", "Klaim palsu 777% tanpa sumber", "6hr vs 8hr pushes capacity multiplying errors by 12x")
    if g_ok >= 0.70:
        passed += 1
    else:
        print(f"[FAIL-GROUNDING-OK] score={g_ok}")
    if g_bad < 0.50:
        passed += 1
    else:
        print(f"[FAIL-GROUNDING-BAD] score={g_bad}")
    print(f"3. Grounding Check     : valid={g_ok} | halusinasi={g_bad}")

    # 4. Filter Bahasa Alami
    total += 1
    nl = mc.parse_nl_filter("kartu kesehatan yang belum dicoba dan berkepercayaan tinggi usia 20-25")
    if nl["bidang"] == "kesehatan" and nl["penerapan"] == "belum-dicoba" and nl["kepercayaan"] == "tinggi" and nl["tahap"] == "20-25":
        passed += 1
        print("4. Filter Bahasa Alami : PASS")
    else:
        print(f"[FAIL-NL-FILTER] got={nl}")

    # 5. Stemmer ID & FTS5 Trigram
    total += 1
    if mc.stem_id("menginvestasikan") == "investasi" and len(bp.search_fts("mengunggah ulang", limit=5)) > 0:
        passed += 1
        print("5. Stemmer + Trigram   : PASS")
    else:
        print("[FAIL-STEM-TRIGRAM]")

    # 6. Deteksi Near-Duplicate 3-gram Jaccard
    total += 1
    sim_hi = mc.compute_shingle_jaccard("tidur enam jam membuat otak lelah dan kabut otak meningkat", "tidur enam jam membuat otak lelah dan kabut otak meningkat drastis")
    sim_lo = mc.compute_shingle_jaccard("tidur enam jam membuat otak lelah", "investasi reksadana saham bulanan untuk pemula")
    if sim_hi >= 0.70 and sim_lo < 0.10:
        passed += 1
        print(f"6. Near-Duplicate 3g   : PASS (mirip={sim_hi:.2f}, beda={sim_lo:.2f})")
    else:
        print(f"[FAIL-JACCARD] hi={sim_hi} lo={sim_lo}")

    print(f"\nTOTAL SET UJI EMAS: {passed}/{total} PASS ({int(passed/max(1,total)*100)}%)")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(run_all())
