---
name: ekstraksi-transkrip
description: Membedah transkrip panjang (podcast, wawancara, video YouTube, thread atau artikel panjang) menjadi kartu wawasan terstruktur tanpa kehilangan konteks pembicara. Gunakan saat pengguna menempelkan transkrip atau teks lebih dari sekitar 1.500 kata ke Pohon Pengetahuan.
---

# Ekstraksi Transkrip

## Gunakan skill ini bila
- Sumber berupa transkrip podcast, video, atau wawancara.
- Teks panjang (>1.500 kata) dengan banyak topik atau lebih dari satu penutur.

## Jangan gunakan bila
- Postingan pendek satu ide. Pakai alur MASUKKAN biasa (AGENTS.md Bagian 4).

## Prosedur
1. **Simpan dulu** ke `sumber/` sesuai AGENTS.md 2.1: teks asli persis, tanpa dibersihkan. Isi `jenis` dan nama penutur di header. Bila penutur tidak jelas, tanyakan sekali: "siapa pewawancara dan siapa tamu?".
2. **Periksa kelengkapan**: terpotong, tanpa penanda penutur, atau caption otomatis berkualitas rendah? Catat di `Saripati`. Jangan memperbaiki isi sumber. Koreksi nama hanya di kartu, dan hanya bila yakin.
3. **Segmentasi**: bagi per topik (±1.000-1.500 kata). Proses satu segmen per giliran dan catat sementara: penutur, topik, penanda waktu.
4. **Ekstrak ide per segmen.** Tiap ide wajib memuat siapa yang mengatakannya, jenisnya (fakta / pengalaman pribadi / opini / saran), dan penanda waktu bila ada. Tulis di kartu sebagai "Menurut <penutur> (±mm:ss)". Klaim tamu tentang dirinya sendiri = `dasar: pengalaman-pribadi`. Pertanyaan pewawancara bukan kartu, kecuali bingkainya penting.
5. **Konsolidasi**: gabungkan ide kembar antar segmen, buang basa-basi/sponsor/promosi. Maksimal 25 kartu. Utamakan ide yang bisa diuji dan punya penjelasan sebab-akibat.
6. **Saripati** sumber: ≤250 kata + 5-10 poin utama dengan penanda waktu.
7. Lanjut ke AGENTS.md Bagian 4 langkah 4-9 (tetangga, cabang, ringkasan, log, laporan).
8. Tambahkan ke laporan: jumlah segmen, kartu dibuat, ide yang dilewati beserta alasan, bagian yang meragukan.

## Aturan keras
- Jangan menukar penutur. Bila tidak yakin: tulis "penutur tidak pasti".
- Jangan mengubah opini tamu menjadi fakta.
- Kutipan pendukung maksimal 2 kalimat.
- Tambahan dari AI diberi label `[inferensi AI]`.
- Jangan membaca ulang seluruh sumber untuk setiap kartu; pakai catatan segmen.
