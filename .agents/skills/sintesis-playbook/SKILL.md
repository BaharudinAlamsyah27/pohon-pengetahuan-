---
name: sintesis-playbook
description: Membandingkan beberapa alat, model AI, atau strategi (kesamaan, perbedaan, dan pilihan terbaik) serta menyusun panduan tahapan kerja sempurna dari awal sampai akhir (playbook) berdasarkan kumpulan kartu Pohon Pengetahuan. Gunakan saat pengguna bertanya "mana yang terbaik antara A vs B", "bandingkan alat AI untuk video/clipping/artikel", atau "buatkan tahapan lengkap dari awal sampai akhir untuk X".
---

# Sintesis Perbandingan & Playbook End-to-End

Prinsip: **skrip menyaring & menghitung dari seluruh big data kartu (0 token), AI menyintesis makna, pengguna mengambil keputusan.**

## Gunakan skill ini bila
- Pengguna ingin membandingkan dua atau lebih alat/model/metode (mis. Claude Fable vs Gemini vs Kling untuk video AI, atau strategi SEO/sosmed berbeda).
- Pengguna meminta tahapan kerja lengkap dari awal sampai akhir (*playbook/SOP*) atas satu aktivitas (clipping, video AI, artikel, proyek coding, digital marketing, bisnis).

## Prosedur (WAJIB hemat token)
1. **Jangan membaca seluruh folder `kartu/`.** Jalankan skrip lokal terlebih dahulu:
   - Untuk perbandingan alat/metode:
     `python scripts/mesin_cerdas.py --bandingkan "<topik atau alat1 vs alat2>"`
   - Untuk tahapan kerja awal sampai akhir:
     `python scripts/mesin_cerdas.py --playbook "<topik/tugas>"`
   - Untuk melihat peta alat & topik terpadat:
     `python scripts/mesin_cerdas.py --tren`
2. Baca **maksimal 10 kartu** yang masuk peringkat teratas dari keluaran skrip bila perlu detail kutipan atau konteks tambahan.
3. Susun sintesis dengan format ketat berikut:
   - **Kesamaan (Konsensus):** teknik atau prinsip yang muncul di banyak sumber/alat → sertakan ID kartu `[[K-xxxx]]`.
   - **Perbedaan & Keunggulan Spesifik:** tabel ringkas tiap alat/metode (keunggulan unik, keterbatasan, jumlah sumber, rata-rata kepercayaan, riwayat penerapan pribadi).
   - **Rekomendasi Terbaik (Kontekstual):** sebutkan alat/alur terbaik **berdasarkan bukti di kartu dan kondisi `persona.md`** (waktu, modal/kuota gratis). Bila sumber masih sedikit (<3 sumber independen), nyatakan terus terang bahwa kesimpulan masih sementara.
   - **Tahapan Kerja Sempurna (Awal → Akhir):**
     1. Riset & Ide
     2. Perencanaan / Skrip / Prompt
     3. Produksi / Eksekusi
     4. Editing & Polish
     5. Distribusi / Sosmed
     6. Evaluasi & Monetisasi
     *(Setiap langkah wajib menautkan `[[K-xxxx]]`; bila agen menambah penyambung dari luar catatan, beri label `[inferensi AI]`.)*
   - **Celah Pengetahuan:** sebutkan tahap mana yang belum punya kartu agar pengguna tahu topik apa yang perlu dicari/ditangkap berikutnya.

## Aturan keras
- Jangan pernah mengarang pemenang jika data pembanding hanya berasal dari 1 postingan promosi.
- Pertentangan antar sumber tetap ditampilkan (rujuk skill `analisis-pertentangan`).
- Utamakan riwayat `penerapan: diterapkan` / `ditolak` milik pengguna sebagai bobot realitas di lapangan.
