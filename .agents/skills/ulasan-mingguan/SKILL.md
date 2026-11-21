---
name: ulasan-mingguan
description: Menjalankan ulasan berkala Pohon Pengetahuan: memilih maksimal 5 kartu untuk diingat dan dicoba, memberi satu langkah kecil dan satu pertanyaan refleksi, lalu memperbarui status penerapan. Gunakan saat pengguna berkata ulasan, ulasan mingguan, atau apa yang perlu saya coba.
---

# Ulasan Mingguan

## Gunakan skill ini bila
- Pengguna meminta ulasan, atau melaporkan hasil mencoba sebuah kartu.

## Jangan gunakan bila
- Pengguna sedang memasukkan sumber baru (selesaikan MASUKKAN dulu). Jangan menyela atau menagih.

## Prosedur
1. Pilih **maksimal 5 kartu** dengan prioritas:
   1. `sedang-dicoba` yang tidak diperbarui >14 hari.
   2. `belum-dicoba` berkepercayaan sedang/tinggi yang paling relevan dengan tujuan di `persona.md` (cari lewat header, jangan buka semua kartu).
   3. Kartu dengan `terakhir-ditinjau` >30 hari.
2. Untuk tiap kartu tampilkan: ide singkat + ID, alasan muncul sekarang, **satu langkah ≤15 menit**, dan **satu pertanyaan refleksi**.
3. Kartu kesehatan/keuangan berkepercayaan rendah: usulkan memverifikasi dulu, bukan mencoba.
4. Setelah pengguna menjawab: perbarui `penerapan`, `penerapan-catatan` (kata-kata pengguna apa adanya), dan `terakhir-ditinjau`; catat di `log.md`.
5. Bila hasil bertentangan dengan isi kartu, tawarkan relasi atau penurunan `kepercayaan`, hanya atas persetujuan pengguna.

## Format keluaran
```
## Ulasan <tanggal>
1. [[K-xxxx]] <ide singkat>
   Mengapa sekarang: ...
   Coba (≤15 menit): ...
   Refleksi: ...
```

## Aturan keras
- Maksimal sekali per sesi kecuali diminta; tanpa nada menagih atau skor.
- Jangan mengklaim saran terbukti berhasil; catat hanya yang dilaporkan pengguna.
- Data penerapan bersifat pribadi dan tidak pernah dipublikasikan.
