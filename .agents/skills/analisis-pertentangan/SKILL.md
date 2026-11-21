---
name: analisis-pertentangan
description: Membandingkan dua atau lebih kartu yang saling bertentangan dan menyusun sintesis perdebatan di bagian Pertentangan pada _cabang.md, tanpa memaksa kesimpulan. Gunakan saat relasi bertentangan-dengan ditemukan, saat RAPIKAN, atau saat pengguna bertanya mana yang benar di antara dua pendapat.
---

# Analisis Pertentangan

## Gunakan skill ini bila
- Kartu baru berlawanan dengan kartu lama (AGENTS.md Bagian 4 langkah 4).
- Pengguna bertanya "mana yang benar" atau "kapan pakai yang mana".

## Jangan gunakan bila
- Dua kartu hanya berbeda detail tanpa konflik. Cukup beri relasi `memperkuat` atau `terkait`.

## Prosedur
1. Baca dua kartu terkait (maksimal 4 bila perdebatan lebih dari dua sisi). Buka sumber hanya bila konteksnya tidak cukup dari kartu.
2. **Klasifikasikan jenis pertentangan:**
   - a. Klaim fakta berlawanan.
   - b. Sama-sama benar di konteks berbeda (tahap hidup, kondisi, tujuan).
   - c. Beda istilah atau definisi.
   - d. Beda nilai atau tujuan.
   - e. Beda kualitas bukti.
3. **Bandingkan** dalam tabel singkat: klaim, dasar, kepercayaan, konteks asal, kondisi berlaku, risiko bila keliru.
4. **Sintesis:**
   - Jenis b/c/d: susun "kapan A, kapan B".
   - Jenis a/e: sebut sisi yang buktinya lebih kuat **hanya bila jelas**; jika tidak, nyatakan masih terbuka.
   - Jangan memilih pemenang atas nama pengguna. Semua sintesis berlabel `[inferensi AI]`.
5. **Tulis di `_cabang.md`** bagian Pertentangan, maksimal 5 baris per perdebatan:
   `- **<topik>**: A [[K-xxxx]] vs B [[K-yyyy]] | jenis: <a-e> | sintesis [inferensi AI]: ... | status: terbuka/tersintesis`
6. Pastikan relasi `bertentangan-dengan` ada di **kedua** kartu.
7. Usulkan satu uji kecil yang bisa dicoba pengguna untuk melihat sisi mana yang cocok dengan kondisinya (terhubung ke status penerapan, Bagian 19).
8. Bila sintesis melahirkan ide baru, **usulkan** kartu baru dan tunggu persetujuan.

## Aturan keras
- Jangan menghapus atau menurunkan salah satu kartu tanpa persetujuan pengguna.
- Jangan menyatukan dua klaim menjadi satu kompromi yang tidak ada di sumber mana pun.
- Topik kesehatan/keuangan: tambahkan catatan bahwa ini pertimbangan, bukan saran profesional.
