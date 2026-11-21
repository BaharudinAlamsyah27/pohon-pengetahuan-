---
name: publikasi-situs
description: Membangun situs statis baca-saja dari kartu berstatus publik dan menjalankan pemeriksaan kebocoran sebelum diunggah. Gunakan saat pengguna berkata publikasikan, update situs, atau build situs, atau saat menandai kartu menjadi publik.
---

# Publikasi Situs

## Gunakan skill ini bila
- Pengguna meminta membangun atau memperbarui situs, atau menandai kartu/cabang `publik: ya`.

## Jangan gunakan bila
- Pengguna hanya ingin melihat tampilan lokal (pakai PETA, AGENTS.md Bagian 12/18).

## Prosedur
1. Kumpulkan kartu `publik: ya` dan `status: aktif` lewat pencarian header. Jangan menandai publik atas inisiatif sendiri.
2. Pra-periksa (AGENTS.md 17.2 langkah 2): kartu tanpa `sumber`/`url`, kartu kesehatan atau keuangan berkepercayaan rendah tanpa label, data pribadi.
3. Hapus isi `situs/`, lalu bangun ulang dari nol sesuai AGENTS.md Bagian 18: Pohon, Timeline, Pencarian, halaman kartu/cabang, `data.json`.
   - Hanya field yang diizinkan (AGENTS.md 17.1). **Tanpa** `penerapan*`, persona, teks asli sumber, log.
   - Relasi ke kartu non-publik dihilangkan dari tampilan.
4. **Jalankan pemeriksa kebocoran (wajib):**
   `python .agents/skills/publikasi-situs/scripts/periksa_kebocoran.py --situs situs --persona persona.md --sumber sumber`
   - Keluaran **GAGAL** → berhenti, perbaiki penyebabnya, bangun ulang, periksa lagi.
   - Keluaran **PERIKSA** → tinjau tiap temuan (biasanya kutipan pendukung yang sah), laporkan ke pengguna.
   - Bila Python tidak tersedia: lakukan pencarian manual atas kata dari `persona.md` dan frasa dari 3 sumber acak, dan katakan bahwa pemeriksaan otomatis tidak berjalan.
5. Laporkan: jumlah kartu/cabang terbit, yang dilewati beserta alasan, hasil pemeriksaan. **Jangan commit atau push sebelum pengguna menyetujui.**
6. Setelah disetujui: commit `situs: update <tanggal> (<n> kartu publik)`.

## Aturan keras
- Default `publik: tidak`. Hanya pengguna yang mengubahnya.
- Jangan pernah mengabaikan hasil GAGAL.
- Ingatkan bahwa riwayat Git dan cache bisa menyimpan versi lama bila kartu ditarik dari publik.
